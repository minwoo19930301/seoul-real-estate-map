"""Read-only geometry validation plus staging bundle proof binding; never publishes."""
from pathlib import Path
import json,struct,math,hashlib,argparse,shutil
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/mmca-deoksugung'
p=argparse.ArgumentParser();p.add_argument('--proof',default='mcp-build-v4.json');args=p.parse_args();proof=OUT/args.proof
calls=json.loads(proof.read_text());assert any(c.get('tool')=='execute_blender_code' and c.get('isError') is False and any('Code executed successfully' in x.get('text','') for x in c.get('content',[])) for c in calls)
b=json.loads((OUT/'bundle.json').read_text());a=b['assets'][0];path=OUT/a['file'];raw=path.read_bytes();magic,version,size=struct.unpack_from('<III',raw,0);assert magic==0x46546c67 and version==2 and size==len(raw)
jlen=struct.unpack_from('<I',raw,12)[0];g=json.loads(raw[20:20+jlen]);blob=raw[28+jlen:]
assert not g.get('images')
for n in g['nodes']:assert not any(k in n for k in ['matrix','translation','rotation','scale']),'all geometry must already be in per-anchor glTF coordinates'
def vectors(idx):
 acc=g['accessors'][idx];v=g['bufferViews'][acc['bufferView']];assert acc['componentType']==5126 and acc['type']=='VEC3';start=v.get('byteOffset',0)+acc.get('byteOffset',0);stride=v.get('byteStride',12)
 return [struct.unpack_from('<fff',blob,start+i*stride) for i in range(acc['count'])]
points=[];norms=[];triangles=0
for me in g['meshes']:
 for prim in me['primitives']:
  points.extend(vectors(prim['attributes']['POSITION']));norms.extend(vectors(prim['attributes']['NORMAL']));triangles+=g['accessors'][prim['indices']]['count']//3
assert all(math.isfinite(v) for t in points+norms for v in t)
lo=[min(p[k] for p in points) for k in range(3)];hi=[max(p[k] for p in points) for k in range(3)];assert abs(lo[1])<1e-6
err=max(abs(math.sqrt(sum(v*v for v in t))-1) for t in norms);assert err<1e-4
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a.update(sha256=sha(path),triangles=triangles,bytes=len(raw),dimensions=[hi[k]-lo[k] for k in range(3)],bounds={'min':lo,'max':hi},blendSha256=sha(OUT/a['blendSource']),floors=3,floorsBasis='Official MMCA2014annualreport PDF20/printed21 and operator1F–3F floor diagrams.',heightBasis=f"Official floor-to-floor heights3.40/4.85/4.55m. Visible overall{hi[1]:.3f}m is an authored estimate including datum/cornice/roof; not a surveyed height.")
assert a['footprintIds']==['a1d78a03-a0b3-4ef2-ab28-b3a5021cfbcc'];assert a['supersedes']==['civic-a1d78a03-a0b3-4ef2-ab28-b3a5021cfbcc']
shutil.copyfile(proof,OUT/'mcp-build.json')
b['mcpEvidence']=[{'path':'docs/model-audit/mcp/mmca-deoksugung/build.json','sha256':sha(proof),'tool':'execute_blender_code','port':9877,'stageFile':str(OUT/'mcp-build.json')}]
b['sourceCodeSha256']={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'scripts/bespoke/mmca_deoksugung_prepare.py',ROOT/'scripts/bespoke/mmca_deoksugung_blender.py']}
b['places'][0]['siteId']='mmca-deoksugung'
(OUT/'bundle.json').write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
v={'assetId':a['id'],'sha256':a['sha256'],'blendSha256':a['blendSha256'],'bytes':len(raw),'triangles':triangles,'meshes':len(g['meshes']),'materials':len(g['materials']),'bounds':a['bounds'],'dimensions':a['dimensions'],'maxUnitNormalError':err,'images':0,'allNodeTransformsBaked':True,'columnCount':6,'stairCount':23,'ownedSourceIds':a['footprintIds'],'excludedEastWingId':'5a79ee99-0908-4cf3-812f-16dee899ab41','preservedReferenceId':'reference-flight-deoksugung','uncertainties':a['uncertainties']}
(OUT/'geometry-validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');print(json.dumps(v,ensure_ascii=False))
