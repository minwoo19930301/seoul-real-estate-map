import bpy,json,math,pathlib
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());N=D['tower'];old=bpy.context.scene
scene=bpy.data.scenes.new('Acro'+N+'_source_parts_corrected');bpy.context.window.scene=scene
scene['anchor_lonlat']=D['anchor_lonlat'];scene['height_policy']=D['height_policy'];scene['reference_scope']=D['reference_scope'];scene['inferredFromAssetIds']='bespoke-acro-riverpark-109';scene['footprint_id']=D['parent']['id']
def mat(n,c,metal=0):
 m=bpy.data.materials.new(N+' '+n);m.diffuse_color=(*c,1);m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*c,1);b.inputs['Roughness'].default_value=.4 if metal else .73;b.inputs['Metallic'].default_value=metal;return m
white=mat('Warm pale planes',(.80,.81,.78));dark=mat('Charcoal lower storeys',(.10,.13,.14));glass=mat('Blue grey glazing',(.12,.25,.29),.35);frame=mat('Silver thin mullions',(.47,.53,.52),.2);roof=mat('Roof equipment',(.38,.40,.39))
objs=[];group={};rid=''
def mesh(n,vs,fs,m):
 key=(rid,m)
 if key not in group:group[key]=[[],[]]
 v,f=group[key];off=len(v);v.extend(vs);f.extend(tuple(off+i for i in face) for face in fs)
def box(n,center,size,m,ang=0):
 x,y,z=center;a,b,c=[s/2 for s in size];vs=[]
 for dz in [-c,c]:
  for dx,dy in [(-a,-b),(a,-b),(a,b),(-a,b)]:vs.append((x+dx*math.cos(ang)-dy*math.sin(ang),y+dx*math.sin(ang)+dy*math.cos(ang),max(.01,z+dz)))
 mesh(n,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
try:
 for R in D['regions']:
  rid=R['id'];H=R['height_m'];deck=H-.30;floor=deck/R['floors']
  # Constrained triangle caps preserve concavity and holes with no fan bridges.
  for tri in R['triangles']:
   area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(tri,tri[1:]+tri[:1]));tri=tri if area>0 else list(reversed(tri))
   mesh('source region bottom and roof',[(x,y,z) for z in [0,deck] for x,y in tri],[(2,1,0),(3,4,5)],white)
  for E in R['edges']:
   a,b=E['a'],E['b'];nx,ny=E['normal'];dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);low=E['adjacent_height'];
   mesh('exact region wall',[(a[0],a[1],0),(b[0],b[1],0),(b[0],b[1],deck),(a[0],a[1],deck)],[(0,1,2,3)],white)
   if low>=H-.01:continue
   def face(n,t,z,w,h,dep,m):
    bottom=max(low,z-h/2,0);top=min(deck,z+h/2)
    if top<=bottom or w<=0:return
    box(n,(a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,(bottom+top)/2),(w,.13,top-bottom),m,ang)
   if low<floor*3:face('dark base',.5,floor*1.5,L,floor*3,.08,dark)
   if L>2.3:
    count=max(1,int(L/3.2));bay=L/count;pale=((a[0]+b[0])*.82+(a[1]+b[1])*.57)<0
    for j in range(count):
     t=(j+.5)/count;w=bay*((.70 if j%3!=2 else .43) if pale else (.88 if j%3!=2 else .66))
     if not pale and j<count-1:face('vertical glazing',t,(deck+floor*3)/2,w,deck-floor*3,.12,glass)
     for f in range(R['floors']):
      z=(f+.5)*floor
      face('window',t,z,w,floor*(.70 if pale else .78),.23,glass)
      face('pale slab',t,z-floor*.5,w+.12,.28,.36,white)
      if not pale:face('dark spandrel',t,z-floor*.39,w,.34,.28,dark)
      face('thin transom',t,z-floor*.30,w,.07,.32,frame)
      face('offset mullion',t-.13/count,z,.06,floor*.76,.33,frame)
      if j%3==0:face('balcony sill',t,z-floor*.42,w+.14,.16,.53,white)
     face('pale pier',j/count+.035,(deck+floor*3)/2,.28,deck-floor*3,.40,white)
   # Parapet sits over the region's own deck; total maximum is source region H.
   box('region parapet',((a[0]+b[0])/2-nx*.09,(a[1]+b[1])/2-ny*.09,H-.15),(L,.16,.30),white,ang)
  # Compact equipment is sunk into roof envelope, never above the region height.
  if min(R['roof_size'])>.5:
   box('region roof plant',(*R['roof_center'],H-.40),(*R['roof_size'],.70),roof,R['roof_axis'])
   box('plant coping',(*R['roof_center'],H-.045),(*R['roof_size'],.09),white,R['roof_axis'])
 for (region,material),(vs,fs) in group.items():
  me=bpy.data.meshes.new(N+' '+region+' '+material.name);me.from_pydata(vs,[],fs);me.update();ob=bpy.data.objects.new(me.name,me);scene.collection.objects.link(ob);me.materials.append(material);ob['region_id']=region;ob['height_m']=next(r['height_m'] for r in D['regions'] if r['id']==region);objs.append(ob)
 for ob in bpy.context.selected_objects:ob.select_set(False)
 for ob in objs:ob.select_set(True)
 bpy.context.view_layer.objects.active=objs[0]
 bpy.ops.export_scene.gltf(filepath=str(P/(D['assetId']+'.glb')),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
 scene.render.engine='CYCLES';scene.cycles.samples=24;scene.render.resolution_x=900;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
 scene.world=bpy.data.worlds.new('Acro corrected review');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.79,.82,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
 ld=bpy.data.lights.new('Acro sun','SUN');lo=bpy.data.objects.new('Acro sun',ld);scene.collection.objects.link(lo);lo.rotation_euler=(.4,-.4,-.6);ld.energy=2.4;scene.view_settings.view_transform='AgX';H=D['height_m']
 for name,loc in [('front',(125,-180,95)),('opposite',(-125,180,95)),('side',(180,110,90)),('roof',(110,-120,240))]:
  ca=bpy.data.cameras.new(N+' '+name);co=bpy.data.objects.new(N+' '+name,ca);scene.collection.objects.link(co);co.location=loc;co.rotation_euler=(Vector((0,0,H*.49))-co.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=max(H*1.22,105);scene.camera=co;scene.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
 bpy.data.libraries.write(str(P/(D['assetId']+'-authored.blend')),{scene},fake_user=True,compress=True)
 report={'tower':N,'scene':scene.name,'mesh_objects':len(objs),'regions':[{'id':r['id'],'floors':r['floors'],'height_m':r['height_m']} for r in D['regions']],'max_height_m':max(v.co.z for o in objs for v in o.data.vertices),'previous_scene_preserved':old.name,'no_parent_full_height_solid':True}
 (P/'mcp-authoring-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:bpy.context.window.scene=old
