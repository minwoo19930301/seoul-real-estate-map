import bpy,pathlib,json,hashlib
from mathutils import Vector
P=pathlib.Path(__file__).parent;old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};out=[]
for t in [106,107]:
 p=P/str(t);f=p/f'seoulforest-riverview-xi-{t}-authored.blend';glb=p/f'seoulforest-riverview-xi-{t}.glb';sha=hashlib.sha256(glb.read_bytes()).hexdigest()
 with bpy.data.libraries.load(str(f),link=False) as (a,b):b.scenes=a.scenes
 assert len(b.scenes)==1;s=b.scenes[0];bpy.context.window.scene=s;vs=[o.matrix_world@v.co for o in s.objects if o.type=='MESH' for v in o.data.vertices];scales={}
 for name in ['front','opposite','side','roof']:
  cam=next(o for o in s.objects if o.type=='CAMERA' and name in o.name);inv=cam.rotation_euler.to_matrix().transposed();q=[inv@(v-cam.location) for v in vs];width=max(v.x for v in q)-min(v.x for v in q);height=max(v.y for v in q)-min(v.y for v in q);cam.data.ortho_scale=max(cam.data.ortho_scale,height*1.14,width/(850/1100)*1.14);scales[name]=cam.data.ortho_scale;s.camera=cam;s.render.filepath=str(p/(name+'.png'));bpy.ops.render.render(write_still=True)
 bpy.data.libraries.write(str(f),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);assert hashlib.sha256(glb.read_bytes()).hexdigest()==sha;out.append({'tower':t,'glb_unchanged':True,'orthographic_scales':scales})
assert before=={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};(P/'view-refit-proof.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
