"""Resumable read-only collector for UPIS layer 86 residential/commercial buildings."""
import argparse,datetime,hashlib,json,os,time,urllib.parse,urllib.request
from pathlib import Path
BASE='https://urban.seoul.go.kr/proxy/proxy.jsp?http://98.33.2.225:6080/arcgis/rest/services/UPIS/20200526_WFS/MapServer/86/query?'
FIELDS='OBJECTID,ADDRESS,SAYONG_YEA,DBJSFLOOR,BLDG_NAME,GU_CODE,DONG_CODE,BLDG_MGRNU,DBJYDCD,ROAD_NAME,DBYDETC'
def get(params,retries=3):
 encoded='&'.join(f'{k}={urllib.parse.quote(str(v),safe=",()")}' for k,v in params.items())
 url=BASE+encoded
 for i in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'seoul-elevation-local/residential-survey'})
   with urllib.request.urlopen(req,timeout=90) as r:
    if r.status in (401,403): raise RuntimeError(f'authorization status {r.status}')
    body=r.read(); data=json.loads(body)
    if 'error' in data: raise RuntimeError(data['error'])
    return url,data
  except urllib.error.HTTPError as e:
   if e.code in (401,403): raise
   if e.code<500 or i==retries-1: raise
   time.sleep(2**i)
  except (TimeoutError,urllib.error.URLError, json.JSONDecodeError):
   if i==retries-1: raise
   time.sleep(2**i)
def atomic_json(path,value,compact=False):
 tmp=path.with_suffix(path.suffix+'.tmp')
 tmp.write_text(json.dumps(value,ensure_ascii=False,indent=None if compact else 2,separators=(',',':') if compact else None)+'\n')
 os.replace(tmp,path)

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=Path('data/sources/residential-survey-2026-09-20')); ap.add_argument('--sample',action='store_true'); ap.add_argument('--supplemental',action='store_true'); args=ap.parse_args(); args.root.mkdir(parents=True,exist_ok=True)
 if args.supplemental:
  where="DBYDETC LIKE '%아파트%' OR DBYDETC LIKE '%다세대%' OR DBYDETC LIKE '%연립%' OR DBYDETC LIKE '%오피스텔%' OR DBYDETC LIKE '%주상복합%' OR DBYDETC LIKE '%공동주택%' OR BLDG_NAME LIKE '%빌라%' OR BLDG_NAME LIKE '%연립%' OR BLDG_NAME LIKE '%다세대%' OR BLDG_NAME LIKE '%오피스텔%' OR BLDG_NAME LIKE '%주상복합%' OR BLDG_NAME LIKE '%아파트%'"
  base=set(json.loads((args.root/'objectids.json').read_text())['objectIds']); outroot=args.root/'supplemental'; outroot.mkdir(parents=True,exist_ok=True); args.root=outroot
 else: where="DBJYDCD IN ('공동주택','업무시설') OR BLDG_NAME LIKE '%오피스텔%'"; base=set()
 parts=( ["DBYDETC LIKE '%아파트%'","DBYDETC LIKE '%다세대%'","DBYDETC LIKE '%연립%'","DBYDETC LIKE '%오피스텔%'","DBYDETC LIKE '%주상복합%'","DBYDETC LIKE '%공동주택%'","BLDG_NAME LIKE '%빌라%'","BLDG_NAME LIKE '%연립%'","BLDG_NAME LIKE '%다세대%'","BLDG_NAME LIKE '%오피스텔%'","BLDG_NAME LIKE '%주상복합%'","BLDG_NAME LIKE '%아파트%'"] if args.supplemental else ["DBJYDCD IN ('공동주택','업무시설')","BLDG_NAME LIKE '%오피스텔%'"] ); idsets=[]; counts=[]
 for part in parts:
  _,co=get({'where':part,'returnCountOnly':'true','f':'json'}); _,io=get({'where':part,'returnIdsOnly':'true','f':'json'}); counts.append(co.get('count')); ids_part=set(io.get('objectIds') or [])
  if co.get('count')!=len(ids_part): raise RuntimeError(f'count/id mismatch for {part}: {co.get("count")} != {len(ids_part)}')
  idsets.append(ids_part)
 ids=sorted(set().union(*idsets)-base)
 oidfile=args.root/'objectids.json'
 if oidfile.exists():
  old=json.loads(oidfile.read_text())
  if old.get('where')!=where or old.get('objectIds')!=ids: raise RuntimeError('existing objectids.json differs')
 else: atomic_json(oidfile,{'where':where,'count':len(ids),'objectIds':ids})
 batches=[ids[i:i+500] for i in range(0,len(ids),500)]; limit=1 if args.sample else len(batches); urls=[]; fetched=False
 for i,batch in enumerate(batches[:limit]):
  out=args.root/f'batch-{i:05d}.json'; side=args.root/f'batch-{i:05d}.meta.json'
  if out.exists() and side.exists():
   old=json.loads(side.read_text()); cached=json.loads(out.read_text())
   got=[f.get('attributes',{}).get('OBJECTID') for f in cached.get('features',[])]
   if old.get('ids')==batch and old.get('sha256')==hashlib.sha256(out.read_bytes()).hexdigest() and len(got)==len(batch) and set(got)==set(batch):
    urls.append(old['url']); continue
  url,final=get({'objectIds':','.join(map(str,batch)),'where':'1=1','outFields':FIELDS,'returnGeometry':'true','outSR':'4326','f':'json'})
  got=[f.get('attributes',{}).get('OBJECTID') for f in final.get('features',[])]
  if len(got)!=len(batch) or set(got)!=set(batch): raise RuntimeError(f'batch {i} missing/extra/duplicate ids: requested {len(batch)} got {len(got)}')
  urls.append(url); fetched=True
  atomic_json(out,final,compact=True)
  atomic_json(side,{'batch':i,'ids':batch,'features':len(final['features']),'url':url,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'collectedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()})
  print(json.dumps({'batch':i,'requested':len(batch),'features':len(final['features'])},ensure_ascii=False))
 if args.sample: return
 for i,batch in enumerate(batches):
  out=args.root/f'batch-{i:05d}.json'; side=args.root/f'batch-{i:05d}.meta.json'
  if not out.exists() or not side.exists(): raise RuntimeError(f'missing batch {i}')
  sm=json.loads(side.read_text())
  if sm.get('ids')!=batch or sm.get('features')!=len(batch) or sm.get('sha256')!=hashlib.sha256(out.read_bytes()).hexdigest(): raise RuntimeError(f'batch {i} validation failed')
 meta={'endpoint':BASE,'where':where,'outFields':FIELDS,'outSR':'4326','count':len(ids),'features':len(ids),'batches':len(batches),'collectedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'requestUrls':urls}
 existing=args.root/'metadata.json'
 if not fetched and existing.exists(): meta['collectedAt']=json.loads(existing.read_text())['collectedAt']
 atomic_json(existing,meta)
if __name__=='__main__': main()
