import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Godeok Arteon323 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['model_upper_envelope_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['complex_household_discrepancy']=D['complex_household_discrepancy'];s['photo_attribution']=D['photo_attribution'];s['source_attribute_discrepancy']=D['source_attribute_discrepancy'];s['photographed_building_number']='unidentified';s['height_status']=D['height_status'];s['osm_height_m']=D['osm_height_m'];s['floor_source']=D['floor_source'];s['scope_exclusions']=json.dumps(D['scope_exclusions'])
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256'] or ''
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('Arteon323 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.81,.82,.78));metal=mat('light grey solid wall',(.50,.53,.52),.08,.66);glass=mat('turquoise balcony glazing',(.19,.29,.32),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.45,.47,.46),.12,.58);base=mat('muted ground wall',(.22,.25,.25),.08,.65);service=mat('narrow charcoal service strips',(.22,.25,.26),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['model_upper_envelope_m'];body=H-1.4;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-1.2),white)
# Arteon photo: grouped dark glazing between pale solid service piers.
charcoal=mat('recessed dark balcony surrounds',(.13,.18,.20));roles=[]
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.08):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 serviceface=L>8 and abs(dx)<abs(dy)*.65
 role='broad pale service wall and sparse narrow apertures' if serviceface else ('white framed recessed glazing module' if L>=3.4 else 'solid short return')
 roles.append({'edge':ei,'length_m':L,'role':role,'basis':'own edge width and direction inferred; not numbered-photo orientation'})
 if L<.5:continue
 face(.5,body/2,L,body,.012,white,depth=.024)
 face(.5,pitch,L,2*pitch,.04,base,depth=.08)
 if serviceface:
  for f in range(FLOORS):
   for t in [.32,.68]:face(t,(f+.55)*pitch,.52,.41*pitch,.07,charcoal,depth=.04)
   face(.5,f*pitch+.02,L-.08,.018,.03,metal,depth=.01)
 elif L>=3.4:
  bw=L*.70;face(.5,body/2,bw,body,.05,charcoal,depth=.06)
  cols=max(2,round(bw/1.35));bay=bw/cols
  for f in range(FLOORS):
   z=(f+.55)*pitch
   for k in range(cols):
    t=.5+((k+.5)*bay-bw/2)/L;face(t,z,bay-.15,.62*pitch,.095,glass,depth=.045)
   face(.5,f*pitch+.24,bw,.48,.13,metal,depth=.10)
  for k in range(cols+1):face(.5+(k*bay-bw/2)/L,body/2,.14 if k not in [0,cols] else .36,body,.18,white,depth=.12)
  face(.5,body-.25,bw+.36,.5,.18,white,depth=.12)
 face(.5,body-.14,L,.28,.06,white,depth=.08)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2))
# Unseen rooftop: low contained equipment only, no entrance gate or speculative crown.
u,v,w,d=D['roof_core_uv'];x,y=u*co-v*si,u*si+v*co
box((x,y,H-.70),(w,d,1.0),metal,theta)
box((x,y,H-.10),(w+.10,d+.10,.20),white,theta)
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('Arteon323 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('Arteon323 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
objs=[o for o in s.objects if o.type=='MESH'];(P/'optimization-proof.json').write_text(json.dumps({'mesh_count':len(objs),'no_decimation':True,'material_batched':True},indent=2))

for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'godeok-arteon-323.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('Arteon323 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('Arteon323 sun','SUN');lo=bpy.data.objects.new('Arteon323 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('Arteon323 '+name);ob=bpy.data.objects.new('Arteon323 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;inv=ob.rotation_euler.to_matrix().transposed();q=[inv@(o.matrix_world@vv.co-ob.location) for o in objs for vv in o.data.vertices];ca.ortho_scale=max(ca.ortho_scale,2*max(abs(v.y) for v in q)*1.12,2*max(abs(v.x) for v in q)/(850/1100)*1.12);s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':D['register_height_m'],'osm_height_m':D['osm_height_m'],'height_status':D['height_status'],'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'godeok-arteon-323-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
