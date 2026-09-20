"""Freeze reviewed candidates and successful MCP evidence; does not approve/publish."""
from pathlib import Path
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/raemian-caelitus';EDIT=ROOT/'modeling/bespoke/raemian-caelitus';PROOF=ROOT/'docs/model-audit/mcp/raemian-caelitus'
EDIT.mkdir(parents=True,exist_ok=True);PROOF.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((OUT/'bundle.json').read_text());b['mcpEvidence']=[]
for source,name in [('mcp-build-final.json','build.json'),('mcp-validation-final.json','validation.json'),('mcp-render-final.json','render.json')]:
 p=OUT/source;calls=json.loads(p.read_text());assert any(c.get('tool')=='execute_blender_code' and c.get('isError') is False and any('Code executed successfully' in x.get('text','') for x in c.get('content',[])) for c in calls)
 dest=PROOF/name;shutil.copy2(p,dest);b['mcpEvidence'].append({'path':str(dest.relative_to(ROOT)),'sha256':sha(dest),'tool':'execute_blender_code','server':'mcp-for-blender2.0.0','blender':'4.5.11 LTS','port':9878})
for name in ['authored-input.json','building-register-rows.json','geometry-validation.json','raemian-caelitus.blend','mcp-viewport.json','mcp-viewport-setup.json']:
 shutil.copy2(OUT/name,EDIT/name)
renders=['southwest_completed_photo','northwest_rear_steps','east_completed_photo','roof_and_bridges','bridge_and_piloti','podium_canopy_ovals','mcp-viewport'];renderdir=EDIT/'review-renders';renderdir.mkdir(exist_ok=True)
for name in renders:shutil.copy2(OUT/(name+'.png'),renderdir/(name+'.png'))
(OUT/'bundle.json').write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
frozen={'siteId':b['siteId'],'status':'frozen-candidate-awaiting-independent-review','assets':[{'id':a['id'],'file':a['file'],'sha256':sha(OUT/a['file']),'blendSource':a['blendSource'],'blendSha256':sha(OUT/a['blendSource'])} for a in b['assets']],'recipes':{n:sha(OUT/n) for n in b['recipeFiles']},'renders':{n+'.png':sha(OUT/(n+'.png')) for n in renders},'mcpEvidence':b['mcpEvidence'],'geometryValidation':sha(OUT/'geometry-validation.json')}
(OUT/'frozen-inputs.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n');shutil.copy2(OUT/'frozen-inputs.json',EDIT/'frozen-inputs.json');print(json.dumps(frozen['assets'],ensure_ascii=False,indent=2))
