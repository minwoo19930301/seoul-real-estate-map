import bpy,json,pathlib,math
from mathutils import Vector,Matrix
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};s=bpy.data.scenes.new('Songpa Helio102 representative');bpy.context.window.scene=s
for k,v in {'source_id':D['id'],'register_id':D['register_row']['id'],'register_height_m':D['register_height_m'],'model_upper_envelope_m':D['register_height_m'],'floors':D['floors'],'reference_scope':D['reference_scope'],'height_assumption':D['height_assumption'],'source_sha256':D['source_sha256'],'photo_sha256':D['photo_sha256'],'supersedesAssetIds':json.dumps(D['supersedesAssetIds']),'binding_status':D['binding_status'],'current_owner_asset_ids':json.dumps(D['current_owner_asset_ids']),'source_ring_m':json.dumps(D['ring_m']),'regions_json':json.dumps(regions),'anchor_lonlat':D['anchor_lonlat']}.items():s[k]=v
s['complex_household_discrepancy']=D['complex_household_discrepancy'];s['photo_list_index']=2;s['scope_exclusions']=json.dumps(D['scope_exclusions'])
s['inferredFromAssetIds']=json.dumps(D['inferredFromAssetIds']);s['ancestor_glb_sha256']=D['ancestor_glb_sha256'] or ''
batches={}
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new('Helio102 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=rough;return m
white=mat('white slab frames',(.84,.85,.82));metal=mat('blankwall grey panels',(.65,.67,.66));glass=mat('dark blue grey glazing',(.065,.14,.20),.38,.25);frame=mat('grey service grille',(.24,.27,.29),.25,.48);roof=mat('low roof deck',(.40,.43,.43));base=mat('dark grey twofloor base',(.22,.23,.24));yellow=mat('yellow projecting rectangular frame',(.94,.65,.025),.12,.48);orange=mat('orange narrow accent',(.90,.29,.045),.12,.48);recess=mat('deep shaded frame recess',(.035,.045,.060))
def mesh(v,f,m):
 V,F=batches.setdefault(m,[[],[]]);off=len(V);V.extend(v);F.extend([tuple(off+i for i in face) for face in f])
def box(c,d,m,ang=0):
 x,y,z=c;w,q,h=[v/2 for v in d];co,si=math.cos(ang),math.sin(ang);mesh([(x+a*co-b*si,y+a*si+b*co,z+k) for k in [-h,h] for a,b in [(-w,-q),(w,-q),(w,q),(-w,q)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
H=D['register_height_m'];body=D['body_height_m'];FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta);entry=D['entry'];shapes=json.loads((P/'entry-shape.json').read_text())
s['number_label']=json.dumps(D['label']);s['colored_frame_dimensions']=json.dumps(D['colored_frame_dimensions']);s['entry_recess']=json.dumps(entry);s['parcel_discrepancy']=D['complex_household_discrepancy']
def mass(shape,z0,z1,m):
 for ring in shape['rings']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in shape['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
for band in json.loads((P/'body-bands.json').read_text()):mass(band['shape'],band['z0'],band['z1'],base if band['material']=='base' else white)
mass(shapes['full'],body,D['roof_deck_height_m'],roof)
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]));roles=[];colorframes=[]
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else(-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.10):
  # Keep the real inward entrance volume unobstructed by foreground facade boxes.
  if ei==entry['edge'] and z-h/2<entry['top_m'] and z+h/2>.18 and abs((t-.5)*L)<(w+entry['width_m'])/2:return
  box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 blank=L<D['blank_edge_threshold_m_inferred'];roles.append({'edge':ei,'length_m':L,'role':'blank panel endwall with short vertical orange accents' if blank else 'white slab grid, blue-grey glazing, narrow grilles and selective colored frames','basis':'Own edge length and numbered416 photo; orientation and stations unmeasured'})
 if blank:
  if L>5:
   for f in range(2,FLOORS):face(.5,f*pitch,L-.08,.023,.045,frame,depth=.012)
   for t in [.25,.50,.75]:face(t,(body+pitch*2)/2,.016,body-pitch*2,.04,metal,depth=.015)
   for j,(t,f) in enumerate([(.30,round(FLOORS*.25)),(.64,round(FLOORS*.33)),(.45,round(FLOORS*.50)),(.30,round(FLOORS*.67)),(.64,round(FLOORS*.75))]):face(t,(f+.45)*pitch,.18,pitch*.72,.060,orange,depth=.025)
 else:
  count=max(4,round(L/3.7));bw=L/count
  for j in range(count):
   t=(j+.5)/count;service=j==count//2;ww=bw*(.38 if service else .82)
   for f in range(FLOORS):
    z=(f+.55)*pitch;hh=.72*pitch;off=-.34 if any(j==jj and ff<=f<ee for jj,ff,ee in D['frame_groups'].get(str(ei),[])) else 0;face(t,z,ww,hh,.035+off,frame if service else glass,depth=.055)
    if service:
     for k in range(9):face(t,z-hh/2+(k+.5)*hh/9,ww,.026,.08+off,metal,depth=.028)
    else:
     face(t,z,.050,hh,.082+off,frame,depth=.035)
     for q in [-.5,.5]:face(t+q*ww/L,z,.055,hh,.09+off,white,depth=.06)
    face(t,(f+.08)*pitch,bw-.03 if off==0 else bw*.96-.34,.30,.11+off,base if f<2 else white)
  for j in range(count+1):
   t=max(.12/L,min(1-.12/L,j/count));face(t,body/2,.28,body,.10,white)
  # Large colored open frames surround selected groups; stations are visual inference.
  for ji,fs,fe,cm in [(jj,ff,ee,[yellow,yellow,orange][kk]) for kk,(jj,ff,ee) in enumerate(D['frame_groups'].get(str(ei),[]))]:
   if ji>=count:continue
   t=(ji+.5)/count;w=bw*.96;z0=fs*pitch;z1=fe*pitch;th=.34
   face(t,(z0+z1)/2,w-.34,z1-z0-.34,-.355,recess,depth=.03)
   for q in [-.5,.5]:face(t+q*w/L,(z0+z1)/2,th,z1-z0+.34,.17,cm,depth=.34)
   for z in [z0,z1]:face(t,z,w+.34,th,.17,cm,depth=.34)
   # Supported colored lower shelf creates a shallow boxlike balcony edge.
   face(t,z0+.15,w-.12,.30,.03,cm,depth=.86);colorframes.append({'edge':ei,'bay':ji,'floors':[fs,fe],'projection_m':.46,'basis':'unmeasured numbered/complex photo frame inference'})
 face(.5,body-.12,L,.24,.10,white)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2));(P/'colored-frame-proof.json').write_text(json.dumps(colorframes,indent=2))
