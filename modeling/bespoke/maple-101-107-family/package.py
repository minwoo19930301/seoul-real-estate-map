from pathlib import Path
import json,hashlib,struct,math
O=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assets=[];mcps=[]
for number in range(101,108):
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

 ring=D['ringEN'];area=abs(sum(ring[i][0]*ring[(i+1)%len(ring)][1]-ring[(i+1)%len(ring)][0]*ring[i][1]for i in range(len(ring))))/2
 registeredArea=float(json.loads(D['register']['raw_json'])['건축면적'])
 source={'modelingBasis':D['modelingBasis'],'inferredFrom':D['inferredFromAssetIds'],'inferredFromAssetIds':D['inferredFromAssetIds'],'inferenceScope':D['inferenceScope'],'sources':D['sources'],'numberedIdentity':{'registerId':D['registerId'],'numberedPlanDong':number,'basis':'Retained original numbered-plan outline and source coordinate; no photograph-number match claimed.'},'footprintMetricLimit':{'tracedAreaM2':area,'registeredBuildingAreaM2':registeredArea,'basis':'Illustrative source plan, not surveyed as-built. Original anchor and trace preserved without area scaling.'}}
 source['facadeRelief']={'nominalProjectedCoreFaceM':1.325,'outermostCladdingJointM':1.342,'basis':'Representative inference; measured GLB bounds below include all modeled relief.'}
 sx=111319.49079327358*math.cos(math.radians(D['coordinate']['lat']));co=D['coordinate'];geoBounds=[co['lon']+bounds['min'][0]/sx,co['lat']-bounds['max'][2]/111319.49079327358,co['lon']+bounds['max'][0]/sx,co['lat']-bounds['min'][2]/111319.49079327358]
 source['measuredEnvelope']={'glbBoundsYUp':bounds,'geoBounds':geoBounds,'maxHeightM':bounds['max'][1],'registerHeightM':D['heightM'],'basis':'Actual final GLB accessor vertex positions, not illustrative footprint bounds.'}
 a={'geoBounds':geoBounds,'id':D['id'],'nameKo':f'메이플자이 {number}동','file':f'bespoke-maple-xi-{number}.glb','blendSource':f'maple-{number}.blend','coordinate':D['coordinate'],'category':'residential-apartment','district':'서초구','floors':D['floors'],'heightM':bounds['max'][1],'sourceHeightM':D['heightM'],'buildingFacts':{'floors':D['floors'],'heightM':bounds['max'][1],'sourceHeightM':D['heightM'],'households':int(D['register']['households']),'registerId':D['registerId']},'floorsBasis':'Exact Seoul register '+D['registerId'],'heightBasis':'heightM is actual exported maximum; sourceHeightM is exact Seoul register '+D['registerId']+' height. Plant cap is approximately0.08m below legal height; facade rows and crown levels inferred.','footprintIds':[],'groundFootprint':D['groundFootprint'],'supersedes':[D['originalId']],'referenceUrl':'https://www.xi.co.kr/Files/cmsPage/20240205_132346_189001.jpg','components':B['components'],'uncertainties':['Nominal projected core-face relief is1.325m; outermost cladding joint strips reach1.342m beyond retained structural plan. Actual measured GLB geoBounds include all relief.',D['inferenceScope'],source['footprintMetricLimit']['basis'],f'Illustrative traced area {area:.3f}m2 differs from register {registeredArea:.3f}m2.','Legal floor count distinct from inferred facade rows; all roof and podium detail provisional.','Only this numbered tower owned; no neighboring tower or shared landscape.'],'minZoom':15,'sourceRecord':source,'modelingBasis':D['modelingBasis'],'inferredFrom':D['inferredFromAssetIds'],'inferredFromAssetIds':D['inferredFromAssetIds'],'inferenceScope':D['inferenceScope'],'numberedIdentity':source['numberedIdentity']};assets.append(a)
 for typ in ['build','validate','render']:
  p=O/f'mcp-{typ}-{number}.json';c=json.loads(p.read_text());assert all(x.get('isError')is False for x in c)
  mcps.append({'path':str(p.resolve()),'sha256':sha(p),'tool':'execute_blender_code','port':9878,'blender':'4.5.11 LTS'})
b={'siteId':'maple-101-107-family','sources':D['sources'],'assets':assets,'places':[],'recipeFiles':[p.name for p in O.iterdir()if p.suffix=='.py'and not p.name.startswith('v1-')]+[p.name for p in O.iterdir()if p.name.startswith(('input-','source-anchor-','geometry-validation-','glb-validation-','build-summary-'))],'mcpEvidence':mcps,'reviewStatus':'final-v2-candidate-awaiting-root-review'}
(O/'bundle.json').write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
files=[p for p in O.iterdir()if p.is_file()and p.suffix in ['.glb','.blend','.py','.png','.jpg','.json','.md','.log']and p.name!='proposed-frozen-hashes.json'and not p.name.startswith(('v1-','mcp-v1-'))]
(O/'proposed-frozen-hashes.json').write_text(json.dumps({'status':'final-v2-candidate-awaiting-root-review','hashes':{p.name:sha(p)for p in files}},indent=2)+'\n')
print('BUNDLE_READY',[(a['id'],sha(O/a['file']))for a in assets])
