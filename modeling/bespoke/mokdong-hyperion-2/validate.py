"""Read-only validation of local exported GLB assets and unique source ownership."""
import json,math,struct,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
B=json.loads((OUT/'bundle.json').read_text());res=[];owned=set()
for asset in B['assets']:
 p=OUT/asset['file'];data=p.read_bytes();magic,version,length=struct.unpack_from('<III',data)
 assert magic==0x46546c67 and version==2 and length==len(data)
 chunks={};off=12
 while off<len(data):
  n,k=struct.unpack_from('<II',data,off);off+=8;chunks[k]=data[off:off+n];off+=n
 doc=json.loads(chunks[0x4e4f534a]);binary=chunks[0x004e4942]
 assert not doc.get('images') and not doc.get('textures')
 assert all(not any(k in n for k in ['matrix','translation','rotation','scale']) for n in doc['nodes'])
 def values(idx):
  a=doc['accessors'][idx];v=doc['bufferViews'][a['bufferView']];base=v.get('byteOffset',0)+a.get('byteOffset',0);typ={5126:'f',5125:'I',5123:'H',5121:'B'}[a['componentType']];count={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']];fmt='<'+typ*count;sz=struct.calcsize(fmt);stride=v.get('byteStride',sz)
  return [struct.unpack_from(fmt,binary,base+i*stride) for i in range(a['count'])]
 verts=[];norms=[];tri=0
 for m in doc['meshes']:
  for p0 in m['primitives']:
   assert p0.get('mode',4)==4
   verts+=values(p0['attributes']['POSITION']);norms+=values(p0['attributes']['NORMAL']);tri+=doc['accessors'][p0['indices']]['count']//3
 assert all(all(math.isfinite(x) for x in q) for q in verts+norms)
 err=max(abs(math.sqrt(sum(x*x for x in q))-1) for q in norms);assert err<.001
 lo=[min(v[k] for v in verts) for k in range(3)];hi=[max(v[k] for v in verts) for k in range(3)];assert abs(lo[1])<.001
 for fid in asset['footprintIds']:assert fid not in owned;owned.add(fid)
 res.append({'id':asset['id'],'triangles':tri,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'bounds':{'min':lo,'max':hi},'maxUnitNormalError':err,'allNodeTransformsBaked':True,'images':0,'coordinate':asset['coordinate'],'footprintIds':asset['footprintIds']})
assert len(owned)==4
assert 'e75bec98-4829-45f0-ac3e-a2b73a4d8999' not in owned
assert '13e9a720-1daf-4c3d-89a0-5d3d53b70139' not in owned
q={'siteId':B['siteId'],'assetCount':len(res),'residentialCount':4,'households':576,'uniqueSourceOwnership':True,'unrelatedNeighborsNotClaimed':True,'assets':res,'totalBytes':sum(r['bytes'] for r in res),'totalTriangles':sum(r['triangles'] for r in res)}
(OUT/'geometry-validation.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');print(json.dumps(q,ensure_ascii=False))