# Actual inset entrance: glazing on the back wall at0.82m inward, supported by floor.
a=r[entry['edge']];b=r[(entry['edge']+1)%len(r)];ang=math.atan2(b[1]-a[1],b[0]-a[0]);cx,cy=entry['center_m'];nx,ny=entry['outward_normal'];top=entry['top_m'];box((cx-nx*.845,cy-ny*.845,(top+.18)/2),(entry['width_m'],.01,top-.18),recess,ang);box((cx-nx*.82,cy-ny*.82,(top+.18)/2),(2.65,.04,top-.18-.10),glass,ang);box((cx-nx*.78,cy-ny*.78,(top+.18)/2),(.06,.08,top-.18-.10),frame,ang)
# Thin actual roof railing inside own inset contour, upper surface exactlyH.
roofrail=D['roof_rail_ring'];postcount=0
for a,b in zip(roofrail,roofrail[1:]+roofrail[:1]):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx)
 for z in [H-.04,H-.58]:box(((a[0]+b[0])/2,(a[1]+b[1])/2,z),(L,.035,.08 if z==H-.04 else .035),frame,ang)
 count=max(1,math.ceil(L/.42))
 for j in range(count+1):
  t=j/count;box((a[0]+dx*t,a[1]+dy*t,(D['roof_deck_height_m']+H-.08)/2),(.027,.027,H-.08-D['roof_deck_height_m']),frame,ang);postcount+=1
objs=[]
for m,(v,f) in batches.items():
 me=bpy.data.meshes.new('Helio102 editable '+m.name);me.from_pydata(v,[],f);me.update();ob=bpy.data.objects.new('Helio102 editable '+m.name,me);s.collection.objects.link(ob);me.materials.append(m);objs.append(ob)
# Verified building number as editable mesh text, on same chosen shortwall as entry.
cx,cy=D['entry']['center_m'];nx,ny=D['entry']['outward_normal'];cu=bpy.data.curves.new('Source numbered102 number','FONT');cu.body='102';cu.align_x='CENTER';cu.align_y='CENTER';cu.size=1.5;cu.extrude=.022;cu.resolution_u=4;ob=bpy.data.objects.new('Source 102 inferred number mesh',cu);s.collection.objects.link(ob);ob.location=(cx+nx*.10,cy+ny*.10,body*.68);ob.rotation_euler=Matrix(((-ny,0,nx),(nx,0,ny),(0,1,0))).to_euler();cu.materials.append(frame)
for q in bpy.context.selected_objects:q.select_set(False)
ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH');bpy.context.view_layer.update();ob=bpy.context.view_layer.objects.active;ob.data.transform(ob.matrix_world.copy());ob.matrix_world=Matrix.Identity(4);objs.append(ob)
(P/'optimization-proof.json').write_text(json.dumps({'mesh_count':len(objs),'material_batching':True,'decimation':False,'roof_railing_posts':postcount,'no_embedded_photo':True},indent=2))
for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'songpa-helio-city-102.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=20;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.world=bpy.data.worlds.new('Helio102 world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('Helio102 sun','SUN');lo=bpy.data.objects.new('Helio102 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,(u,v),z in [('front',(75,-155),H),('opposite',(-75,155),H),('side',(170,50),H),('roof',(65,-85),H*2.55)]:
 ca=bpy.data.cameras.new('Helio102 '+name);ob=bpy.data.objects.new('Helio102 '+name,ca);s.collection.objects.link(ob);ob.location=(u*co-v*si,u*si+v*co,z);ob.rotation_euler=(Vector((0,0,H/2))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=H*1.23;inv=ob.rotation_euler.to_matrix().transposed();q=[inv@(o.matrix_world@vv.co-ob.location) for o in objs for vv in o.data.vertices];ca.ortho_scale=max(ca.ortho_scale,2*max(abs(v.y) for v in q)*1.12,2*max(abs(v.x) for v in q)/(850/1100)*1.12);s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices];report={'source_id':D['id'],'floors':D['floors'],'register_height_m':H,'uniform_height_assumption':True,'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'mesh_count':len(objs),'image_nodes':0,'finite':all(math.isfinite(c) for v in vs for c in v)};assert abs(report['bounds_xyz'][0][2])<1e-5 and abs(report['bounds_xyz'][1][2]-H)<1e-4 and report['finite'];(P/'validation.json').write_text(json.dumps(report,indent=2));bpy.data.libraries.write(str(P/'songpa-helio-city-102-authored.blend'),{s},fake_user=True,compress=True);bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name,'before':before,'after':after},indent=2));print(json.dumps(report))
