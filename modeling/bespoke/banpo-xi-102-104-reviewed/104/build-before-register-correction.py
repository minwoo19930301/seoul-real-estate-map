import bpy, math, json, pathlib
from mathutils import Vector
P=pathlib.Path(__file__).parent; D=json.loads((P/'source-data.json').read_text()); old=bpy.context.scene

for prior in list(bpy.data.scenes):
 if prior.name=='Banpo Xi 104 pilot':
  bpy.data.batch_remove(ids=list(prior.objects))
  bpy.data.scenes.remove(prior)
s=bpy.data.scenes.new('Banpo Xi 104 pilot');bpy.context.window.scene=s
s['reference_scope']='KB uncredited built complex photo; tower identity and orientation unverified; 104 facade and upper step are inference'
s['height_basis']='81.0m and 29 floors OSM local mapping; no individual register confirmation; lower wing inferred'
objs=[]
def mat(n,c,metal=0):
 m=bpy.data.materials.new('BX104 '+n);m.diffuse_color=(*c,1);m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF');q.inputs['Base Color'].default_value=(*c,1);q.inputs['Metallic'].default_value=metal;q.inputs['Roughness'].default_value=.3 if metal else .72;return m
stone=mat('pale silver limestone',(.66,.68,.66));white=mat('ivory course bands',(.86,.87,.82));core=mat('grey service core',(.37,.40,.40));glass=mat('blue grey broad glazing',(.12,.25,.31),.38);frame=mat('white window frames',(.79,.83,.81),.15);cap=mat('dark coping',(.20,.17,.14));base=mat('warm ground stone',(.39,.36,.31))
def mesh(n,v,f,m):
 me=bpy.data.meshes.new(n);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new('BX104 '+n,me);s.collection.objects.link(o);me.materials.append(m);objs.append(o);return o
def box(n,c,d,m,ang=0):
 x,y,z=c;u,v,w=[k/2 for k in d];co,si=math.cos(ang),math.sin(ang);return mesh(n,[(x+a*co-b*si,y+a*si+b*co,z+h) for h in [-w,w] for a,b in [(-u,-v),(u,-v),(u,v),(-u,v)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def uv(p):return p[0]*co+p[1]*si,-p[0]*si+p[1]*co
def xy(u,v):return (u*co-v*si,u*si+v*co)
def clip(r,cut):
 out=[]
 for a,b in zip(r,r[1:]+r[:1]):
  ua=-uv(a)[1];ub=-uv(b)[1]
  if ua>=cut:out.append(a)
  if (ua>=cut)!=(ub>=cut):
   t=(cut-ua)/(ub-ua);out.append([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])])
 return out
upper=clip(r,7.2);pitch=(81.0-3)/29;lower=24*pitch;body=81.0-3

def mass(n,ring,z0,z1):
 N=len(ring);return mesh(n,[(x,y,z) for z in [z0,z1] for x,y in ring],[tuple(reversed(range(N))),tuple(range(N,2*N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)],stone)
o=mass('exact own footprint 24 floor lower wing',r,0,lower);o['source_ring_m']=json.dumps(r);o['footprint_id']=D['id'];o['anchor_lonlat']=D['anchor_lonlat'];mass('inferred 29 floor taller wing',upper,lower,body)

def facade(ring,first,last):
 area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]+ring[:1]))
 for ei,(a,b) in enumerate(zip(ring,ring[1:]+ring[:1])):
  dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
  def face(n,t,z,w,h,dep,m):return box(n,(a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,.12,h),m,ang)
  if first==0:face('three storey warm stone base',.5,pitch*1.5,L,pitch*3,.08,base)
  if L<2.5:continue
  # Quiet broad service return selected in local orientation: inference, not surveyed.
  quiet=abs(math.cos(ang-theta))<.4 and (a[0]+b[0])>8
  if quiet:
   for f in range(first,last):face('quiet service wall horizontal joints',.5,(f+.04)*pitch,L,.08,.17,white)
   face('quiet wall roof coping',.5,last*pitch-.18,L+.5,.36,.35,cap)
   continue
  count=max(1,round(L/4.8));bw=L/count
  for j in range(count):
   service=(j%3==1) or L<4.3;t=(j+.5)/count;w=bw*(.39 if service else .86)
   if service:face('grey narrow service strip',t,(first+last)*pitch/2,bw*.76,(last-first)*pitch,.065,core)
   for f in range(first,last):
    z=(f+.56)*pitch;h=pitch*(.36 if service else .64)
    face('service window' if service else 'wide living room window',t,z,w,h,.145,glass)
    for off in [-h/2,h/2]:face('window sill head',t,z+off,w+.10,.075,.23,frame)
    panes=2 if service else (4 if w>3.5 else 3)
    for k in range(panes+1):face('window upright mullion',t+(k/panes-.5)*w/L,z,.065,h,.24,frame)
    if not service:face('living window lower transom',t,z-h*.18,w,.05,.25,frame)
    face('pale horizontal floor course',t,(f+.04)*pitch,bw,.13,.20,base if f<3 else white)
   for side in [-1,1]:face('vertical panel joint',t+side*(bw*.48)/L,(first+last)*pitch/2,.07,(last-first)*pitch,.16,white)
  face('deep roof cornice',.5,last*pitch-.15,L+.2,.30,.32,cap)
