import json,pathlib,struct,numpy as np
from shapely.geometry import Polygon,shape
from shapely.ops import unary_union
P=pathlib.Path(__file__).parent;d=json.loads((P/'source-data.json').read_text());raw=(P/(d['assetId']+'.glb')).read_bytes();n=struct.unpack_from('<I',raw,12)[0];g=json.loads(raw[20:20+n]);binary=raw[28+n:]
def acc(i):
 a=g['accessors'][i];v=g['bufferViews'][a['bufferView']];o=v.get('byteOffset',0)+a.get('byteOffset',0);t={5126:'f',5125:'I',5123:'H'}[a['componentType']];cnt={'SCALAR':1,'VEC3':3}[a['type']];size=struct.calcsize('<'+t*cnt);stride=v.get('byteStride',size);return np.array([struct.unpack_from('<'+t*cnt,binary,o+j*stride) for j in range(a['count'])])
allv=[];allt=[]
for m in g['meshes']:
 for pr in m['primitives']:
  v=acc(pr['attributes']['POSITION'])[:,[0,2,1]];v[:,1]*=-1;ix=acc(pr['indices']).reshape(-1,3);allv.append(v);allt.append(v[ix])
v=np.concatenate(allv);t=np.concatenate(allt);source=shape(d['geometry_m']);bottom=t[np.max(np.abs(t[:,:,2]),axis=1)<1e-5];top=t[np.max(np.abs(t[:,:,2]-(d['official_height_m']-.9)),axis=1)<1e-4];base=unary_union([Polygon(q[:,:2]) for q in bottom]);roof=unary_union([Polygon(q[:,:2]) for q in top]);base_error=base.symmetric_difference(source).area;roof_error=roof.symmetric_difference(source).area
r={'assetId':d['assetId'],'finite':bool(np.isfinite(v).all()),'local_ground_m':float(v[:,2].min()),'max_height_m':float(v[:,2].max()),'official_recorded_height_m':d['official_height_m'],'osm_height_m':d['osm_height_m'],'base_union_error_m2':base_error,'constrained_roof_union_error_m2':roof_error,'roofdeck_m':(d['official_height_m']-.9),'no_fan_bridges':roof_error<.001,'source_ring_vertices_at_grade':all(any(abs(q[0]-x)<1e-4 and abs(q[1]-y)<1e-4 and abs(q[2])<1e-5 for q in v) for ring in d['rings_m'] for x,y in ring),'images':len(g.get('images',[])),'scenes':len(g['scenes']),'triangles':len(t),'vertices':len(v)}
print(r)
assert r['finite'] and r['local_ground_m']==0 and abs(r['max_height_m']-d['official_height_m'])<1e-4 and base_error<.001 and roof_error<.001 and r['source_ring_vertices_at_grade'] and r['images']==0 and r['scenes']==1
r['passed']=True;(P/'glb-validation.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
