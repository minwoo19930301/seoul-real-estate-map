import bpy,json,math
from pathlib import Path
OUT=Path('/Users/hyemini/Documents/Codex/2026-09-08/seoul-elevation-local/data/model-source/bespoke/maple-height-corrected');rows=[]
for o in bpy.data.objects:
 if o.type!='MESH' or o.get('dong') not in [208,209,212] or o.get('reviewContextDong'):continue
 o.data.calc_loop_triangles();volume=0
 for v in o.data.vertices:assert all(math.isfinite(c) for c in v.co)
 for t in o.data.loop_triangles:
  a,b,c=[o.data.vertices[i].co for i in t.vertices];volume+=a.dot(b.cross(c))/6
 assert volume>0,(o.name,volume)
 rows.append({'name':o.name,'dong':o.get('dong'),'triangles':len(o.data.loop_triangles),'signedVolume':volume,'minLocalZ':min(v.co.z for v in o.data.vertices)})
for d in [208,209,212]:assert min(r['minLocalZ'] for r in rows if r['dong']==d)==0
(OUT/'geometry-validation.json').write_text(json.dumps({'blender':bpy.app.version_string,'finiteVertices':True,'positiveMeshVolumes':True,'groundMinZEachAsset':0,'components':rows},indent=2)+'\n')
bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-height-corrected.blend'));print('MAPLE_NEXT_VALIDATED',len(rows),'components',sum(r['triangles'] for r in rows),'triangles')

D=json.loads((OUT/'authored-input.json').read_text());old=json.loads((OUT.parent/'maple-next-towers/authored-input.json').read_text())
checks=[]
for a in D['assets']:
 prior=next(v for v in old['assets'] if v['dong']==a['dong'])
 assert a['ring']==prior['ring'] and a['coordinate']==prior['coordinate'] and a['faces']==prior['faces']
 for key in a['roof']:
  if key!='heights':assert a['roof'][key]==prior['roof'][key]
 objs=[o for o in bpy.data.objects if o.type=='MESH' and o.get('dong')==a['dong']]
 checks.append({'dong':a['dong'],'sourceHeightM':a['sourceHeightM'],'heightM':max(v.co.z for o in objs for v in o.data.vertices),'wingFloors':a['wingFloors'],'upperWindowRows':[f-2 for f in a['wingFloors']],'ringAnchorFacadeRoofAssembliesPreserved':True})
(OUT/'height-validation.json').write_text(json.dumps(checks,indent=2))
print('HEIGHT_VALIDATION',checks)
