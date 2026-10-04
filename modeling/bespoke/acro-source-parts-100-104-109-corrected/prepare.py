import json,pathlib,math
from shapely.geometry import shape,mapping,Polygon
from shapely.ops import transform,unary_union
from shapely import constrained_delaunay_triangles
P=pathlib.Path(__file__).parent;B=P.parent;S=B/'acro-all15-partition-review'
for n in [100,101,103,104,109]:
 n=str(n);src=json.loads((S/f'tower-{n}-source-parts.json').read_text());par=src['parent'];p=P/n;p.mkdir(exist_ok=True)
 if n in ['100','109']:old=next(d for d in json.loads((B/'acro-riverpark-109-100/source-data.json').read_text()) if d['name']==n)
 else:old=json.loads((B/'acro-riverpark-101-104-family'/n/'source-data.json').read_text())
 anchor=old['anchor_lonlat'];sx=111320*math.cos(math.radians(anchor[1]));project=lambda g:transform(lambda x,y:((x-anchor[0])*sx,(y-anchor[1])*111320),shape(g))
 parent=project(par['geometry']);taken=Polygon();regions=[];den=max(src['mapping_floors'],max(c['num_floors'] for c in src['children']))
 for c in src['children']:
  geo=project(c['geometry']).intersection(parent).difference(taken);taken=unary_union([taken,geo]);regions.append((geo,c['num_floors'],c['id'],'OSM child floors; metre height floor-derived estimate'))
 rem=parent.difference(taken)
 if n=='100':
  recover=json.loads((S/'osm/recovered-parts.geojson').read_text());matches=[f for f in recover['features'] if project(f['geometry']).symmetric_difference(rem).area<.00001];assert len(matches)==1
  regions.append((rem,19,'historical-way-544771983','Historical OSM19F exact remainder; metre height floor-derived estimate'))
 elif rem.area>1e-8:regions.append((rem,src['mapping_floors'],'parent-remainder','Parent full source height; official numbered floor count'))
 out=[]
 for idx,(geo,f,ident,basis) in enumerate(regions):
  geos=[geo] if geo.geom_type=='Polygon' else list(geo.geoms)
  for sub in geos:
   if sub.area<1e-7:continue
   h=par['height_m']*f/den if ident!='parent-remainder' else par['height_m'];rings=[list(sub.exterior.coords)[:-1]]+[list(q.coords)[:-1] for q in sub.interiors];tri=[list(t.exterior.coords)[:3] for t in constrained_delaunay_triangles(sub).geoms];assert abs(sum(Polygon(t).area for t in tri)-sub.area)<1e-5
   point=sub.representative_point();clear=point.distance(sub.boundary);axis=max((math.dist(a,b),math.atan2(b[1]-a[1],b[0]-a[0])) for a,b in zip(rings[0],rings[0][1:]+rings[0][:1]))[1]
   out.append({'id':f'region-{len(out)}','source_id':ident,'basis':basis,'floors':f,'height_m':h,'rings':rings,'triangles':tri,'geometry':mapping(sub),'area_m2':sub.area,'roof_center':[point.x,point.y],'roof_size':[min(6,clear*.9),min(4,clear*.7)],'roof_axis':axis})
 union=unary_union([shape(r['geometry']) for r in out]);assert union.symmetric_difference(parent).area<1e-5
 for r in out:
  r['edges']=[]
  for ring in r['rings']:
   area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]+ring[:1]));is_hole=ring is not r['rings'][0]
   for a,b in zip(ring,ring[1:]+ring[:1]):
    length=math.dist(a,b)
    if length<1e-6:continue
    dx,dy=b[0]-a[0],b[1]-a[1];nx,ny=(dy/length,-dx/length) if area>0 else (-dy/length,dx/length)
    if is_hole:nx,ny=-nx,-ny
    from shapely.geometry import Point
    probe=Point((a[0]+b[0])/2+nx*.005,(a[1]+b[1])/2+ny*.005);adj=max([rr['height_m'] for rr in out if rr is not r and shape(rr['geometry']).buffer(.000001).covers(probe)]+[0])
    r['edges'].append({'a':a,'b':b,'normal':[nx,ny],'adjacent_height':adj})
 d={'tower':n,'assetId':'bespoke-acro-riverpark-'+n+('-corrected' if n in ['100','109'] else ''),'anchor_lonlat':anchor,'parent':par,'official_floors':src['mapping_floors'],'height_m':par['height_m'],'regions':out,'parent_geometry_m':mapping(parent),'base_union_error_m2':union.symmetric_difference(parent).area,'inferredFromAssetIds':['bespoke-acro-riverpark-109'],'height_policy':'Parent OSM estimates; child metre heights derived from parent * floors / max(official main floors, child floors); not legal or measured','reference_scope':'Complex-level representative photo facade inference; per-tower photo/orientation unverified'}
 (p/'source-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print(n,[(r['floors'],round(r['height_m'],4),round(r['area_m2'],2)) for r in out])
