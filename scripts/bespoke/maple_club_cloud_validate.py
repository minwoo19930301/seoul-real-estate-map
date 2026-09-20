import bpy,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-club-cloud';rows=[]
for o in bpy.data.objects:
 if o.type!='MESH':continue
 o.data.calc_loop_triangles();lo=min(v.co.z for v in o.data.vertices);volume=0
 for v in o.data.vertices:assert all(math.isfinite(c) for c in v.co)
 for tri in o.data.loop_triangles:
  a,b,c=[o.data.vertices[i].co for i in tri.vertices];volume+=a.dot(b.cross(c))/6
 assert volume>0,(o.name,volume)
 rows.append({'name':o.name,'dong':o.get('dong'),'triangles':len(o.data.loop_triangles),'signedVolume':volume,'minLocalZ':lo})
assert min(r['minLocalZ'] for r in rows)==0
(OUT/'geometry-validation.json').write_text(json.dumps({'blender':bpy.app.version_string,'finiteVertices':True,'outwardVolumes':True,'groundMinZ':0,'components':rows},indent=2)+'\n')
print('MAPLE_CLOUD_VALIDATED',len(rows),'components',sum(r['triangles'] for r in rows),'triangles')

for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  area.spaces.active.lens=50;area.spaces.active.region_3d.view_location=(15,6,52);area.spaces.active.region_3d.view_distance=175;area.spaces.active.region_3d.view_rotation=bpy.data.objects['Source2_east'].rotation_euler.to_quaternion()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-club-cloud.blend'))
