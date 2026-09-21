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

def skytower(m,f,r,part):
 x0,y0,x1,y1=part['bounds'];h=part['height'];v0,v1=part['void'];p=rect(part['bounds']);W=x1-x0
 # Full lower envelope with an actual three-metre recessed vertical slot on the river face.
 slot=(x0+W*(.34 if part['name']=='ONE BAILEY' else .50));sw=3.2
 m.prism(rect([x0,y0,x1,y1-3.1]),0,v0,0)
 m.prism(rect([x0,y1-3.1,slot-sw/2,y1]),0,v0,0);m.prism(rect([slot+sw/2,y1-3.1,x1,y1]),0,v0,0)
 f.edge((slot+sw/2,y1-3),(slot-sw/2,y1-3),.45,v0-.3,2,.03,.08)
 for a,b in zip(p,p[1:]+p[:1]):
  if abs(a[1]-y1)<.01 and abs(b[1]-y1)<.01:continue
  towerface(f,[a,b],3.4,v0)
 front_bays(f,(x1,y1),(slot+sw/2,y1),3.4,v0,False);front_bays(f,(slot-sw/2,y1),(x0,y1),3.4,v0,False)
 # Upper main front is set forward of lower side wings. Roof is an unequal group of flat terraces,
 # not four concentric stepped floorplates. Reverse roof depths remain photo-limited estimates.
 cx0=x0+4.8;cx1=x1-4.5;backtop=h-7.6;coretop=h-1.35
 side=rect([x0,y0,x1,y1-6.2]);m.prism(side,v1,backtop,0);towerface(f,side,v1+.12,backtop)
 # Main forward spine and a narrow one-storey-lower edge form the photographed asymmetric crown.
 lowedge=rect([cx0,y1-12,cx0+2.55,y1]);main=rect([cx0+2.55,y1-12,cx1,y1])
 m.prism(lowedge,v1,h-4.4,0);m.prism(main,v1,coretop,0)
 front_bays(f,(cx1,y1),(cx0,y1),v1+.12,h-4.4,True)
 # Highest course keeps its wide main block; only the outermost narrow edge steps down.
 front_bays(f,(cx1,y1),(cx0+2.55,y1),h-4.4,coretop,True)
 for xx,zz in [(cx0,h-4.4),(cx1,coretop)]:
  aa,bb=((xx,y1),(xx,y1-12)) if xx==cx0 else ((xx,y1-12),(xx,y1))
  towerface(f,[aa,bb],v1+.1,zz)
 # Three separate openings in the photographed gallery, with substantial stone piers between.
 m.prism(rect([x0,y0,x1,y1-7]),v0,v1-.65,0)
 gallery_x0=cx0;gallery_x1=cx1;gw=gallery_x1-gallery_x0
 openings=[(.04,.20),(.30,.73),(.82,.98)]
 boundaries=[0,.04,.20,.30,.73,.82,.98,1]
 for lo,hi in [(0,.04),(.20,.30),(.73,.82),(.98,1)]:
  m.prism(rect([gallery_x0+lo*gw,y1-7,gallery_x0+hi*gw,y1]),v0,v1-.65,0)
 for lo,hi in openings:
  aa=(gallery_x0+hi*gw,y1-6.7);bb=(gallery_x0+lo*gw,y1-6.7);edgewindow(f,aa,bb,v0+.5,v1-.6,2,False)
 for b in [[x0,y1-7,cx0,y1],[cx1,y1-7,x1,y1]]:m.prism(rect(b),v0,v1-.65,0)
 for zz in [v0-.15,v1-.65]:m.prism(p,zz,zz+.65,0)
 # Jointed large stone gallery panels, interrupted by actual openings.
 for zz in [v0+.12,v1-.55]:f.edge((x1,y1),(x0,y1),zz,zz+.065,7,.1,.03)
 roofrail(r,side,backtop);roofrail(r,lowedge,h-4.4);roofrail(r,main,coretop)
 for pp,zz in [(side,backtop),(lowedge,h-4.4),(main,coretop)]:r.prism(pp,zz-.02,zz+.08,9)
 # Brand backing follows the actual upper main face; text is converted to editable mesh below.
 r.box(((cx0+2.55+cx1)/2,y1+.45,h-.55),(cx1-cx0-2.55,.36,1.1),7)
 part['brandPosition']=[(cx0+2.55+cx1)/2,y1+.75,h-.80]
 part['brandWidth']=cx1-cx0-2.9


