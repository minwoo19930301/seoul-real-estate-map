import bpy, math, json, bmesh, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
OUT=Path(__file__).resolve().parent
R=json.loads((OUT/'recipe.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
 if not c.objects and not c.children:bpy.data.collections.remove(c)
def coll(name):
 c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c
REVIEW=coll('REVIEW_ONLY_NOT_EXPORTED')
def mat(name,c,rough=.5,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True;n=next(x for x in m.node_tree.nodes if x.type=='BSDF_PRINCIPLED');n.inputs['Base Color'].default_value=(*c,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal;return m
M=[mat('Hyperion2 pale limestone',(.69,.68,.61),.70),mat('Completed bluegreen residential glass',(.13,.29,.31),.22,.40),mat('Dark openable casements',(.095,.18,.18),.3,.22),mat('Silver frame',(.59,.62,.58),.4,.45),mat('Dark horizontal base band',(.13,.15,.14),.62),mat('Roof stone',(.58,.59,.53),.7),mat('Review ground',(.32,.34,.31),.85),mat('Service ventilation',(.16,.19,.18),.75),mat('Upper glass reflection',(.22,.36,.37),.22,.34)]
class Mesh:
 def __init__(self,name):self.name=name;self.v=[];self.f=[];self.mi=[]
 def face(self,pts,mi):
  k=len(self.v);self.v.extend(pts);self.f.append(tuple(range(k,k+len(pts))));self.mi.append(mi)
 def box(self,c,s,mi):
  x,y,z=c;w,d,h=s
  if min(w,d,h)<1e-5:return
  q=[(x+w*a,y+d*b,z+h*c) for a,b,c in [(-.5,-.5,-.5),(.5,-.5,-.5),(.5,.5,-.5),(-.5,.5,-.5),(-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5)]]
  for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([q[i] for i in ids],mi)
 def prism(self,pts,z0,z1,mi):
  if z1<=z0:return
  pts=[tuple(p) for p in pts]
  if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts,pts[1:]+pts[:1]))<0:pts.reverse()
  for a,b in zip(pts,pts[1:]+pts[:1]):self.face([(*a,z0),(*b,z0),(*b,z1),(*a,z1)],mi)
  vec=[Vector((*a,0)) for a in pts]
  for tri in tessellate_polygon([vec]):
   vs=[vec[q] if isinstance(q,int) else q for q in tri];self.face([(v.x,v.y,z1) for v in vs],mi);self.face([(v.x,v.y,z0) for v in reversed(vs)],mi)
 def edge(self,a,b,z0,z1,mi,out=.0,depth=.04):
  dx=b[0]-a[0];dy=b[1]-a[1];L=math.hypot(dx,dy)
  if L<1e-5 or z1<=z0:return
  nx=dy/L;ny=-dx/L
  a1=(a[0]+nx*out,a[1]+ny*out);b1=(b[0]+nx*out,b[1]+ny*out)
  # Geometry is a solid shallow quad slab, not coplanar facade overlays.
  self.prism([a1,b1,(b1[0]+nx*depth,b1[1]+ny*depth),(a1[0]+nx*depth,a1[1]+ny*depth)],z0,z1,mi)
 def obj(self,col):
  me=bpy.data.meshes.new(self.name);me.from_pydata(self.v,[],self.f);me.update()
  for m in M:me.materials.append(m)
  for f,i in zip(me.polygons,self.mi):f.material_index=i
  ob=bpy.data.objects.new(self.name,me);col.objects.link(ob)
  bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free();return ob

def lerp(a,b,t):return [a[k]+(b[k]-a[k])*t for k in range(len(a))]
def strip(mesh,a,b,z0,z1,mi,offset=.06,depth=.08):mesh.edge(a,b,z0,z1,mi,offset,depth)
def bar(mesh,a,b,width,mi):
 a,b=Vector(a),Vector(b);d=b-a
 if d.length<.001:return
 u=d.cross(Vector((0,0,1)))
 if u.length<.01:u=d.cross(Vector((1,0,0)))
 u.normalize();v=d.normalized().cross(u);u*=width/2;v*=width/2
 q=[a-u-v,a+u-v,a+u+v,a-u+v,b-u-v,b+u-v,b+u+v,b-u+v]
 for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:mesh.face([tuple(q[i]) for i in ids],mi)
def ensureccw(pts):
 return list(reversed(pts)) if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts,pts[1:]+pts[:1]))<0 else pts


