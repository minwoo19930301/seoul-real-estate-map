from pathlib import Path
import json,hashlib,struct,math
O=Path(__file__).parent;D=json.loads((O/'authored-input.json').read_text());B=json.loads((O/'build-summary.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=O/'bespoke-maple-xi-203.glb';raw=p.read_bytes();n=struct.unpack_from('<I',raw,12)[0];g=json.loads(raw[20:20+n]);binstart=20+n+8
assert not g.get('images') and not g.get('textures')
positions=[];normals=[];triangles=0
for m in g['meshes']:
 for pr in m['primitives']:
  triangles+=g['accessors'][pr['indices']]['count']//3
  for semantic,target in [('POSITION',positions),('NORMAL',normals)]:
   ac=g['accessors'][pr['attributes'][semantic]];bv=g['bufferViews'][ac['bufferView']];stride=bv.get('byteStride',12);start=binstart+bv.get('byteOffset',0)+ac.get('byteOffset',0)
   for i in range(ac['count']):target.append(struct.unpack_from('<fff',raw,start+i*stride))
assert all(math.isfinite(c) for v in positions+normals for c in v);assert all(.99<sum(c*c for c in v)<1.01 for v in normals)
bounds={'min':[min(v[i] for v in positions) for i in range(3)],'max':[max(v[i] for v in positions) for i in range(3)]};assert abs(bounds['min'][1])<1e-6;assert bounds['max'][1]<62.451
v={'status':'PASS','finitePositionsAndNormals':True,'unitNormals':True,'noEmbeddedImages':True,'groundMinY0':True,'gltfCoordinate':'eastX upY southZ','triangles':triangles,'bounds':bounds,'sourceOwnership':['maple-xi-203'],'neighborExclusions':['maple-xi-204','maple-xi-202','shared plazas and gardens'],'sha256':sha(p)};(O/'glb-validation.json').write_text(json.dumps(v,indent=2)+'\n')
limits=[D['footprintMetricLimit']['basis'],D['height']['basis'],'Identity matched through official numberedP andtwoopposedaerials withstreetrouteW41-44; no literal203number read inretainedcrops.','FarNWend e0,innercourtyardlowerparts andpilotiinteriors remain partlyhidden/provisional, not fullcompletioncredit.','Photo widths,depths,groundportal,stonecolors,threeplantheights andPVdimensions areperspectiveestimates.','Neighbor204/202/construction,sharedgardens,sunkenfacilities andhighwaybarrier excluded.']
b={'siteId':'maple-xi-203','sources':[{'url':s['url'],'observations':s['observations']} for s in D['sources']],'assets':[{'id':D['id'],'nameKo':'메이플자이 203동','file':p.name,'blendSource':'maple-203.blend','coordinate':D['coordinate'],'category':'residential-apartment','district':'서초구','buildingFacts':{'floors':19,'heightM':62.45,'heightBasis':D['height']['basis']},'footprintIds':[],'groundFootprint':D['groundFootprint'],'supersedes':['maple-xi-203'],'referenceUrl':'https://beyondapartment.kr/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja','components':B['components'],'uncertainties':limits,'minZoom':15}],'places':[],'recipeFiles':['authored-input.json','source-anchor.json','reference-hashes.json','source-evidence.json','ground-photo-ledger.json','register-row.json','orientation-audit.json','build.py','package.py','render.py','render_a.py','render_b.py','validate.py','geometry-validation.json','opening-visibility.json','glb-validation.json'],'mcpEvidence':[],'reviewStatus':'candidate-awaiting-photo-review'}
for f in ['mcp-build.json','mcp-validation.json','mcp-render-a.json','mcp-render-b.json']:
 p=O/f;c=json.loads(p.read_text());assert any(x.get('tool')=='execute_blender_code' and x.get('isError') is False and any('Code executed successfully' in z.get('text','') for z in x.get('content',[])) for x in c),f
 b['mcpEvidence'].append({'path':str(p.resolve()),'sha256':sha(p),'tool':'execute_blender_code','port':9878,'blender':'4.5.11 LTS'})
(O/'bundle.json').write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
files=['bespoke-maple-xi-203.glb','maple-203.blend','authored-input.json','build.py']+[str(p.relative_to(O)) for p in (O/'renders').glob('*.png')]
(O/'candidate-hashes.json').write_text(json.dumps({'status':'candidate-awaiting-photo-review','hashes':{f:sha(O/f) for f in files}},indent=2)+'\n')
(O/'reference-crops-hashes.json').write_text(json.dumps({p.name:sha(p) for p in (O/'references').iterdir() if p.is_file()},indent=2)+'\n')
# Prior accepted204/207 files remain immutable.
S=O.parent/'maple-207';assert sha(S/'bespoke-maple-xi-207.glb')=='88ecc887f024f5d7aea925c0d5a39e43d6850c2b14e85af9ac1e1964759c78b2';assert sha(S/'maple-207.blend')=='39a6ba8c3a7b252215fdd1f3467f61b2f41068424f3e56467e149e3f715c0715'
print(json.dumps(v,indent=2));print('207_FROZEN_HASHES_UNCHANGED')

T=O.parent/'maple-204';assert sha(T/'bespoke-maple-xi-204.glb')=='69cb1475637437f8dc1a1e07acc6707f46c62db385e1d802d17ed7e0a5c7fda5';assert sha(T/'maple-204.blend')=='6d328b60b9b01cf4d11d4222830baec01ab441e85133ef4d2a786755b3725d8d'
A=json.loads((O/'source-anchor.json').read_text());assert A['coordinate']==D['coordinate'] and A['groundFootprint']==D['groundFootprint'];print('204_FROZEN_HASHES_UNCHANGED;203_ANCHOR_TRACE_EXACT')

V1=O.parent/'maple-215';V2=O.parent/'maple-215-v2';V3=O.parent/'maple-214'
for stage in [V1,V2,V3]:
 frozen=json.loads((stage/'frozen-inputs.json').read_text());assert all(sha(stage/f)==h for f,h in frozen['hashes'].items());print(stage.name,'FROZEN_FILES_UNCHANGED')