def visibleedge(part,a,b,others,z):
 mid=lerp(a,b,.5);dx=b[0]-a[0];dy=b[1]-a[1];L=math.hypot(dx,dy)
 test=(mid[0]+dy/L*.15,mid[1]-dx/L*.15)
 for o in others:
  if o is part or o['height']<z:continue
  x0,y0,x1,y1=o['bounds']
  if x0-.01<test[0]<x1+.01 and y0-.01<test[1]<y1+.01:return False
 return True

def lowwing(m,f,r,part,others,T):
 b=part['bounds'];x0,y0,x1,y1=b;p=part.get('profile',rect(b));h=part['height'];top=h-1.35;step=(top-3.4)/(part['floors']-1)
 m.prism(p,0,top,4)
 for ix,(a,bb) in enumerate(zip(p,p[1:]+p[:1])):
  L=math.dist(a,bb)
  if L<2.8:continue
  ix=(0 if bb[0]>a[0] else 2) if abs(bb[0]-a[0])>abs(bb[1]-a[1]) else (1 if bb[1]>a[1] else 3)
  isstem=part['height']==T['registerHeightM']
  courtyard_white=(isstem and ((T['number'] in [102,123] and ix==1) or (T['number']==122 and ix==3))) or (T['number']==101 and ix==0 and (a[0]+bb[0])/2>-22)
  # 0452: broad pale service walls with one tall narrow window and a small square light.
  white=(.70,1.0) if part['whiteSide']=='east' else (0,.30)
  pale_full=courtyard_white or (ix==1 and part['whiteSide']=='east') or (ix==3 and part['whiteSide']=='west')
  pale_spans=[(0,1)] if pale_full else ([white] if ix in [0,2] else [])
  N=max(2,round(L/3.15))
  for k in range(part['floors']-1):
   z=3.4+k*step
   if not visibleedge(part,a,bb,others,z+1):continue
   # Dark shafts retain narrow residential stacks; do not place broad glass plates over pale walls.
   for j in range(N):
    lo=(j+.32)/N;hi=(j+.64)/N
    if any(pl<hi and lo<ph for pl,ph in pale_spans):continue
    # Surround narrow dark-shaft apertures with raised wall, rather than projecting glass plates.
    left=j/N;right=(j+1)/N
    for pl,ph in pale_spans:
     if left<ph and pl<right:
      if ph<=lo:left=max(left,ph)
      elif pl>=hi:right=min(right,pl)
    f.edge(lerp(a,bb,left),lerp(a,bb,lo),z,z+step,4,.20,.12)
    f.edge(lerp(a,bb,hi),lerp(a,bb,right),z,z+step,4,.20,.12)
    f.edge(lerp(a,bb,lo),lerp(a,bb,hi),z,z+.55,4,.20,.12)
    f.edge(lerp(a,bb,lo),lerp(a,bb,hi),z+step-.65,z+step,4,.20,.12)
    f.edge(lerp(a,bb,lo),lerp(a,bb,hi),z+.55,z+step-.65,2,.065,.025)
    for t in [lo,hi]:
     q=.025/L;f.edge(lerp(a,bb,t-q),lerp(a,bb,t+q),z+.55,z+step-.65,3,.10,.20)
  for pl,ph in pale_spans:
   width=L*(ph-pl);groups=max(1,round(width/7.5));holes=[]
   for j in range(groups):
    mid=pl+(ph-pl)*(j+.50)/groups
    holes += [(max(pl,mid-.70/L),min(ph,mid+.15/L),.48,step-.45),
              (max(pl,mid+1.50/L),min(ph,mid+2.30/L),1.03,min(step-.65,1.96))]
   for k in range(part['floors']-1):
    z=3.4+k*step
    if not visibleedge(part,a,bb,others,z+1):continue
    cut=pl
    for lo,hi,bottom,upper in sorted(holes):
     if hi<=lo:continue
     f.edge(lerp(a,bb,cut),lerp(a,bb,lo),z,z+step,5,.20,.12)
     f.edge(lerp(a,bb,lo),lerp(a,bb,hi),z,z+bottom,5,.20,.12)
     f.edge(lerp(a,bb,lo),lerp(a,bb,hi),z+upper,z+step,5,.20,.12)
     # Glazing sits 0.20 m behind the wall plane; dark jambs show actual reveal depth.
     f.edge(lerp(a,bb,lo),lerp(a,bb,hi),z+bottom,z+upper,2,.065,.025)
     for t in [lo,hi]:
      q=.025/L;f.edge(lerp(a,bb,max(pl,t-q)),lerp(a,bb,min(ph,t+q)),z+bottom,z+upper,3,.10,.20)
     f.edge(lerp(a,bb,lo),lerp(a,bb,hi),z+bottom,z+bottom+.035,3,.10,.20)
     cut=hi
    f.edge(lerp(a,bb,cut),lerp(a,bb,ph),z,z+step,5,.20,.12)
    f.edge(lerp(a,bb,pl),lerp(a,bb,ph),z+.025,z+.045,7,.323,.01)
   f.edge(lerp(a,bb,pl),lerp(a,bb,ph),.2,3.4,5,.20,.12)
  if visibleedge(part,a,bb,others,top):
   f.edge(a,bb,top-.3,top+.15,4,.26,.20)
  if visibleedge(part,a,bb,others,2):edgewindow(f,lerp(a,bb,.22),lerp(a,bb,.78),.6,2.9,2)
 r.prism(p,top,top+.20,9);roofrail(r,p,top+.2)
 # Photo-visible flat roof rooms only: no unsupported glass boxes on these low wings.
 if False:
  r.box(((x0+x1)/2,(y0+y1)/2,top+.50),(max(3,(x1-x0)*.32),max(2,(y1-y0)*.38),.55),4)

