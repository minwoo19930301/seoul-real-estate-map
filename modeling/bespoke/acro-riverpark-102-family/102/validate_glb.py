import json,struct,pathlib,math
p=pathlib.Path(__file__).parent;b=(p/'acro-riverpark-102.glb').read_bytes();n=struct.unpack_from('<I',b,12)[0];d=json.loads(b[20:20+n]);binary=b[28+n:];vals=[]
for m in d['meshes']:
 for prim in m['primitives']:
  a=d['accessors'][prim['attributes']['POSITION']];v=d['bufferViews'][a['bufferView']];o=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',12)
  vals.extend(struct.unpack_from('<3f',binary,o+i*stride) for i in range(a['count']))
r={'vertices':len(vals),'finite':all(math.isfinite(x) for v in vals for x in v),'axis':'glTF Y up','min':[min(v[i] for v in vals) for i in range(3)],'max':[max(v[i] for v in vals) for i in range(3)],'images':len(d.get('images',[])),'scenes':len(d['scenes'])};source=json.loads((p/'source-data.json').read_text());r['own_ring_at_grade']=all(any(abs(v[0]-x)<1e-4 and abs(v[1])<1e-5 and abs(v[2]+y)<1e-4 for v in vals) for ring in source['rings_m'] for x,y in ring);r['anchor_lonlat']=source['anchor_lonlat'];assert r['own_ring_at_grade'];assert r['finite'] and abs(r['min'][1])<1e-5 and abs(r['max'][1]-source['height_m'])<1e-4 and not r['images'];(p/'glb-validation.json').write_text(json.dumps(r,indent=2));print(r)
