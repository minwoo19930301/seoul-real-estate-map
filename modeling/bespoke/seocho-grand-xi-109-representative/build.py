import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Godeok GrandXi109 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['model_upper_envelope_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['complex_household_discrepancy']=D['complex_household_discrepancy'];s['photo_attribution']=D['photo_attribution'];s['source_attribute_discrepancy']=D['source_attribute_discrepancy'];s['photographed_building_number']='109 visible on central narrow tower; compass inferred';s['height_status']=D['height_status'];s['osm_height_m']=D['osm_height_m'];s['floor_source']=D['floor_source'];s['scope_exclusions']=json.dumps(D['scope_exclusions'])
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256'] or ''
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('GrandXi109 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.81,.82,.78));metal=mat('light grey solid wall',(.50,.53,.52),.08,.66);glass=mat('turquoise balcony glazing',(.19,.29,.32),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.45,.47,.46),.12,.58);base=mat('muted ground wall',(.22,.25,.25),.08,.65);service=mat('narrow charcoal service strips',(.22,.25,.26),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['model_upper_envelope_m'];body=H-3.6;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-3.4),white)
# Photo109 specific charcoal end and sharp pale edges, two bright window banks.
charcoal=mat('109 charcoal solid endwall',(.14,.16,.18));stone=mat('grey stone lower storeys',(.30,.32,.32));roles=[]
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.08):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 darkend=ei==0;main=L>15
 roles.append({'edge':ei,'length_m':L,'role':'109photo charcoal end wall' if darkend else ('paired bright glazing banks with staggered projecting slabs' if main else 'pale service face'),'orientation':'inferred exactcompass'})
 face(.5,body/2,L,body,.012,charcoal if darkend else white,depth=.024)
 face(.5,pitch*2,L,pitch*4,.04,stone,depth=.08)
 if darkend:
  for t in [.03,.97]:face(t,body/2,.25,body,.13,white,depth=.12)
  for t in [.38,.66]:face(t,body/2,.065,body,.045,metal,depth=.025)
 elif main:
  face(.5,body/2,L*.10,body,.035,metal,depth=.04)
  for lo,hi in [(.04,.43),(.57,.96)]:
   mid=(lo+hi)/2;bw=(hi-lo)*L
   for f in range(FLOORS):
    z=(f+.56)*pitch;face(mid,z,bw-.25,.65*pitch,.085,glass,depth=.035)
    for delta in [-.28,0,.28]:face(mid+delta*bw/L,z,.065,.65*pitch,.145,white,depth=.045)
    face(mid,f*pitch+.19,bw,.38,.16,white,depth=.12)
   for t in [lo,hi]:face(t,body/2,.34,body,.155,white,depth=.12)
  for f in range(4,26,3):
   t=.15 if (f//3)%2 else .23;ww=min(3.5,L*.19);z=f*pitch+.23
   face(t,z,ww,.34,.265,white,depth=.35)
   face(t,z+.55,ww,.70,.32,glass,depth=.05)
   for delta in [-1,1]:face(t+delta*(ww-.12)/2/L,z+.50,.24,.92,.265,white,depth=.35)
   face(t,z+.55,ww,.07,.395,metal,depth=.06)
   for delta in [-.46,0,.46]:face(t+delta*ww/L,z+.30,.065,.60,.395,metal,depth=.045)
 else:
  for f in range(FLOORS):face(.5,(f+.55)*pitch,min(.7,L*.15),.36*pitch,.065,glass,depth=.04)
 face(.5,body-.17,L,.34,.07,white,depth=.10)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2))
# Higher source-shaped charcoal end crown, source-contained instead of oversized equipment box.
q=D['raised_end_region'];rr=q['ring'];n=len(rr);mesh([(x,y,z) for z in [q['base_m'],q['top_m']] for x,y in rr],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],charcoal)
for tr in q['triangles']:mesh([(x,y,q['top_m']) for x,y in tr],[(0,1,2)],charcoal)
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('GrandXi109 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('GrandXi109 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
objs=[o for o in s.objects if o.type=='MESH'];(P/'optimization-proof.json').write_text(json.dumps({'mesh_count':len(objs),'no_decimation':True,'material_batched':True},indent=2))

for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'seocho-grand-xi-109.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('GrandXi109 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('GrandXi109 sun','SUN');lo=bpy.data.objects.new('GrandXi109 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('GrandXi109 '+name);ob=bpy.data.objects.new('GrandXi109 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;inv=ob.rotation_euler.to_matrix().transposed();q=[inv@(o.matrix_world@vv.co-ob.location) for o in objs for vv in o.data.vertices];ca.ortho_scale=max(ca.ortho_scale,2*max(abs(v.y) for v in q)*1.12,2*max(abs(v.x) for v in q)/(850/1100)*1.12);s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':D['register_height_m'],'osm_height_m':D['osm_height_m'],'height_status':D['height_status'],'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'seocho-grand-xi-109-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
