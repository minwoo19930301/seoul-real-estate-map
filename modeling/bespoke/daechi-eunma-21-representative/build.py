import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Daechi Eunma21 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['model_upper_envelope_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['complex_household_discrepancy']=D['complex_household_discrepancy'];s['photo_list_index']=1;s['scope_exclusions']=json.dumps(D['scope_exclusions'])
s['height_status']=D['height_status'];s['height_formula']=D['height_formula'];s['estimated_height_m']=D['estimated_height_m']
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256'] or ''
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('Eunma21 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.81,.82,.77));metal=mat('light grey solid wall',(.65,.67,.61),.08,.66);glass=mat('turquoise balcony glazing',(.18,.36,.37),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.19,.21,.22),.12,.58);base=mat('muted ground wall',(.58,.51,.42),.08,.65);service=mat('narrow charcoal service strips',(.22,.25,.26),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['model_upper_envelope_m'];body=H-1.8;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-1.55),mat('solid pale roof deck',(.81,.82,.77)))
# Eunma21 long bent slab, mixed balcony panes and physical fine rails; rear treatment inferred.
darkglass=mat('aged charcoal balcony panes',(.16,.20,.23),.18,.43);cream=mat('pale beige service wall',(.70,.68,.56));ac=mat('offwhite outdoor AC units',(.68,.69,.65));roles=[];blankedges=[]
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.08):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 blank=L<15;roles.append({'edge':ei,'length_m':L,'role':'pale blank numbered end wall' if blank else 'mixed enclosed balcony banks, thin metal rails and white spandrels','basis':'numbered21/complex photo inference; hidden faces and exact counts unmeasured'})
 if blank:
  blankedges.append(ei);face(.5,body/2,L-.02,body,.01,white,depth=.02)
  for f in range(1,FLOORS):face(.5,f*pitch,L-.10,.026,.035,metal,depth=.012)
 else:
  count=8;bw=(L-.50)/count
  for j in range(count):
   t=(.25+(j+.5)*bw)/L;ww=bw-.38
   for f in range(FLOORS):
    z=(f+.57)*pitch;hh=.76*pitch;m=darkglass if (j*7+f*3+ei)%5<2 else glass
    face(t,z,ww,hh,.04,m)
    for q in [-.5,-1/6,1/6,.5]:face(t+q*ww/L,z,.045,hh,.105,white,depth=.035)
    face(t,f*pitch+.18,bw,.36,.09,white,depth=.10)
    railw=ww-.08;bottom=(f+.23)*pitch;top=bottom+.87
    face(t,bottom,railw,.055,.24,white,depth=.045);face(t,top,railw,.055,.24,white,depth=.045)
    for k in range(max(4,round(railw/.20))+1):
     num=max(4,round(railw/.20));face(t+(k/num-.5)*railw/L,(bottom+top)/2,.022,.87,.24,white,depth=.025)
    if (j+f*2)%5==0:
     at=t+ww*.32/L;face(at,(f+.34)*pitch,.60,.40,.25,ac,depth=.34)
     face(at,(f+.34)*pitch,.28,.28,.425,frame,depth=.012)
   face((.25+j*bw)/L,body/2,.30,body,.105,white,depth=.11)
  face((L-.25)/L,body/2,.30,body,.105,white,depth=.11)
  # Narrow fullheight solid beige wall near each wing junction; avoids all-glass curtain facade.
  t=.955 if ei in [1,4] else .045;face(t,body/2,L*.045,body,.15,cream,depth=.07)
 face(.5,body-.18,L,.36,.08,white,depth=.10)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2))
