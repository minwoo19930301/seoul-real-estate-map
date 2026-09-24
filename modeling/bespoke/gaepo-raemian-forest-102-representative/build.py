import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Godeok Gaepo102 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['model_upper_envelope_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['complex_household_discrepancy']=D['complex_household_discrepancy'];s['photo_attribution']=D['photo_attribution'];s['source_attribute_discrepancy']=D['source_attribute_discrepancy'];s['photographed_building_number']='unidentified';s['height_status']=D['height_status'];s['osm_height_m']=D['osm_height_m'];s['floor_source']=D['floor_source'];s['scope_exclusions']=json.dumps(D['scope_exclusions'])
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256'] or ''
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('Gaepo102 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.81,.82,.78));metal=mat('light grey solid wall',(.50,.53,.52),.08,.66);glass=mat('turquoise balcony glazing',(.19,.29,.32),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.45,.47,.46),.12,.58);base=mat('muted ground wall',(.22,.25,.25),.08,.65);service=mat('narrow charcoal service strips',(.22,.25,.26),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['model_upper_envelope_m'];body=H-2.6;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-2.4),white)
# Gaepo-specific thick white grid around blue apertures, dark vertical window banks.
dark=mat('dark grey vertical window banks',(.25,.29,.31));blue=mat('blue glazing',(.15,.29,.39),.32,.3);roles=[]
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.08):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 main=L>6 and ei not in [0,2];roles.append({'edge':ei,'length_m':L,'role':'thick white grid with dark grey vertical banks' if main else 'pale service/endwall','basis':'ownedge classification, photo complex inference'})
 face(.5,body/2,L,body,.012,white,depth=.024);face(.5,pitch*.7,L,1.4*pitch,.04,metal,depth=.08)
 if main:
  count=max(2,round(L/3.6));bay=L/count
  for k in range(count):
   t=(k+.5)/count;ww=bay*.69;isdark=k%4 in [1,2]
   if isdark:face(t,body/2,bay-.12,body,.04,dark,depth=.04)
   for f in range(FLOORS):
    z=(f+.55)*pitch;face(t,z,ww+.16,.62*pitch,.075,dark,depth=.035);face(t,z,ww,.55*pitch,.12,blue,depth=.035)
    face(t,z,.08,.55*pitch,.16,dark,depth=.045);face(t,f*pitch+.28,bay,.56,.13,dark if isdark else white,depth=.10)
   face(k/count+.015,body/2,.34,body,.15,white,depth=.12)
 else:
  if L>3:
   for f in range(FLOORS):
    face(.5,(f+.55)*pitch,.64,.37*pitch,.065,blue,depth=.035)
  for f in range(1,FLOORS):face(.5,f*pitch,L-.05,.018,.029,metal,depth=.01)
 face(.5,body-.2,L,.40,.07,white,depth=.10)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2))
# Long open concrete upper frame; sky remains visible between crossmembers.
u,v,w,dep=D['roof_open_frame_uv'];x,y=u*co-v*si,u*si+v*co
roofang=theta
for uu in [-w/2+.26,0,w/2-.26]:
 for vv in [-dep/2+.26,dep/2-.26]:box((x+uu*co-vv*si,y+uu*si+vv*co,H-1.425),(.52,.52,1.95),white,roofang)
for vv in [-dep/2+.25,dep/2-.25]:box((x-vv*si,y+vv*co,H-.225),(w,.5,.45),white,roofang)
for k in range(11):
 uu=-w/2+.25+k*(w-.5)/10;box((x+uu*co,y+uu*si,H-.225),(.18,dep-1,.45),white,roofang)
(P/'open-roof-proof.json').write_text(json.dumps({'frame_uv':D['roof_open_frame_uv'],'base_m':H-2.4,'top_m':H,'open_clear_height_m':1.95,'continuous_side_beams':True,'crossmembers':11,'no_solid_infill':True,'dimensions_inferred':True},indent=2))
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('Gaepo102 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('Gaepo102 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
objs=[o for o in s.objects if o.type=='MESH'];(P/'optimization-proof.json').write_text(json.dumps({'mesh_count':len(objs),'no_decimation':True,'material_batched':True},indent=2))

for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'gaepo-raemian-forest-102.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('Gaepo102 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('Gaepo102 sun','SUN');lo=bpy.data.objects.new('Gaepo102 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('Gaepo102 '+name);ob=bpy.data.objects.new('Gaepo102 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;inv=ob.rotation_euler.to_matrix().transposed();q=[inv@(o.matrix_world@vv.co-ob.location) for o in objs for vv in o.data.vertices];ca.ortho_scale=max(ca.ortho_scale,2*max(abs(v.y) for v in q)*1.12,2*max(abs(v.x) for v in q)/(850/1100)*1.12);s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':D['register_height_m'],'osm_height_m':D['osm_height_m'],'height_status':D['height_status'],'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'gaepo-raemian-forest-102-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
