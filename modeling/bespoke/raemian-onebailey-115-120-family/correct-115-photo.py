import bpy,math,json,bmesh,hashlib
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.geometry import tessellate_polygon
OUT=Path(__file__).resolve().parent
R=json.loads((OUT/'recipe.json').read_text());T=next(t for t in R['towers'] if t['number']==115)
scene=bpy.data.scenes.get('OneBailey115to120_authoring');assert scene
bpy.context.window.scene=scene
C=next(c for c in scene.collection.children if c.name=='115_retained_individual_massing')
for ob in list(C.objects):bpy.data.objects.remove(ob,do_unlink=True)
def mat(name,c,rough=.5,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True;n=next(x for x in m.node_tree.nodes if x.type=='BSDF_PRINCIPLED');n.inputs['Base Color'].default_value=(*c,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal;return m
M=[mat('Warm silver grey tower stone',(.285,.278,.245),.66,.1),mat('Blue silver residential glazing',(.245,.33,.36),.24,.45),mat('Dark openable window',(.075,.12,.15),.3,.2),mat('Champagne metal frames',(.49,.465,.38),.44,.35),mat('Blue charcoal opaque panels',(.14,.185,.225),.65),mat('White warm facade',(.78,.79,.75),.72),mat('Review ground',(.40,.43,.40),.85),mat('Recess shadow stone',(.20,.22,.23),.62),mat('Pale window reflection',(.43,.52,.54),.22,.34),mat('Roof membrane',(.43,.45,.44),.8),mat('Clear lounge glass',(.26,.44,.49),.17,.2)]
M[10].diffuse_color=(.26,.44,.49,.20)
node=next(x for x in M[10].node_tree.nodes if x.type=='BSDF_PRINCIPLED');node.inputs['Alpha'].default_value=.20
M[10].surface_render_method='DITHERED'
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


def rect(b):
 x0,y0,x1,y1=b;return [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
def edgewindow(m,a,b,z0,z1,mi=1,paired=True):
 L=math.dist(a,b)
 if L<.3:return
 m.edge(a,b,z0,z1,mi,.24,.045)
 for zz in [z0,z1-.040]:m.edge(a,b,zz,zz+.040,7,.31,.035)
 for t in [0,.5,1] if paired else [0,1]:
  w=.025/L;m.edge(lerp(a,b,max(0,t-w)),lerp(a,b,min(1,t+w)),z0,z1,7,.33,.035)
 if paired:
  m.edge(lerp(a,b,.57),lerp(a,b,.90),z0+.20,min(z0+1.07,z1-.12),2,.54,.07)
  m.edge(lerp(a,b,.55),lerp(a,b,.93),z0+1.08,min(z0+1.145,z1),3,.60,.06)
def roofrail(m,p,z):
 for a,b in zip(p,p[1:]+p[:1]):
  m.edge(a,b,z,z+.28,0,.03,.20);m.edge(a,b,z+1.03,z+1.1,3,.07,.07)
  N=max(1,round(math.dist(a,b)/1.4))
  for j in range(N+1):
   t=j/N;u=.035/max(math.dist(a,b),.1);m.edge(lerp(a,b,max(0,t-u)),lerp(a,b,min(1,t+u)),z+.28,z+1.05,3,.08,.06)
def towerface(m,p,base,top,floorstep=3.05):
 for ix,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
  L=math.dist(a,b);N=max(2,round(L/4.9))
  for j in range(N):
   lo=(j+.12)/N;hi=(j+.88)/N
   for k in range(max(1,round((top-base)/floorstep))):
    z=base+k*floorstep
    if z+.75>=top:continue
    # Framed residential window pairs, not an undifferentiated glass curtain wall.
    edgewindow(m,lerp(a,b,lo),lerp(a,b,hi),z+.72,min(z+floorstep-.26,top-.18),1)
    m.edge(lerp(a,b,lo-.028),lerp(a,b,hi+.028),z+.48,z+.68,0,.36,.20)
  # Broad uninterrupted vertical piers between the visible window groups.
  for j in range(N+1):
   t=j/N;w=.28/L;m.edge(lerp(a,b,max(0,t-w)),lerp(a,b,min(1,t+w)),base,top,0,.38,.27)
  for k in range(max(1,round((top-base)/floorstep))):
   z=base+k*floorstep;m.edge(a,b,z+.13,z+.25,3,.27,.12)
def front_bays(f,a,b,z0,z1,upper=True):
 L=math.dist(a,b);step=3.05
 spans=[(.025,.13,'narrow'),(.153,.188,'service'),(.255,.345,'narrow'),(.414,.504,'narrow'),(.572,.662,'narrow'),(.744,.971,'wide')] if upper else [(0,.23,'wide'),(.285,.515,'wide'),(.575,.70,'narrow'),(.77,.96,'wide')]
 for lo,hi,kind in spans:
  for k in range(max(1,math.ceil((z1-z0)/step))):
   z=z0+k*step
   if z+.6>=z1:continue
   if kind=='service':edgewindow(f,lerp(a,b,lo),lerp(a,b,hi),z+1.08,min(z+1.76,z1-.12),2,False)
   else:
    edgewindow(f,lerp(a,b,lo),lerp(a,b,hi),z+.56,min(z+2.68,z1-.15),8,False)
    if kind=='wide':
     for t in [.25,.52,.74]:
      u=lo+(hi-lo)*t;w=.022/L;f.edge(lerp(a,b,u-w),lerp(a,b,u+w),z+.57,min(z+2.67,z1-.15),7,.52,.05)
    else:
     u=lo+(hi-lo)*.64;w=.02/L;f.edge(lerp(a,b,u-w),lerp(a,b,u+w),z+.57,min(z+2.67,z1-.15),7,.52,.05)
    # One dark inset openingpane, considerably smaller than the full glazing bay.
    f.edge(lerp(a,b,lo+.012),lerp(a,b,lo+(hi-lo)*.27),z+.67,z+1.35,1,.52,.04)
   # Actual pale bedjoint is subdued; no bright rectangular border around every window.
  if kind=='wide':
   for k in range(max(1,math.ceil((z1-z0)/step))):
    z=z0+k*step;f.edge(lerp(a,b,lo-.02),lerp(a,b,hi+.018),z+.20,z+.37,0,.35,.20)
 for k in range(max(1,math.ceil((z1-z0)/step))):
  z=z0+k*step;f.edge(a,b,z+.04,z+.08,7,.10,.035)

def clip(p,axis,cut,side):
 out=[];k=0 if axis=='x' else 1
 for a,b in zip(p,p[1:]+p[:1]):
  ia=(a[k]-cut)*side>=-1e-9;ib=(b[k]-cut)*side>=-1e-9
  if ia:out.append(a)
  if ia!=ib:out.append(lerp(a,b,(cut-a[k])/(b[k]-a[k])))
 return ensureccw(out)
def facade(f,p,h,floors):
 step=(h-3.5)/(floors-1)
 for ix,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
  L=math.dist(a,b)
  if L<2:continue
  N=max(1,round(L/5.8));pale=(L>5.5)
  for j in range(N):
   left=j/N;right=(j+1)/N;W=L/N
   # Pale dwelling planes stay continuous between asymmetric tall and service apertures.
   mi=5 if pale and j%4!=3 else 4
   if j%3==0 and W>4:holes=[(.12,.37,.30,step-.22),(.62,.81,.90,min(1.9,step-.3))]
   elif j%3==1:holes=[(.13,.70,.28,step-.25)]
   else:holes=[(.17,.41,.27,step-.23),(.58,.82,.27,step-.23)]
   # 115's road-facing service plane is visibly blank in official DJI_0062.
   # Face orientation and extent are approximate; hidden faces remain inferred.
   if T['number']==115 and L>23 and abs(a[1]-b[1])<2 and (a[1]+b[1])/2 < -10 and j in [1,2]:mi=7;holes=[]
   for k in range(floors-1):
    z=3.5+k*step;cursor=left
    for x0,x1,z0,z1 in holes:
     lo=left+(right-left)*x0;hi=left+(right-left)*x1
     f.edge(lerp(a,b,cursor),lerp(a,b,lo),z,z+step,mi,.25,.14)
     f.edge(lerp(a,b,lo),lerp(a,b,hi),z,z+z0,mi,.25,.14)
     f.edge(lerp(a,b,lo),lerp(a,b,hi),z+z1,z+step,mi,.25,.14)
     # Recessed glazing behind actual solid reveal planes, varying width and height.
     f.edge(lerp(a,b,lo),lerp(a,b,hi),z+z0,z+z1,1,.09,.035)
     if x1-x0>.4:
      mid=(lo+hi)/2;q=.025/L;f.edge(lerp(a,b,mid-q),lerp(a,b,mid+q),z+z0,z+z1,3,.16,.08)
     cursor=hi
    f.edge(lerp(a,b,cursor),lerp(a,b,right),z,z+step,mi,.25,.14)
   if mi==5:f.edge(lerp(a,b,left),lerp(a,b,right),.2,3.5,5,.25,.14)
  edgewindow(f,lerp(a,b,.22),lerp(a,b,.65),.5,3.0,2,False)
def crown(m,f,r,T,top,H):
 x0,y0,x1,y1=T['crownBounds'];W=x1-x0;D=y1-y0
 # A narrow upright glazed lantern and adjacent opaque service volume leave roof terraces exposed.
 p=rect([x0+W*.20,y0+D*.30,x0+W*.60,y0+D*.73]);service=rect([x0+W*.62,y0+D*.34,x0+W*.87,y0+D*.73])
 m.prism(service,top,H-1.0,4);r.prism(service,H-1,H-.75,9)
 m.prism(p,top,top+.28,4);r.prism(p,H-.20,H,4)
 for a,b in zip(p,p[1:]+p[:1]):
  L=math.dist(a,b);f.edge(a,b,top+.28,H-.20,1,0,.06)
  for j in range(round(L/1.15)+1):
   t=j/max(1,round(L/1.15));w=.035/L;f.edge(lerp(a,b,max(0,t-w)),lerp(a,b,min(1,t+w)),top+.28,H-.20,3,.08,.07)
  f.edge(a,b,top+(H-top)/2,top+(H-top)/2+.07,3,.08,.07)

M.append(mat('115 medium gray photo wall',(.37,.385,.38),.8))
M.append(mat('115 dark brown photo service block',(.16,.125,.14),.8))
m=Mesh('115_editable_massing');f=Mesh('115_pale_bays_navy_shafts');r=Mesh('115_glass_roof_crown')
p=ensureccw(T['localRing']);H=T['registerHeightM'];top=H-6.4
m.prism(p,0,3.5,4)
split=T['split'];high=clip(p,split['axis'],split['cut'],split['highSide']);low=clip(p,split['axis'],split['cut'],-split['highSide']);lh=3.5+(split['lowFloors']-1)*3.05
for pp,hh,fl in [(high,top,T['registerFloors']),(low,lh,split['lowFloors'])]:
 m.prism(pp,3.5,hh,4);facade(f,pp,hh,fl);r.prism(pp,hh,hh+.12,9)
a,b=p[1],p[2]
# Road-facing orientation and proportions estimated; these features are visible in DJI_0062.
f.edge(lerp(a,b,.22),lerp(a,b,.78),3.5,top,11,.68,.20)
f.edge(lerp(a,b,.47),lerp(a,b,.79),0,39.0,12,1.0,.75)
# Pale vertical frames flanking the central wall and narrow service window stack.
for lo,hi in [(.19,.22),(.78,.81)]:f.edge(lerp(a,b,lo),lerp(a,b,hi),0,top,5,1.05,.22)
# Strong white roof bands and horizontal recessed vent louvers, not a glazed lantern.
r.prism(high,top,top+.22,9)
for aa,bb in zip(high,high[1:]+high[:1]):
 for z in [top-3.0,top-2.35,top-1.7,top-.9]:r.edge(aa,bb,z,z+.30,5,.5,.45)
# Tall opaque roof/service housing within register maximum.
q=rect([-9,-11,7,-3]);m.prism(q,top,H-.35,12);r.prism(q,H-.35,H,5)
for aa,bb in zip(q,q[1:]+q[:1]):
 for j in range(9):r.edge(aa,bb,top+.6+j*.48,top+.78+j*.48,7,.06,.16)
# Readable photo-identifying lettering, converted to editable geometry.
d=Vector((b[0]-a[0],b[1]-a[1],0)).normalized();up=Vector((0,0,1));normal=d.cross(up)
basis=Matrix(((d.x,up.x,normal.x),(d.y,up.y,normal.y),(d.z,up.z,normal.z)))
def glyph(text,t,z,size,out):
 cv=bpy.data.curves.new('115_photo_letter','FONT');cv.body=text;cv.size=size;cv.align_x='CENTER';cv.extrude=.015
 ob=bpy.data.objects.new('115_photo_letter',cv);C.objects.link(ob)
 ob.rotation_euler=basis.to_euler();v=Vector((*lerp(a,b,t),z))+normal*out;ob.location=v
 bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();ev=ob.evaluated_get(dg);me=ev.to_mesh()
 for poly in me.polygons:f.face([tuple(ob.matrix_world@me.vertices[i].co) for i in poly.vertices],5)
 ev.to_mesh_clear();bpy.data.objects.remove(ob,do_unlink=True);bpy.data.curves.remove(cv)
# No ONEBAILEY mark claimed for115; only number is directly visible.
glyph('115',.64,30.5,1.5,1.80)
ang=math.radians(T['angleDeg']);co,si=math.cos(ang),math.sin(ang)
for mesh in [m,f,r]:mesh.v=[(x*co-y*si,x*si+y*co,z) for x,y,z in mesh.v];mesh.obj(C)
for ob in scene.objects:ob.select_set(False)
obs=list(C.objects)
for ob in obs:ob.select_set(True)
bpy.context.view_layer.objects.active=obs[0]
bpy.ops.export_scene.gltf(filepath=str(OUT/(T['id']+'.glb')),export_format='GLB',use_selection=True,use_active_scene=True,export_apply=True,export_yup=True,export_texcoords=False,export_cameras=False,export_lights=False)
for ob in obs:ob.location.x=0
# Store only this family scene; other scenes and completed115–120 are neither altered nor saved.
bpy.data.libraries.write(str(OUT/'raemian-onebailey-115-120.blend'),{scene},fake_user=True)
checks=json.loads((OUT/'geometry-check.json').read_text())
for q in checks:
 if q['id']==T['id']:
  lo=[min(v.co[k] for ob in obs for v in ob.data.vertices) for k in range(3)];hi=[max(v.co[k] for ob in obs for v in ob.data.vertices) for k in range(3)];tri=0
  for ob in obs:ob.data.calc_loop_triangles();tri+=len(ob.data.loop_triangles)
  q.update(blenderBounds=[lo,hi],triangles=tri,heightErrorM=abs(hi[2]-H),sha256=hashlib.sha256((OUT/(T['id']+'.glb')).read_bytes()).hexdigest())
(OUT/'geometry-check.json').write_text(json.dumps(checks,indent=2))
print('115-only photo correction exported; existing116–120 geometry retained')
