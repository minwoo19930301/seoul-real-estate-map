"""Validate agent selections against retained official data and district boundaries."""
from pathlib import Path
import argparse, collections, json, math, re, sqlite3
from shapely.geometry import Point, shape
ROOT=Path(__file__).resolve().parents[1]
def connect(name):
 c=sqlite3.connect((ROOT/'data'/name).as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c

def curate(boundaries):
 districts={f['properties']['names']['primary']:shape(f['geometry']) for f in json.loads(boundaries.read_text())['features']}
 apartments=connect('apartments.sqlite');places=connect('places.sqlite')
 all_apts={r['code']:dict(r) for r in apartments.execute('SELECT * FROM apartments')}
 ep=ROOT/'docs/landmark-selection-exclusions.json'
 excluded=set(json.loads(ep.read_text())) if ep.exists() else set()
 selections=[];audit=[];seen_codes=set();seen_osm=set()
 def valid_point(d,lon,lat):return lon is not None and lat is not None and districts[d].buffer(0.00003).covers(Point(lon,lat))
 def too_close(x):
  lon,lat=x['coordinate']['lon'],x['coordinate']['lat']
  return any(math.hypot((lon-y['coordinate']['lon'])*88000,(lat-y['coordinate']['lat'])*111000)<100 for y in selections)
 def apt(code):
  r=all_apts.get(code)
  if 'apt-'+code.lower() in excluded:return None
  if not r or r['coordinate_status'] in ('unresolved','official_shared_address') or not valid_point(r['district'],r['lon'],r['lat']):return None
  osm=json.loads(r['matched_osm'] or 'null');osm_id=str(osm.get('id')) if isinstance(osm,dict) and osm.get('id') else None
  if code in seen_codes or (osm_id and osm_id in seen_osm):return None
  x={'id':'apt-'+code.lower(),'nameKo':r['name'],'district':r['district'],'kind':'major-apartment-complex','apartmentCode':code,'householdCount':r['household_count'],
    'coordinate':{'lon':r['lon'],'lat':r['lat'],'basis':r['location_method'],'confidence':r['coordinate_status']},'coordinateStatus':r['coordinate_status'],
    'sourceUrls':[r['coordinate_source_url']], 'evidence':{'source':'data/apartments.sqlite','address':r['address'],'coordinate_issues':json.loads(r['coordinate_issues'] or '[]'),'matched_osm':osm},
    'modelingNotes':{'morphology':'Preserve matched building footprints and heights; complex membership and decorative facade details are approximate.','selection':'Representative large complex, not a verified property-price ranking.'}}
  if too_close(x):return None
  seen_codes.add(code)
  if osm_id:seen_osm.add(osm_id)
  return x
 for suffix in ('a','b'):
  path=ROOT/f'docs/landmark-candidates-{suffix}.json';draft=json.loads(path.read_text());by_district=collections.defaultdict(list)
  for x in draft:by_district[x['district']].append(x)
  final=[]
  for district,items in by_district.items():
   accepted=[]
   # Named landmarks take precedence over apartment fill-ins at the same site.
   for x in sorted(items,key=lambda x:bool(x.get('apartmentCode'))):
    item=None
    if x.get('apartmentCode'):item=apt(x['apartmentCode'])
    else:
     for identifier in x.get('buildingIds',[]):
      r=places.execute('SELECT * FROM places WHERE building_id=? AND district_name=? AND source_url IS NOT NULL LIMIT 1',(identifier.removeprefix('building:'),district)).fetchone()
      if r and valid_point(district,r['lon'],r['lat']) and re.search(r'openstreetmap.org/(way|relation)/\d+$',r['source_url'] or ''):
       item={'id':'landmark-'+r['building_id'],'nameKo':r['name'],'district':district,'kind':'civic-cultural-landmark','coordinate':{'lon':r['lon'],'lat':r['lat'],'basis':'retained named OSM footprint centroid'},'buildingIds':[r['building_id']], 'sourceUrls':[r['source_url']], 'coordinateStatus':'named-footprint-in-district','modelingNotes':{'morphology':'Use actual matched footprint and published/source height where available. Roof and facade details are approximations.'}}
       # Keep exact operator evidence when already distinguished from a namesake.
       if r['name']=='DDP 패션몰':item['sourceUrls'].append('https://sisul.or.kr/open_content/ddpfm/introduce/contents.jsp')
       if too_close(item):item=None
       break
    if item:
     accepted.append(item);selections.append(item)
     if item['nameKo']!=x['nameKo']:audit.append({'input':x['nameKo'],'actualMatchedName':item['nameKo'],'reason':'Use exact footprint identity'})
    else:audit.append({'input':x['nameKo'],'district':district,'reason':'Rejected ambiguous identity, unsupported coordinate, duplicate site, or district mismatch'})
   for r in sorted((r for r in all_apts.values() if r['district']==district),key=lambda r:-(r['household_count'] or 0)):
    if len(accepted)>=10:break
    x=apt(r['code'])
    if x:accepted.append(x);selections.append(x);audit.append({'replacement':x['nameKo'],'district':district})
   assert len(accepted)==10,(district,len(accepted))
   final.extend(accepted)
  path.write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
 counts=collections.Counter(x['district'] for x in selections)
 assert len(counts)==25 and set(counts.values())=={10} and len({x['id'] for x in selections})==250
 audit_path=ROOT/'docs/landmark-selection-audit.json'
 if audit_path.exists():audit=json.loads(audit_path.read_text()).get('corrections',[])+audit
 (ROOT/'docs/landmark-selection-audit.json').write_text(json.dumps({'counts':counts,'total':len(selections),'civic':sum(not x.get('apartmentCode') for x in selections),'corrections':audit},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'counts':counts,'total':len(selections),'civic':sum(not x.get('apartmentCode') for x in selections),'corrections':len(audit)},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--boundaries',type=Path,required=True);curate(p.parse_args().boundaries)
