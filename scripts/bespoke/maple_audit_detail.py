import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-audit';scene=bpy.context.scene;cam=scene.camera
bounds=json.loads((OUT/'imported-bounds.json').read_text())
for n in bounds:bpy.data.collections[n].hide_render=False
lo=Vector([min(r['min'][i] for r in bounds.values()) for i in range(3)]);hi=Vector([max(r['max'][i] for r in bounds.values()) for i in range(3)]);target=(lo+hi)/2
labels=[]
for n,r in bounds.items():
 if n.rsplit('-',1)[-1].isdigit():
  c=(Vector(r['min'])+Vector(r['max']))/2;data=bpy.data.curves.new(n+' label','FONT');data.body=n.rsplit('-',1)[-1];data.size=7;data.align_x='CENTER';ob=bpy.data.objects.new(n+' label',data);scene.collection.objects.link(ob);ob.location=(c.x,c.y,r['max'][2]+3);labels.append(ob)
cam.location=(target.x,target.y,1000);cam.rotation_euler=(0,0,0);cam.data.ortho_scale=920;scene.render.filepath=str(OUT/'plan-numbered.png');bpy.ops.render.render(write_still=True)
for o in labels:o.hide_render=True;o.hide_set(True)
for n in bounds:bpy.data.collections[n].hide_render=n not in ['maple-xi-210','maple-xi-211']
target=(Vector(bounds['maple-xi-210']['min'])+Vector(bounds['maple-xi-211']['max']))/2
cam.location=target+Vector((220,-100,125));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=190;scene.render.filepath=str(OUT/'210-211-opposite.png');bpy.ops.render.render(write_still=True)
for n in bounds:bpy.data.collections[n].hide_render=False
bpy.ops.object.select_all(action='DESELECT')
for a in bpy.context.screen.areas:
 if a.type=='VIEW_3D':
  sp=a.spaces.active;sp.overlay.show_overlays=False;sp.shading.type='MATERIAL';sp.region_3d.view_location=Vector((0,0,45));sp.region_3d.view_rotation=(Vector((0,0,45))-Vector((700,500,520))).to_track_quat('-Z','Y');sp.region_3d.view_distance=850;sp.clip_end=5000
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-audit.blend'))
print('MAPLE_DETAIL_AND_NUMBERED_PLAN_COMPLETE')