def opening(m,a,b,z,h,glass=1):
 m.edge(a,b,z,z+h,glass,.16,.08)
 L=math.dist(a,b)
 m.edge(a,b,z,z+.055,3,.29,.055);m.edge(a,b,z+h-.055,z+h,3,.29,.055)
 divisions=max(1,round(L/1.10))
 for k in range(divisions+1):
  t=k/divisions;d=.035/max(L,.1);m.edge(lerp(a,b,max(0,t-d)),lerp(a,b,min(1,t+d)),z,z+h,3,.3,.05)
 # Nonrandom visible openingpanel inset in paired residential glazing.
 if L>2.5:
  m.edge(lerp(a,b,.75),lerp(a,b,.94),z+.20,z+min(1.02,h-.13),2,.32,.05)
  m.edge(a,b,z+.68,z+.725,3,.30,.06)
def facade(m,T,top,base=8.3):
 p=T['profile'];step=(top-base)/(T['floors']-3)
 for desc,(a,b) in zip(T['faceRoles'],zip(p,p[1:]+p[:1])):
  role=desc['role'];L=math.dist(a,b)
  if role=='stone_return':spans=[(.38,.64)]
  elif role=='stone_spur_end':spans=[(.15,.25),(.43,.56),(.75,.85)]
  elif role=='courtyard_bay':spans=[(.10,.90)]
  elif role=='broad_south_front':spans=[(.055,.455),(.56,.95)]
  else:spans=[(.08,.43),(.56,.93)]
  for j in range(T['floors']-3):
   z=base+j*step
   for lo,hi in spans:
    height=1.18 if role.startswith('stone_') else step-.82
    opening(m,lerp(a,b,lo),lerp(a,b,hi),z+.51,height,8 if (j>=T['floors']-6 or (role=='stone_spur_end' and lo==.43)) else 1)
   # Thin actual stone bedjoints, deliberately not a dark universal grid.
   if role not in ['stone_return']:
    m.edge(a,b,z+.10,z+.12,5,.12,.025)
  # Panel joint in each broad end wall: only mortar-scale recess, not large darkgrid.
  if role=='stone_spur_end':
   for t in [.09,.36,.64,.94]:
    w=.010/L;m.edge(lerp(a,b,t-w),lerp(a,b,t+w),base,top,5,.145,.025)
  # The tall glass bays have broad stone edges and central service stonebands.
  if role=='courtyard_bay':
   for lo,hi in [(0,.095),(.90,1)]:m.edge(lerp(a,b,lo),lerp(a,b,hi),base,top,0,.33,.25)
  # Narrow protruding stone window surrounds along only spur-side positions.
  if role=='stone_spur_end':
   for j in range(T['floors']-3):
    z=base+j*step
    for lo,hi in spans:m.edge(lerp(a,b,lo-.045),lerp(a,b,hi+.04),z+.42,z+.54,0,.34,.30)
  m.edge(a,b,top-.56,top+.14,0,.23,.50)
  m.edge(a,b,6.7,7.9,4,.25,.30)
  # Low double-height stone entry piers/individual residential lobby.
  n=max(1,round(L/3.8))
  for j in range(n):opening(m,lerp(a,b,(j+.12)/n),lerp(a,b,(j+.87)/n),.8,5.5,2)
  for j in range(n+1):
   t=j/n;w=.35/L;m.edge(lerp(a,b,max(0,t-w)),lerp(a,b,min(1,t+w)),0,6.7,0,.34,.45)

def trans(p,angle,offset=(0,0)):
 c=math.cos(angle);s=math.sin(angle);return [(x*c-y*s+offset[0],x*s+y*c+offset[1]) for x,y in p]
def export(col,A):
 bpy.ops.object.select_all(action='DESELECT');obs=list(col.objects)
 for ob in obs:ob.select_set(True)
 bpy.context.view_layer.objects.active=obs[0]
 bpy.ops.export_scene.gltf(filepath=str(OUT/A['file']),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_texcoords=False,export_cameras=False,export_lights=False)
 lo=[min(v.co[k] for ob in obs for v in ob.data.vertices) for k in range(3)];hi=[max(v.co[k] for ob in obs for v in ob.data.vertices) for k in range(3)];tri=0
 for ob in obs:ob.data.calc_loop_triangles();tri+=len(ob.data.loop_triangles)
 checks.append({'id':A['id'],'blenderBounds':[lo,hi],'triangles':tri,'sha256':hashlib.sha256((OUT/A['file']).read_bytes()).hexdigest()})
 dx=(A['coordinate']['lon']-R['siteCenter'][0])*111320*math.cos(math.radians(R['siteCenter'][1]));dy=(A['coordinate']['lat']-R['siteCenter'][1])*111320
 for ob in obs:ob.location=(dx,dy,0)
 assets.append(A)
