import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('SeoulForest Riverview Xi107 sibling');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['register_height_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256']
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('SFRX107 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.82,.83,.81));metal=mat('light grey solid wall',(.68,.70,.70),.08,.66);glass=mat('blue grey horizontal glazing',(.15,.27,.30),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.35,.37,.37),.12,.58);base=mat('muted ground wall',(.34,.36,.35),.08,.65);service=mat('deep gray recessed service wall',(.25,.28,.29),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['register_height_m'];body=H-1.5;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m,rings=None,triangles=None):
 for ring in (rings or D['rings_m']):
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in (triangles or regions[0]['triangles']):
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
s['central_recess']=json.dumps(D['central_recess']);s['visual_revision']='v2 broader white grid; unmeasured photo-derived ratios'
C=D['central_recess'];mass(0,1,metal);mass(1,body-.25,metal,C['shell_rings'],C['shell_triangles']);mass(body-.25,body,metal);mass(body,(H-1.25),roof)
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.10):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 def bank(lo,hi):
  count=max(1,int((hi-lo)*L/2.8));bw=(hi-lo)*L/count
  for f in range(FLOORS):
   z=(f+.54)*pitch;hh=pitch*.59
   for j in range(count):
    t=lo+(j+.5)*(hi-lo)/count;ww=bw-.60;face(t,z,ww,hh,.05,glass)
    face(t,z,.22,hh,.16,white);face(t,z-hh*.15,ww,.05,.13,frame)
   face((lo+hi)/2,(f+.11)*pitch,(hi-lo)*L,.57,.16,white)
  for j in range(count+1):face(lo+j*(hi-lo)/count,body/2,.56,body,.19,white)
 if ei==C['edge']:
  # Two white gridded strips flank a true inward recessed central wall.
  bank(.02,.315);bank(.685,.98)
  center=(.34+.66)/2;width=L*.32
  face(center,body/2,width,body-2,-1.48,service,depth=.025)
  for f in range(FLOORS):
   # Very small staggered service apertures on the back wall.
   t=.46 if f%2==0 else .55;face(t,(f+.52)*pitch,.38,.48,-1.445,glass,depth=.025)
   face(center,(f+.15)*pitch,width,.022,-1.455,frame,depth=.012)
  for t in [.42,.50,.58]:face(t,body/2,.018,body-2,-1.455,frame,depth=.012)
  for j,(start,end) in enumerate(C['box_bands']):
   t=.415 if j%2==0 else .585;bw=width*.42;z0=start*pitch;z1=end*pitch
   # Back of box touches recessed solid wall; front stays within own source edge.
   face(t,(z0+z1)/2,bw,z1-z0,-.755,metal,depth=1.49)
   for f in range(start,end):
    face(t,(f+.54)*pitch,bw-.32,pitch*.60,-.004,glass,depth=.008)
    face(t,(f+.08)*pitch,bw,.24,-.003,white,depth=.006)
    for q in [-.5,.5]:face(t+q*(bw-.16)/L,(f+.54)*pitch,.12,pitch,-.003,white,depth=.006)
   # Contained shallow sill and flush coping support box silhouette.
   face(t,z0+.10,bw,.20,-.75,white,depth=1.5)
   face(t,z1-.10,bw,.20,-.75,white,depth=1.5)
 elif L>=9 and abs(math.cos(ang-theta))>.55:
  bank(.08,.92)
  face(.035,body/2,.20,body,.025,service)
 elif L>6:
  # Broad pale blank side walls, with fine panel joints and one dark cut.
  for f in range(1,FLOORS):face(.5,f*pitch,L-.10,.023,.055,roof,depth=.016)
  face(.18,body/2,.22,body,.025,service)
  for t in [.035,.965]:face(t,body/2,.24,body,.09,white)
 else:
  face(.5,body/2,L*.85,body,.012,service)
  if L>3.2:
   for f in range(FLOORS):face(.52,(f+.54)*pitch,L*.36,pitch*.45,.05,glass)
 face(.5,body-.14,L,.28,.17,white)
# Foreground roof cropped; a low contained access cap is conservative inference.
u,v,w,d=D['roof_cap_uv'];x,y=u*co-v*si,u*si+v*co
box((x,y,(H-.75)),(w,d,1.0),metal,theta)
box((x,y,(H-.125)),(w+.30,d+.30,.25),roof,theta)
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('SFRX107 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('SFRX107 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'seoulforest-riverview-xi-107.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('SFRX107 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('SFRX107 sun','SUN');lo=bpy.data.objects.new('SFRX107 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(65,-175),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('SFRX107 '+name);ob=bpy.data.objects.new('SFRX107 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':H,'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'seoulforest-riverview-xi-107-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
