"""Select additional 100+ household apartments using source footprints and documented membership estimates."""
import json, re, sqlite3, collections, subprocess, tempfile, math
from pathlib import Path
from shapely.geometry import shape, Point
ROOT=Path(__file__).resolve().parents[1]

def main():
    b=json.loads((ROOT/'data/building-source/districts.geojson').read_text())
    districts={f['properties']['names']['primary']:shape(f['geometry']) for f in b['features']}
    manifest=json.loads((ROOT/'public/models/manifest.json').read_text())['assets']
    existing_ids={a['id'] for a in manifest}; fm=json.loads((ROOT/'public/models/footprint-matches.json').read_text())
    used_buildings={str(bid) for ids in fm.values() if isinstance(ids,list) for bid in ids}
    existing_buildings=set(used_buildings)
    allowed={'아파트','주상복합','도시형 생활주택(아파트)','도시형 생활주택(주상복합)'}
    adb=sqlite3.connect('file:'+str(ROOT/'data/apartments.sqlite')+'?mode=ro',uri=True); adb.row_factory=sqlite3.Row
    pdb=sqlite3.connect('file:'+str(ROOT/'data/places.sqlite')+'?mode=ro',uri=True); pdb.row_factory=sqlite3.Row
    bdb=sqlite3.connect('file:'+str(ROOT/'data/buildings.sqlite')+'?mode=ro',uri=True); bdb.row_factory=sqlite3.Row
    place={}
    for r in pdb.execute("SELECT * FROM places WHERE building_id IS NOT NULL"):
        place.setdefault((r['district_name'],r['name']),[]).append(r)
    selected=[]; rejected=[]; counts=collections.Counter()
    for r in adb.execute('SELECT * FROM apartments WHERE household_count>=100 AND classification IN (?,?,?,?) ORDER BY district,name,code',tuple(allowed)):
        aid='apt-'+r['code'].lower(); d=r['district']; counts[d]+=1
        if aid in existing_ids: continue
        reason=None; matches=[]
        if not d or d not in districts: reason='district missing or outside Seoul boundary'
        elif r['lon'] is None or r['lat'] is None or r['coordinate_status'] in ('unresolved','official_shared_address'): reason='coordinate unresolved or shared-address ambiguity'
        elif not districts[d].covers(Point(r['lon'],r['lat'])): reason='coordinate outside district polygon'
        else:
            matches=place.get((d,r['name']),[])
            matches=[x for x in matches if x['building_id'] not in used_buildings and math.hypot((x['lon']-r['lon'])*88400,(x['lat']-r['lat'])*111320)<=500 and bdb.execute('SELECT 1 FROM buildings WHERE id=? AND geometry IS NOT NULL',(x['building_id'],)).fetchone()]
            if not matches: reason='no exact named footprint; defer to bounded apartment-footprint matcher'
        if reason and reason.startswith('district') or reason and reason.startswith('coordinate'):
            rejected.append({'id':aid,'nameKo':r['name'],'district':d,'householdCount':r['household_count'],'reason':reason}); continue
        bids=[]; evidence=[]
        for x in matches:
            if x['building_id'] not in bids: bids.append(x['building_id']); evidence.append({'buildingId':x['building_id'],'name':x['name'],'sourceUrl':x['source_url']})
        selected.append({'id':aid,'nameKo':r['name'],'district':d,'kind':'major-apartment-complex','apartmentCode':r['code'],'householdCount':r['household_count'],'coordinate':{'lon':r['lon'],'lat':r['lat'],'basis':r['location_method'],'confidence':r['coordinate_status']},'coordinateStatus':r['coordinate_status'],'sourceUrls':list(dict.fromkeys([r['coordinate_source_url']]+[e['sourceUrl'] for e in evidence if e.get('sourceUrl')])), 'buildingIds':bids,'evidence':{'source':'data/apartments.sqlite','address':r['address'],'coordinate_issues':json.loads(r['coordinate_issues'] or '[]'),'matchedBuildings':evidence},'modelingNotes':{'selection':'Official household count >=100; no price-ranking inference.','morphology':'Use matched named building footprint(s); facade, height and complex boundaries remain approximate.'}})
        used_buildings.update(bids)
    # Re-run the established bounded apartment-footprint matcher without a district cap.
    with tempfile.TemporaryDirectory() as td:
        pool=Path(td)/'pool.json'; out=Path(td)/'out.json'; rej=Path(td)/'rej.json'
        pool.write_text(json.dumps(selected,ensure_ascii=False))
        subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/match_district_landmarks.py'),'--additional-pool',str(pool),'--per-district','9999','--allow-shortfall','--output',str(out),'--rejections-output',str(rej)],check=True)
        final=json.loads(out.read_text()); rejects=json.loads(rej.read_text())
    # Final geometry ownership and district-boundary assertions.
    claimed=set(); clean=[]
    for c in final:
        r=adb.execute('SELECT district,lon,lat FROM apartments WHERE code=?',(c['apartmentCode'],)).fetchone()
        bad=[]
        for bid in c.get('buildingIds',[]):
            if bid in existing_buildings or bid in claimed: bad.append('existing footprint ownership')
            brow=bdb.execute('SELECT geometry FROM buildings WHERE id=?',(bid,)).fetchone()
            if not brow or not brow[0] or not districts.get(c['district'],shape({'type':'Polygon','coordinates':[]})).covers(shape(json.loads(brow[0])).representative_point()): bad.append('building outside district polygon')
        if bad: rejects.append({'id':c['id'],'name':c['nameKo'],'reason':'; '.join(sorted(set(bad)))}); continue
        claimed.update(c['buildingIds']); clean.append(c)
    final=clean
    assert not (existing_buildings&{b for c in final for b in c.get('buildingIds',[])})
    (ROOT/'docs/apartment-100-candidates.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'docs/apartment-100-audit.json').write_text(json.dumps({'minimumHouseholds':100,'sourcePoolCounts':dict(counts),'selectedCount':len(final),'selectedByDistrict':dict(collections.Counter(x['district'] for x in final)),'rejected':rejected+rejects},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'selected':len(final),'pool':sum(counts.values()),'districts':dict(collections.Counter(x['district'] for x in final))},ensure_ascii=False))
if __name__=='__main__': main()
