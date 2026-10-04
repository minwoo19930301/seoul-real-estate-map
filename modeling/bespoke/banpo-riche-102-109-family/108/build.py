import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Banpo Riche108 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['register_height_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256'];s['facade_edge_classes']=json.dumps(D['facade_edge_classes'])
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('Riche108 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.82,.83,.81));metal=mat('light grey solid wall',(.71,.73,.72),.08,.66);glass=mat('teal rectangular grouped windows',(.16,.34,.36),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.35,.37,.37),.12,.58);base=mat('muted ground wall',(.34,.36,.35),.08,.65);service=mat('dark recessed service strip',(.18,.22,.24),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['register_height_m'];body=H-3.5;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-3.25),roof)
# Banpo Riche-specific solid service walls and thick punched-window frames.
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
face_roles=[]
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.10):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 face(.5,.6,L,1.2,.025,base)
 blank=D['facade_edge_classes'][ei]['blank']
 face_roles.append({'edge':ei,'length_m':L,'role':'blank panel service wall' if blank else 'punched living windows with narrow recessed service strip','basis':'complex photo inference; orientation not surveyed'})
 if blank:
  # Intentionally windowless broad pale wall; joints are subtle, not glazing.
  for k in range(1,FLOORS*2):face(.5,k*body/(FLOORS*2),max(.1,L-.16),.023,.061,roof,depth=.015)
  for t in [.035,.965]:face(t,body/2,min(.28,L*.055),body,.09,white)
 else:
  service_w=min(1.05,L*.10);face(.12,body/2,service_w+.18,body,.018,service)
  lo=.24;hi=.965;count=max(1,int(L*(hi-lo)/3.4));bw=(hi-lo)*L/count
  for f in range(FLOORS):
   z=(f+.55)*pitch;wh=pitch*.66
   face(.12,z,service_w*.70,pitch*.48,.08,glass)
   face(.12,(f+.08)*pitch,service_w+.20,.22,.15,white)
   for j in range(count):
    t=lo+(j+.5)*(hi-lo)/count;ww=max(.3,bw-.58)
    face(t,z,ww,wh,.075,glass)
    for q in [-.5,.5]:face(t+q*ww/L,z,.085,wh,.16,frame)
    face(t,z, .065,wh,.16,frame)
    face(t,z-wh*.18,ww,.055,.16,frame)
   # Strong continuous white spandrels and thick piers.
   face((lo+hi)/2,(f+.07)*pitch,(hi-lo)*L,.36,.19,white)
  for j in range(count+1):
   t=lo+j*(hi-lo)/count;face(t,body/2,.48,body,.22,white)
  face(.025,body/2,.35,body,.18,white)
 face(.5,body-.18,L,.36,.18,white)
(P/'facade-regions.json').write_text(json.dumps(face_roles,indent=2))
# Photo-visible squared roof grille; fully contained and below registered maximum.
u,v,w,d=D['roof_cap_uv'];x,y=u*co-v*si,u*si+v*co
# Closed low service plinth supports four frame legs and fine grille bars.
box((x,y,(H-2.95)),(w,d,.60),metal,theta)
for uu in [-w/2+.22,w/2-.22]:
 for vv in [-d/2+.22,d/2-.22]:box((x+uu*co-vv*si,y+uu*si+vv*co,(H-1.5)),(.44,.44,3.0),white,theta)
for vv in [-d/2+.22,d/2-.22]:
 box((x-vv*si,y+vv*co,(H-.25)),(w,.44,.50),white,theta)
 for k in range(1,13):
  uu=-w/2+k*w/13;box((x+uu*co-vv*si,y+uu*si+vv*co,(H-1.45)),(.10,.12,2.25),service,theta)
for uu in [-w/2+.22,w/2-.22]:box((x+uu*co,y+uu*si,(H-.25)),(.44,d,.50),white,theta)
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('Riche108 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('Riche108 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'banpo-riche-108.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('Riche108 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('Riche108 sun','SUN');lo=bpy.data.objects.new('Riche108 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('Riche108 '+name);ob=bpy.data.objects.new('Riche108 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':H,'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'banpo-riche-108-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
