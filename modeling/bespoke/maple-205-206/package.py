from pathlib import Path
import json,hashlib,struct,math
O=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assets=[];recipes=['prepare.py','build.py','validate.py','render.py','package.py','prior-stage-hashes.json','build-205.py','street-fix.py','roof-fix-205.py'];mcps=[]
for number in [205,206]:
 D=json.loads((O/f'input-{number}.json').read_text());B=json.loads((O/f'build-summary-{number}.json').read_text());p=O/f'bespoke-maple-xi-{number}.glb';raw=p.read_bytes();n=struct.unpack_from('<I',raw,12)[0];g=json.loads(raw[20:20+n]);binstart=20+n+8
 assert not g.get('images') and not g.get('textures')
 positions=[];normals=[];triangles=0
 for m in g['meshes']:
  for pr in m['primitives']:
   triangles+=g['accessors'][pr['indices']]['count']//3
   for semantic,target in [('POSITION',positions),('NORMAL',normals)]:
    ac=g['accessors'][pr['attributes'][semantic]];bv=g['bufferViews'][ac['bufferView']];stride=bv.get('byteStride',12);start=binstart+bv.get('byteOffset',0)+ac.get('byteOffset',0)
    for i in range(ac['count']):target.append(struct.unpack_from('<fff',raw,start+i*stride))
 assert all(math.isfinite(c)for v in positions+normals for c in v);assert all(.99<sum(c*c for c in v)<1.01 for v in normals)
 for node in g.get('nodes',[]):
  assert not any(k in node for k in ['matrix','translation','rotation','scale']),node
 bounds={'min':[min(v[i]for v in positions)for i in range(3)],'max':[max(v[i]for v in positions)for i in range(3)]};assert abs(bounds['min'][1])<1e-6 and bounds['max'][1]<=D['heightM']+.001
 val={'status':'PASS','bounds':bounds,'triangles':triangles,'unitNormals':True,'finite':True,'noNodeTransforms':True,'noEmbeddedImages':True,'groundMinY0':True,'sha256':sha(p)};(O/f'glb-validation-{number}.json').write_text(json.dumps(val,indent=2)+'\n')
 scope='Representative facade grammar inferred from approved Maple203/204/207: window bay rhythm, stone base, recessed glazing, service cores and rooftop details. Individual exact register height and existing numbered-plan footprint/anchor retained. No separate all-face photo validation. '+('206 W22/F21 and A/Bv3 support two gray small-window banks, white large-window banks, west glass end, broad white core, continuous L roof and three plants; hidden elevations and metric dimensions inferred.'if number==206 else'205 individual stepped wing levels are unverified; model conservatively uses a continuous roof within its registered height. Lower wing profile, facade placement and rooftop layout are family inference, not verified as-built dimensions.')
 uncertainties=[D['footprintMetricLimit']['basis'],f"Illustrative traced area {D['footprintMetricLimit']['tracedAreaM2']:.3f}m2 differs from register area {D['footprintMetricLimit']['registeredBuildingAreaM2']:.4f}m2; unresolved.",scope,'Legal floor count is separate from 32 inferred visible upper rows. No photographs embedded in GLB or blend.','Only this numbered tower is owned. Adjacent towers, shared garden and ClubCloud excluded.']
 a={'id':D['id'],'nameKo':f'메이플자이 {number}동','file':p.name,'blendSource':f'maple-{number}.blend','coordinate':D['coordinate'],'category':'residential-apartment','district':'서초구','buildingFacts':{'floors':D['floors'],'heightM':D['heightM'],'heightBasis':'Exact Seoul building-register row '+D['register']['id']+'; facade row pitch and roof levels estimated within height envelope.','households':int(D['register']['households']),'registerId':D['register']['id']},'footprintIds':[],'groundFootprint':D['groundFootprint'],'supersedes':D['supersedes'],'referenceUrl':'https://www.xi.co.kr/Files/cmsPage/20240205_132346_189001.jpg','components':B['components'],'uncertainties':uncertainties,'minZoom':15,'modelingBasis':D['modelingBasis'],'inferredFromAssetIds':D['inferredFromAssetIds'],'inferenceScope':scope,'numberedIdentity':D['identity']};a.update({'floors':D['floors'],'heightM':D['heightM'],'floorsBasis':'Exact Seoul register '+D['register']['id'],'heightBasis':'Exact Seoul register '+D['register']['id']+'; modeled within legal height envelope.'});assets.append(a)
 recipes.extend([f'input-{number}.json',f'source-anchor-{number}.json',f'build-summary-{number}.json',f'geometry-validation-{number}.json',f'glb-validation-{number}.json'])
 for typ in ['build','validation','render']:
  p=O/f'mcp-{typ}-{number}.json';c=json.loads(p.read_text());assert any(x.get('tool')=='execute_blender_code'and x.get('isError')is False and any('Code executed successfully' in z.get('text','')for z in x.get('content',[]))for x in c)
  mcps.append({'path':str(p.resolve()),'sha256':sha(p),'tool':'execute_blender_code','port':9878,'blender':'4.5.11 LTS'})
for f,h in json.loads((O/'prior-stage-hashes.json').read_text()).items():assert sha(O.parent/f)==h,('prior stage changed',f)
p=O/'mcp-street-fix-206.json';mcps.append({'path':str(p.resolve()),'sha256':sha(p),'tool':'execute_blender_code','port':9878,'blender':'4.5.11 LTS'})
p=O/'mcp-roof-fix-205.json';mcps.append({'path':str(p.resolve()),'sha256':sha(p),'tool':'execute_blender_code','port':9878,'blender':'4.5.11 LTS'})
b={'siteId':'maple-205-206','sources':D['sources'],'assets':assets,'places':[],'recipeFiles':recipes,'mcpEvidence':mcps,'reviewStatus':'candidate-awaiting-representative-inference-review'};(O/'bundle.json').write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
files=[p for p in O.rglob('*')if p.is_file()and p.suffix in ['.glb','.blend','.py','.png','.json']and p.name not in ['frozen-inputs.json']]
(O/'frozen-inputs.json').write_text(json.dumps({'status':'candidate-awaiting-representative-inference-review','hashes':{str(p.relative_to(O)):sha(p)for p in files}},indent=2)+'\n')
print('BUNDLE_READY',[a['id']for a in assets])