assets=[];checks=[]
for T in R['towers']:
 n=T['number'];col=coll(f'{n}_individual_residential');m=Mesh(f'{n}_sourceplate_stone');f=Mesh(f'{n}_face_specific_windows');r=Mesh(f'{n}_crown_sloping_blades_and_stone_gallery')
 h=T['heightM'];top=h-9.2;p=T['profile'];ang=math.radians(T['angleDeg']);m.prism(p,0,top,0);facade(f,T,top)
 # Rooftop body: consultant near-roof photo shows two tall stone end piers
 # and a separate narrower central mechanical crown, not an office helipad.
 r.prism(p,top,top+.20,5)
 for q in T['lowParapets']:r.prism(q,top+.21,top+.38,0)
 for q in T['highParapets']:r.prism(q,top+.39,top+1.65,0)
 for desc,(a,b) in zip(T['faceRoles'],zip(p,p[1:]+p[:1])):
  if desc['role']=='stone_spur_end':
   # high plate-shaped end walls with compact upper servicewindow
   pass # highParapets above already unioned allsameelevation edges
   r.edge(lerp(a,b,.22),lerp(a,b,.76),top+.25,top+.55,7,.50,.10)
 # Raised small stone roof-room with three long dark ventilator slots.
 center=(0,1.0);q=trans([(-4.2,-4.0),(4.2,-4.0),(4.2,4.2),(-4.2,4.2)],ang,center)
 r.prism(q,top+.2,top+5.50,0)
 for a,b in zip(q,q[1:]+q[:1]):
  for j in range(3):
   t=(j+.5)/3;r.edge(lerp(a,b,t-.029),lerp(a,b,t+.029),top+.85,top+4.60,7,.12,.10)
  for lo,hi in [(0,.10),(.90,1)]:r.edge(lerp(a,b,lo),lerp(a,b,hi),top+.20,top+5.30,0,.24,.24)
  r.edge(a,b,top+1.55,top+1.88,0,.34,.60)
  r.edge(a,b,top+2.30,top+2.48,5,.41,.65)
  r.edge(a,b,top+4.65,top+5.15,0,.22,.40)
 # Two angled sail blades and crossing horizontal bars are directly visible
 # in consultant-1; dimension/hidden reverse are conservative interpretations.
 for x in [-2.2,2.2]:
  aa=trans([(x,-4.7)],ang,center)[0];bb=trans([(x,4.6)],ang,center)[0]
  # Broad sloping blade: tall rectangular section, not thin ladderrails.
  ux,uy=math.cos(ang)*.34,math.sin(ang)*.34
  v=[(aa[0]-ux,aa[1]-uy,top+4.12),(aa[0]+ux,aa[1]+uy,top+4.12),(bb[0]+ux,bb[1]+uy,h-1.45),(bb[0]-ux,bb[1]-uy,h-1.45),(aa[0]-ux,aa[1]-uy,top+5.48),(aa[0]+ux,aa[1]+uy,top+5.48),(bb[0]+ux,bb[1]+uy,h),(bb[0]-ux,bb[1]-uy,h)]
  for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:r.face([v[i] for i in ids],5)
  bar(r,(*bb,top+4.5),(*bb,h-1.0),.60,5)
 for y in [-3.1,-.45,2.2]:
  aa,bb=trans([(-3.35,y),(3.35,y)],ang,center);z=top+5.1+(y+4.7)/9.3*(h-.44-top-5.1)
  bar(r,(*aa,z),(*bb,z),.26,5)
 # Row of distinct stone fins over the south living wing. Top visible between
 # end piers in AURUM4 and summitcourtyard; no solid cap over those openings.
 for x in [-7.5,-4.5,-1.5,1.5,4.5,7.5]:
  aa,bb=trans([(x,-9.5),(x,-3.9)],ang,(0,-3.5))
  # Sloping fin top follows visible roofscreen ratherthan a row of antennas.
  w=.42;d=(bb[0]-aa[0],bb[1]-aa[1]);L=math.hypot(*d);off=(d[1]/L*w,-d[0]/L*w)
  a1=(aa[0]+off[0],aa[1]+off[1]);b1=(bb[0]+off[0],bb[1]+off[1]);a2=(aa[0]-off[0],aa[1]-off[1]);b2=(bb[0]-off[0],bb[1]-off[1])
  r.face([(*a1,top),(*b1,top),(*b1,top+4.0),(*a1,top+2.1)],0);r.face([(*a2,top),(*b2,top),(*b2,top+4.0),(*a2,top+2.1)],0);r.face([(*a1,top+2.1),(*b1,top+4),(*b2,top+4),(*a2,top+2.1)],0)
 # A lowroof equipment slab rather than invented fullsite podium.
 for mesh in [m,f,r]:mesh.obj(col)
 A={'id':T['id'],'nameKo':f'목동 하이페리온2차 {n}동','file':T['id']+'.glb','blendSource':'mokdong-hyperion-2.blend','coordinate':T['coordinate'],'category':'apartment','district':'양천구','footprintIds':[T['footprintId']],'supersedes':['apt-a15805111'],'referenceUrl':R['sources'][0]['url'],'components':['individuallytraced Y floorplate','stone spur ends andservicewindowrows','green residentialbayglazing andpalespandrels','higherroofpier ends','raisedstonecrown angledpairedblades andcrossbars','open sixfins roofscreen','simplified individualstoneandglassentry'],'uncertainties':R['uncertainties'],'floors':T['floors'],'households':T['households'],'modelEnvelopeM':h,'heightBasis':'exactbuildingregister legalheight usedasconservativeenvelope; roof-tipdatum notverified'}
 export(col,A)
