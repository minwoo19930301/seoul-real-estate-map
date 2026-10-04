from pathlib import Path
import json,math,hashlib,sqlite3
from shapely.geometry import shape,mapping,Polygon,Point,LineString,GeometryCollection
from shapely.ops import transform,unary_union
from shapely import constrained_delaunay_triangles
P=Path(__file__).parent;R=P.parent;A=R/'acro-all15-partition-review';nums=[105,106,107,108,110,111,112,113,114]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=[R/'acro-riverpark-105-108-family',R/'acro-riverpark-110-114-family'];(P/'prior-stage-hashes.json').write_text(json.dumps({str(p.resolve()):sha(p) for d in old for p in d.rglob('*') if p.is_file()},indent=2))
C=sqlite3.connect('file:'+str(R.parent.parent/'buildings.sqlite')+'?mode=ro',uri=True);C.row_factory=sqlite3.Row
all15=json.loads((A/'source-parts-all15.json').read_text());rec=json.loads((A/'osm/recovered-parts.geojson').read_text());summary=[]
def polys(g):return [g] if g.geom_type=='Polygon' else [p for p in getattr(g,'geoms',[]) if p.geom_type=='Polygon']
def rings(g):return [[list(x) for x in r.coords[:-1]] for p in polys(g) for r in [p.exterior,*p.interiors]]
def tris(g):
 ts=list(constrained_delaunay_triangles(g).geoms);u=unary_union(ts);assert u.symmetric_difference(g).area<1e-7
 return [[list(c) for c in t.exterior.coords[:-1]] for t in ts]
