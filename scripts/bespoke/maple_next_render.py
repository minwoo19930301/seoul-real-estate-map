import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-next-towers';scene=bpy.context.scene
for dong in [208,209,212,213]:
 for name in ['east','west','roof']:
  for o in scene.objects:
   if o.type=='MESH':o.hide_render=o.get('dong')!=dong
  scene.camera=bpy.data.objects[f'{dong}_{name}'];scene.render.filepath=str(OUT/f'{dong}_{name}.png');bpy.ops.render.render(write_still=True)
for o in scene.objects:o.hide_render=False
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  sp=area.spaces.active;sp.overlay.show_overlays=False;sp.shading.type='MATERIAL';sp.lens=50;sp.region_3d.view_location=(0,70,52);sp.region_3d.view_rotation=bpy.data.objects['208_east'].rotation_euler.to_quaternion();sp.region_3d.view_distance=350;sp.clip_end=4000
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-next-towers.blend'));print('MAPLE_NEXT_TWELVE_VIEWS_COMPLETE')
