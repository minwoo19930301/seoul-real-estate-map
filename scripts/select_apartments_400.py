"""Select additional complexes from retained official data, preserving prior sites."""
from pathlib import Path
import argparse,collections,json,math,sqlite3
from shapely.geometry import shape,Point
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--boundaries',type=Path,required=True);p.add_argument('--minimum-households',type=int,default=400);args=p.parse_args()
 districts={f['properties']['names']['primary']:shape(f['geometry']) for f in json.loads(args.boundaries.read_text())['features']}
 manifest=json.loads((ROOT/'public/models/manifest.json').read_text())['assets'];existing_ids={a['id'] for a in manifest}
 existing=manifest[:]
 for fn in ('landmark-candidates-matched.json','landmark-candidates-expansion-matched.json'):
  existing+=json.loads((ROOT/'docs'/fn).read_text())
 used_osm={str(x['evidence']['matched_osm']['id']) for x in existing if isinstance(x.get('evidence',{}).get('matched_osm'),dict) and x['evidence']['matched_osm'].get('id')}
 points=[(x['coordinate']['lon'],x['coordinate']['lat']) for x in existing]
 def distance(a,b):return math.hypot((a[0]-b[0])*88000,(a[1]-b[1])*111000)
 db=sqlite3.connect((ROOT/'data/apartments.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 rows=list(db.execute('SELECT * FROM apartments ORDER BY household_count DESC, code'))
 selected=[];rejected=[];counts=collections.Counter()
 for r in rows:
  identifier='apt-'+r['code'].lower();d=r['district'];reason=None
  if d not in districts or identifier in existing_ids:continue
  if (r['household_count'] or 0)<args.minimum_households:continue
  counts[d]+=1
  osm=json.loads(r['matched_osm'] or 'null');oid=str(osm.get('id')) if isinstance(osm,dict) and osm.get('id') else None
  if r['coordinate_status'] in ('unresolved','official_shared_address') or r['lon'] is None or r['lat'] is None:reason='unresolved or ambiguous source coordinate'
  elif not districts[d].buffer(.00003).covers(Point(r['lon'],r['lat'])):reason='source coordinate outside district'
  elif oid and oid in used_osm:reason='existing or duplicate OSM site'
  elif any(distance((r['lon'],r['lat']),q)<100 for q in points):reason='within 100m of an existing or preferred candidate anchor'
  if reason:rejected.append({'id':identifier,'nameKo':r['name'],'district':d,'householdCount':r['household_count'],'reason':reason});continue
  candidate={'id':identifier,'nameKo':r['name'],'district':d,'kind':'major-apartment-complex','apartmentCode':r['code'],'householdCount':r['household_count'],'coordinate':{'lon':r['lon'],'lat':r['lat'],'basis':r['location_method'],'confidence':r['coordinate_status']},'coordinateStatus':r['coordinate_status'],'sourceUrls':[r['coordinate_source_url']],'evidence':{'source':'data/apartments.sqlite','address':r['address'],'coordinate_issues':json.loads(r['coordinate_issues'] or '[]'),'matched_osm':osm},'modelingNotes':{'selection':'Source household count prioritization; not property-price ranking.','morphology':'Retained source footprints and heights; complex membership, facade and missing heights are approximate.'}}
  selected.append(candidate);points.append((r['lon'],r['lat']))
  if oid:used_osm.add(oid)
 audit={'minimumHouseholds':args.minimum_households,'existingModels':len(manifest),'requestedAdditionalPerDistrict':25,'sourceRemainingAtThreshold':dict(counts),'eligiblePoolCounts':dict(collections.Counter(x['district'] for x in selected)),'rejected':rejected}
 for path,value in [('apartment-400-pool.json',selected),('apartment-400-selection-audit.json',audit)]:
  (ROOT/'docs'/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in audit.items() if k!='rejected'},ensure_ascii=False))
if __name__=='__main__':main()