for n in nums:
 t=str(n);p=P/t;p.mkdir(exist_ok=True);frozen=json.loads((A/f'tower-{t}-source-parts.json').read_text());d=next(x for x in all15['towers'] if x['number']==n)
 assert frozen==d
 prior=old[0]/t if n<110 else old[1]/t;s=json.loads((prior/'source-data.json').read_text());parent=d['parent'];live=dict(C.execute('select * from buildings where id=?',(parent['id'],)).fetchone());assert json.loads(live['geometry'])==parent['geometry']==s['geometry'] and live['name']==t and live['height_m']==parent['height_m']
 anchor=s['anchor_lonlat'];project=lambda g:transform(lambda x,y,z=None:((x-anchor[0])*111320*math.cos(math.radians(anchor[1])),(y-anchor[1])*111320),shape(g));pg=project(parent['geometry']);target=pg
 ch=list(d['children']);official=d['mapping_floors'];denom=max(official,*[c['num_floors'] for c in ch]);H=parent['height_m'];raw=[]
 for c in ch:
  lv=dict(C.execute('select * from buildings where id=?',(c['id'],)).fetchone());assert json.loads(lv['geometry'])==c['geometry'] and lv['parent_id']==parent['id'] and lv['num_floors']==c['num_floors']
  assert c['height_m'] is None and c['min_height_m'] is None
  raw.append((c['id'],project(c['geometry']).intersection(pg),c['num_floors'],'source-child-floor-derived'))
 if n==110:
  fid='ce2823b4-6bb2-4b4a-b1f6-21f035384ce1';lv=dict(C.execute('select * from buildings where id=?',(fid,)).fetchone());historical=next(x for x in rec['features'] if x['properties']['way_id']=='543323180');g=project(historical['geometry']);assert g.symmetric_difference(project(json.loads(lv['geometry']))).area<1e-7 and lv['num_floors']==20
  target=unary_union([pg,g]);raw.append((fid,g,20,'historical-OSM110-membership-way543323180'))
 used=GeometryCollection();regions=[]
 for fid,g,fl,basis in raw:
  g=g.difference(used);used=unary_union([used,g])
  if not g.is_empty:regions.append({'id':fid,'geom':g,'floors':fl,'height':H*fl/denom,'basis':basis})
 remainder=target.difference(used)
 if remainder.area>1e-8:regions.append({'id':parent['id']+'-uncovered','geom':remainder,'floors':official,'height':H,'basis':'uncovered-parent-retains-parent-envelope'})
 union=unary_union([r['geom'] for r in regions]);assert target.symmetric_difference(union).area<1e-7;assert sum(r['geom'].area for r in regions)-union.area<1e-7
 allpoints=[xy for r in regions for ring in rings(r['geom']) for xy in ring];out=[]
 for ri,r in enumerate(regions):
  g=r['geom'];walls=[]
  for poly in polys(g):
   for ring in [poly.exterior,*poly.interiors]:
    pts=list(ring.coords)
    for a,b in zip(pts,pts[1:]):
     line=LineString([a,b]);L=line.length
     if L<1e-8:continue
     dx=(b[0]-a[0])/L;dy=(b[1]-a[1])/L;cuts=[0,L]
     for q in allpoints:
      if line.distance(Point(q))<1e-7:cuts.append(line.project(Point(q)))
     cuts=sorted(set(round(v,9) for v in cuts))
     for lo,hi in zip(cuts,cuts[1:]):
      if hi-lo<1e-7:continue
      aa=[a[0]+dx*lo,a[1]+dy*lo];bb=[a[0]+dx*hi,a[1]+dy*hi];mx=(aa[0]+bb[0])/2;my=(aa[1]+bb[1])/2;nx,ny=dy,-dx
      if g.contains(Point(mx+nx*1e-5,my+ny*1e-5)):nx,ny=-nx,-ny
      adjacent=[j for j,rr in enumerate(regions) if j!=ri and rr['geom'].covers(Point(mx+nx*1e-5,my+ny*1e-5))]
      neighbor=max([regions[j]['height'] for j in adjacent],default=0)
      if r['height']>neighbor+1e-6:walls.append({'a':aa,'b':bb,'normal':[nx,ny],'bottom':max(0,neighbor-.65),'neighbor_height':neighbor,'neighbor_region_ids':[regions[j]['id'] for j in adjacent]})
  strips=[]
  for w in walls:
   a,b=w['a'],w['b'];nx,ny=w['normal'];strips.append(Polygon([a,b,[b[0]-nx*.22,b[1]-ny*.22],[a[0]-nx*.22,a[1]-ny*.22]]).intersection(g))
  parapet=unary_union(strips)
  out.append({'region_id':r['id'],'geometry_m':mapping(g),'floor_count':r['floors'],'height_m':r['height'],'height_basis':r['basis'],'roof_deck_z':r['height']-.65,'area_m2':g.area,'cap_triangles_m':tris(g),'exposed_walls':walls,'parapet_geometry_m':mapping(parapet),'parapet_triangles_m':tris(parapet),'parapet_rings_m':rings(parapet)})
 result={'tower':t,'footprint_id':parent['id'],'additional_footprint_ids':['ce2823b4-6bb2-4b4a-b1f6-21f035384ce1'] if n==110 else [],'anchor_lonlat':anchor,'parent_height_m':H,'official_main_floors':official,'osm_parent_floors':parent['num_floors'],'height_formula':'parentHeight * childFloors / max(officialMainFloors,maxChildFloors)','height_denominator_floors':denom,'source_parent_geometry':parent['geometry'],'target_geometry_m':mapping(target),'regions':out,'coverage_symmetric_difference_m2':target.symmetric_difference(union).area,'region_overlap_m2':max(0,sum(r['geom'].area for r in regions)-union.area),'source_parts_sha256':sha(A/f'tower-{t}-source-parts.json'),'source_recipe':str(prior/'build.py'),'source_recipe_sha256':sha(prior/'build.py'),'inferredFromAssetIds':['bespoke-acro-riverpark-109'],'reference_scope':'complex-level official photo inference; numbered photo identity/orientation unconfirmed'}
 result.update(parent=parent,official_floors=official,height_m=H,assetId='bespoke-acro-riverpark-'+t,parent_geometry_m=result['target_geometry_m'],base_union_error_m2=result['coverage_symmetric_difference_m2'],height_policy='Parent OSM estimate; child height=parentHeight*childFloors/max(officialMainFloors,maxChildFloors); uncovered retains max',boundary_allowance={'max_outward_projection_m':.53,'facade_half_thickness_m':.06,'validation_allowance_m':.60,'basis':'0.59m normal detail reach plus0.01m numerical/corner margin; actual triangle test; roof coverage0.03m inset'})
 for i,rr in enumerate(out):
  sid=rr['region_id'];sid='parent-remainder' if sid.endswith('-uncovered') else ('historical-way-543323180' if sid=='ce2823b4-6bb2-4b4a-b1f6-21f035384ce1' else sid)
  rr.update(id='region-'+str(i),source_id=sid,basis=rr['height_basis'],floors=rr['floor_count'],rings=[ring[:-1] for ring in rr['geometry_m']['coordinates']],triangles=rr['cap_triangles_m'],geometry=rr['geometry_m'])
 (p/'source-data.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));summary.append({k:result[k] for k in ['tower','footprint_id','additional_footprint_ids','anchor_lonlat','parent_height_m','official_main_floors','coverage_symmetric_difference_m2','region_overlap_m2'] }|{'regions':[{'id':r['region_id'],'floors':r['floor_count'],'height_m':r['height_m'],'area_m2':r['area_m2']} for r in out]})
(P/'source-geometry-proof.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
