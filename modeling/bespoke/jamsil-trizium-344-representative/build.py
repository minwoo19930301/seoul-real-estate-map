import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Jamsil Trizium344 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['register_height_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['complex_household_discrepancy']=D['complex_household_discrepancy'];s['photo_list_index']=0;s['scope_exclusions']=json.dumps(D['scope_exclusions'])
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256'] or ''
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('Trizium344 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.85,.85,.80));metal=mat('light grey solid wall',(.55,.57,.58),.08,.66);glass=mat('turquoise balcony glazing',(.20,.36,.42),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.45,.47,.46),.12,.58);base=mat('muted ground wall',(.64,.51,.29),.08,.65);service=mat('narrow charcoal service strips',(.22,.25,.26),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['register_height_m'];body=H-3.;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-2.7),white)
# Trizium344: punched horizontal windows in broad off-white walls, solid grey service faces.
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]));roles=[]
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.08):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 blank=ei in [0,8];serviceface=ei in [2,3,4,5,6,10,12]
 roles.append({'edge':ei,'length_m':L,'role':'numbered pale endwall/yellow lower band' if blank else 'concave grey service face' if serviceface else 'offwhite punched window bank','basis':'own detailed edge geometry; endwall344 photo, foreground service detail complex inference; orientation unmeasured'})
 face(.5,body/2,L,body,.01,metal if serviceface else white,depth=.02)
 if blank:
  for t in [.20,.40,.60,.80]:face(t,body/2,.022,body,.034,metal,depth=.012)
  for f in range(1,FLOORS):face(.5,f*pitch,L-.08,.023,.034,metal,depth=.012)
  face(.5,body*.20,L-.05,1.15*pitch,.035,base,depth=.025)
  face(.5,body*.32,L-.05,.34*pitch,.035,metal,depth=.025)
 elif serviceface:
  for f in range(FLOORS):
   face(.5,(f+.56)*pitch,min(.42,L*.24),.81*pitch,.055,glass,depth=.04)
   face(.5,f*pitch+.025,L-.10,.05,.062,roof,depth=.02)
 else:
  count=max(2,round(L/2.95));bw=(L-.24)/count
  for j in range(count):
   t=(.12+(j+.5)*bw)/L;ww=bw*(.72 if j%2==0 else .57)
   for f in range(FLOORS):
    z=(f+.58)*pitch;hh=.46*pitch
    face(t,z,ww+.10,hh+.10,.035,frame,depth=.04)
    face(t,z,ww,hh,.065,glass,depth=.04)
    face(t,z,.05,hh,.098,white,depth=.025)
    face(t,(f+.32)*pitch,ww+.15,.09,.11,white,depth=.10)
  for j in range(count+1):face((.12+j*bw)/L,body/2,.12,body,.035,white,depth=.04)
  for f in range(1,FLOORS):face(.5,f*pitch,L-.10,.025,.036,metal,depth=.012)
 face(.5,body-.16,L,.32,.06,white,depth=.10)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2))
# Fully contained open rectangular frames: separate supporting posts and four perimeter beams, no filled top.
for u,v,w,d in D['roof_frames_uv']:
 x,y=u*co-v*si,u*si+v*co
 for a in [-w/2,w/2]:
  for b in [-d/2,d/2]:box((x+a*co-b*si,y+a*si+b*co,H-1.72),(.26,.26,1.96),white,theta)
 for b in [-d/2,d/2]:box((x-b*si,y+b*co,H-.72),(w+.30,.30,.32),roof,theta)
 for a in [-w/2,w/2]:box((x+a*co,y+a*si,H-.72),(.30,d-.30,.32),roof,theta)
u,v,w,d=D['roof_core_uv'];x,y=u*co-v*si,u*si+v*co
box((x,y,H-1.45),(w,d,2.50),metal,theta)
box((x,y,H-.10),(w+.10,d+.10,.20),white,theta)
# Narrow service-core slit, attached to a solid supported core.
box((x-d/2*si,y+d/2*co,H-1.40),(.18,.035,2.05),glass,theta)
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('Trizium344 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('Trizium344 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
# Separate photograph-supported building-number mesh, normalized name for future clone hiding.
ei=0;a=r[ei];b=r[(ei+1)%len(r)];dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
cu=bpy.data.curves.new('344 number font','FONT');cu.body='344';cu.size=1.35;cu.align_x='CENTER';cu.extrude=.005;no=bpy.data.objects.new('building-number-label',cu);s.collection.objects.link(no);no.location=(a[0]+dx*.40+nx*.11,a[1]+dy*.40+ny*.11,body*.76);no.rotation_euler=(math.pi/2,0,math.atan2(ny,nx)+math.pi/2);cu.materials.append(service)
for o in bpy.context.selected_objects:o.select_set(False)
no.select_set(True);bpy.context.view_layer.objects.active=no;bpy.ops.object.convert(target='MESH');no=bpy.context.object;no.data.transform(no.matrix_world);no.matrix_world.identity();no.name='building-number-label';no['label_number']='344';no['hide_on_representative_clones']=True;s['clone_hide_node_names']=json.dumps(['building-number-label'])
objs=[o for o in s.objects if o.type=='MESH'];(P/'optimization-proof.json').write_text(json.dumps({'mesh_count':len(objs),'no_decimation':True,'material_batched':True},indent=2))

for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'jamsil-trizium-344.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('Trizium344 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('Trizium344 sun','SUN');lo=bpy.data.objects.new('Trizium344 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('Trizium344 '+name);ob=bpy.data.objects.new('Trizium344 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;inv=ob.rotation_euler.to_matrix().transposed();q=[inv@(o.matrix_world@vv.co-ob.location) for o in objs for vv in o.data.vertices];ca.ortho_scale=max(ca.ortho_scale,2*max(abs(v.y) for v in q)*1.12,2*max(abs(v.x) for v in q)/(850/1100)*1.12);s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':H,'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'jamsil-trizium-344-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
