import bpy,math,json,pathlib
from mathutils import Vector
P=pathlib.Path(__file__).parent
D=json.loads((P/'source-data.json').read_text())[0]
old=bpy.context.scene
scene=bpy.data.scenes.new('Acro109_representative_revised');bpy.context.window.scene=scene
scene['prior_scene_preserved']=old.name
scene['reference_scope']='Complex-level official photo inference; individual 109 photograph identity unverified.'
scene['height_basis']='132m OpenStreetMap value, not verified legal building-register height'
def mat(n,c,metal=0):
 m=bpy.data.materials.new(n);m.diffuse_color=(*c,1);m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*c,1);b.inputs['Roughness'].default_value=.38 if metal else .73;b.inputs['Metallic'].default_value=metal;return m
white=mat('Warm pale architectural planes',(.8,.81,.78));dark=mat('Charcoal stone lower storeys',(.10,.13,.14));glass=mat('Blue grey glazing',(.12,.25,.29),.35);frame=mat('Silver glazing mullions',(.47,.53,.52),.2);roof=mat('Roof equipment',(.38,.40,.39))
objs=[]
def mesh(n,vs,fs,m):
 me=bpy.data.meshes.new(n);me.from_pydata(vs,[],fs);me.update();o=bpy.data.objects.new(n,me);scene.collection.objects.link(o);o.data.materials.append(m);objs.append(o);return o
def box(n,center,size,m,ang=0):
 x,y,z=center;a,b,c=[s/2 for s in size];vs=[]
 for dz in [-c,c]:
  for dx,dy in [(-a,-b),(a,-b),(a,b),(-a,b)]:vs.append((x+dx*math.cos(ang)-dy*math.sin(ang),y+dx*math.sin(ang)+dy*math.cos(ang),max(0,z+dz)))
 return mesh(n,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
r=D['ring_m'];N=len(r);H=D['height_m'];floor=H/38
# Exact source footprint, no rectangular replacement.
vs=[(x,y,z) for z in [0,H-1.1] for x,y in r]
o=mesh('109 exact OSM footprint pale mass',vs,[tuple(reversed(range(N))),tuple(range(N,N*2))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)],white)
o['footprint_id']=D['id'];o['anchor_lonlat']=D['anchor_lonlat'];o['floors']=38;o['height_source']='OpenStreetMap';o['source_ring_m']=json.dumps(r)
area=sum(r[i][0]*r[(i+1)%N][1]-r[(i+1)%N][0]*r[i][1] for i in range(N))
for i,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(n,t,z,w,h,dep,m):return box(n,(a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,.16,h),m,ang)
 face('109 charcoal 3-storey plinth',.5,floor*1.5,L,floor*3,.10,dark)
 if L<2.3:continue
 count=max(1,int(L/3.2));bay=L/count
 # Court-oriented broad southern planes carry asymmetric continuous glazing fields;
 # end/return walls carry narrow slots with larger pale planes.
 broad=L>2.8
 pale_wing=((a[0]+b[0])*.82+(a[1]+b[1])*.57)<0
 for j in range(count):
  t=(j+.5)/count
  w=bay*((.70 if j%3!=2 else .43) if pale_wing else ((.88 if j%3!=2 else .66) if broad else .42))
  if broad and not pale_wing and j<count-1:face('109 full-height glazed vertical field',t,(H+floor*3)/2,w,H-floor*3-2,.12,glass)
  for f in range(38):
   z=(f+.5)*floor
   face('109 window broad' if broad else '109 recessed window slot',t,z,w,floor*(.70 if pale_wing else .78),.23,glass)
   if broad:
    face('109 horizontal pale slab band',t,z-floor*.5,w+.12,.30,.48,white)
    if not pale_wing:face('109 dark recessed spandrel',t,z-floor*.39,w,.36,.30,dark)
    face('109 horizontal silver transom',t,z-floor*.30,w,.075,.34,frame)
    face('109 window offset mullion',t-.13/count,z,.065,floor*.78,.35,frame)
    if j%3==0:
     face('109 projecting balcony sill',t,z-floor*.42,w+.18,.17,.74,white)
     face('109 balcony side return',t-w/(2*L),z,.19,floor*.80,.65,white)
  if broad:face('109 projecting pale pier',j/count+.035,(H+floor*3)/2,.32,H-floor*3,.65,white)
 face('109 roof parapet',.5,H-.55,L,1.1,.14,white)
# Low restrained roof cap inferred from complex photo; no speculative bridge/canopy.
box('109 compact roof plant cap',(-1,1,H-1.10),(8,6,1.9),roof,.48)
box('109 pale roof cap coping',(-1,1,H-.11),(8.6,6.6,.22),white,.48)
# Join by architectural material while retaining editable component names in authored blend.
for obj in bpy.context.selected_objects:obj.select_set(False)
for obj in objs:obj.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
bpy.ops.export_scene.gltf(filepath=str(P/'acro-riverpark-109.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=900;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Acro review world');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.79,.82,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
ld=bpy.data.lights.new('Acro sun','SUN');lo=bpy.data.objects.new('Acro sun',ld);scene.collection.objects.link(lo);lo.rotation_euler=(.4,-.4,-.6);ld.energy=2.4
scene.view_settings.view_transform='AgX'
for name,loc in [('court',(125,-180,95)),('opposite',(-125,180,95)),('side',(180,110,90)),('roof',(110,-120,240))]:
 ca=bpy.data.cameras.new('109 '+name);co=bpy.data.objects.new('109 '+name,ca);scene.collection.objects.link(co);co.location=loc;co.rotation_euler=(Vector((0,0,H*.49))-co.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=155;scene.camera=co
 scene.render.filepath=str(P/('109-'+name+'.png'));bpy.ops.render.render(write_still=True)
# Save new copy only, preserve original scene and original on-disk file.
bpy.data.libraries.write(str(P/'acro-riverpark-109-authored.blend'),{scene},fake_user=True,compress=True)
report={'tower':'109','floors':38,'height_m':H,'height_basis':'OpenStreetMap; not legal register','footprint_id':D['id'],'ring_vertex_count':N,'anchor_lonlat':D['anchor_lonlat'],'mesh_objects':len(objs),'reference_scope':scene['reference_scope'],'original_scene_preserved':old.name,'views':['court','opposite','side','roof']}
(P/'109-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
