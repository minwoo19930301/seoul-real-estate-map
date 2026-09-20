import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-club-cloud';scene=bpy.context.scene
o=bpy.data.objects['Source2_east'];o.location=(165,-60,130);o.rotation_euler=(Vector((25,14,80))-o.location).to_track_quat('-Z','Y').to_euler();o.data.lens=52
for name in ['Courtyard','Highway','Roof_close','Under_bridge','Source2_east']:
 scene.camera=bpy.data.objects[name];scene.render.filepath=str(OUT/(name.lower()+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.object.select_all(action='DESELECT')
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  sp=area.spaces.active;sp.overlay.show_overlays=False;sp.shading.type='MATERIAL';sp.lens=50;sp.region_3d.view_location=Vector((10,2,47));sp.region_3d.view_rotation=bpy.data.objects['Courtyard'].rotation_euler.to_quaternion();sp.region_3d.view_distance=175;sp.clip_end=5000
scene.camera=bpy.data.objects['Courtyard'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-club-cloud.blend'))
print('MAPLE_CLUB_FOUR_REVIEW_VIEWS_COMPLETE')
