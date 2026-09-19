"""Fill deficient districts with named source apartment sites; never infer households."""
import argparse,collections,json,math,re,sqlite3
from pathlib import Path
from shapely.geometry import shape,Point
ROOT=Path(__file__).resolve().parents[1]
def key(n):return re.sub(r'[^가-힣a-z0-9]','',n.lower()).replace('아파트','')
def main():
 p=argparse.ArgumentParser();p.add_argument('--boundaries',type=Path,required=True);a=p.parse_args()
 districts={f['properties']['names']['primary']:shape(f['geometry']) for f in json.loads(a.boundaries.read_text())['features']}
 matched=json.loads((ROOT/'docs/apartment-400-matched.json').read_text());old=json.loads((ROOT/'public/models/manifest.json').read_text())['assets'];counts=collections.Counter(c['district'] for c in matched)
 claimed=set(sum(json.loads((ROOT/'public/models/footprint-matches.json').read_text()).values(),[])+sum((x['buildingIds'] for x in matched),[]))
 names={key(x['nameKo']) for x in old+matched};points=[(x['coordinate']['lon'],x['coordinate']['lat']) for x in old+matched]
 db=sqlite3.connect((ROOT/'data/places.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 buildings=sqlite3.connect((ROOT/'data/buildings.sqlite').as_uri()+'?mode=ro',uri=True);buildings.row_factory=sqlite3.Row
 supplemental=[]
 for d in sorted(districts):
  if counts[d]>=25:continue
  groups=collections.defaultdict(list)
  for r in db.execute("SELECT * FROM places WHERE district_name=? AND building_id IS NOT NULL AND (name LIKE '%아파트%' OR name LIKE '%맨션%') ORDER BY name",(d,)):
   if not re.search(r'(아파트|맨션)(\s*\d+동?)?$',r['name']):continue
   n=re.sub(r'(아파트)\s*\d+동?$',r'\1',r['name']);groups[key(n)].append((n,r))
  for name,group in groups.items():
   if counts[d]>=25:break
   if name in names or any(r['building_id'] in claimed for _,r in group):continue
   n,r=group[0];lon,lat=r['lon'],r['lat']
   if not districts[d].covers(Point(lon,lat)):continue
   if any(math.hypot((lon-x)*88000,(lat-y)*111000)<100 for x,y in points):continue
   ids=[];urls=[]
   for _,part in group:
    b=buildings.execute('SELECT * FROM buildings WHERE id=?',(part['building_id'],)).fetchone()
    if not b or b['kind']!='building' or not b['is_apartment']:continue
    if not re.search(r'openstreetmap.org/(way|relation)/\d+$',part['source_url'] or ''):continue
    ids.append(part['building_id']);urls.append(part['source_url'])
   if not ids:continue
   c={'id':'named-apt-'+ids[0],'nameKo':n,'district':d,'kind':'named-apartment-site','householdCount':None,'householdCountStatus':'unverified; not counted as 400+','coordinate':{'lon':lon,'lat':lat,'basis':'retained named apartment footprint centroid'},'coordinateStatus':'named-source-footprint-in-district','buildingIds':ids,'sourceUrls':urls,'membership':{'method':'exact named apartment source footprints','confidence':'named-source-footprint','scope':'Single named apartment site; no claim of 400 households or complete complex boundary.'}}
   supplemental.append(c);matched.append(c);counts[d]+=1;names.add(name);claimed.update(ids);points.append((lon,lat))
 audit_path=ROOT/'docs/apartment-400-selection-audit.json'
 audit=json.loads(audit_path.read_text())
 audit.update(priorityHouseholds=400,selectionPolicy='Prefer source-confirmed 400+ households, then smaller official complexes; named apartment footprints with unknown household count supplement deficient districts.',matchedTotal=len(matched),atLeast400=sum((x.get('householdCount') or 0)>=400 for x in matched),below400=sum(0<(x.get('householdCount') or 0)<400 for x in matched),unknownHouseholds=sum(x.get('householdCount') is None for x in matched),finalCounts={d:counts[d] for d in sorted(districts)},shortfalls={d:25-counts[d] for d in sorted(districts) if counts[d]<25},scope='Remaining source records and conservative footprint matches; not proof that no other apartment sites exist in these districts.')
 audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
 for path,value in [('apartment-400-supplements.json',supplemental),('apartment-400-matched.json',matched)]:
  (ROOT/'docs'/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'supplements':[(x['district'],x['nameKo']) for x in supplemental],'total':len(matched),'counts':counts},ensure_ascii=False))
if __name__=='__main__':main()