facade(r,0,24);facade(upper,24,29)
# Ground stone reveals, exact footprint retained; upper crowns are open frames rather than solid caps.
for name,u,v,z,w,d in [('tall open pergola',5,-11,body,10,5),('lower offset pergola',-13,2,lower,7,6)]:
 for a in [-w/2,w/2]:
  for b in [-d/2,d/2]:
   x,y=xy(u+a,v+b);box(name+' upright',(x,y,z+1.35),(.65,.65,2.7),white,theta)
 for b in [-d/2,d/2]:
  x,y=xy(u,v+b);box(name+' long overhead beam',(x,y,z+2.8),(w+1.4,1.05,.4),cap,theta)
 for a in [-w/2,w/2]:
  x,y=xy(u+a,v);box(name+' side overhead beam',(x,y,z+2.8),(.9,d+1.0,.4),cap,theta)
x,y=xy(5,-11);box('compact roof access',(x,y,body+1.1),(7,2.4,2.2),white,theta)
x,y=xy(5,-11);box('thick projecting roof access slab',(x,y,body+2.5),(8.2,3.4,.45),cap,theta)
# Consolidate editable geometry by material to keep artifact and session responsive.
groups={}
for ob in objs:groups.setdefault(ob.data.materials[0],[]).append(ob)
merged=[]
for material,group in groups.items():
 vertices=[];faces=[]
 for ob in group:
  offset=len(vertices);vertices.extend([tuple(v.co) for v in ob.data.vertices]);faces.extend([tuple(offset+i for i in p.vertices) for p in ob.data.polygons])
 merged.append(mesh('editable '+material.name,vertices,faces,material))
bpy.data.batch_remove(ids=[ob for group in groups.values() for ob in group]);objs=merged
s['source_ring_m']=json.dumps(r);s['footprint_id']=D['id'];s['anchor_lonlat']=D['anchor_lonlat'];s['floors']=29;s['inferredFromAssetIds']='bespoke-banpo-xi-101'
# Export only own mesh objects.
for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
bpy.ops.export_scene.gltf(filepath=str(P/'banpo-xi-104.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
s.render.engine='CYCLES';s.cycles.samples=16;s.render.resolution_x=850;s.render.resolution_y=1100;s.render.resolution_percentage=100
s.world=bpy.data.worlds.new('BX104 review world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.82,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('BX104 sun','SUN');lo=bpy.data.objects.new('BX104 sun',ld);s.collection.objects.link(lo);lo.rotation_euler=(.45,-.4,-.6);ld.energy=2.3;s.view_settings.view_transform='AgX'
for name,uvloc,z in [('front',(75,-155),80),('opposite',(-75,155),80),('side',(170,50),80),('roof',(65,-85),210)]:
 ca=bpy.data.cameras.new('BX104 '+name);ob=bpy.data.objects.new('BX104 '+name,ca);s.collection.objects.link(ob);x,y=xy(*uvloc);ob.location=(x,y,z);ob.rotation_euler=(Vector((0,0,40.5))-ob.location).to_track_quat('-Z','Y').to_euler();ca.type='ORTHO';ca.ortho_scale=98.82;s.camera=ob;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
vs=[o.matrix_world@v.co for o in objs for v in o.data.vertices]
report={'footprint_id':D['id'],'anchor_lonlat':D['anchor_lonlat'],'ring_m':r,'finite':all(math.isfinite(c) for v in vs for c in v),'zmin':min(v.z for v in vs),'zmax':max(v.z for v in vs),'floors':29,'lower_wing_floors_inferred':24,'height_m_osm_estimate':81.0,'legal_height_m':None,'prior_scene_preserved':old.name,'mesh_count':len(objs),'embedded_image_textures':0,'reference_scope':s['reference_scope']}
(P/'validation.json').write_text(json.dumps(report,indent=2))
bpy.data.libraries.write(str(P/'banpo-xi-104-authored.blend'),{s},fake_user=True,compress=True)
bpy.context.window.scene=old
print(json.dumps(report))
