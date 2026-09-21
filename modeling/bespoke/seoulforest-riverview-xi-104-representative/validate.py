import pathlib,json,sys,numpy as np,shapely,hashlib
from shapely.geometry import Polygon,shape
from shapely.ops import unary_union
R=pathlib.Path.cwd();P=R/'data/model-source/bespoke/seoulforest-riverview-xi-104-representative';sys.path.insert(0,str(R/'scripts/bespoke'));from validate_height_regions import read_triangles
D=json.loads((P/'source-data.json').read_text());A=json.loads((P.parent/'seoulforest-riverview-xi-research/root-reviewed-source-101-107.json').read_text());e=next(x for x in A['entries'] if x['tower']=='104동');g=json.loads(e['osm_building']['geometry']);assert g==D['geometry'] and e['osm_building']['id']==D['id'] and e['register']==D['register_row'];poly=Polygon(D['rings_m'][0],D['rings_m'][1:]);tri=read_triangles(P/'seoulforest-riverview-xi-104.glb');xyz=tri.reshape(-1,3);xy=xyz[:,[0,2]]*[1,-1];projection=float(shapely.distance(shapely.points(xy),poly).max());assert projection<.5
caps={}
for label,z in [('grade',0),('roof',113.05)]:
 rows=tri[np.max(np.abs(tri[:,:,1]-z),axis=1)<1e-4];surface=unary_union([Polygon(q[:,[0,2]]*[1,-1]) for q in rows]);target=poly if label=='grade' else poly.buffer(-.03);missing=target.difference(surface).area;assert missing<.001;caps[label]={'surface_area_m2':surface.area,'missing_target_area_m2':missing,'coverage_ratio':1-missing/target.area}
assert abs(xyz[:,1].min())<1e-5 and abs(xyz[:,1].max()-114.3)<1e-4
roofpts=xyz[xyz[:,1]>113.0501];roofproj=float(shapely.distance(shapely.points(roofpts[:,[0,2]]*[1,-1]),poly).max());assert roofproj<1e-5
report={'roof_structure_maximum_projection_m':roofproj,'source_id':D['id'],'source_geometry_exact':True,'register_row_exact':True,'anchor_lonlat':D['anchor_lonlat'],'floors':39,'height_m':114.3,'uniform_height_assumption':True,'roof_deck_height_m':113.05,'source_children':e['child_parts'],'bounds_gltf_x_up_south':[xyz.min(axis=0).tolist(),xyz.max(axis=0).tolist()],'whole_surface_maximum_vertex_projection_m':projection,'triangle_count':len(tri),'caps':caps,'scene_count':1,'images':0,'glb_sha256':hashlib.sha256((P/'seoulforest-riverview-xi-104.glb').read_bytes()).hexdigest()};(P/'geometry-proof.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
