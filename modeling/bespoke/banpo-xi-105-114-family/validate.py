import pathlib,json,hashlib,sys,numpy as np
import shapely
from shapely.geometry import Polygon,shape,Point
from shapely.ops import unary_union
R=pathlib.Path.cwd();P=R/'data/model-source/bespoke/banpo-xi-105-114-family';sys.path.insert(0,str(R/'scripts/bespoke'));from validate_height_regions import read_triangles,above_ceiling
A=json.loads((P.parent/'banpo-xi-all44-research/modeling-ready-101-144.json').read_text());reports=[]
for t in map(str,range(105,115)):
 p=P/t
 if not (p/('banpo-xi-'+t+'.glb')).exists():continue
 d=json.loads((p/'source-data.json').read_text());regions=json.loads((p/'regions.json').read_text());e=next(e for e in A['entries'] if e['tower']==t+'동');assert d['geometry']==json.loads(e['osm_building']['geometry']) and d['id']==e['osm_building']['id'] and d['register_row']==e['register'];poly=Polygon(d['ring_m']);parts=[shape(r['geometry']) for r in regions];assert parts[0].intersection(parts[1]).area<1e-8 and unary_union(parts).symmetric_difference(poly).area<1e-8
 tri=read_triangles(p/('banpo-xi-'+t+'.glb'));xyz=tri.reshape(-1,3);xy=xyz[:,[0,2]]*[1,-1];projection=float(shapely.distance(shapely.points(xy),poly).max());assert projection<=.35, (t,projection)
 grade=tri[:,:,1].max(axis=1)<1e-5;sur=unary_union([Polygon(q[:,[0,2]]*[1,-1]) for q in tri[grade] if Polygon(q[:,[0,2]]*[1,-1]).area>1e-9]);missing=poly.difference(sur).area;assert missing<.001
 lower=parts[0].difference(parts[1].buffer(.35));ceiling=regions[0]['height_m'];bad=[]
 for q in tri[tri[:,:,1].max(axis=1)>ceiling+.001]:
  clip=above_ceiling(q,ceiling+.001)
  if len(clip)>=3:
   pp=Polygon(clip[:,[0,2]]*[1,-1]);area=pp.intersection(lower).area
   if area>1e-6:bad.append(area)
 assert not bad,(t,sum(bad))
 result={'tower':t,'source_id':d['id'],'source_geometry_exact':True,'register_row_exact':True,'source_ring_local_area_m2':poly.area,'source_anchor_lonlat':d['anchor_lonlat'],'bounds_gltf_x_up_south':[xyz.min(axis=0).tolist(),xyz.max(axis=0).tolist()],'maximum_surface_vertex_projection_m':projection,'grade_missing_source_area_m2':missing,'grade_extra_decor_area_m2':sur.difference(poly).area,'regions_partition_gap_area_m2':unary_union(parts).symmetric_difference(poly).area,'regions_overlap_area_m2':parts[0].intersection(parts[1]).area,'lower_envelope_exceedance_area_m2':sum(bad),'height_m':d['register_height_m'],'floors_official':d['floors'],'lower_floors_inferred':d['lower_wing_floors_inferred'],'region_boundaries_inferred':True,'images':0,'scene_count':1,'triangle_count':len(tri),'tolerance_m':.35,'tolerance_basis':'Facade maximum intended offset .25 + half thickness .06 = .31m; .04 numerical/junction allowance, checked actual projection <=.35m'}
 assert abs(result['bounds_gltf_x_up_south'][0][1])<1e-5 and abs(result['bounds_gltf_x_up_south'][1][1]-d['register_height_m'])<1e-4
 (p/'geometry-proof.json').write_text(json.dumps(result,indent=2));reports.append(result)
(P/'independent-geometry-review.json').write_text(json.dumps(reports,indent=2));print([(r['tower'],r['maximum_surface_vertex_projection_m']) for r in reports])
