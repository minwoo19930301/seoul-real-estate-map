import pathlib,json,struct,math,numpy as np
from shapely.geometry import shape,Polygon
from shapely.ops import unary_union
import shapely
P=pathlib.Path(__file__).parent
for n in ['100','101','103','104','109']:
 p=P/n;d=json.loads((p/'source-data.json').read_text());b=(p/(d['assetId']+'.glb')).read_bytes();length=struct.unpack_from('<I',b,12)[0];g=json.loads(b[20:20+length]);binary=b[28+length:]
 def acc(i):
  a=g['accessors'][i];v=g['bufferViews'][a['bufferView']];o=v.get('byteOffset',0)+a.get('byteOffset',0);types={5126:'f',5125:'I',5123:'H',5121:'B'};t=types[a['componentType']];cnt={'VEC3':3,'SCALAR':1}[a['type']];size=struct.calcsize('<'+t*cnt);stride=v.get('byteStride',size)
  return np.array([struct.unpack_from('<'+t*cnt,binary,o+j*stride) for j in range(a['count'])])
 triangles=[];vertices=[]
 for m in g['meshes']:
  for pr in m['primitives']:
   v=acc(pr['attributes']['POSITION']);v=v[:,[0,2,1]];v[:,1]*=-1;ix=acc(pr['indices']).reshape(-1,3);triangles.append(v[ix]);vertices.append(v)
 ts=np.concatenate(triangles);vs=np.concatenate(vertices);assert np.isfinite(vs).all();assert abs(vs[:,2].min())<1e-5 and abs(vs[:,2].max()-d['height_m'])<1e-4
 bottom=ts[np.max(np.abs(ts[:,:,2]),axis=1)<1e-5];base=unary_union([Polygon(t[:,:2]) for t in bottom]);parent=shape(d['parent_geometry_m']);error=base.symmetric_difference(parent).area;assert error<.003,(n,'base',error)
 results=[]
 for r in d['regions']:
  poly=shape(r['geometry']);core=poly.buffer(-.85);h=r['height_m'];above=ts[np.max(ts[:,:,2],axis=1)>h+.001];bad=[]
  if len(above) and not core.is_empty:
   projected=shapely.polygons(above[:,:,:2]);areas=shapely.area(shapely.intersection(projected,core));bad=np.where(areas>1e-5)[0].tolist()
  assert not bad,(n,r['id'],'triangles above core',len(bad))
  top=ts[np.max(np.abs(ts[:,:,2]-(h-.30)),axis=1)<1e-4];roof=unary_union([Polygon(t[:,:2]) for t in top]);missing=poly.difference(roof.buffer(.00001)).area;assert missing<.005,(n,r['id'],'roofmissing',missing)
  results.append({'region':r['id'],'floors':r['floors'],'height_m':h,'roofdeck_height_m':h-.30,'roofdeck_missing_m2':missing,'triangles_above_core':len(bad),'boundary_detail_tolerance_m':.85})
 report={'tower':n,'base_union_error_m2':error,'region_checks':results,'ground_m':float(vs[:,2].min()),'max_height_m':float(vs[:,2].max()),'triangles':len(ts),'finite':True,'images':len(g.get('images',[])),'scenes':len(g['scenes']),'passed':True};assert report['images']==0 and report['scenes']==1
 (p/'glb-region-validation.json').write_text(json.dumps(report,indent=2));print(n,'passed',error)
