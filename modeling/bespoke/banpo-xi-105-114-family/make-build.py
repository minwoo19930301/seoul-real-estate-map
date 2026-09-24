from pathlib import Path
B=Path('data/model-source/bespoke');P=B/'banpo-xi-105-114-family';old=(B/'banpo-xi-102-104-family/102/build.py').read_text();start=old[old.index('objs=[]'):old.index('upper=clip')];start=start[:start.index('def clip')];start=start.replace('BX102','BX'+"{t}")
fac=old[old.index('def facade'):old.index('facade(r,0,24)')];fac=fac.replace('L+.5,.36,.35','L,.36,.23').replace('L+.2,.30,.32','L,.30,.23')
merge=old[old.index('# Consolidate'):old.index("s['source_ring_m']")]
script='''import bpy, math, json, pathlib
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());t=D['name'].replace('동','');old=bpy.context.scene
s=bpy.data.scenes.new('Banpo Xi '+t+' inferred family');bpy.context.window.scene=s
s['reference_scope']=D['reference_scope'];s['height_basis']=D['height_basis'];s['source_id']=D['id'];s['register_id']=D['register_row']['id'];s['register_height_m']=D['register_height_m'];s['floors']=D['floors'];s['supersedesAssetIds']='null';s['binding_status']='pending root binding map';s['inferredFromAssetIds']='bespoke-banpo-xi-101';s['regions_json']=json.dumps(regions);s['anchor_lonlat']=D['anchor_lonlat'];s['source_ring_m']=json.dumps(D['ring_m'])
'''+start+'''
pitch=D['body_height_m']/D['floors'];F=D['floors'];LF=D['lower_wing_floors_inferred'];body=D['body_height_m'];lower=D['lower_body_height_m']
def mass(n,part,z0,z1):
 ring=part['ring'];N=len(ring);v=[(x,y,z) for z in [z0,z1] for x,y in ring];f=[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
 for tri in part['triangles']:
  offset=len(v);v.extend([(x,y,z0) for x,y in reversed(tri)]);f.append(tuple(range(offset,offset+3)));offset=len(v);v.extend([(x,y,z1) for x,y in tri]);f.append(tuple(range(offset,offset+3)))
 return mesh(n,v,f,stone)
# Source footprint body is tiled by exact disjoint inferred regions, with triangulated concave caps.
for region in regions:
 for part in region['polygons']:mass(region['id'],part,0,region['body_height_m'])
'''+fac+'''
facade(r,0,LF)
for part in regions[1]['polygons']:facade(part['ring'],LF,F)
# Frames fit inside individual roof regions. No photo-specific identity is asserted.
for region in regions:
 u,v,w,d=region['roof_frame_uv'];z=region['body_height_m'];name=region['id']
 for a in [-w/2,w/2]:
  for b in [-d/2,d/2]:
   x,y=xy(u+a,v+b);box(name+' roof pillar',(x,y,z+1.35),(.3,.3,2.7),white,theta)
 for b in [-d/2,d/2]:
  x,y=xy(u,v+b);box(name+' thick brown long coping',(x,y,z+2.8),(w+.4,.4,.4),cap,theta)
 for a in [-w/2,w/2]:
  x,y=xy(u+a,v);box(name+' thick brown end coping',(x,y,z+2.8),(.4,d+.4,.4),cap,theta)
 x,y=xy(u,v);box(name+' opaque cream access wall',(x,y,z+1.05),(w*.60,d*.45,2.1),white,theta);box(name+' access coping',(x,y,z+2.22),(w*.7,d*.55,.3),cap,theta)
'''+merge+'''
for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
bpy.ops.export_scene.gltf(filepath=str(P/('banpo-xi-'+t+'.glb')),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=12;s.render.resolution_x=700;s.render.resolution_y=900;s.render.resolution_percentage=100
s.world=bpy.data.worlds.new('BX'+t+' world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('BX'+t+' sun','SUN');lo=bpy.data.objects.new('BX'+t+' sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
H=D['register_height_m']
for name,uvloc,z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.6)]:
 ca=bpy.data.cameras.new('BX'+t+' '+name);ob=bpy.data.objects.new('BX'+t+' '+name,ca);s.collection.objects.link(ob);x,y=xy(*uvloc);ob.location=(x,y,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.25;s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'tower':t,'source_id':D['id'],'finite':all(math.isfinite(c) for v in vs for c in v),'base_z':min(v.z for v in vs),'max_z':max(v.z for v in vs),'mesh_count':len(objs),'embedded_image_textures':0,'reference_scope':D['reference_scope'],'lower_wing_floors_inferred':LF}
assert report['finite'] and abs(report['base_z'])<1e-5 and abs(report['max_z']-H)<1e-4
(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/('banpo-xi-'+t+'-authored.blend')),{s},fake_user=True,compress=True)
bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);print(json.dumps(report))
'''
for t in map(str,range(105,115)):(P/t/'build.py').write_text(script.replace('BX{t}','BX'+t))
(P/'build-all.py').write_text("import bpy,pathlib,json\nP=pathlib.Path(__file__).parent;old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes}\nfor t in map(str,range(105,115)):\n p=P/t/'build.py';exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})\nafter={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after and bpy.context.scene==old\n(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'active_scene':old.name,'before':before,'after':after},indent=2))\n")
