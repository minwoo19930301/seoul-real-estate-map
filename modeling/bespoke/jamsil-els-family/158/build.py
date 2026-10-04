import bpy,json,pathlib,math
from mathutils import Vector
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Jamsil Els158 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['register_height_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['complex_household_discrepancy']=D['complex_household_discrepancy'];s['photo_list_index']=0;s['scope_exclusions']=json.dumps(D['scope_exclusions'])
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256'] or ''
s['shared_wall_mask']=json.dumps(D['shared_wall_mask'])
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('Els158 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('broad white facade frames',(.86,.84,.77));metal=mat('light grey solid wall',(.64,.65,.63),.08,.66);glass=mat('turquoise balcony glazing',(.17,.42,.43),.38,.28);frame=mat('dark horizontal spandrels and mullions',(.22,.25,.28),.18,.46);roof=mat('modest grey flat roof caps',(.35,.37,.37),.12,.58);base=mat('muted ground wall',(.36,.25,.19),.08,.65);service=mat('narrow charcoal service strips',(.22,.25,.26),.08,.68)
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)

# Clip decorative boxes only against actual neighbor polygon below shared height.
# Full parent mass is built by mass()/mesh(), so source walls/grade/deck stay exact.
mask_stats={'decorative_boxes_examined':0,'decorative_boxes_changed':0,'fully_hidden_boxes_removed':0,'clipped_prisms_generated':0,'cutoff_m':D['shared_wall_mask']['height_m'],'neighbor':D['shared_wall_mask']['neighbor_tower']}
mask_materials={}
def signed_area(q):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(q,q[1:]+q[:1]))/2
cutters=D['shared_wall_mask']['neighbor_triangles_m']
cutters=[q if signed_area(q)>0 else list(reversed(q)) for q in cutters]
def halfclip(q,a,b,inside):
 out=[]
 def dist(p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
 for u,v in zip(q,q[1:]+q[:1]):
  du,dv=dist(u),dist(v);iu=du>=0 if inside else du<=0;iv=dv>=0 if inside else dv<=0
  if iu:out.append(u)
  if iu!=iv:
   f=du/(du-dv);out.append((u[0]+(v[0]-u[0])*f,u[1]+(v[1]-u[1])*f))
 clean=[]
 for p in out:
  if not clean or math.dist(p,clean[-1])>1e-8:clean.append(p)
 if len(clean)>1 and math.dist(clean[0],clean[-1])<1e-8:clean.pop()
 return clean if len(clean)>=3 and abs(signed_area(clean))>1e-10 else []
def subtract_triangle(q,tr):
 remain=q;outside=[]
 for a,b in zip(tr,tr[1:]+tr[:1]):
  if not remain:break
  piece=halfclip(remain,a,b,False)
  if piece:outside.append(piece)
  remain=halfclip(remain,a,b,True)
 return outside
original_box=box
def prism(q,z0,z1,m):
 if z1-z0<1e-8:return
 if signed_area(q)<0:q=list(reversed(q))
 n=len(q);vv=[(x,y,z) for z in [z0,z1] for x,y in q];ff=[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 ff += [(0,i+1,i) for i in range(1,n-1)]+[(n,n+i,n+i+1) for i in range(1,n-1)]
 mesh(vv,ff,m);mask_stats['clipped_prisms_generated']+=1
def box(c,d,m,ang=0):
 z0,z1=c[2]-d[2]/2,c[2]+d[2]/2;limit=D['shared_wall_mask']['height_m']
 if z0>=limit:return original_box(c,d,m,ang)
 mask_stats['decorative_boxes_examined']+=1
 co,si=math.cos(ang),math.sin(ang);w,h=d[0]/2,d[1]/2;q=[(c[0]+u*co-v*si,c[1]+u*si+v*co) for u,v in [(-w,-h),(w,-h),(w,h),(-w,h)]];parts=[q]
 for tr in cutters:
  nextparts=[]
  for piece in parts:
   if max(p[0] for p in piece)<min(p[0] for p in tr) or min(p[0] for p in piece)>max(p[0] for p in tr) or max(p[1] for p in piece)<min(p[1] for p in tr) or min(p[1] for p in piece)>max(p[1] for p in tr):nextparts.append(piece)
   else:nextparts.extend(subtract_triangle(piece,tr))
  parts=nextparts
 before=abs(signed_area(q));after=sum(abs(signed_area(v)) for v in parts)
 if before-after<1e-9:return original_box(c,d,m,ang)
 mask_stats['decorative_boxes_changed']+=1
 if not parts:mask_stats['fully_hidden_boxes_removed']+=1
 if m not in mask_materials:
  cm=m.copy();cm.name='Shared-wall clipped surface '+str(len(mask_materials));mask_materials[m]=cm
 cm=mask_materials[m]
 for qpart in parts:prism(qpart,z0,min(z1,limit),cm)
 if z1>limit:prism(q,limit,z1,cm)

H=D['register_height_m'];body=H-2.5;FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def mass(z0,z1,m):
 for ring in D['rings_m']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in regions[0]['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(0,body,metal);mass(body,(H-2.25),roof)
# Els-specific facade derived from KB15617: wide banks either side of twin service windows.
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]));roles=[]
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.10):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 blank=L<(18 if len(r)==4 else 12);roles.append({'edge':ei,'length_m':L,'role':'representative-inferred gray blankwall with rectangular panel joints' if blank else 'paired broad balcony banks flanking pale twin service window field','basis':'own long/short edge dimensions; approved representative wall and balcony inference; compass unmeasured'})
 face(.5,pitch,L,2*pitch,.025,base)
 if blank:
  for k in range(1,FLOORS*2):face(.5,k*body/(FLOORS*2),L-.12,.022,.058,roof,depth=.014)
  for t in [.20,.40,.60,.80]:face(t,body/2,.018,body,.057,roof,depth=.014)
  for t in [.025,.975]:face(t,body/2,.32,body,.12,white)
 else:
  # Solid central wall occupies16%; twin narrow window strips stay distinct.
  face(.5,body/2,L*.16,body,.035,white)
  for t in [.466,.534]:
   for f in range(FLOORS):
    z=(f+.57)*pitch;face(t,z,L*.033,.64*pitch,.075,glass)
    face(t,z,.06,.64*pitch,.135,white)
    face(t,(f+.18)*pitch,L*.034,.10,.14,white)
  for side0,side1 in [(.02,.42),(.58,.98)]:
   count=max(2,round(L*(side1-side0)/5.2));bw=L*(side1-side0)/count
   for j in range(count):
    t=side0+(j+.5)*(side1-side0)/count;ww=bw-.42
    for f in range(FLOORS):
     z=(f+.56)*pitch;hh=.69*pitch;face(t,z,ww,hh,.06,glass)
     for q in [-.5,0,.5]:face(t+q*ww/L,z,.055,hh,.13,white)
     face(t,(f+.105)*pitch,bw-.02,.32,.15,base if f<2 else white)
     railw=ww-.08;bottom=(f+.23)*pitch;top=bottom+.87
     face(t,bottom,railw,.055,.275,white,depth=.045);face(t,top,railw,.055,.275,white,depth=.045)
     num=max(4,round(railw/.19))
     for k in range(num+1):face(t+(k/num-.5)*railw/L,(bottom+top)/2,.022,.87,.275,white,depth=.025)
     for q in [-.5,.5]:face(t+q*railw/L,top,.04,.045,.19,white,depth=.20)
   for j in range(count+1):
    t=side0+j*(side1-side0)/count;face(t,body/2,.38,body,.17,white);face(t,pitch,.38,2*pitch,.19,base)
  # Fine panel joints across central solid field, no continuous dark service curtain.
  for f in range(1,FLOORS):face(.5,f*pitch,L*.16,.018,.093,metal,depth=.012)
 face(.5,body-.20,L,.40,.18,white)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2))
