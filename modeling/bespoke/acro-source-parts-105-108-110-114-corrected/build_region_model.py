import bpy,math,json,pathlib,hashlib
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());T=D['tower'];old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes}
s=bpy.data.scenes.new('Acro '+T+' source regions corrected');bpy.context.window.scene=s
s['reference_scope']=D['reference_scope'];s['inferredFromAssetIds']='bespoke-acro-riverpark-109';s['source_data_sha256']=hashlib.sha256((P/'source-data.json').read_bytes()).hexdigest();s['anchor_lonlat']=D['anchor_lonlat'];s['footprint_id']=D['footprint_id'];s['additional_footprint_ids']=json.dumps(D['additional_footprint_ids']);s['height_basis']='OSM parent metre estimate; child heights floor-derived; not legal heights';s['source_regions']=json.dumps([{'id':r['region_id'],'height':r['height_m'],'floors':r['floor_count']} for r in D['regions']])
def mat(n,c,metal=0):
 m=bpy.data.materials.new(T+' '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=.38 if metal else .73;return m
materials={'body':mat('pale source region mass',(.8,.81,.78)),'white':mat('warm pale architectural planes',(.8,.81,.78)),'dark':mat('charcoal lower storeys',(.10,.13,.14)),'glass':mat('blue grey glazing',(.12,.25,.29),.35),'frame':mat('silver mullions',(.47,.53,.52),.2)}
meshes=[];stats=[]
for idx,r in enumerate(D['regions']):
 prefix='R%02d '%idx;H=r['height_m'];deck=r['roof_deck_z'];F=r['floor_count'];pitch=deck/F;groups={k:[[],[]] for k in materials}
 def add(key,vs,fs):
  v,f=groups[key];off=len(v);v.extend(vs);f.extend([tuple(off+i for i in face) for face in fs])
 def box(key,center,size,ang=0,zlo=0,zhi=H):
  x,y,z=center;a,b,c=[q/2 for q in size];bottom=max(zlo,z-c);top=min(zhi,z+c)
  if top<=bottom+1e-6:return
  co,si=math.cos(ang),math.sin(ang);vs=[(x+u*co-v*si,y+u*si+v*co,h) for h in [bottom,top] for u,v in [(-a,-b),(a,-b),(a,b),(-a,b)]]
  add(key,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
 for tri in r['cap_triangles_m']:
  area=sum(tri[i][0]*tri[(i+1)%3][1]-tri[(i+1)%3][0]*tri[i][1] for i in range(3));q=tri if area>0 else tri[::-1]
  add('body',[(x,y,deck) for x,y in q],[(0,1,2)]);add('body',[(x,y,0) for x,y in q],[(2,1,0)])
 for w in r['exposed_walls']:
  a,b=w['a'],w['b'];lo=w['bottom'];nx,ny=w['normal'];dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx)
  # Wall winding outward, with only upper exposed portion at shared boundaries.
  vs=[(*a,lo),(*b,lo),(*b,deck),(*a,deck)];normal=(dy,-dx)
  add('body',vs,[(0,1,2,3)] if normal[0]*nx+normal[1]*ny>0 else [(3,2,1,0)])
  facade_lo=w['neighbor_height'] if w['neighbor_height'] else 0
  def face(key,t,z,width,h,dep):box(key,(a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(width,.12,h),ang,facade_lo,deck)
  if facade_lo==0:face('dark',.5,min(pitch*3,deck)/2,L,min(pitch*3,deck),.08)
  if L<2.3:continue
  count=max(1,int(L/3.2));bay=L/count;broad=L>2.8;pale=((a[0]+b[0])*.82+(a[1]+b[1])*.57)<0
  for j in range(count):
   t=(j+.5)/count;width=bay*((.70 if j%3!=2 else .43) if pale else ((.88 if j%3!=2 else .66) if broad else .42));bottom=max(facade_lo,pitch*3)
   if broad and not pale and j<count-1 and deck>bottom:face('glass',t,(deck+bottom)/2,width,deck-bottom,.12)
   for f in range(F):
    z=(f+.5)*pitch
    if z+pitch*.4<=facade_lo:continue
    face('glass',t,z,width,pitch*(.70 if pale else .78),.23)
    if broad:
     face('white',t,z-pitch*.5,width+.12,.30,.48)
     if not pale:face('dark',t,z-pitch*.39,width,.36,.30)
     face('frame',t,z-pitch*.30,width,.075,.34);face('frame',t-.13/count,z,.065,pitch*.78,.35)
     if j%3==0:face('white',t,z-pitch*.42,width+.18,.17,.53);face('white',t-width/(2*L),z,.19,pitch*.80,.53)
   if broad and deck>bottom:face('white',j/count+.035,(deck+bottom)/2,.32,deck-bottom,.53)
 # Inward-clipped roof coping, no guessed machinery or full-parent high solid.
 for tri in r['parapet_triangles_m']:
  area=sum(tri[i][0]*tri[(i+1)%3][1]-tri[(i+1)%3][0]*tri[i][1] for i in range(3));q=tri if area>0 else tri[::-1];add('white',[(x,y,H) for x,y in q],[(0,1,2)])
 for ring in r['parapet_rings_m']:
  for a,b in zip(ring,ring[1:]+ring[:1]):add('white',[(*a,deck),(*b,deck),(*b,H),(*a,H)],[(0,1,2,3)])
 for key,(vs,fs) in groups.items():
  if not vs:continue
  me=bpy.data.meshes.new(prefix+key);me.from_pydata(vs,[],fs);me.update();o=bpy.data.objects.new(T+' '+prefix+key,me);s.collection.objects.link(o);me.materials.append(materials[key]);o['region_id']=r['region_id'];o['region_height_m']=H;o['region_floors']=F;o['height_basis']=r['height_basis'];meshes.append(o)
 stats.append({'region_id':r['region_id'],'height_m':H,'floor_count':F,'roof_deck_z':deck,'cap_triangle_count':len(r['cap_triangles_m']),'exposed_wall_count':len(r['exposed_walls']),'xy_area_m2':r['area_m2']})
for o in bpy.context.selected_objects:o.select_set(False)
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=meshes[0]
bpy.ops.export_scene.gltf(filepath=str(P/('bespoke-acro-riverpark-'+T+'.glb')),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=16;s.render.resolution_x=900;s.render.resolution_y=1000;s.render.resolution_percentage=100
s.world=bpy.data.worlds.new(T+' region review world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.79,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.7
ld=bpy.data.lights.new(T+' sun','SUN');lo=bpy.data.objects.new(T+' sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.4,-.4,-.6);ld.energy=2.4;s.view_settings.view_transform='AgX';H=D['parent_height_m']
for n,loc in [('front',(125,-180,95)),('opposite',(-125,180,95)),('side',(180,110,90)),('roof',(110,-120,240))]:
 ca=bpy.data.cameras.new(T+' '+n);o=bpy.data.objects.new(T+' '+n,ca);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,H*.49))-o.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=max(H*1.2,105);s.camera=o;s.render.filepath=str(P/(n+'.png'));bpy.ops.render.render(write_still=True)
vs=[v.co for o in meshes for v in o.data.vertices];assert min(v.z for v in vs)==0 and abs(max(v.z for v in vs)-H)<1e-4
bpy.data.libraries.write(str(P/('bespoke-acro-riverpark-'+T+'-authored.blend')),{s},fake_user=True,compress=True)
report={'tower':T,'actual_mcp_port':9878,'source_sha256':hashlib.sha256((P/'source-data.json').read_bytes()).hexdigest(),'base':min(v.z for v in vs),'max_height':max(v.z for v in vs),'finite':all(math.isfinite(c) for v in vs for c in v),'mesh_objects':len(meshes),'regions':stats,'images':0,'initial_scene':old.name};(P/'validation.json').write_text(json.dumps(report,indent=2))
bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after
(P/'scene-preservation.json').write_text(json.dumps({'same_scene_object_lists':True,'initial_scene':old.name,'before_scene_names':list(before),'after_scene_names':list(after)},indent=2));print(json.dumps(report))
