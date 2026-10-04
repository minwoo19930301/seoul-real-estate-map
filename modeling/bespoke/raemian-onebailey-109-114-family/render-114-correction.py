import bpy,json,time
from pathlib import Path
O=Path(__file__).resolve().parent;s=bpy.data.scenes['OneBailey109to114_authoring'];bpy.context.window.scene=s;records=[]
for cam in sorted([o for o in s.objects if o.type=='CAMERA' and o.name.startswith('114_')],key=lambda o:o.name):
 
 for c in s.collection.children:
  if c.name.endswith('_retained_individual_massing'):c.hide_render=not c.name.startswith(cam.name[:3])
 for ob in s.objects:
  if ob.name.endswith('_review_ground'):ob.hide_render=not ob.name.startswith(cam.name[:3])
 s.camera=cam;s.render.filepath=str(O/f'review-{cam.name}.png');t=time.time();bpy.ops.render.render(write_still=True);records.append({'camera':cam.name,'file':s.render.filepath,'seconds':time.time()-t})
(O/'render-114-correction-records.json').write_text(json.dumps(records,indent=2));print(records)
