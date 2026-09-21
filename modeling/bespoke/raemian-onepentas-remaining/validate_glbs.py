from pathlib import Path
import json,struct,hashlib,math
P=Path(__file__).resolve().parent;out=[]
for f in sorted(P.glob('bespoke-*.glb')):
 data=f.read_bytes();magic,version,length=struct.unpack_from('<III',data);assert magic==0x46546c67 and version==2 and length==len(data)
 jslen,jst=struct.unpack_from('<II',data,12);g=json.loads(data[20:20+jslen]);binsize,bint=struct.unpack_from('<II',data,20+jslen);binary=data[28+jslen:28+jslen+binsize];pos=[];norms=[];tris=0
 def read(i):
  a=g['accessors'][i];v=g['bufferViews'][a['bufferView']];width={'VEC3':3,'SCALAR':1}[a['type']];fmt={5126:'f',5123:'H',5125:'I'}[a['componentType']];size=struct.calcsize('<'+fmt)*width;stride=v.get('byteStride',size);start=v.get('byteOffset',0)+a.get('byteOffset',0);return [struct.unpack_from('<'+fmt*width,binary,start+j*stride) for j in range(a['count'])]
 for n in g['nodes']:
  assert not any(k in n for k in ('matrix','translation','rotation','scale'))
 for m in g['meshes']:
  for p in m['primitives']:
   assert p.get('mode',4)==4;pos+=read(p['attributes']['POSITION']);norms+=read(p['attributes']['NORMAL']);tris+=g['accessors'][p['indices']]['count']//3
 assert all(math.isfinite(x) for p in pos+norms for x in p);assert all(abs(sum(x*x for x in n)-1)<1e-4 for n in norms)
 low=[min(p[i] for p in pos) for i in range(3)];hi=[max(p[i] for p in pos) for i in range(3)];assert low[1]==0
 assert not g.get('images') and all('uri' not in b for b in g['buffers'])
 out.append({'file':f.name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'triangles':tris,'meshes':len(g['meshes']),'materials':len(g['materials']),'bounds':{'min':low,'max':hi},'dimensions':[hi[i]-low[i] for i in range(3)],'finitePositions':True,'unitNormals':True,'normalCount':len(norms),'bakedIdentityNodes':True,'noSourcePhotoTextures':True})
(P/'glb-validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
