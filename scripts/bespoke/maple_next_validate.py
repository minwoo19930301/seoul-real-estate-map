import bpy,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-next-towers';rows=[]
for o in bpy.data.objects:
 if o.type!='MESH' or o.get('dong') not in [208,209,212,213] or o.get('reviewContextDong'):continue
 o.data.calc_loop_triangles();volume=0
 for v in o.data.vertices:assert all(math.isfinite(c) for c in v.co)
 for t in o.data.loop_triangles:
  a,b,c=[o.data.vertices[i].co for i in t.vertices];volume+=a.dot(b.cross(c))/6
 assert volume>0,(o.name,volume)
 rows.append({'name':o.name,'dong':o.get('dong'),'triangles':len(o.data.loop_triangles),'signedVolume':volume,'minLocalZ':min(v.co.z for v in o.data.vertices)})
for d in [208,209,212,213]:assert min(r['minLocalZ'] for r in rows if r['dong']==d)==0
(OUT/'geometry-validation.json').write_text(json.dumps({'blender':bpy.app.version_string,'finiteVertices':True,'positiveMeshVolumes':True,'groundMinZEachAsset':0,'components':rows},indent=2)+'\n')
bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-next-towers.blend'));print('MAPLE_NEXT_VALIDATED',len(rows),'components',sum(r['triangles'] for r in rows),'triangles')
