import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/raemian-caelitus'
scene=bpy.context.scene;scene.camera=bpy.data.objects['northwest_rear_steps']
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  space=area.spaces.active;space.region_3d.view_perspective='CAMERA';space.region_3d.view_camera_zoom=0;space.clip_end=3000;space.shading.type='MATERIAL';space.overlay.show_overlays=False
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'raemian-caelitus.blend'));print('CAELITUS_VIEWPORT_READY')