# Courtyard galleries follow actual inner profile edges, not bounds minima.
G={101:(-31.25,-21.55,15.25,16.0,27.9,34.0),102:(6.7,23.20,7.10,16.4,27.9,34.0),123:(14.0,24.35,8.55,20.0,34.0,40.1),122:(-27.0,-16.6,10.10,20.7,34.0,40.1)}
def bridge_end_curtain(m,T):
 if T['number'] not in G:return
 x0,x1,y,base,sill,top=G[T['number']];a=(x0,y);b=(x1,y);L=x1-x0
 # Solid attached lower podium and shallow reveals connect the gallery to its wing.
 m.prism(rect([x0,y+.08,x1,y+2.2]),0,base,7)
 m.edge(a,b,base,sill-.25,1,.03,.055)
 for j in range(round(L/1.35)+1):
  u=j/round(L/1.35);w=.035/L;m.edge(lerp(a,b,max(0,u-w)),lerp(a,b,min(1,u+w)),base,sill-.25,3,.12,.065)
 for j in range(5):
  z=base+(sill-base)*j/4;m.edge(a,b,z,z+.085,3,.12,.065)
 for x in [x0,x1]:m.box((x,y+.72,(base+sill)/2),(.25,1.55,sill-base),5)
 m.box(((x0+x1)/2,y+.50,base-.17),(L,1.1,.34),7)
 m.box(((x0+x1)/2,y+.65,sill-.18),(L+.25,1.55,.36),5)
 # Dark plinth has a sparse entrance bay, not another curtain-wall strip.
 m.edge((x0+L*.30,y-.02),(x0+L*.68,y-.02),.6,4.3,2,.03,.05)

def skybridge(m,f,r,B):
 x0,y0,x1,y1=B['bounds'];z=B['bottom'];h=B['height']
 if B['peer']==102:
  front=14.65;left=-57.08;right=-21.3;split0=-40.55;split1=-31.35
 else:
  front=8.40;left=14.;right=55.45;split0=24.35;split1=45.45
 # Deep pale bottom and roof plates of the enclosed rear bridge.
 m.prism(rect([x0,y0,x1,y1]),z,z+.75,5)
 m.prism(rect([x0,y0,x1,y1]),z+h-.60,z+h,5)
 for a,b in [((x1,y1),(x0,y1)),((x0,y0),(x1,y0))]:
  L=math.dist(a,b);f.edge(a,b,z+.75,z+h-.60,10,.03,.06)
  for j in range(max(2,round(L/1.3))+1):
   u=j/max(2,round(L/1.3));w=.03/L;f.edge(lerp(a,b,max(0,u-w)),lerp(a,b,min(1,u+w)),z+.75,z+h-.60,3,.14,.07)
 # One physical unbroken front header spans unequal attached side galleries.
 m.box(((left+right)/2,front+.32,z+h-.43),(right-left,.90,.86),5)
 for lo,hi in [(left,split0),(split1,right)]:
  m.prism(rect([lo,front,hi,y0+.4]),z,z+.55,5)
  m.prism(rect([lo,front,hi,y0+.4]),z+h-.60,z+h,5)
  a,b=(lo,front+.48),(hi,front+.48);L=hi-lo
  f.edge(a,b,z+.55,z+h-.60,1,.02,.075)
  for j in range(max(2,round(L/1.3))+1):
   u=j/max(2,round(L/1.3));w=.03/L;f.edge(lerp(a,b,max(0,u-w)),lerp(a,b,min(1,u+w)),z+.55,z+h-.60,3,.13,.07)
  f.edge(a,b,z+3.,z+3.08,3,.13,.07)
 for j in range(8):
  x=split0+(split1-split0)*j/7;r.box((x,(front+y0)/2,z+h-.43),(.20,y0-front,.37),5)
 # Recessed central lounge is behind the open pergola; no detached front glass slab.
 f.edge((split0,y0-.2),(split1,y0-.2),z+.8,z+h-.6,10,.03,.06)
 for x in [left,right]:m.box((x,front+.45,z+h/2),(.28,.9,h),5)

