import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Shinbanpo Xi105 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['register_height_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256']
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('SBX105 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('white vertical frame',(.80,.81,.77));metal=mat('lavender grey metallic panels',(.43,.39,.45),.28,.42);glass=mat('pale teal glazing',(.16,.32,.33),.38,.26);frame=mat('thin grey window mullions',(.47,.52,.52),.25,.36);roof=mat('broad charcoal roof caps',(.13,.15,.18),.18,.48);base=mat('dark glazed base',(.10,.15,.17),.32,.30);service=mat('grey inset service walls',(.27,.29,.32),.18,.50)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['register_height_m'];body=H-2.40;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-2.15),service)
# Photo-derived window/panel vocabulary; individual orientation is unconfirmed.
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.12):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 face(.5,pitch*1.5,L,pitch*3,.04,base)
 if L<2.4:
  face(.5,body/2,L,body,.035,service)
  for f in range(1,FLOORS):face(.5,f*pitch,L,.06,.12,frame)
  continue
 bays=max(1,round(L/3.9));bw=L/bays
 for j in range(bays):
  t=(j+.5)/bays;quiet=(j==bays//2);w=bw*(.30 if quiet else .56)
  if quiet:face(t,body/2,bw*.94,body,.035,service)
  for f in range(FLOORS):
   z=(f+.56)*pitch;h=pitch*(.38 if quiet else .49);face(t,z,w,h,.13,glass if f>=3 else base)
   for off in [-h/2,h/2]:face(t,z+off,w+.10,.075,.205,frame)
   panes=2 if quiet else 3
   for k in range(panes+1):face(t+(k/panes-.5)*w/L,z,.065,h,.205,frame)
   face(t,z-h*.21,w,.05,.21,frame)
   # Grey metal spandrels stay broad; white grid defines selected central banks.
   face(t,(f+.02)*pitch,bw,.105,.14,white if j%3==1 else metal)
  for side in [-1,1]:
   if j%3==1:face(t+side*bw*.47/L,body/2,.55,body,.20,white)
  if j%3==1:face(t,body-.18,bw,.36,.23,white)
 # A broad rectangular charcoal cap crowns each principal face, unlike open Banpo pergolas.
 face(.5,body-.20,L,.40,.18,white,depth=.20)
 # Wider white end piers create the tall vertical framework visible in the approved photo.
 for t in [.55/L,1-.55/L]:face(t,body/2,1.05,body,.21,white)
# Root-reviewed revision: raised rectangular coping inside the source footprint.
u,v,w,d=D['roof_frame_uv'];deck=(H-2.15)
for a in [-w/2,w/2]:
 for b in [-d/2,d/2]:
  x,y=(u+a)*co-(v+b)*si,(u+a)*si+(v+b)*co;box((x,y,(deck+(H-.60))/2),(.80,.80,(H-.60)-deck),white,theta)
for b in [-d/2,d/2]:
 x,y=u*co-(v+b)*si,u*si+(v+b)*co;box((x,y,(H-.30)),(w+.85,.85,.60),roof,theta)
for a in [-w/2,w/2]:
 x,y=(u+a)*co-v*si,(u+a)*si+v*co;box((x,y,(H-.30)),(.85,d+.85,.60),roof,theta)
x,y=u*co-v*si,u*si+v*co;box((x,y,(H-1.55)),(w*.48,d*.42,1.20),metal,theta)
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('SBX105 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('SBX105 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'shinbanpo-xi-105.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('SBX105 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('SBX105 sun','SUN');lo=bpy.data.objects.new('SBX105 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('SBX105 '+name);ob=bpy.data.objects.new('SBX105 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':H,'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'shinbanpo-xi-105-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
