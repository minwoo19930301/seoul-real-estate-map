import bpy, math, json, pathlib
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());t=D['name'].replace('동','');old=bpy.context.scene
s=bpy.data.scenes.new('Banpo Xi '+t+' inferred family');bpy.context.window.scene=s
s['reference_scope']=D['reference_scope'];s['height_basis']=D['height_basis'];s['source_id']=D['id'];s['register_id']=D['register_row']['id'];s['register_height_m']=D['register_height_m'];s['floors']=D['floors'];s['supersedesAssetIds']=json.dumps(D['supersedesAssetIds']);s['binding_status']=D['binding_status'];s['inferredFromAssetIds']='bespoke-banpo-xi-101';s['regions_json']=json.dumps(regions);s['anchor_lonlat']=D['anchor_lonlat'];s['source_ring_m']=json.dumps(D['ring_m'])
objs=[]
def mat(n,c,metal=0):
 m=bpy.data.materials.new('BX121 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=.3 if metal else .72;return m
stone=mat('pale silver limestone',(.66,.68,.66));white=mat('ivory course bands',(.86,.87,.82));core=mat('grey service core',(.37,.40,.40));glass=mat('blue grey broad glazing',(.12,.25,.31),.38);frame=mat('white window frames',(.79,.83,.81),.15);cap=mat('dark coping',(.20,.17,.14));base=mat('warm ground stone',(.39,.36,.31))
batches={}
def mesh(n,v,f,m):
 vertices,faces=batches.setdefault(m,[[],[]]);offset=len(vertices);vertices.extend(v);faces.extend([tuple(offset+i for i in face) for face in f]);return None
def box(n,c,d,m,ang=0):
 x,y,z=c;u,v,w=[k/2 for k in d];co,si=math.cos(ang),math.sin(ang);return mesh(n,[(x+a*co-b*si,y+a*si+b*co,z+h) for h in [-w,w] for a,b in [(-u,-v),(u,-v),(u,v),(-u,v)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def uv(p):return p[0]*co+p[1]*si,-p[0]*si+p[1]*co
def xy(u,v):return (u*co-v*si,u*si+v*co)

pitch=D['body_height_m']/D['floors'];F=D['floors'];LF=D['lower_wing_floors_inferred'];body=D['body_height_m'];lower=D['lower_body_height_m']
def mass(n,part,z0,z1):
 ring=part['ring'];N=len(ring);v=[(x,y,z) for z in [z0,z1] for x,y in ring];f=[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
 for tri in part['triangles']:
  offset=len(v);v.extend([(x,y,z0) for x,y in reversed(tri)]);f.append(tuple(range(offset,offset+3)));offset=len(v);v.extend([(x,y,z1) for x,y in tri]);f.append(tuple(range(offset,offset+3)))
 return mesh(n,v,f,stone)
# Source footprint body is tiled by exact disjoint inferred regions, with triangulated concave caps.
for region in regions:
 for part in region['polygons']:mass(region['id'],part,0,region['body_height_m'])
def facade(ring,first,last):
 area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]+ring[:1]))
 for ei,(a,b) in enumerate(zip(ring,ring[1:]+ring[:1])):
  dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
  def face(n,t,z,w,h,dep,m):return box(n,(a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,.12,h),m,ang)
  if first==0:face('three storey warm stone base',.5,pitch*1.5,L,pitch*3,.08,base)
  if L<2.5:continue
  # Quiet broad service return selected in local orientation: inference, not surveyed.
  quiet=abs(math.cos(ang-theta))<.4 and (a[0]+b[0])>8
  if quiet:
   for f in range(first,last):face('quiet service wall horizontal joints',.5,(f+.04)*pitch,L,.08,.17,white)
   face('quiet wall roof coping',.5,last*pitch-.18,L,.36,.23,cap)
   continue
  count=max(1,round(L/4.8));bw=L/count
  for j in range(count):
   service=(j%3==1) or L<4.3;t=(j+.5)/count;w=bw*(.39 if service else .86)
   if service:face('grey narrow service strip',t,(first+last)*pitch/2,bw*.76,(last-first)*pitch,.065,core)
   for f in range(first,last):
    z=(f+.56)*pitch;h=pitch*(.36 if service else .64)
    face('service window' if service else 'wide living room window',t,z,w,h,.145,glass)
    for off in [-h/2,h/2]:face('window sill head',t,z+off,w+.10,.075,.23,frame)
    panes=2 if service else (4 if w>3.5 else 3)
    for k in range(panes+1):face('window upright mullion',t+(k/panes-.5)*w/L,z,.065,h,.24,frame)
    if not service:face('living window lower transom',t,z-h*.18,w,.05,.25,frame)
    face('pale horizontal floor course',t,(f+.04)*pitch,bw,.13,.20,base if f<3 else white)
   for side in [-1,1]:face('vertical panel joint',t+side*(bw*.48)/L,(first+last)*pitch/2,.07,(last-first)*pitch,.16,white)
  face('deep roof cornice',.5,last*pitch-.15,L,.30,.23,cap)

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
# Same geometry order, accumulated in memory to avoid thousands of transient Blender objects.
objs=[]
for material,(vertices,faces) in batches.items():
 me=bpy.data.meshes.new('editable '+material.name);me.from_pydata(vertices,[],faces);me.update();ob=bpy.data.objects.new('editable '+material.name,me);s.collection.objects.link(ob);me.materials.append(material);objs.append(ob)
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