# Photo-specific roof: supported low dark horizontal grille between raised pale ends.
u,v,w,d=D['roof_cap_uv'];x,y=u*co-v*si,u*si+v*co
box((x,y,H-1.90),(w,d,.70),metal,theta)
for off in [-w/2+.40,w/2-.40]:
 box((x+off*co,y+off*si,H-1.10),(.80,d,2.20),white,theta)
# Dark inset equipment enclosure backs the horizontal slats; all inside source.
box((x,y,H-1.02),(w-1.60,d-.38,1.50),service,theta)
for off in [-d/2,d/2]:
 for z in [H-1.67,H-1.40,H-1.13,H-.86,H-.59]:
  box((x-off*si,y+off*co,z),(w-1.60,.12,.12),roof,theta)
box((x,y,H-.24),(w-1.60,d,.12),roof,theta)
(P/'shared-wall-mask-proof.json').write_text(json.dumps(mask_stats,indent=2))
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('Els158 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('Els158 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
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
 stop=min(start+chunkboxes,len(boxes));vv=verts[start*8:stop*8];ff=[tuple(j-start*8 for j in faces[pi]) for pi in range(start*6,stop*6) if pi not in removed];nm=bpy.data.meshes.new('Els158 exact white rail chunk');nm.from_pydata(vv,[],ff);nm.update();no=bpy.data.objects.new('Els158 white exact chunk '+str(start//chunkboxes),nm);s.collection.objects.link(no);nm.materials.append(mat);chunks.append(no)
bpy.data.objects.remove(ob,do_unlink=True);s['mesh_optimization']='Only fully enclosed vertical-rail caps removed; exact coordinates/rail count/spacing retained; white mesh split for16bit indices';s['removed_fully_internal_quad_faces']=len(removed)

objs=[o for o in s.objects if o.type=='MESH'];(P/'optimization-proof.json').write_text(json.dumps({'vertical_rail_bars_unchanged':len(vertical),'white_box_components_unchanged':len(boxes),'removed_fully_enclosed_quad_caps':len(removed),'removed_triangles':len(removed)*2,'white_chunks':len(chunks),'mesh_count':len(objs),'unchanged_coordinates':True,'no_decimation':True,'witnesses':witness},indent=2))

for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'jamsil-els-158.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('Els158 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('Els158 sun','SUN');lo=bpy.data.objects.new('Els158 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('Els158 '+name);ob=bpy.data.objects.new('Els158 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;inv=ob.rotation_euler.to_matrix().transposed();q=[inv@(o.matrix_world@vv.co-ob.location) for o in objs for vv in o.data.vertices];ca.ortho_scale=max(ca.ortho_scale,2*max(abs(v.y) for v in q)*1.12,2*max(abs(v.x) for v in q)/(850/1100)*1.12);s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':H,'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'jamsil-els-158-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
