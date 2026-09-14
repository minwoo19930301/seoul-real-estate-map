"""Resumable binary uploads; credentials and checkpoints stay outside the repository."""
from __future__ import annotations
import argparse, hashlib, http.client, json, os, sqlite3, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
SAVE_LOCK=Lock()
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONFIG=Path.home()/'.config/seoul-map-turso'

def save(path, data, private=False):
 with SAVE_LOCK:
  encoded=json.dumps(data,ensure_ascii=False,indent=2)
  path.parent.mkdir(parents=True,exist_ok=True)
  tmp=path.with_suffix(path.suffix+'.tmp')
  fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600 if private else 0o644)
  with os.fdopen(fd,'w') as f:f.write(encoded)
  tmp.replace(path)

def request(url,token,body=None,method=None):
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method=method)
 try:
  with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
 except urllib.error.HTTPError as e:
  raise RuntimeError(f'Turso HTTP {e.code}: '+e.read().decode()[:300]) from None

def sql(endpoint, token, statements):
 result=request('https://'+endpoint+'/v2/pipeline',token,{'requests':[{'type':'execute','stmt':{'sql':s,'want_rows':True}} for s in statements]+[{'type':'close'}]})
 rows=[]
 for r in result['results'][:-1]:
  if r['type']=='error':raise RuntimeError(r['error'].get('message','SQL failure'))
  rows.append(r['response']['result']['rows'])
 return rows

def upload_file(endpoint,token,path):
 conn=http.client.HTTPSConnection(endpoint,timeout=180)
 try:
  conn.putrequest('POST','/v1/upload');conn.putheader('Authorization','Bearer '+token);conn.putheader('Content-Length',str(path.stat().st_size));conn.putheader('Content-Type','application/octet-stream');conn.endheaders()
  with path.open('rb') as f:
   while b:=f.read(1024*1024):conn.send(b)
  response=conn.getresponse();payload=response.read()
  if response.status!=200:raise RuntimeError(f'Upload HTTP {response.status}: '+payload.decode(errors='replace')[:300])
 finally:conn.close()

def run(export, verify_only=False):
 manifest=json.loads((export/'manifest.json').read_text());accounts=json.loads((CONFIG/'accounts.json').read_text())['accounts']
 state_path=CONFIG/'upload-state.json';state=json.loads(state_path.read_text()) if state_path.exists() else {}
 entries=[manifest['service'],*manifest['shards'].values()]
 loads={a['organization']:0 for a in accounts}
 for e in entries:
  if e['file'] in state:loads[state[e['file']]['organization']]+=e['bytes']
 for e in sorted(entries,key=lambda e:e['bytes'],reverse=True):
  if e['file'] not in state:
   a=min(accounts,key=lambda a:loads[a['organization']]);loads[a['organization']]+=e['bytes']
   state[e['file']]={'organization':a['organization'],'name':Path(e['file']).stem,'sha256':e['sha256'],'bytes':e['bytes']}
 if max(loads.values())>4_500_000_000:raise RuntimeError('Allocation exceeds conservative account storage budget')
 save(state_path,state,True)
 print('allocation',loads,flush=True)
 if not verify_only:
  for a in accounts:
   t=(CONFIG/a['token_file']).read_text().strip();base='https://api.turso.tech/v1/organizations/'+a['organization']
   if not request(base+'/groups',t)['groups']:request(base+'/groups',t,{'name':'seoul-map','location':'aws-ap-northeast-1'})
 def process(e):
  item=state[e['file']];path=export/e['file'];a=next(a for a in accounts if a['organization']==item['organization'])
  if item['sha256']!=e['sha256']:raise RuntimeError('Snapshot changed; use a new database name rather than overwrite')
  if hashlib.file_digest(path.open('rb'),'sha256').hexdigest()!=e['sha256']:raise RuntimeError('Local snapshot checksum mismatch')
  token=(CONFIG/a['token_file']).read_text().strip();base='https://api.turso.tech/v1/organizations/'+a['organization']
  if not item.get('hostname'):
   if verify_only:raise RuntimeError('Not uploaded: '+e['file'])
   groups=request(base+'/groups',token)['groups']
   if not groups:request(base+'/groups',token,{'name':'seoul-map','location':'aws-ap-northeast-1'});group='seoul-map'
   else:group=groups[0]['name']
   databases=request(base+'/databases',token)['databases'];found=next((d for d in databases if d.get('Name',d.get('name'))==item['name']),None)
   if found:raise RuntimeError('Untracked existing database; refusing to overwrite '+item['name'])
   db=request(base+'/databases',token,{'name':item['name'],'group':group,'seed':{'type':'database_upload'}})['database']
   item['hostname']=db.get('Hostname',db.get('hostname'));save(state_path,state,True)
  if not item.get('read_token'):
   item['read_token']=request(base+'/databases/'+item['name']+'/auth/tokens?authorization=read-only&expiration=never',token,method='POST')['jwt'];save(state_path,state,True)
  if not item.get('uploaded'):
   if verify_only:raise RuntimeError('Not uploaded')
   write=request(base+'/databases/'+item['name']+'/auth/tokens?authorization=full-access&expiration=1d',token,method='POST')['jwt']
   print('uploading',e['file'],e['bytes'],flush=True)
   upload_file(item['hostname'],write,path);item['uploaded']=True;save(state_path,state,True)
  c=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
  names=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
  expected=[c.execute('SELECT COUNT(*) FROM "'+n.replace('"','""')+'"').fetchone()[0] for n in names];c.close()
  actual=[]
  for start in range(0,len(names),12):
   queries=['SELECT COUNT(*) FROM "'+n.replace('"','""')+'"' for n in names[start:start+12]]
   for retry in range(6):
    try:
     result=sql(item['hostname'],item['read_token'],queries);break
    except (RuntimeError,urllib.error.URLError):
     if retry==5:raise
     time.sleep(3)
   actual.extend(int(r[0][0]['value']) for r in result)
  if actual!=expected:raise RuntimeError('Remote count mismatch: '+e['file'])
  item['verified_counts']=dict(zip(names,actual));save(state_path,state,True)
  print('verified',e['file'],len(names),'tables',flush=True)
 with ThreadPoolExecutor(max_workers=3) as pool:
  list(pool.map(process,entries))
 service=state[manifest['service']['file']]
 routes={'version':1,'databases':{name:{'hostname':service['hostname'],'token':service['read_token'],'metadata_table':Path(name).stem+'_metadata','bytes':info['bytes']} for name,info in manifest['service_sources'].items()}}
 save(CONFIG/'runtime.json',routes,True)
 public={'accounts_bytes':loads,'databases':[{k:v for k,v in item.items() if k!='read_token'} for item in state.values()]}
 save(ROOT/'docs/turso-upload-report.json',public)
 print('ALL VERIFIED',len(entries),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--export',type=Path,default=ROOT/'data/turso-export');p.add_argument('--verify-only',action='store_true');a=p.parse_args();run(a.export.resolve(),a.verify_only)