# Modest solid equipment box supported on own roof; roof plan/dimensions inferred.
u,v,w,d=D['roof_core_uv'];x,y=u*co-v*si,u*si+v*co
box((x,y,H-.80),(w,d,1.50),base,theta)
box((x,y,H-.025),(w+.12,d+.12,.05),white,theta)
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('Eunma21 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('Eunma21 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
ob=next(o for o in s.objects if o.type=='MESH' and 'broad white facade frames' in o.name);me=ob.data;verts=[v.co.copy() for v in me.vertices];faces=[tuple(p.vertices) for p in me.polygons];assert len(verts)%8==0 and len(faces)==len(verts)//8*6
boxes=[];rails={};vertical=[]
for i in range(len(verts)//8):
 v=verts[i*8:i*8+8];center=sum(v,Vector())/8;ex=v[1]-v[0];ey=v[3]-v[0];w=ex.length;dep=ey.length;h=v[4].z-v[0].z;b={'i':i,'center':center,'ex':ex.normalized(),'ey':ey.normalized(),'w':w,'dep':dep,'h':h};boxes.append(b)
 if abs(h-.055)<.0001 and abs(dep-.045)<.0001 and w>1:rails.setdefault(round(center.z,3),[]).append(b)
 if abs(h-.87)<.0001 and abs(w-.022)<.0001 and abs(dep-.025)<.0001:vertical.append(b)
removed=set();witness=[]
for b in vertical:
 for faceidx in [0,1]:
  pi=b['i']*6+faceidx;vs=[verts[j] for j in faces[pi]];z=sum(v.z for v in vs)/4
  for rail in rails.get(round(z,3),[]):
   if all(abs((v-rail['center']).dot(rail['ex']))<=rail['w']/2-1e-5 and abs((v-rail['center']).dot(rail['ey']))<=rail['dep']/2-1e-5 and abs(v.z-rail['center'].z)<=rail['h']/2-1e-5 for v in vs):
    removed.add(pi);witness.append({'removed_face':pi,'vertical_box':b['i'],'containing_horizontal_rail_box':rail['i'],'z':z});break
assert len(vertical)>0
# Export-friendly chunks retain exact coordinates, flat normals and material; no decimation.
mat=me.materials[0];chunks=[];chunkboxes=2048
for start in range(0,len(boxes),chunkboxes):
 stop=min(start+chunkboxes,len(boxes));vv=verts[start*8:stop*8];ff=[tuple(j-start*8 for j in faces[pi]) for pi in range(start*6,stop*6) if pi not in removed];nm=bpy.data.meshes.new('Eunma21 exact white rail chunk');nm.from_pydata(vv,[],ff);nm.update();no=bpy.data.objects.new('Eunma21 white exact chunk '+str(start//chunkboxes),nm);s.collection.objects.link(no);nm.materials.append(mat);chunks.append(no)
bpy.data.objects.remove(ob,do_unlink=True);s['mesh_optimization']='Only fully enclosed vertical-rail caps removed; exact coordinates/rail count/spacing retained; white mesh split for16bit indices';s['removed_fully_internal_quad_faces']=len(removed)

# Separate photograph-supported building-number mesh, normalized name for future clone hiding.
ei=blankedges[0];a=r[ei];b=r[(ei+1)%len(r)];dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
cu=bpy.data.curves.new('21 number font','FONT');cu.body='21';cu.size=1.35;cu.align_x='CENTER';cu.extrude=.005;no=bpy.data.objects.new('building-number-label',cu);s.collection.objects.link(no);no.location=(a[0]+dx*.40+nx*.11,a[1]+dy*.40+ny*.11,body*.76);no.rotation_euler=(math.pi/2,0,math.atan2(ny,nx)+math.pi/2);cu.materials.append(service)
for o in bpy.context.selected_objects:o.select_set(False)
no.select_set(True);bpy.context.view_layer.objects.active=no;bpy.ops.object.convert(target='MESH');no=bpy.context.object;no.data.transform(no.matrix_world);no.matrix_world.identity();no.name='building-number-label';no['label_number']='21';no['hide_on_representative_clones']=True;s['clone_hide_node_names']=json.dumps(['building-number-label'])
objs=[o for o in s.objects if o.type=='MESH'];(P/'optimization-proof.json').write_text(json.dumps({'vertical_rail_bars_unchanged':len(vertical),'white_box_components_unchanged':len(boxes),'removed_fully_enclosed_quad_caps':len(removed),'removed_triangles':len(removed)*2,'white_chunks':len(chunks),'mesh_count':len(objs),'unchanged_coordinates':True,'no_decimation':True,'witnesses':witness},indent=2))

for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'daechi-eunma-21.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('Eunma21 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('Eunma21 sun','SUN');lo=bpy.data.objects.new('Eunma21 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('Eunma21 '+name);ob=bpy.data.objects.new('Eunma21 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;inv=ob.rotation_euler.to_matrix().transposed();q=[inv@(o.matrix_world@vv.co-ob.location) for o in objs for vv in o.data.vertices];ca.ortho_scale=max(ca.ortho_scale,2*max(abs(v.y) for v in q)*1.12,2*max(abs(v.x) for v in q)/(850/1100)*1.12);s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':D['register_height_m'],'estimated_height_m':H,'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'daechi-eunma-21-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
