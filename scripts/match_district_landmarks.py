"""Conservative source-footprint membership for candidate landmarks (read-only DB).

Exact civic IDs take priority. Apartment memberships use named OSM site polygons
when available; otherwise nearby apartment-classified footprints within competing
complex-centroid Voronoi cells. The latter is an approximation, not parcel proof.
"""
from pathlib import Path
import json, math, sqlite3, re, zlib
from shapely.geometry import shape, Polygon, Point
from shapely.ops import unary_union
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parents[1]

def key(s):return re.sub(r'[^가-힣a-z0-9]','',s.lower()).replace('아파트','').replace('분양','').replace('임대','')
def main():
    apt=sqlite3.connect(f'file:{ROOT}/data/apartments.sqlite?mode=ro',uri=True);apt.row_factory=sqlite3.Row
    db=sqlite3.connect(f'file:{ROOT}/data/buildings.sqlite?mode=ro',uri=True);db.row_factory=sqlite3.Row
    records={r['code']:dict(r) for r in apt.execute('select * from apartments where lon is not null and lat is not null')}
    # Official/K-apt points already retain their source confidence in candidates.
    points=[];codes=[]
    for code,r in records.items():
        osm=json.loads(r['matched_osm'] or 'null')
        lon,lat=(osm['lon'],osm['lat']) if osm else (r['lon'],r['lat'])
        r['anchor']=(lon,lat);points.append((lon*88400,lat*111320));codes.append(code)
    tree=cKDTree(points)
    boundaries={};bp=ROOT/'docs/landmark-source-boundaries.json'
    if bp.exists():
        try:
            data=json.loads(bp.read_text())
            for e in data.get('elements',[]):
                polygons=[]
                if e.get('geometry'):polygons=[Polygon([(p['lon'],p['lat']) for p in e['geometry']])]
                elif e.get('members'):
                    for m in e['members']:
                        if m.get('role')=='outer' and m.get('geometry') and len(m['geometry'])>=4:polygons.append(Polygon([(p['lon'],p['lat']) for p in m['geometry']]))
                if polygons:boundaries[f"osm:{e['type']}/{e['id']}"]=unary_union(polygons).buffer(0)
        except (ValueError,KeyError):pass
    candidates=sum([json.loads((ROOT/f'docs/landmark-candidates-{k}.json').read_text()) for k in 'ab'],[])
    claimed=set();result=[];missing=[]
    # Exact civic IDs reserved before neighborhood matching.
    for c in candidates:
        if c.get('buildingIds'):claimed.update(c['buildingIds'])
    for c in candidates:
        c=dict(c)
        if c.get('buildingIds'):
            c['membership']={'method':'exact retained building identifier','confidence':'named-source-footprint'};result.append(c);continue
        code=c.get('apartmentCode');r=records.get(code)
        if not r:missing.append({'id':c['id'],'name':c['nameKo'],'reason':'apartment code absent from DB'});continue
        coord=c['coordinate'];anchor=(coord['lon'],coord['lat']);osm=json.loads(r['matched_osm'] or 'null')
        if osm and math.hypot((osm['lon']-anchor[0])*88400,(osm['lat']-anchor[1])*111320)<750:anchor=(osm['lon'],osm['lat'])
        boundary=boundaries.get(osm['id']) if osm else None
        props=json.loads(zlib.decompress(r['source_properties']));expected=props.get('k-전체동수')
        try:count=int(float(expected))
        except (TypeError,ValueError):count=10
        radius=min(500,max(105,math.sqrt(max(1,count))*65))
        if boundary is not None:bounds=boundary.bounds
        else:bounds=(anchor[0]-radius/88400,anchor[1]-radius/111320,anchor[0]+radius/88400,anchor[1]+radius/111320)
        rows=[dict(v) for v in db.execute('select b.* from building_index i join buildings b on b.rowid=i.rowid where i.maxx>=? and i.minx<=? and i.maxy>=? and i.miny<=? and b.kind=\'building\'',(bounds[0],bounds[2],bounds[1],bounds[3]))]
        selected=[]
        for b in rows:
            if b['id'] in claimed:continue
            poly=shape(json.loads(b['geometry']));p=poly.representative_point();d=math.hypot((p.x-anchor[0])*88400,(p.y-anchor[1])*111320)
            exact=bool(b['name'] and len(key(b['name']))>=4 and (key(b['name']) in key(c['nameKo']) or key(c['nameKo']) in key(b['name'])))
            if boundary is not None:
                if not boundary.covers(p) or not (b['is_apartment'] or exact):continue
            else:
                if not (b['is_apartment'] or exact) or d>radius:continue
                distances,indices=tree.query((p.x*88400,p.y*111320),k=min(5,len(codes)))
                nearest=records[codes[int(indices[0])]]
                own=math.hypot((p.x-anchor[0])*88400,(p.y-anchor[1])*111320)
                # Shared rentals/management records may describe same named site.
                same=key(nearest['name'])==key(c['nameKo'])
                if nearest['code']!=code and not same and own>float(distances[0])+35 and not exact:continue
            selected.append((d,b))
        selected.sort(key=lambda pair:pair[0]);selected=selected[:max(1,min(80,count+3))]
        if not selected:
            missing.append({'id':c['id'],'name':c['nameKo'],'district':c['district'],'reason':'no unclaimed semantically matching apartment footprint in bounded source neighborhood','coordinate':c['coordinate']});continue
        ids=[b['id'] for _,b in selected];claimed.update(ids);c['buildingIds']=ids
        c['membership']={'method':'inside exact-name retained OSM residential polygon' if boundary is not None else 'apartment-classified footprints in bounded source-coordinate neighborhood and nearest-complex partition','confidence':'source-polygon' if boundary is not None else 'approximate-membership-not-parcel-proof','anchor':anchor,'radiusM':radius,'expectedBuildingsFromApartmentRecord':count,'modeledBuildings':len(ids),'maximumCentreDistanceM':round(max(d for d,_ in selected),1),'osmBoundary':osm['id'] if boundary is not None else None,'scope':'Only selected source footprints are replaced; completeness of complex membership is not asserted.'}
        result.append(c)
    (ROOT/'docs/landmark-candidates-matched.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'docs/landmark-unmatched.json').write_text(json.dumps(missing,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'matched':len(result),'unmatched':missing},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
