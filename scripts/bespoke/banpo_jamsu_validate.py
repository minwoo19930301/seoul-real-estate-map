import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/banpo-jamsu'
rows=[];minimum=float('inf')
for o in bpy.data.objects:
 if o.type!='MESH':continue
 o.data.calc_loop_triangles();volume=0
 for v in o.data.vertices:
  p=o.matrix_world@v.co;assert all(math.isfinite(c) for c in p);minimum=min(minimum,p.z)
 for tri in o.data.loop_triangles:
  a,b,c=[o.data.vertices[i].co for i in tri.vertices];volume+=a.dot(b.cross(c))/6
 assert volume>0,(o.name,volume)
 rows.append({'name':o.name,'triangles':len(o.data.loop_triangles),'outwardSignedVolume':volume})
assert abs(minimum)<.001
(OUT/'geometry-validation.json').write_text(json.dumps({'blender':bpy.app.version_string,'minZ':minimum,'components':rows,'triangles':sum(r['triangles'] for r in rows),'finiteVertices':True,'outwardNormals':True},indent=2))
bpy.ops.object.select_all(action='DESELECT')
cam=bpy.data.objects['Underdeck']
for o in bpy.data.objects:
 if o.type in ['LIGHT','CAMERA']:o.hide_set(True)
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  space=area.spaces.active;space.overlay.show_overlays=False;space.shading.type='MATERIAL';space.region_3d.view_rotation=cam.rotation_euler.to_quaternion();space.region_3d.view_distance=65;space.region_3d.view_location=cam.location + cam.rotation_euler.to_quaternion()@Vector((0,0,-65));space.region_3d.view_perspective='PERSP';space.lens=25
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'banpo-jamsu.blend'))
print('GEOMETRY_VERIFIED',len(rows),'components','minZ',minimum)
