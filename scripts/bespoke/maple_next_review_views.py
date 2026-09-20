"""Extra source comparable views, including read-only frozen210/211 context."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-next-towers';D=json.loads((OUT/'authored-input.json').read_text());scene=bpy.context.scene;ref=D['assets'][0]['coordinate']
for d in [210,211]:
 if any(o.get('reviewContextDong')==d for o in scene.objects):continue
 old=json.loads((ROOT/'docs/MAPLE_XI_MODEL_RECIPE.json').read_text());a=next(a for a in old['assets'] if a['id']==f'maple-xi-{d}');before=set(scene.objects)
 path=ROOT/'public/models/bespoke'/f'bespoke-maple-xi-{d}.glb'
 if not path.exists():continue
 bpy.ops.import_scene.gltf(filepath=str(path));obs=list(set(scene.objects)-before);dx=(a['coordinate']['lon']-ref['lon'])*111320*math.cos(math.radians(ref['lat']));dy=(a['coordinate']['lat']-ref['lat'])*111320
 for o in obs:
  o['reviewContextDong']=d
  if o.parent not in obs:o.location+=Vector((dx,dy,0))
def camera(name,loc,target,scale=None):
 o=bpy.data.objects.get(name)
 if not o:c=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,c);scene.collection.objects.link(o)
 o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();o.data.clip_end=4000
 if scale:o.data.type='ORTHO';o.data.ortho_scale=scale
 else:o.data.type='PERSP';o.data.lens=45
 scene.camera=o;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
for o in scene.objects:o.hide_render=False
camera('six-tower-east-context',(340,65,255),(-10,70,50),280)
camera('six-tower-opposite-context',(-220,-200,250),(-10,70,50),290)
A=D['assets'][0];V=[Vector(v) for v in A['ring']];e=A['entry']['edge'];a,b=V[e],V[(e+1)%len(V)];v=b-a;n=Vector((-v.y,v.x)).normalized();p=a+v*A['entry']['fraction']
for o in scene.objects:
 if o.type=='MESH':o.hide_render=o.get('dong')!=208
camera('208-numbered-entry-detail',(p.x+n.x*14,p.y+n.y*14,3.4),(p.x,p.y,2.8))
for o in scene.objects:o.hide_render=False
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  sp=area.spaces.active;sp.overlay.show_overlays=False;sp.shading.type='MATERIAL';sp.lens=50;sp.region_3d.view_location=(-10,70,52);sp.region_3d.view_rotation=bpy.data.objects['six-tower-east-context'].rotation_euler.to_quaternion();sp.region_3d.view_distance=330;sp.clip_end=4000
scene.camera=bpy.data.objects['six-tower-east-context'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-next-towers.blend'));print('MAPLE_NEXT_CONTEXT_AND_ENTRY_REVIEW_VIEWS')
