"""Extract official low-rise residential source records and conservative footprint matches."""
import json,sqlite3,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 a=sqlite3.connect('file:'+str(ROOT/'data/apartments.sqlite')+'?mode=ro',uri=True);a.row_factory=sqlite3.Row
 p=sqlite3.connect('file:'+str(ROOT/'data/places.sqlite')+'?mode=ro',uri=True);p.row_factory=sqlite3.Row
 b=sqlite3.connect('file:'+str(ROOT/'data/buildings.sqlite')+'?mode=ro',uri=True);b.row_factory=sqlite3.Row
 fm=json.loads((ROOT/'public/models/footprint-matches.json').read_text()); owned={str(x) for ids in fm.values() if isinstance(ids,list) for x in ids}
 out=[]; named={}
 for q in p.execute('select * from places where building_id is not null'): named.setdefault((q['district_name'],q['name']),[]).append(q)
 for r in a.execute("select * from apartments where classification in ('연립주택','다세대') order by district,name,code"):
  aid='apt-'+r['code'].lower(); matches=[]
  if r['lon'] is not None and r['lat'] is not None:
   for q in named.get((r['district'],r['name']),[]):
    dist=math.hypot((q['lon']-r['lon'])*88400,(q['lat']-r['lat'])*111320); br=b.execute('select geometry,kind from buildings where id=?',(q['building_id'],)).fetchone()
    if dist<=150 and q['building_id'] not in owned and br and br[0] and br[1]=='building': matches.append({'buildingId':q['building_id'],'distanceM':round(dist,1),'name':q['name'],'sourceUrl':q['source_url']})
  out.append({'id':aid,'nameKo':r['name'],'district':r['district'],'classification':r['classification'],'apartmentCode':r['code'],'householdCount':r['household_count'],'coordinate':{'lon':r['lon'],'lat':r['lat'],'basis':r['location_method'],'confidence':r['coordinate_status']},'coordinateStatus':r['coordinate_status'],'sourceUrls':[r['coordinate_source_url']] if r['coordinate_source_url'] else [],'buildingIds':[x['buildingId'] for x in matches],'matchingStatus':'exact_named_same_district_within_150m' if matches else 'unmatched','evidence':{'source':'data/apartments.sqlite','address':r['address'],'matchedBuildings':matches,'unmatchedReason':None if matches else 'no unowned named building with same district/name and source distance <=150m'}})
 (ROOT/'docs/residential-expansion-official-lowrise.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'total':len(out),'matched':sum(bool(x['buildingIds']) for x in out),'unmatched':sum(not x['buildingIds'] for x in out)},ensure_ascii=False))
if __name__=='__main__':main()
