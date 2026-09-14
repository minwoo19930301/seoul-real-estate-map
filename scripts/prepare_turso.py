"""Build a query-ready service database and lossless district source shards."""
from __future__ import annotations
import argparse, collections, hashlib, json, re, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISTRICTS = dict(zip('종로구 중구 용산구 성동구 광진구 동대문구 중랑구 성북구 강북구 도봉구 노원구 은평구 서대문구 마포구 양천구 강서구 구로구 금천구 영등포구 동작구 관악구 서초구 강남구 송파구 강동구'.split(), 'jongno jung yongsan seongdong gwangjin dongdaemun jungnang seongbuk gangbuk dobong nowon eunpyeong seodaemun mapo yangcheon gangseo guro geumcheon yeongdeungpo dongjak gwanak seocho gangnam songpa gangdong'.split()))
SERVICE_TABLES = {'kapt_basic_info_weekly','kapt_reb_link','reb_dong_summary','seoul_apartment_mgmt_fee_oa_15822','upis_renewal_districts_uq181','upis_renewal_project_zones_uq120'}
def q(s): return '"'+s.replace('"','""')+'"'
def ro(p): return sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True)
def tables(c): return list(c.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
def setup(p):
 c=sqlite3.connect(p); c.execute('PRAGMA page_size=4096'); c.execute('PRAGMA auto_vacuum=0'); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA cache_size=-2048'); return c

def finish(c,p):
 c.commit(); check=c.execute('PRAGMA quick_check').fetchone()[0]
 if check!='ok': raise RuntimeError(check)
 c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()
 return {'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()}

def prepare(source, out):
 out.mkdir(parents=True,exist_ok=True)
 if (out/'manifest.json').exists(): raise SystemExit('Manifest already exists; use a new output directory for a new snapshot.')
 if list(out.glob('*.sqlite')):raise SystemExit('Partial output exists; use a fresh output directory.')
 manifest={'version':1,'service_sources':{},'shards':{},'source_counts':{},'partition_counts':{}}
 service_path=out/'seoul-service.sqlite'; service=setup(service_path)
 for path in sorted(source.glob('*.sqlite')):
  src=ro(path); objects=tables(src)
  shadows={name+suffix for name,sql in objects if 'CREATE VIRTUAL TABLE' in sql.upper() for suffix in ('_node','_parent','_rowid')}
  selected=[(n,s) for n,s in objects if n not in shadows and (path.stem!='apartment_sources' or n in SERVICE_TABLES)]
  service.execute('ATTACH DATABASE ? AS incoming',(path.resolve().as_uri()+'?mode=ro',))
  counts={}
  for name,sql in selected:
   target=path.stem+'_metadata' if name=='metadata' else name
   if target!=name:sql=re.sub(r'(?i)^(CREATE TABLE\s+)(?:"metadata"|metadata)',lambda m:m[1]+q(target),sql,count=1)
   service.execute(sql)
   cols=[r[1] for r in src.execute('PRAGMA table_info('+q(name)+')')]
   cols_sql=','.join(map(q,cols))
   service.execute(f'INSERT INTO {q(target)} ({cols_sql}) SELECT {cols_sql} FROM incoming.{q(name)}')
   count=src.execute(f'SELECT COUNT(*) FROM {q(name)}').fetchone()[0]
   assert service.execute(f'SELECT COUNT(*) FROM {q(target)}').fetchone()[0]==count
   counts[name]={'table':target,'rows':count}
  for name,table,sql in src.execute("SELECT name,tbl_name,sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):
   if table in counts:service.execute(sql)
  service.commit();service.execute('DETACH DATABASE incoming');src.close()
  manifest['service_sources'][path.name]={'bytes':path.stat().st_size,'tables':counts}
  print('service copied',path.name,flush=True)
 service.execute('CREATE INDEX IF NOT EXISTS service_basic_code ON kapt_basic_info_weekly(단지코드)')
 service.execute('CREATE INDEX IF NOT EXISTS service_fee_code_month ON seoul_apartment_mgmt_fee_oa_15822(아파트코드,년월)')
 manifest['service']=finish(service,service_path)
 src=ro(source/'apartment_sources.sqlite');src.row_factory=sqlite3.Row
 codes={str(r[0]):r[1] for r in src.execute('SELECT DISTINCT 자치구코드,자치구명 FROM seoul_realestate_sales_oa_21275') if r[1] in DISTRICTS}
 def district(value):
  s=str(value or '').strip()
  if s in DISTRICTS:return s
  if s[:5] in codes:return codes[s[:5]]
  for word in re.split(r'[\s,()]+',s):
   if word in DISTRICTS:return word
  return None
 kapt={}
 for r in src.execute('SELECT kaptcode,bjdcode,addr FROM kapt_seoul_complex_list'):
  d=district(r[1]) or district(r[2])
  if d:kapt[str(r[0])]=d
 for r in src.execute('SELECT 단지코드,시군구 FROM kapt_basic_info_weekly'):
  d=district(r[1])
  if d:kapt[str(r[0])]=d
 reb={}
 for r in src.execute('SELECT 단지고유번호,필지고유번호,주소 FROM reb_complex_identifier_basic WHERE seoul_flag=1'):
  d=district(r[1]) or district(r[2])
  if d:reb[str(r[0])]=d
 names=[*DISTRICTS,'shared']; paths={d:out/('seoul-source-'+DISTRICTS.get(d,d)+'.sqlite') for d in names}
 dest={d:setup(paths[d]) for d in names}; objects=tables(src)
 for c in dest.values():
  for _,sql in objects:c.execute(sql)
  c.commit()
 direct=['시군구','시군구명','시군구코드명','자치구명','자치구','구명','oa15818_district','법정동코드','bjdcode','bjd_code','signgu_se','자치구코드','시군구코드','필지고유번호','derived_pnu','법정동주소','주소','addr','대지위치','도로명주소','소재지','지역','col_02']
 for name,_ in objects:
  cols=[r[1] for r in src.execute('PRAGMA table_info('+q(name)+')')]; positions={n:i for i,n in enumerate(cols)}
  direct_i=[positions[k] for k in direct if k in positions]
  kapt_i=[positions[k] for k in ('kaptcode','kapt_code','단지코드','아파트코드','oa15818_code') if k in positions]
  reb_i=[positions[k] for k in ('단지고유번호','reb_complex_id') if k in positions]
  fixed=next((d for d,s in DISTRICTS.items() if name.startswith(s+'_')),None)
  sql=f'INSERT INTO {q(name)} VALUES ('+','.join('?' for _ in cols)+')'
  counts=collections.Counter(); batches=collections.defaultdict(list); total=0
  for row in src.execute('SELECT * FROM '+q(name)):
   row=tuple(row)
   d=fixed or next((d for i in direct_i if (d:=district(row[i]))),None) or next((kapt[str(row[i])] for i in kapt_i if str(row[i]) in kapt),None) or next((reb[str(row[i])] for i in reb_i if str(row[i]) in reb),None) or 'shared'
   if 'seoul_flag' in positions and str(row[positions['seoul_flag']])=='0':d='shared'
   batches[d].append(row); counts[d]+=1; total+=1
   if len(batches[d])>=1000:dest[d].executemany(sql,batches[d]);batches[d].clear()
  for d,rows in batches.items():
   if rows:dest[d].executemany(sql,rows)
  for d,c in dest.items():
   c.commit();actual=c.execute('SELECT COUNT(*) FROM '+q(name)).fetchone()[0]
   assert actual==counts[d],(name,d,actual,counts[d])
  assert total==src.execute('SELECT COUNT(*) FROM '+q(name)).fetchone()[0]
  manifest['source_counts'][name]=total;manifest['partition_counts'][name]=dict(counts)
  print('partitioned',name,total,'shared',counts['shared'],flush=True)
 for c in dest.values():
  for (sql,) in src.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):c.execute(sql)
 src.close()
 for d,c in dest.items():manifest['shards'][d]=finish(c,paths[d])
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 print('complete',sum(x['bytes'] for x in manifest['shards'].values())+manifest['service']['bytes'],flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=ROOT/'data');p.add_argument('--output',type=Path,default=ROOT/'data/turso-export');a=p.parse_args();prepare(a.source,a.output)
