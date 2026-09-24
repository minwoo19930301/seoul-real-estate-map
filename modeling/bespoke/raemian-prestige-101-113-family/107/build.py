import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());old=bpy.context.scene;scene=bpy.data.scenes.new('Raemian_Prestige_107_reviewed_family');bpy.context.window.scene=scene
H=D['official_height_m'];deck=(H-0.9);facade_top=(H-1.2);step=facade_top/D['floors'];base=step*3
scene['anchor_lonlat']=D['anchor_lonlat'];scene['footprint_id']=D['footprint_id'];scene['register_id']=D['register_id'];scene['official_height_m']=H;scene['osm_height_m']=D['osm_height_m'];scene['reference_scope']=D['reference_scope'];scene['height_policy']=D['height_policy'];scene['supersedes']='fallback-prestige-107';scene['inferredFromAssetIds']='bespoke-raemian-prestige-126';scene['ancestor_glb_sha256']=D['ancestor_glb_sha256'];scene['uniform_height_assumption']=True
def material(name,color,rough=.65,metal=0):
 m=bpy.data.materials.new('Prestige '+name);m.diffuse_color=(*color,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;return m
ivory=material('warm ivory rendered wall',(.78,.725,.625));taupe=material('wide taupe pilasters',(.48,.415,.335));trim=material('pale limestone band',(.87,.835,.74));stone=material('dark brown grey stone base',(.235,.23,.205));glass=material('recessed blue green window',(.045,.105,.125),.43,.12);glazing_alt=material('muted green window pair',(.075,.145,.155),.46,.10);frame=material('dark bronze thin window frame',(.065,.07,.065),.62,.08);gold=material('cream gold crown coping',(.76,.67,.44),.55,.12)
groups={}
def geo(label,vertices,faces,mat):
 if mat not in groups:groups[mat]=[[],[]]
 vs,fs=groups[mat];off=len(vs);vs.extend(vertices);fs.extend(tuple(off+i for i in f) for f in faces)
def prism(label,center,size,mat,angle=0):
 x,y,z=center;w,t,h=size;v=[]
 for zz in [z-h/2,z+h/2]:
  for xx,yy in [(-w/2,-t/2),(w/2,-t/2),(w/2,t/2),(-w/2,t/2)]:v.append((x+xx*math.cos(angle)-yy*math.sin(angle),y+xx*math.sin(angle)+yy*math.cos(angle),max(.01,min(H,zz))))
 geo(label,v,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat)
try:
 for tri in D['triangles_m']:
  a=sum(x[0]*y[1]-y[0]*x[1] for x,y in zip(tri,tri[1:]+tri[:1]));t=tri if a>0 else list(reversed(tri));geo('constrained source caps',[(x,y,z) for z in [0,deck] for x,y in t],[(2,1,0),(3,4,5)],ivory)
 for ring_index,r in enumerate(D['rings_m']):
  area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
  for index,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
   dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy);angle=math.atan2(dy,dx);nx,ny=(dy/length,-dx/length) if area>0 else (-dy/length,dx/length)
   if ring_index:nx,ny=-nx,-ny
   geo('exact full concave footprint wall',[(a[0],a[1],0),(b[0],b[1],0),(b[0],b[1],deck),(a[0],a[1],deck)],[(0,1,2,3)],ivory)
   def panel(label,t,z,w,h,depth,mat,thick=.10):prism(label,(a[0]+dx*t+nx*depth,a[1]+dy*t+ny*depth,z),(w,thick,h),mat,angle)
   # Three-storey stone base, substantial cornice above, observed on both photographs.
   panel('stone ground storeys',.5,base/2,length,base,.075,stone)
   panel('base transition lower cornice',.5,base-.12,length+.15,.22,.26,taupe,.23)
   panel('base transition pale cap',.5,base+.13,length+.18,.20,.28,trim,.27)
   # V2 photo reading: broad SOLID wall banks, small grouped punched openings.
   # No per-floor bright string courses or repeated projecting heads.
   broad=length>6.5
   blank_return=length<5.0
   if blank_return:
    panel('blank beige vertical return',.5,(base+facade_top)/2,length,facade_top-base,.08,taupe if index%2 else ivory,.12)
   else:
    margin=.72 if length>20 else (.95 if index==0 else .62)
    usable=length-2*margin
    weights=[1.06,.82,1.26,.82,1.06] if length>20 else ([1.16,.82] if length>8 else [1.0])
    total=sum(weights);cursor=margin
    for j,weight in enumerate(weights):
     bank=usable*weight/total;t=(cursor+bank/2)/length;cursor+=bank
     taupe_bank=(j%2==1) or (index in [0,2] and j==0)
     # Flat colored bank contains substantial matching spandrels above/below windows.
     field_width=bank*.88
     if taupe_bank:panel('wide continuous taupe wall bank',t,(base+facade_top)/2,field_width,facade_top-base,.045,taupe,.065)
     narrow=(j%2==1);opening=bank*(.48 if narrow else .61);gap=.20
     if opening>1.7:
      left=(opening-gap)*(.55 if j%2==0 else .45);right=opening-gap-left
      pair_offsets=[(-(opening-left)/2,left),((opening-right)/2,right)]
     else:pair_offsets=[(0,min(opening,1.30))]
     for f in range(D['floors']):
      z=(f+.54)*step;wh=step*(.46 if narrow else .52)
      for k,(off,w) in enumerate(pair_offsets):
       u=t+off/length
       panel('dark punched opening recess',u,z,w+.10,wh+.10,.099,frame,.055)
       panel('inset dark glazing',u,z,w,wh,.135,glass if (f+j+k)%5 else glazing_alt,.018)
       # Shallow low-contrast sill only; broad spandrel remains solid wall.
       panel('restrained recessed sill',u,z-wh/2-.055,w+.10,.055,.135,taupe if taupe_bank else ivory,.06)
       if w>1.35:panel('dark central sash',u+.02/length,z,.035,wh,.152,frame,.027)
   # The warm cream crown is continuous on source outline, with shallow gold coping.
   panel('upper ivory crown frieze',.5,(H-1.07),length,.28,.10,trim,.14)
   panel('recessed parapet warm wall',.5,(H-0.53),length,.70,-.12,ivory,.20)
   panel('gold cream top coping',.5,(H-0.08),length+.04,.16,-.10,gold,.31)
   if broad:
    for t in [.025,.975]:
     panel('small crown cream block',t,(H-0.35),.32,.66,.035,trim,.20)
     panel('small gold cream crown accent',t,(H-0.06),.35,.12,.035,gold,.21)
 # Source-contained compact plant block, subordinate to crown; dimensions are inferred.
 center=D['roof_center'];size=D['roof_size'];prism('low roof plant housing',(*center,(H-0.65)),(*size,.50),taupe)
 prism('plant cream coping',(*center,(H-0.36)),(*size,.08),trim)
 objects=[]
 for mat,(vs,fs) in groups.items():
  me=bpy.data.meshes.new(mat.name);me.from_pydata(vs,[],fs);me.update();o=bpy.data.objects.new(mat.name,me);scene.collection.objects.link(o);me.materials.append(mat);objects.append(o)
 for o in bpy.context.selected_objects:o.select_set(False)
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
 bpy.ops.export_scene.gltf(filepath=str(P/(D['assetId']+'.glb')),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
 scene.render.engine='CYCLES';scene.cycles.samples=32;scene.render.resolution_x=900;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
 scene.world=bpy.data.worlds.new('Prestige review daylight');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.79,.82,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
 sun=bpy.data.lights.new('Prestige sun','SUN');ob=bpy.data.objects.new('Prestige sun',sun);scene.collection.objects.link(ob);sun.energy=2.3;ob.rotation_euler=(.4,-.4,-.65)
 for name,loc in [('front',(85,-145,73)),('opposite',(-85,145,73)),('side',(150,75,75)),('roof',(80,-100,190))]:
  ca=bpy.data.cameras.new('Prestige '+name);co=bpy.data.objects.new('Prestige '+name,ca);scene.collection.objects.link(co);co.location=loc;co.rotation_euler=(Vector((0,0,H*.48))-co.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.19;scene.camera=co;scene.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
 bpy.data.libraries.write(str(P/(D['assetId']+'-authored.blend')),{scene},fake_user=True,compress=True)
 report={'assetId':D['assetId'],'mesh_objects':len(objects),'min_z':min(v.co.z for o in objects for v in o.data.vertices),'max_z':max(v.co.z for o in objects for v in o.data.vertices),'register_height':(H-0),'osm_height':D['osm_height_m'],'floor_count':D['floors'],'prior_scene':old.name,'created_scene':scene.name,'reference_scope':D['reference_scope'],'supersedes':D['supersedes']};assert abs(report['max_z']-(H-0))<1e-4 and report['min_z']==0
 (P/'authoring-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:bpy.context.window.scene=old