def transmesh(mesh,ang):
 c,s=math.cos(ang),math.sin(ang);mesh.v=[(x*c-y*s,x*s+y*c,z) for x,y,z in mesh.v]
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
 no=T['number'];C=coll(f'{no}_independent_residential_and_assigned_bridge');m=Mesh(f'{no}_authored_massing');f=Mesh(f'{no}_observed_facade_bays');r=Mesh(f'{no}_setback_roof_and_bridge_bracing')
 for part in T['parts']:
  if part['kind']=='skyTower':skytower(m,f,r,part)
  else:lowwing(m,f,r,part,T['parts'],T)
 # Replace the inferred residential wall overlays where the photo shows galleries.
 if no in G:
  gx0,gx1,gy,gbase,gsill,gtop=G[no];keep=[]
  for face,mi in zip(f.f,f.mi):
   pts=[f.v[i] for i in face];cx=sum(p[0] for p in pts)/len(pts);cy=sum(p[1] for p in pts)/len(pts);cz=sum(p[2] for p in pts)/len(pts)
   if gx0-.15<cx<gx1+.15 and gy-.4<cy<gy+1.8 and gbase<cz<gtop:continue
   keep.append((face,mi))
  f.f=[q[0] for q in keep];f.mi=[q[1] for q in keep]
 bridge_end_curtain(f,T)
 if T.get('bridge'):
  skybridge(m,f,r,T['bridge'])
  B=T['bridge'];bx0,by0,bx1,by1=B['bounds'];passage_z=6.6;yc=by1-2.2
  m.box(((bx0+bx1)/2,yc,passage_z),(bx1-bx0,2.7,.42),7)
  for yy in [yc-1.35,yc+1.35]:
   r.box(((bx0+bx1)/2,yy,passage_z+2.6),(bx1-bx0,.22,.24),7)
   for x in [bx0+1.5,bx1-1.5]:r.box((x,yy,passage_z+1.4),(.23,.23,2.5),7)
   f.edge((bx0,yy),(bx1,yy),passage_z+.25,passage_z+1.4,10,0,.045)
  for x in [bx0+1.5,bx1-1.5]:m.box((x,yc,passage_z/2),(.36,.40,passage_z),7)
 for mesh in [m,f,r]:transmesh(mesh,math.radians(T['angleDeg']));mesh.obj(C)
 for part in T['parts']:
  if 'brandPosition' not in part:continue
  uv=part['brandPosition'];ang=math.radians(T['angleDeg']);cu=bpy.data.curves.new(f'{no}_roof_brand','FONT');cu.body=part['name'].replace(' ','');cu.align_x='CENTER';cu.size=1;cu.extrude=.055;cu.bevel_depth=.007;cu.resolution_u=2
  ob=bpy.data.objects.new(f'{no}_roof_brand',cu);C.objects.link(ob);ob.rotation_euler=(math.pi/2,0,math.pi+ang);ob.location=(uv[0]*math.cos(ang)-uv[1]*math.sin(ang),uv[0]*math.sin(ang)+uv[1]*math.cos(ang),uv[2]);cu.materials.append(M[5]);bpy.context.view_layer.update();fac=min(part['brandWidth']/ob.dimensions.x,1.18/max(ob.dimensions.z,.01));ob.scale=(fac,fac,fac)
  bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH');bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
 # Keep the roof lettering within the registered maximum; do not scale the building.
 for ob in C.objects:
  if 'roof_brand' in ob.name:
   excess=max(v.co.z for v in ob.data.vertices)-T['registerHeightM']
   if excess>0:
    for v in ob.data.vertices:v.co.z-=excess
 components=['registered individual residential floorplate','photo-authored independent wing heights','face-specific white/navy/grey glazing and casement windows']
 if no in [101,121]:components+=['open recessed intermediate sky gallery','unequal side-wing terraces and taller forward spine with mesh roof brand' ]
 if T.get('bridge'):components+=[f"enclosed skycommunity bridge {no}–{T['bridge']['peer']} with deep metal frame and diagonal internal bracing"]
 A={'id':T['id'],'nameKo':f'래미안원베일리 {no}동','file':T['id']+'.glb','blendSource':'raemian-onebailey-family.blend','coordinate':{'lon':T['coordinate'][0],'lat':T['coordinate'][1]},'category':'apartment','district':'서초구','footprintIds':[T['sourceId']],'supersedes':[f'fallback-onebailey-{no}'],'referenceUrl':R['sources'][0]['url'],'components':components,'modelingBasis':'individual-photo-review' if no==101 else 'representative-photo-inference','inferredFromAssetIds':[] if no==101 else ['bespoke-raemian-onebailey-101'],'inferenceScope':'101 visible courtyard sparse pale service wall and narrow recessed windows; hidden faces uncertain' if no==101 else '101 representative facade family inferred onto retained individual massing; not independently photo compared','publicationDependency':None if no==101 else 'bespoke-raemian-onebailey-101 must be approved and published first','uncertainties':R['uncertainties'],'floors':T['registerFloors'],'households':T['households'],'heightBasis':'Exact per-building register legal maximum; parapet datum unspecified. Individual wing heights and gallery elevation inferred from completed photographs.'}
 export(C,A)
