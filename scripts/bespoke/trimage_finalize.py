"""Validate isolated authored Trimage outputs and bind actual Blender MCP proof. No publication."""
from pathlib import Path
import json,struct,math,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/trimage';proof=OUT/'mcp-build-v4.json';calls=json.loads(proof.read_text());assert any(c.get('tool')=='execute_blender_code' and c.get('isError') is False and any('Code executed successfully' in x.get('text','') for x in c.get('content',[])) for c in calls)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((OUT/'bundle.json').read_text());r=json.loads((OUT/'authored-input.json').read_text());checks=[]
for a in b['assets']:
 path=OUT/a['file'];raw=path.read_bytes();magic,version,size=struct.unpack_from('<III',raw,0);assert magic==0x46546c67 and version==2 and size==len(raw);jlen=struct.unpack_from('<I',raw,12)[0];g=json.loads(raw[20:20+jlen]);blob=raw[28+jlen:];assert not g.get('images')
 for n in g['nodes']:assert not any(k in n for k in ['matrix','translation','rotation','scale'])
 def vectors(idx):
  acc=g['accessors'][idx];v=g['bufferViews'][acc['bufferView']];assert acc['componentType']==5126 and acc['type']=='VEC3';start=v.get('byteOffset',0)+acc.get('byteOffset',0);stride=v.get('byteStride',12);return [struct.unpack_from('<fff',blob,start+i*stride) for i in range(acc['count'])]
 points=[];norms=[];tri=0
 for me in g['meshes']:
  for prim in me['primitives']:points.extend(vectors(prim['attributes']['POSITION']));norms.extend(vectors(prim['attributes']['NORMAL']));tri+=g['accessors'][prim['indices']]['count']//3
 assert all(math.isfinite(v) for p in points+norms for v in p)
 lo=[min(p[k] for p in points) for k in range(3)];hi=[max(p[k] for p in points) for k in range(3)];assert abs(lo[1])<1e-6
 err=max(abs(math.sqrt(sum(v*v for v in p))-1) for p in norms);assert err<1e-4,(a['id'],err)
 T=next(t for t in r['towers'] if t['assetId']==a['id']);assert abs(hi[1]-T['sourceHeightM'])<.01
 assert a['footprintIds']==[T['footprintId']] and a['supersedes']==['apt-a10026988']
 a.update(sha256=sha(path),triangles=tri,bytes=len(raw),dimensions=[hi[k]-lo[k] for k in range(3)],bounds={'min':lo,'max':hi},blendSha256=sha(OUT/a['blendSource']))
 checks.append({'id':a['id'],'triangles':tri,'bytes':len(raw),'sha256':a['sha256'],'bounds':a['bounds'],'maxUnitNormalError':err,'images':0,'allNodeTransformsBaked':True,'footprintIds':a['footprintIds'],'coordinate':a['coordinate'],'registerHeightM':T['sourceHeightM'],'registerId':T['registerId'],'households':T['households']})
assert len({f for a in b['assets'] for f in a['footprintIds']})==4
shutil.copyfile(proof,OUT/'mcp-build.json');b['mcpEvidence']=[{'path':'docs/model-audit/mcp/trimage/build.json','sha256':sha(proof),'tool':'execute_blender_code','port':9877,'stageFile':str(OUT/'mcp-build.json')}]
b['sourceCodeSha256']={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'scripts/bespoke/trimage_prepare.py',ROOT/'scripts/bespoke/trimage_blender.py']}
(OUT/'bundle.json').write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n');report={'siteId':'trimage','assets':checks,'blendSha256':sha(OUT/'trimage.blend'),'mcpBuildSha256':sha(proof),'households':sum(t['households'] for t in r['towers']),'coverage':r['coverage'],'heightDatumCaveat':r['heightBasis']};(OUT/'geometry-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
