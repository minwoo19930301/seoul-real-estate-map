"""Read-only visual audit of existing public GLBs, not model regeneration."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-audit';OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
recipe=json.loads((ROOT/'docs/MAPLE_XI_MODEL_RECIPE.json').read_text());LON,LAT=127.0128,37.5118
collections={};centers={};bounds={}
for asset in recipe['assets']:
 ident=asset['id'];before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/'public/models/maple-xi'/asset['model']))
 imported=list(set(bpy.data.objects)-before);collection=bpy.data.collections.new(ident);bpy.context.scene.collection.children.link(collection)
 x=(asset['coordinate']['lon']-LON)*111320*math.cos(math.radians(LAT));y=(asset['coordinate']['lat']-LAT)*111320
 for o in imported:
  for c in list(o.users_collection):c.objects.unlink(o)
  collection.objects.link(o)
  if o.parent not in imported:o.location+=Vector((x,y,0))
 collections[ident]=collection
 bpy.context.view_layer.update();pts=[o.matrix_world@Vector(v) for o in imported if o.type=='MESH' for v in o.bound_box]
 lo=Vector([min(p[i] for p in pts) for i in range(3)]);hi=Vector([max(p[i] for p in pts) for i in range(3)])
 centers[ident]=(lo+hi)/2;bounds[ident]={'min':list(lo),'max':list(hi)}
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=1400;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.38,.43,.48,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
scene.view_settings.view_transform='AgX';sun=bpy.data.lights.new('Audit_sun','SUN');sun.energy=3;ob=bpy.data.objects.new('Audit_sun',sun);scene.collection.objects.link(ob);ob.rotation_euler=(.45,-.5,-.7)
cam=bpy.data.cameras.new('Audit_camera');ob=bpy.data.objects.new('Audit_camera',cam);scene.collection.objects.link(ob);scene.camera=ob;cam.type='ORTHO';cam.clip_end=10000
views=[('complex-sw',None,Vector((0,0,45)),Vector((-640,-730,630)),750),('complex-ne',None,Vector((0,0,45)),Vector((700,500,520)),740),('plan',None,Vector((0,0,0)),Vector((0,0,1200)),690)]
for dong in [101,104]:
 ident='maple-xi-'+str(dong);target=centers[ident];views.append((str(dong),[ident],target,target+Vector((-160,-210,125)),170))
target=(centers['maple-xi-210']+centers['maple-xi-211'])/2;views.append(('210-211',['maple-xi-210','maple-xi-211'],target,target+Vector((-180,-230,140)),185))
for name,visible,target,location,scale in views:
 for ident,c in collections.items():c.hide_render=visible is not None and ident not in visible
 ob.location=location;ob.rotation_euler=(target-location).to_track_quat('-Z','Y').to_euler();cam.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
for c in collections.values():c.hide_render=False
(OUT/'imported-bounds.json').write_text(json.dumps(bounds,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-audit.blend'))
print('MAPLE_AUDIT_RENDERED_EXISTING_PUBLIC_GLBS',len(collections))
