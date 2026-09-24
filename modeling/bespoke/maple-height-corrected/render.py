import bpy,json
from pathlib import Path
from mathutils import Vector
OUT=Path('/Users/hyemini/Documents/Codex/2026-09-08/seoul-elevation-local/data/model-source/bespoke/maple-height-corrected');scene=bpy.context.scene
scene.cycles.samples=16;scene.render.resolution_x=1200;scene.render.resolution_y=1000
D=json.loads((OUT/'authored-input.json').read_text())
for A in D['assets']:
 dong=A['dong'];objs=[o for o in scene.objects if o.type=='MESH' and o.get('dong')==dong]
 center=objs[0].location.copy();center.z=max(A['roof']['heights'])-5
 c=bpy.data.cameras.new(str(dong)+'_close');c.type='ORTHO';c.ortho_scale=48;c.clip_end=4000;cam=bpy.data.objects.new(str(dong)+'_close',c);scene.collection.objects.link(cam);cam.location=center+Vector((90,-105,45));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
 for name in ['east','west','roof','close']:
  for obj in scene.objects:
   if obj.type=='MESH':obj.hide_render=obj.get('dong')!=dong
  scene.camera=bpy.data.objects[f'{dong}_{name}'];scene.render.filepath=str(OUT/f'{dong}_{name}.png');bpy.ops.render.render(write_still=True)
for obj in scene.objects:obj.hide_render=False
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-height-corrected.blend'))
print('CORRECTED_TWELVE_VIEWS_COMPLETE')
