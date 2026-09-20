"""Read actual staged GLB accessors and validate the independently owned heritage asset."""
import json,hashlib,math,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/jungmyeongjeon'
p=OUT/'bespoke-jungmyeongjeon.glb';raw=p.read_bytes()
magic,version,size=struct.unpack_from('<III',raw);assert magic==0x46546c67 and version==2 and size==len(raw)
n,t=struct.unpack_from('<II',raw,12);assert t==0x4e4f534a;g=json.loads(raw[20:20+n]);bn,bt=struct.unpack_from('<II',raw,20+n);assert bt==0x004e4942;binary=raw[28+n:28+n+bn]
lo=[math.inf]*3;hi=[-math.inf]*3;tris=0;ne=0;normal_count=0
for node in g.get('nodes',[]):
    assert 'matrix' not in node and 'translation' not in node and 'scale' not in node and 'rotation' not in node,'Coordinates must be baked'
for mesh in g['meshes']:
    for primitive in mesh['primitives']:
        assert primitive.get('mode',4)==4
        tris+=g['accessors'][primitive['indices']]['count']//3
        for attr in ['POSITION','NORMAL']:
            a=g['accessors'][primitive['attributes'][attr]];v=g['bufferViews'][a['bufferView']]
            assert a['componentType']==5126 and a['type']=='VEC3'
            offset=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',12)
            for i in range(a['count']):
                xyz=struct.unpack_from('<fff',binary,offset+i*stride);assert all(math.isfinite(x) for x in xyz)
                if attr=='POSITION':
                    for k in range(3):lo[k]=min(lo[k],xyz[k]);hi[k]=max(hi[k],xyz[k])
                else:ne=max(ne,abs(math.sqrt(sum(x*x for x in xyz))-1));normal_count+=1
assert lo[1]==0 and 13.14<=hi[1]<14 and ne<1e-5 and tris>30000
assert not g.get('images') and not g.get('textures')
b=json.loads((OUT/'bundle.json').read_text());a=b['assets'][0]
assert a['footprintIds']==['4c53ad91-93b0-4472-b7a4-0086e45cbdd2']
assert a['supersedes']==['civic-4c53ad91-93b0-4472-b7a4-0086e45cbdd2']
assert a['sha256']==hashlib.sha256(raw).hexdigest()
r=json.loads((OUT/'recipe-input.json').read_text());assert r['frontArcadeBays']==7 and r['eastArcadeBays']==8 and r['westArcadeBays']==6
proof={'sha256':a['sha256'],'bytes':len(raw),'triangles':tris,'meshCount':len(g['meshes']),'materialCount':len(g['materials']),'bounds':{'min':lo,'max':hi},'dimensions':[hi[k]-lo[k] for k in range(3)],'normalCount':normal_count,'maxUnitNormalError':ne,'embeddedSourceImages':0,'groundMinY':lo[1],'ownershipVerified':True,'bakedNodeTransforms':True,'blendSha256':hashlib.sha256((OUT/'jungmyeongjeon.blend').read_bytes()).hexdigest()}
(OUT/'geometry-validation.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