g=Mesh('review_ground');g.box((0,0,-.6),(330,330,1),6);g.obj(REVIEW)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1600;scene.render.resolution_y=1500;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX';scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.70,.78,.85,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.85
sun=bpy.data.lights.new('Daylight','SUN');ob=bpy.data.objects.new('Daylight',sun);REVIEW.objects.link(ob);ob.rotation_euler=(.35,-.6,-.5);sun.energy=2;sun.angle=.12
views=[('SE-source',(170,-220,85),(0,-15,65),200),('SW-all',(-210,-220,90),(0,-20,64),210),('north-courtyard',(10,260,85),(0,-20,60),200),('NE-roof-consultant',(125,120,205),(-5,-20,105),165),('202-crown',(110,-150,160),(40,-63,127),62),('roof-plan',(0,-20,400),(0,-20,0),180)]
for name,loc,target,scale in views:
 cam=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,cam);REVIEW.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=scale
# Ground perspective provides a fairer photo comparison than orthographic views.
cam=bpy.data.cameras.new('SW-ground-photo');ob=bpy.data.objects.new('SW-ground-photo',cam);REVIEW.objects.link(ob);ob.location=(-115,-155,2.0);ob.rotation_euler=(Vector((-10,-28,62))-ob.location).to_track_quat('-Z','Y').to_euler();cam.type='PERSP';cam.lens=31
cam=bpy.data.cameras.new('NW-ground-photo');ob=bpy.data.objects.new('NW-ground-photo',cam);REVIEW.objects.link(ob);ob.location=(-165,150,2.0);ob.rotation_euler=(Vector((-3,-12,63))-ob.location).to_track_quat('-Z','Y').to_euler();cam.type='PERSP';cam.lens=40
scene.camera=bpy.data.objects['SE-source'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'mokdong-hyperion-2.blend'))
(OUT/'geometry-check.json').write_text(json.dumps({'assets':checks,'views':[v[0] for v in views],'embeddedImages':0},ensure_ascii=False,indent=2))
bundle={'siteId':'mokdong-hyperion-2','sources':R['sources'],'assets':assets,'recipeFiles':['recipe.json','build.py','prepare.py','source-buildings.json','source-register.json','source-ledger.json','REFERENCE-NOTES.md','validate.py','render-v4.py'],'coverage':R['coverage'],'places':[{'id':'bespoke-mokdong-hyperion-2','siteId':'mokdong-hyperion-2','name':'목동 하이페리온2차','subtitle':'576세대 · 주거201–204동','center':R['siteCenter'],'zoom':17.2,'household_count':576,'source_url':R['sources'][3]['url'],'supersedesPlaceIds':['model:apt-a15805111','seoul-apartment:A15805111']}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n');print(json.dumps(checks))