g=Mesh('review_ground');g.box((0,0,-.6),(500,360,1),6);g.obj(REVIEW)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True;scene.render.resolution_x=1200;scene.render.resolution_y=800;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX';scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.70,.78,.85,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.80
sun=bpy.data.lights.new('Daylight','SUN');ob=bpy.data.objects.new('Daylight',sun);REVIEW.objects.link(ob);ob.rotation_euler=(.35,-.6,-.5);sun.energy=2;sun.angle=.12
ang=math.radians(R['angleDeg'])
def en(u,v,z):return (u*math.cos(ang)-v*math.sin(ang),u*math.sin(ang)+v*math.cos(ang),z)
views=[('river-source',(-45,340,62),(-25,0,53),275),('courtyard',(-10,-300,100),(-25,0,52),285),('roof-plan',(-25,0,450),(-25,0,0),285),('101-crown',(-120,105,135),(-76,8,86),98),('123-122-bridge',(60,155,58),(30,45,36),116),('east-diagonal',(230,200,120),(-25,0,55),280),('123-122-inner-low',(47,-9,15),(47,40,26),85),('101-102-inner-low',(-109,-60,2),(-109,28,25),70)]
for name,loc,target,scale in views:
 cam=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,cam);REVIEW.objects.link(ob);ob.location=en(*loc);ob.rotation_euler=(Vector(en(*target))-ob.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=scale
 if name.endswith('inner-low'):cam.type='PERSP';cam.lens=28 if name.startswith('123') else 40
cam=bpy.data.cameras.new('river-ground-photo');ob=bpy.data.objects.new('river-ground-photo',cam);REVIEW.objects.link(ob);ob.location=en(-10,330,3);ob.rotation_euler=(Vector(en(-25,0,53))-ob.location).to_track_quat('-Z','Y').to_euler();cam.type='PERSP';cam.lens=48
scene.camera=bpy.data.objects['river-source'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'raemian-onebailey-family.blend'))
(OUT/'geometry-check.json').write_text(json.dumps({'assets':checks,'embeddedImages':0,'coverage':R['coverage']},ensure_ascii=False,indent=2))
bundle={'siteId':R['siteId'],'sources':R['sources'],'assets':assets,'recipeFiles':['recipe.json','build.py','prepare.py','source-register.json','numbered-source-mapping.json','ratio-ledger.json','tour-bridge-ledger.json','REFERENCE-NOTES.md','validate.py','render-family.py','photo-dossier.md','family-lineage.json'],'coverage':R['coverage'],'places':[{'id':'bespoke-raemian-onebailey-north-first5','siteId':R['siteId'],'name':'래미안원베일리 수변 5개 동','subtitle':'101·102·121·122·123동 및 두 스카이브릿지 · 전체23동 중5동','center':R['siteCenter'],'zoom':17.3,'source_url':R['sources'][1]['url'],'supersedesPlaceIds':[]}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n');print(json.dumps(checks))
