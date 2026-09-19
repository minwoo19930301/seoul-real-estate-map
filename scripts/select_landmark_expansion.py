import json, sqlite3, math, collections, argparse
from pathlib import Path
from shapely.geometry import Point, shape

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(); ap.add_argument('--boundaries',required=True); args=ap.parse_args()
districts={f['properties']['names']['primary']:shape(f['geometry']) for f in json.loads(Path(args.boundaries).read_text())['features']}
existing=[]
for fn in ('landmark-candidates-a.json','landmark-candidates-b.json','landmark-candidates-matched.json'):
    existing += json.loads((ROOT/'docs'/fn).read_text())
existing=list({x['id']:x for x in existing}.values())
existing += json.loads((ROOT/'public/models/manifest.json').read_text())['assets']
apt_existing={x.get('apartmentCode') for x in existing if x.get('apartmentCode')}
def dist(a,b): return math.hypot((a[0]-b[0])*88000,(a[1]-b[1])*111000)
coords=[(x['coordinate']['lon'],x['coordinate']['lat']) for x in existing if x.get('coordinate')]
used_existing_osm={str(x['evidence']['matched_osm']['id']) for x in existing if isinstance(x.get('evidence',{}).get('matched_osm'),dict) and x['evidence']['matched_osm'].get('id')}
con=sqlite3.connect(f'file:{ROOT}/data/apartments.sqlite?mode=ro',uri=True); con.row_factory=sqlite3.Row
rows=[]
for r in con.execute('select * from apartments'):
    if r['code'] in apt_existing or r['coordinate_status'] in ('unresolved','official_shared_address') or not r['lon'] or not r['lat'] or r['district'] not in districts: continue
    if not districts[r['district']].buffer(0.00003).covers(Point(r['lon'],r['lat'])): continue
    try: osm=json.loads(r['matched_osm'] or 'null')
    except Exception: osm=None
    if not isinstance(osm,dict): osm={}
    if any(dist((r['lon'],r['lat']),p)<100 for p in coords): continue
    rows.append((r,osm))
by=collections.defaultdict(list)
for r,osm in rows: by[r['district']].append((r,osm))
for d in by: by[d].sort(key=lambda z:-(z[0]['household_count'] or 0))
selected=[]; reserves=[]; used_codes=set(apt_existing); used_osm=set(used_existing_osm)
def make(r,osm):
    return {'id':'apt-'+r['code'].lower(),'nameKo':r['name'],'district':r['district'],'kind':'major-apartment-complex','apartmentCode':r['code'],'householdCount':r['household_count'],'coordinate':{'lon':r['lon'],'lat':r['lat'],'basis':r['location_method'],'confidence':r['coordinate_status']},'coordinateStatus':r['coordinate_status'],'sourceUrls':[r['coordinate_source_url']],'evidence':{'source':'data/apartments.sqlite','address':r['address'],'coordinate_issues':json.loads(r['coordinate_issues'] or '[]'),'matched_osm':osm},'modelingNotes':{'morphology':'Preserve matched building footprints and heights; complex membership and decorative facade details are approximate.','selection':'Representative large complex, not a verified property-price ranking.'}}
for d in sorted(districts):
    chosen=[]; reserve=[]
    for r,osm in by[d]:
        oid=str(osm.get('id') or 'official:'+r['code'])
        if r['code'] in used_codes or oid in used_osm: continue
        p=(r['lon'],r['lat'])
        if any(dist(p,(x['coordinate']['lon'],x['coordinate']['lat']))<100 for x in chosen+selected+reserve+reserves): continue
        x=make(r,osm)
        if len(chosen)<12: chosen.append(x)
        elif len(reserve)<5: reserve.append(x)
        else: continue
        used_codes.add(r['code']); used_osm.add(oid)
    selected.extend(chosen); reserves.extend(reserve)
# Fill the requested total from districts with deeper eligible pools when a few
# districts cannot reach twelve after the 100m separation rule.
for d in sorted(by):
    for r,osm in by[d]:
        if len(selected)>=300: break
        oid=str(osm.get('id') or 'official:'+r['code']); p=(r['lon'],r['lat'])
        if r['code'] in used_codes or oid in used_osm or any(dist(p,(x['coordinate']['lon'],x['coordinate']['lat']))<100 for x in selected+reserves): continue
        selected.append(make(r,osm)); used_codes.add(r['code']); used_osm.add(oid)
    if len(selected)>=300: break
assert len(selected)>=300, collections.Counter(x['district'] for x in selected)
selected=selected[:300]
# Build reserves from all remaining eligible rows, preserving the same spacing.
for d in sorted(by):
    for r,osm in by[d]:
        if len(reserves)>=325: break
        oid=str(osm.get('id') or 'official:'+r['code']); p=(r['lon'],r['lat'])
        if r['code'] in used_codes or oid in used_osm or any(dist(p,(x['coordinate']['lon'],x['coordinate']['lat']))<100 for x in selected+reserves): continue
        reserves.append(make(r,osm)); used_codes.add(r['code']); used_osm.add(oid)
    if len(reserves)>=325: break
assert len(reserves)>=75
(ROOT/'docs/landmark-candidates-expansion-draft.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n')
(ROOT/'docs/landmark-candidates-expansion-reserves.json').write_text(json.dumps(reserves,ensure_ascii=False,indent=2)+'\n')
(ROOT/'docs/landmark-candidates-expansion-pool.json').write_text(json.dumps(selected+reserves,ensure_ascii=False,indent=2)+'\n')
print(len(selected),len(reserves),collections.Counter(x['district'] for x in selected),collections.Counter(x['district'] for x in reserves))
