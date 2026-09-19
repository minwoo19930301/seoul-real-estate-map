"""Named school/public-office source footprints, with explicit boundary and ownership checks."""
import argparse,collections,json,re,sqlite3,hashlib
from pathlib import Path
from shapely.geometry import shape,Point
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[1]
def connect(name):
 c=sqlite3.connect((ROOT/'data'/name).as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c

def main():
 p=argparse.ArgumentParser();p.add_argument('--boundaries',type=Path,required=True);args=p.parse_args()
 districts={f['properties']['names']['primary']:shape(f['geometry']) for f in json.loads(args.boundaries.read_text())['features']}
 places=connect('places.sqlite');buildings=connect('buildings.sqlite')
 matches=json.loads((ROOT/'public/models/footprint-matches.json').read_text())
 claimed={bid for model,ids in matches.items() if not model.startswith('public-') for bid in ids};groups=collections.defaultdict(list);rejected=[]
 pat=r'(초등학교|중학교|고등학교|구청|주민센터|행정복지센터|동사무소)$'
 for r in places.execute('SELECT * FROM places WHERE building_id IS NOT NULL ORDER BY district_name,name,id'):
  if not re.search(pat,r['name']) or re.search(r'유치원|대학교|대학원|학원|어린이집',r['name']):continue
  d=r['district_name'];b=buildings.execute('SELECT * FROM buildings WHERE id=?',(r['building_id'],)).fetchone()
  reason=None
  if r['name'].endswith('구청') and r['name'].replace(' ','') not in {d+'청','서울특별시'+d+'청','서울'+d+'청'}:reason='not a district administrative office'
  elif d not in districts or not b or b['kind']!='building':reason='no matched building in supported district'
  elif b['id'] in claimed:reason='footprint already modeled'
  else:
   geo=shape(json.loads(b['geometry']));pt=geo.representative_point()
   if not districts[d].buffer(.00003).covers(pt):reason='footprint outside recorded district'
   elif not re.search(r'openstreetmap.org/(way|relation)/\d+$',r['source_url']):reason='no exact source identity URL'
  if reason:rejected.append({'nameKo':r['name'],'district':d,'reason':reason});continue
  groups[(d,r['name'])].append((dict(r),dict(b),geo))
 result=[]
 for (d,name),group in groups.items():
  # Split distant namesakes; combine nearby same-name pieces only.
  clusters=[]
  for r,b,g in group:
   cluster=next((c for c in clusters if g.centroid.distance(c[0][2].centroid)<.0045),None)
   if cluster is None:clusters.append([(r,b,g)])
   else:cluster.append((r,b,g))
  for parts in clusters:
   unique={b['id']:(r,b,g) for r,b,g in parts if b['id'] not in claimed}
   if not unique:continue
   r,b,g=next(iter(unique.values()));site=unary_union([v[2] for v in unique.values()]);pt=site.centroid
   kind='k12-school' if re.search(r'(초등학교|중학교|고등학교)$',name) else 'district-public-office'
   entry={'id':'public-'+b['id'],'nameKo':name,'district':d,'kind':kind,'coordinate':{'lon':pt.x,'lat':pt.y,'basis':'centroid of retained named building footprints; district polygon checked'},'buildingIds':list(unique),'sourceUrls':list(dict.fromkeys(v[0]['source_url'] for v in unique.values())),'membership':{'method':'exact named source building identifiers','scope':'Named buildings only; complete school campus membership not asserted.'},'geometryEvidence':[{'buildingId':v[1]['id'],'heightM':v[1]['height_m'],'floors':v[1]['num_floors']} for v in unique.values()]}
   result.append(entry);claimed.update(unique)
 assert len({x['id'] for x in result})==len(result)
 (ROOT/'docs/public-facility-candidates.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 audit={'accepted':len(result),'kinds':dict(collections.Counter(x['kind'] for x in result)),'districts':dict(collections.Counter(x['district'] for x in result)),'rejected':rejected,'scope':'Retained named footprints, not a complete education/public-facility census'}
 (ROOT/'docs/public-facility-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in audit.items() if k!='rejected'},ensure_ascii=False))
if __name__=='__main__':main()
