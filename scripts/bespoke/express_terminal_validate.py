"""Check the staged bespoke terminal's actual exported GLB bytes, without Blender."""
import hashlib, json, math, struct
from pathlib import Path

root=Path(__file__).resolve().parents[2]
out=root/'data/model-source/bespoke/express-terminal'
path=out/'express-terminal.glb';raw=path.read_bytes()
magic,version,length=struct.unpack_from('<III',raw)
assert magic==0x46546C67 and version==2 and length==len(raw)
n,t=struct.unpack_from('<II',raw,12);assert t==0x4E4F534A
g=json.loads(raw[20:20+n]);bn,bt=struct.unpack_from('<II',raw,20+n);assert bt==0x004E4942
binary=raw[28+n:28+n+bn]
bounds=[[math.inf]*3,[-math.inf]*3];triangles=0;normal_count=0;error=0
for m in g['meshes']:
    for primitive in m['primitives']:
        assert primitive.get('mode',4)==4
        triangles+=g['accessors'][primitive['indices']]['count']//3
        for attribute in ['POSITION','NORMAL']:
            a=g['accessors'][primitive['attributes'][attribute]]
            assert a['componentType']==5126 and a['type']=='VEC3'
            v=g['bufferViews'][a['bufferView']]
            offset=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',12)
            for i in range(a['count']):
                xyz=struct.unpack_from('<fff',binary,offset+i*stride)
                assert all(math.isfinite(x) for x in xyz)
                if attribute=='POSITION':
                    for k in range(3):
                        bounds[0][k]=min(bounds[0][k],xyz[k]);bounds[1][k]=max(bounds[1][k],xyz[k])
                else:
                    error=max(error,abs(math.sqrt(sum(x*x for x in xyz))-1));normal_count+=1
assert bounds[0][1]==0 and bounds[1][1]<=51.00001 and error<1e-5
assert triangles>20000
assert not g.get('images') and not g.get('textures'), 'Source photographs must not be embedded'
report=json.loads((out/'report.json').read_text())
assert report['sha256']==hashlib.sha256(raw).hexdigest()
assert report['triangles']==triangles
assert report['gltfBounds']=={'min':bounds[0],'max':bounds[1]}
bundle=json.loads((out/'bundle.json').read_text())
assert bundle['assets'][0]['footprintIds']==['c313b964-022c-4f5a-9599-d69d0155d010']
assert bundle['assets'][0]['supersedes']==[]
proof={'sha256':report['sha256'],'bytes':len(raw),'triangles':triangles,
       'meshCount':len(g['meshes']),'materialCount':len(g['materials']),
       'bounds':bounds,'normalCount':normal_count,'maxUnitNormalError':error,
       'embeddedSourceImages':0,'groundMinY':bounds[0][1]}
(out/'geometry-validation.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof,indent=2))
