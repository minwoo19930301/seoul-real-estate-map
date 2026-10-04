import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Acro Riverview Shinbanpo104 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['register_height_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256']
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('ARV104 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.82,.83,.81));metal=mat('light grey solid wall',(.62,.65,.65),.08,.66);glass=mat('blue grey horizontal glazing',(.18,.31,.40),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.35,.37,.37),.12,.58);base=mat('muted ground wall',(.34,.36,.35),.08,.65);service=mat('recessed brown vertical seams',(.16,.11,.10),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['register_height_m'];body=H-1.25;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-1.),roof)
# Acro Riverview-specific broad horizontal glazing and narrower service grids.
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.12):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 face(.5,pitch*.75,L,pitch*1.5,.03,base)
 if L<2.5:
  face(.5,body/2,L,body,.015,service);continue
 if L>=6:
  # Distinct asymmetric living bank, brown seam, and tight service grid.
  living_t=.355;living_w=L*.61;service_t=.855;service_w=L*.19
  face(.718,body/2,min(.65,L*.06),body,.025,service)
  for f in range(FLOORS):
   z=(f+.57)*pitch;h=pitch*.65
   face(living_t,z,living_w,h,.09,glass)
   face(living_t,(f+.16)*pitch,living_w,.34,.18,frame)
   for off in [-h/2,h/2]:face(living_t,z+off,living_w,.085,.205,frame)
   for k in range(1,4):face(living_t+(k/4-.5)*living_w/L,z,.06,h,.20,frame)
   face(living_t,z-h*.22,living_w,.055,.20,frame)
   sh=pitch*.46;sz=(f+.55)*pitch;face(service_t,sz,service_w,sh,.08,glass)
   for k in [-.5,0,.5]:face(service_t+k*service_w/L,sz,.075,sh,.18,white)
   face(service_t,(f+.05)*pitch,service_w+.16,.20,.20,white)
  for t in [.028,.681,.768,.974]:
   width=.56 if t in [.028,.974] else .42;pos=max(width/(2*L),min(1-width/(2*L),t));face(pos,body/2,width,body,.22,white)
 else:
  face(.5,body/2,L*.88,body,.02,service)
  for f in range(FLOORS):
   z=(f+.55)*pitch;w=L*.62;h=pitch*.47;face(.5,z,w,h,.10,glass);face(.5,(f+.04)*pitch,L,.20,.19,white)
   for t in [.15,.5,.85]:face(t,body/2,.16,body,.20,white)
 face(.5,body-.20,L,.40,.20,white)
# Foreground roof is cropped in the photo: modest contained flat access cap only.
u,v,w,d=D['roof_cap_uv'];x,y=u*co-v*si,u*si+v*co
box((x,y,(H-.60)),(w,d,.80),metal,theta)
box((x,y,(H-.15)),(w+.30,d+.30,.30),roof,theta)
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('ARV104 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('ARV104 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'acro-riverview-104.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('ARV104 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('ARV104 sun','SUN');lo=bpy.data.objects.new('ARV104 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('ARV104 '+name);ob=bpy.data.objects.new('ARV104 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':H,'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'acro-riverview-104-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
