import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Godeok Gracium101 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['register_height_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['complex_household_discrepancy']=D['complex_household_discrepancy'];s['photo_attribution']=D['photo_attribution'];s['source_attribute_discrepancy']=D['source_attribute_discrepancy'];s['photographed_building_number']='unidentified';s['scope_exclusions']=json.dumps(D['scope_exclusions'])
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256'] or ''
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('Gracium101 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.82,.84,.83));metal=mat('light grey solid wall',(.43,.46,.47),.08,.66);glass=mat('turquoise balcony glazing',(.19,.31,.39),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.45,.47,.46),.12,.58);base=mat('muted ground wall',(.25,.27,.28),.08,.65);service=mat('narrow charcoal service strips',(.22,.25,.26),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['register_height_m'];body=H-1.8;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-1.6),white)
# V2 photo-directed mass/color hierarchy: wide solid dark service piers, grouped white frames.
charcoal=mat('broad charcoal solid service wall',(.12,.14,.155));roles=[]
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.08):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 main=L>=18;role='grouped window banks and broad dark solid service pier' if main else 'pale solid wall with sparse small service windows'
 roles.append({'edge':ei,'length_m':L,'role':role,'basis':'v2 root reviewed complex photograph proportions; ownedge geometry; exact dimensions inferred'})
 face(.5,body/2,L,body,.015,white,depth=.03)
 face(.5,pitch,L,2*pitch,.045,base,depth=.06)
 if L<4:
  for f in range(1,FLOORS):face(.5,f*pitch,L-.1,.022,.038,metal,depth=.01)
 elif not main:
  # Broad continuous pale/grey surface, not another curtain-wall grid.
  face(.55,body/2,L*.48,body,.038,metal,depth=.035)
  for f in range(FLOORS):
   for t in [.43,.68]:face(t,(f+.58)*pitch,.60,.45*pitch,.075,glass,depth=.045)
   face(.5,f*pitch+.035,L-.15,.035,.06,white,depth=.025)
  for t in [.04,.96]:face(t,body/2,.48,body,.12,white,depth=.12)
 else:
  # Center36% is dark solid wall with a narrow staggered service strip; visual width not measured.
  face(.5,body/2,L*.36,body,.038,charcoal,depth=.055)
  for start,end in [(.045,.295),(.705,.955)]:
   mid=(start+end)/2;bw=(end-start)*L
   face(mid,body/2,bw,body,.055,metal,depth=.05)
   for f in range(FLOORS):
    # A pair of panes grouped by a single strong outer frame, no additional window rows.
    z=(f+.59)*pitch;hh=.61*pitch
    for q in [-.25,.25]:
     t=mid+q*(end-start);ww=bw*.5-.24;face(t,z,ww,hh,.10,glass,depth=.04)
     face(t,z,.052,hh,.15,charcoal,depth=.04)
    face(mid,(f+.13)*pitch,bw,.40,.16,white,depth=.12)
   for t in [start,end]:face(t,body/2,.72,body,.20,white,depth=.16)
   face(mid,body-.28,bw+.72,.56,.20,white,depth=.16)
  for f in range(FLOORS):
   # Spaced small apertures leave the large charcoal pier visibly solid.
   face(.405,(f+.58)*pitch,.72,.46*pitch,.076,glass,depth=.04)
   t=.575+(.015 if f%2 else -.015);z=(f+.57)*pitch
   face(t,z,.82,.49*pitch,.076,glass,depth=.04)
   face(t,(f+.20)*pitch,L*.085,.13,.22,white,depth=.32)
   face(t,(f+.38)*pitch,L*.085,.07,.37,white,depth=.035)
   for q in [-.5,.5]:face(t+q*.085,(f+.30)*pitch,.08,.30*pitch,.22,metal,depth=.32)
 face(.5,body-.14,L,.28,.075,white,depth=.08)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2))
# Source-clipped split upper ends: supported from fullroofdeck104.0 to105.6; center remains lower.
for cap in D['roof_end_caps']:
 ring=cap['ring'];n=len(ring);z0=D['roof_deck_height_m'];z1=H
 mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],white)
 for tr in cap['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],white);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],white)
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('Gracium101 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('Gracium101 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
objs=[o for o in s.objects if o.type=='MESH'];(P/'optimization-proof.json').write_text(json.dumps({'mesh_count':len(objs),'no_decimation':True,'material_batched':True},indent=2))

for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'godeok-gracium-101.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('Gracium101 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('Gracium101 sun','SUN');lo=bpy.data.objects.new('Gracium101 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('Gracium101 '+name);ob=bpy.data.objects.new('Gracium101 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;inv=ob.rotation_euler.to_matrix().transposed();q=[inv@(o.matrix_world@vv.co-ob.location) for o in objs for vv in o.data.vertices];ca.ortho_scale=max(ca.ortho_scale,2*max(abs(v.y) for v in q)*1.12,2*max(abs(v.x) for v in q)/(850/1100)*1.12);s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':H,'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'godeok-gracium-101-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
