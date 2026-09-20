"""Read-only audit/pool for all retained apartment/complex source records."""
import argparse, json, sqlite3, collections, math
from pathlib import Path
from shapely.geometry import shape, Point
ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'아파트','주상복합','도시형 생활주택(아파트)','도시형 생활주택(주상복합)'}
def bucket(v):
    if v is None or v<=0: return 'unknown'
    return '100_or_less' if v<=100 else 'over_100'
def main():
  parser=argparse.ArgumentParser()
  parser.add_argument('--manifest',type=Path,default=ROOT/'public/models/manifest.json')
  parser.add_argument('--footprints',type=Path,default=ROOT/'public/models/footprint-matches.json')
  args=parser.parse_args()
  districts={f['properties']['names']['primary']:shape(f['geometry']) for f in json.loads((ROOT/'data/building-source/districts.geojson').read_text())['features']}
  man=json.loads(args.manifest.read_text())['assets']; existing_ids={x['id'] for x in man}
  fm=json.loads(args.footprints.read_text()); owned={str(b) for ids in fm.values() if isinstance(ids,list) for b in ids}
  a=sqlite3.connect('file:'+str(ROOT/'data/apartments.sqlite')+'?mode=ro',uri=True);a.row_factory=sqlite3.Row
  p=sqlite3.connect('file:'+str(ROOT/'data/places.sqlite')+'?mode=ro',uri=True);p.row_factory=sqlite3.Row
  b=sqlite3.connect('file:'+str(ROOT/'data/buildings.sqlite')+'?mode=ro',uri=True);b.row_factory=sqlite3.Row
  named=collections.defaultdict(list)
  for r in p.execute('select * from places where building_id is not null'): named[(r['district_name'],r['name'])].append(r)
  pool=[]; reject=[]; stats=collections.Counter(); source=collections.Counter(); household=collections.Counter(); remaining_household=collections.Counter()
  for r in a.execute('select * from apartments order by district,name,code'):
    cls=r['classification'] or 'unknown'; source[cls]+=1
    household[bucket(r['household_count'])]+=1
    if cls not in ALLOWED: continue
    stats['eligible_source']+=1
    aid='apt-'+r['code'].lower()
    if aid in existing_ids: stats['already_modelled']+=1; continue
    if r['lon'] is None or r['lat'] is None or not r['district'] or r['district'] not in districts:
      reject.append({'id':aid,'nameKo':r['name'],'district':r['district'],'reason':'missing coordinate or district boundary'}); continue
    if r['coordinate_status'] in ('unresolved','official_shared_address'):
      reject.append({'id':aid,'nameKo':r['name'],'district':r['district'],'reason':'ambiguous or unresolved source coordinate','coordinateStatus':r['coordinate_status']}); continue
    if not districts[r['district']].covers(Point(r['lon'],r['lat'])):
      reject.append({'id':aid,'nameKo':r['name'],'district':r['district'],'reason':'coordinate outside district polygon'}); continue
    exact=[]
    for q in named.get((r['district'],r['name']),[]):
      if q['building_id'] in owned: continue
      if math.hypot((q['lon']-r['lon'])*88400,(q['lat']-r['lat'])*111320)<=500 and b.execute('select 1 from buildings where id=? and geometry is not null',(q['building_id'],)).fetchone(): exact.append(q)
    exact=list({q['building_id']:q for q in exact}.values())
    status='exact_named_footprint' if exact else 'approximate_neighborhood_matching_required'
    stats[status]+=1
    pool.append({'id':aid,'nameKo':r['name'],'district':r['district'],'kind':'major-apartment-complex','classification':cls,'apartmentCode':r['code'],'householdCount':r['household_count'],'coordinate':{'lon':r['lon'],'lat':r['lat'],'basis':r['location_method'],'confidence':r['coordinate_status']},'coordinateStatus':r['coordinate_status'],'sourceUrls':list(dict.fromkeys([r['coordinate_source_url']]+[q['source_url'] for q in exact if q['source_url']])), 'buildingIds':[q['building_id'] for q in exact], 'matchingStatus':status,'evidence':{'source':'data/apartments.sqlite','address':r['address'],'coordinateIssues':json.loads(r['coordinate_issues'] or '[]'),'matchedNamedBuildings':[{'buildingId':q['building_id'],'name':q['name'],'sourceUrl':q['source_url']} for q in exact]},'modelingNotes':{'selection':'Source apartment/complex record; no price-ranking inference.','morphology':'Exact footprint candidates are named local buildings; approximate candidates require bounded apartment-classified footprint matching and must not invent geometry, height, or membership.'}})
    remaining_household[bucket(r['household_count'])]+=1
  audit={'allowedClassifications':sorted(ALLOWED),'sourceCountsByClassification':dict(source),'householdBucketsAllSource':dict(household),'sourceCountsByClassificationAndHousehold':{cls:{b:sum(1 for x in a.execute('select classification,household_count from apartments where classification=?',(cls,)) if bucket(x[1])==b) for b in ('100_or_less','over_100','unknown')} for cls in sorted(ALLOWED)},'eligibleSourceCount':stats['eligible_source'],'alreadyModelledCount':stats['already_modelled'],'remainingCandidateCount':len(pool),'remainingHouseholdBuckets':dict(remaining_household),'matchingStatusCounts':{'exact_named_footprint':stats['exact_named_footprint'],'approximate_neighborhood_matching_required':stats['approximate_neighborhood_matching_required']},'rejectedCount':len(reject),'rejected':reject,'ownedFootprintCount':len(owned),'notes':['Unknown classification and multi-family/row-house records are excluded from this apartment/complex pool.','Existing model IDs and all footprint IDs in footprint-matches.json are excluded.','Approximate candidates are retained as research pool entries only; they require the bounded matching pipeline before modeling.']}
  (ROOT/'docs/residential-expansion-apartment-pool.json').write_text(json.dumps(pool,ensure_ascii=False,indent=2)+'\n')
  (ROOT/'docs/residential-expansion-apartment-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({k:v for k,v in audit.items() if k not in ('rejected','notes')},ensure_ascii=False))
if __name__=='__main__': main()
