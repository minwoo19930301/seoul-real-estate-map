"""Seven individually anchored Tower Palace assets, authored through Blender MCP.

I: square banked-window towers with occupied setback penthouses and open belts.
II: angular five-part stepped bodies with triangular frames and open arch roofs.
III: the named serrated Y plan, three unequal blades, fine curtain-wall fins.
No game meshes, city templates, seeded facade variation or source photographs.
"""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/tower-palace';OUT.mkdir(parents=True,exist_ok=True)
rp=OUT/'recipe-input.json'
if not rp.exists():rp=ROOT/'modeling/bespoke/tower-palace/recipe-input.json'
recipe=json.loads(rp.read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for mesh in list(bpy.data.meshes):
 if mesh.users==0:bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
 if mat.users==0:bpy.data.materials.remove(mat)
for col in list(bpy.data.collections):
 if not col.objects and not col.children:bpy.data.collections.remove(col)
def material(name,color,metal=0,rough=.5):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
 return m
MAT=[material('I pale neutral limestone and aluminium',(.70,.70,.65),.12,.49),
 material('I blue bank glazing',(.105,.245,.355),.46,.23),
 material('I narrow champagne mullion',(.44,.46,.43),.55,.35),
 material('I muted operable window and vent',(.13,.19,.205),.2,.5),
 material('deep open gallery shadow',(.027,.038,.042),0,.84),
 material('I flat penthouse cornice',(.83,.82,.76),.14,.44),
 material('II broad ivory stone spandrel',(.83,.825,.77),.05,.6),
 material('II cool blue green horizontal glazing',(.16,.29,.34),.40,.27),
 material('II dark ventilation panel',(.026,.039,.045),.2,.56),
 material('II open arch and triangular frame',(.86,.86,.82),.42,.36),
 material('III blue curtain wall',(.08,.24,.34),.56,.22),
 material('III silver vertical blade fins',(.70,.75,.76),.68,.30),
 material('III blue grey spandrel',(.145,.24,.30),.30,.42),
 material('III dark continuous louver returns',(.045,.065,.077),.36,.48),
 material('dark green ground stone',(.095,.135,.122),.12,.42),
 material('roof surface',(.22,.25,.25),.1,.77),
 material('review ground',(.40,.43,.43),0,.87)]
def ccw(p):
 p=[tuple(v[:2]) for v in p]
 if p[0]==p[-1]:p=p[:-1]
 if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))<0:p.reverse()
 return p
def edge(a,b,t):return [a[k]+(b[k]-a[k])*t for k in [0,1]]
def rect(w,d):return [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]
def step_rect(w,d,c=1.1):
 # Very shallow recessed corners, visible on the architect's phase-I photos.
 return [(-w/2+c,-d/2),(w/2-c,-d/2),(w/2-c,-d/2+c),(w/2,-d/2+c),(w/2,d/2-c),(w/2-c,d/2-c),(w/2-c,d/2),(-w/2+c,d/2),(-w/2+c,d/2-c),(-w/2,d/2-c),(-w/2,-d/2+c),(-w/2+c,-d/2+c)]
class Mesh:
 def __init__(self,name):self.name=name;self.v=[];self.f=[];self.m=[]
 def face(self,p,mi):
  i=len(self.v);self.v.extend(p);self.f.append(tuple(range(i,i+len(p))));self.m.append(mi)
 def prism(self,p,z0,z1,mi):
  p=ccw(p)
  for a,b in zip(p,p[1:]+p[:1]):self.face([(a[0],a[1],z0),(b[0],b[1],z0),(b[0],b[1],z1),(a[0],a[1],z1)],mi)
  vs=[Vector((x,y,0)) for x,y in p]
  for tri in tessellate_polygon([vs]):
   t=[vs[v] if isinstance(v,int) else v for v in tri];self.face([(v.x,v.y,z1) for v in t],mi);self.face([(v.x,v.y,z0) for v in reversed(t)],mi)
 def box(self,c,s,mi):
  x,y,z=c;w,d,h=s;self.prism([(x-w/2,y-d/2),(x+w/2,y-d/2),(x+w/2,y+d/2),(x-w/2,y+d/2)],z-h/2,z+h/2,mi)
 def beam(self,a,b,w,d,mi):
  a,b=Vector(a),Vector(b);v=b-a
  if v.length<.00001:return
  v.normalize();s=v.cross(Vector((0,0,1)))
  if s.length<.01:s=Vector((1,0,0))
  s.normalize();t=v.cross(s).normalized();p=[a+s*w*i+t*d*j for i,j in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]]+[b+s*w*i+t*d*j for i,j in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]]
  for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([p[i] for i in f],mi)
 def panel(self,a,b,z0,z1,n,depth,mi):
  self.face([(a[0]+n[0]*depth,a[1]+n[1]*depth,z0),(b[0]+n[0]*depth,b[1]+n[1]*depth,z0),(b[0]+n[0]*depth,b[1]+n[1]*depth,z1),(a[0]+n[0]*depth,a[1]+n[1]*depth,z1)],mi)
 def obj(self,col):
  mesh=bpy.data.meshes.new(self.name);mesh.from_pydata(self.v,[],self.f);mesh.update()
  for m in MAT:mesh.materials.append(m)
  for p,mi in zip(mesh.polygons,self.m):p.material_index=mi
  ob=bpy.data.objects.new(self.name,mesh);col.objects.link(ob);return ob
def collection(name):
 c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c
def each_edge(poly):
 p=ccw(poly)
 for i,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
  L=math.dist(a,b)
  if L>.05:yield i,a,b,L,((b[1]-a[1])/L,-(b[0]-a[0])/L)
def upright(m,p,n,z0,z1,w,d,mi,offset=.3):
 m.beam((p[0]+n[0]*offset,p[1]+n[1]*offset,z0),(p[0]+n[0]*offset,p[1]+n[1]*offset,z1),w,d,mi)
def fine_upright(m,p,n,z0,z1,w,mi,offset=.3):
 # Thin window mullions need only one visible face, not twelve box triangles.
 tangent=(-n[1],n[0]);a=(p[0]-tangent[0]*w/2,p[1]-tangent[1]*w/2);b=(p[0]+tangent[0]*w/2,p[1]+tangent[1]*w/2)
 m.panel(a,b,z0,z1,n,offset,mi)
def side_name(no):
 if abs(no[0])>abs(no[1]):return 'east' if no[0]>0 else 'west'
 return 'north' if no[1]>0 else 'south'
def offset_ring(poly,factor):return [(x*factor,y*factor) for x,y in poly]

def phase_one(b):
 n=b['tower'];w,d=b['widthM'],b['depthM'];top=b['mainTopM'];H=b['heightM'];p=step_rect(w,d)
 mass=Mesh(n+'_01_rectangular_bank_massing');bands=Mesh(n+'_02_pale_horizontal_bands');glass=Mesh(n+'_03_individual_bank_glazing');cols=Mesh(n+'_04_paired_column_axes');gallery=Mesh(n+'_05_open_middle_gallery');pent=Mesh(n+'_06_occupied_setback_penthouse');roof=Mesh(n+'_07_flat_cornice_and_roof')
 m0=b['mechanicalBandCentreM']-b['mechanicalBandHeightM']/2;m1=m0+b['mechanicalBandHeightM']
 mass.prism(p,0,7.4,14);mass.prism(p,7.4,m0,1);mass.prism(p,m1,top,1)
 mass.prism(rect(w-5.5,d-5.5),m0,m1,4)
 # The gallery is genuinely recessed and interrupted by a few large piers.
 for _,a,bb,L,no in each_edge(p):
  if L<5:continue
  gallery.panel(a,bb,m0-.6,m0+.2,no,.36,0);gallery.panel(a,bb,m1-.2,m1+.55,no,.36,0)
  for t in [0,.25,.75,1]:upright(gallery,edge(a,bb,t),no,m0,m1,1.0,.7,0,.10)
  gallery.panel(edge(a,bb,.25),edge(a,bb,.75),m0+.2,m0+.9,no,-.5,2)
 bodyfloors=b['floors']-(6 if n!='D' else 5)-2;fh=(top-7.4)/bodyfloors
 for ei,a,bb,L,no in each_edge(p):
  if L<5:
   cols.panel(a,bb,7.4,top,no,.18,0)
   continue
  banks=b['faceBankDivisions'][(ei//3)%4]
  for f in range(bodyfloors):
   z=7.4+f*fh
   if z<m1 and z+fh>m0:continue
   bands.panel(a,bb,z,z+.53,no,.32,0)
   # Repeating bank modules are consistent with visible apartment windows:
   # four slim panes, a lower transom, and one muted opening panel per bank.
   for j in range(banks):
    la,lb=edge(a,bb,(j+.055)/banks),edge(a,bb,(j+.945)/banks)
    glass.panel(la,lb,z+.55,min(z+fh-.08,top),no,.12,1)
    glass.panel(la,lb,z+.58,z+.94,no,.16,12)
    for k in [1,2,3]:
     q=edge(la,lb,k/4);fine_upright(glass,q,no,z+.55,min(z+fh-.10,top),.075,2,.27)
    glass.panel(la,lb,z+fh*.59,z+fh*.59+.065,no,.27,2)
    va,vb=edge(la,lb,.76),edge(la,lb,.97)
    glass.panel(va,vb,z+.99,min(z+fh-.18,top),no,.18,3)
  for j in range(banks+1):
   t=j/banks;delta=.13/L
   for dt in [-delta,delta]:
    q=edge(a,bb,max(0,min(1,t+dt)))
    upright(cols,q,no,7.4,m0,.16,.24,0,.33);upright(cols,q,no,m1,top,.16,.24,0,.33)
  # Ground-level tall glass lobby and a dark stone sill are not tiny apartments.
  mass.panel(a,bb,.35,1.1,no,.2,14);glass.panel(edge(a,bb,.05),edge(a,bb,.95),1.1,6.9,no,.20,1)
  for j in range(7):upright(cols,edge(a,bb,j/6),no,1.1,7.4,.27,.25,0,.33)
  roof.panel(a,bb,top-.40,top+.35,no,.65,5)
  if side_name(no)==b['courtyardSlotFace']:
   # Source59 seq3: continuous central blue slot bracketed by paired broad
   # pale piers, visibly different from seq4 outer horizontal-bank facades.
   sw=b['centralSlotWidthM'];pw=b['centralPierWidthM'];t0=.5-sw/(2*L);t1=.5+sw/(2*L)
   aa,zz=edge(a,bb,t0),edge(a,bb,t1)
   glass.panel(aa,zz,7.4,top,no,.57,1)
   for k in range(1,6):fine_upright(glass,edge(aa,zz,k/6),no,7.4,top,.10,2,.78)
   for f in range(bodyfloors):
    z=7.4+f*fh
    glass.panel(aa,zz,z,z+.09,no,.78,2)
    glass.panel(aa,zz,z+fh*.56,z+fh*.56+.07,no,.78,2)
    if f%4==0:bands.panel(aa,zz,z,z+.54,no,.82,0)
   for l,r in [(t0-pw/L,t0),(t1,t1+pw/L)]:
    la,lb=edge(a,bb,l),edge(a,bb,r)
    cols.panel(la,lb,0,top,no,1.0,0)
    for q in [la,lb]:upright(cols,q,no,0,top,.16,.8,5,.68)
    for z in range(5,int(top),3):cols.panel(la,lb,z,z+.028,no,1.02,2)
   gallery.panel(edge(a,bb,t0-pw/L),edge(a,bb,t1+pw/L),m0-.85,m1+.75,no,1.04,0)
 # Roof setback is occupied, with several clear storeys under a flat cap.
 pw,pd=w*b['penthouseWidthRatio'],d*b['penthouseDepthRatio'];pp=step_rect(pw,pd,.65);pt=b['penthouseTopM'];pent.prism(pp,top,pt,1)
 pn=6 if n!='D' else 5;pf=(pt-top)/pn
 for ei,a,bb,L,no in each_edge(pp):
  if L<3:
   pent.panel(a,bb,top,pt,no,.25,5);continue
  for j in range(pn):
   z=top+j*pf;pent.panel(a,bb,z,z+.73,no,.35,5)
   pent.panel(a,bb,z+.74,z+pf-.05,no,.11,1)
   pent.panel(a,bb,z+pf*.56,z+pf*.56+.09,no,.25,2)
  # Broad corner walls flank two apartment window banks. Two slender full-height
  # glass slots near the returns contrast with the much denser main shaft.
  for t0,t1 in [(0,.07),(.18,.235),(.48,.535),(.83,.885),(.97,1)]:pent.panel(edge(a,bb,t0),edge(a,bb,t1),top,pt,no,.42,5)
  for t in [.12,.28,.35,.42,.59,.66,.73,.93]:upright(pent,edge(a,bb,t),no,top,pt,.08,.10,2,.29)
  if side_name(no)==b['courtyardSlotFace']:
   sw=b['centralSlotWidthM'];pier=b['centralPierWidthM']*1.45;lo=.5-sw/(2*L);hi=.5+sw/(2*L)
   la,lb=edge(a,bb,lo),edge(a,bb,hi)
   pent.panel(la,lb,top,pt-.7,no,.63,1)
   for k in range(1,6):fine_upright(pent,edge(la,lb,k/6),no,top,pt-.7,.10,2,.78)
   for j in range(pn):pent.panel(la,lb,top+j*pf,top+j*pf+.12,no,.8,2)
   for aa,zz in [(lo-pier/L,lo),(hi,hi+pier/L)]:pent.panel(edge(a,bb,aa),edge(a,bb,zz),top,pt,no,.93,5)
   pent.panel(la,lb,pt-3.6,pt-.7,no,.79,4)
 roof.prism(offset_ring(p,.998),top+.015,top+.035,15)
 roof.prism(step_rect(pw+1.15,pd+1.15,.7),pt,H-.3,5)
 roof.prism(rect(pw*.72,pd*.70),H-.30,H,15)
 return [mass,bands,glass,cols,gallery,pent,roof]

def phase_two(b):
 n=b['tower'];mass=Mesh(n+'_01_angular_stepped_five_part_body');bands=Mesh(n+'_02_broad_white_spandrels');glaze=Mesh(n+'_03_reentrant_blue_banks');stone=Mesh(n+'_04_solid_core_and_vent_axes');crowns=Mesh(n+'_05_open_triangular_roof_frames');arches=Mesh(n+'_06_two_open_roof_arches');base=Mesh(n+'_07_ground_lobby')
 for wi,wing in enumerate(b['wings']):
  p=wing['polygon'];h=wing['topM'];mass.prism(p,0,h,7)
  for ei,a,bb,L,no in each_edge(p):
   count=max(2,round(L/2.4));fh=3.38
   for f in range(int((h-7.1)/fh)):
    z=7.1+f*fh
    bands.panel(a,bb,z,z+.80,no,.34,6)
    glaze.panel(a,bb,z+.82,z+fh-.10,no,.13,7)
    glaze.panel(a,bb,z+fh*.56,z+fh*.56+.075,no,.27,2)
    for k in range(1,count):fine_upright(glaze,edge(a,bb,k/count),no,z+.82,z+fh-.10,.075,2,.25)
    # The photographs show dark vent stripes in the middle of broad banks,
    # not random colour panes or identical boxed windows.
    if L>12:glaze.panel(edge(a,bb,.44),edge(a,bb,.495),z+.82,z+fh-.10,no,.29,8)
   for t in [0,1]:upright(stone,edge(a,bb,t),no,7.1,h,.70,.45,6,.30)
   # Two large solid mechanical/spandrel breaks and occasional blank returns.
   for z in [36.5,109]:
    if h>z+2.6:stone.panel(a,bb,z,z+2.6,no,.42,6)
   if wi==0 and L>30:
    stone.panel(edge(a,bb,.0),edge(a,bb,.19),7.1,h,no,.47,6)
    for j in range(10,int(h-7),7):glaze.panel(edge(a,bb,.065),edge(a,bb,.125),j,j+1.55,no,.50,8)
   base.panel(a,bb,0,1.1,no,.2,14);base.panel(a,bb,1.1,6.5,no,.18,7);base.panel(a,bb,6.5,7.1,no,.4,6)
   crowns.panel(a,bb,h-.6,h+.45,no,.48,9)
  crowns.prism(offset_ring(p,.998),h+.01,h+.03,15)
  # Lower shoulders have a large triangular open white screen at their top,
  # spanning a whole facade bay rather than repeating tiny gables.
  if wi in [1,4]:
   candidates=[e for e in each_edge(p) if e[3]>18]
   ei,a,bb,L,no=max(candidates,key=lambda e:e[3]);aa=edge(a,bb,.10);cc=edge(a,bb,.90);mid=edge(a,bb,.5);z=h+.45;rise=8.5
   crowns.beam((*aa,z),(*mid,z+rise),.85,.55,9);crowns.beam((*mid,z+rise),(*cc,z),.85,.55,9)
   crowns.beam((*aa,z),(*cc,z),.65,.55,9);upright(crowns,mid,no,z,z+rise,.65,.55,9,0)
 # Tall rooftop shoulders bracket an actually open longitudinal arch canopy.
 # Its low glazed plant enclosure is recessed below the arch rather than a cone.
 mass.prism([(-8,-19),(-2,-19),(-2,19),(-8,19)],181,189.5,6)
 mass.prism([(3,-18),(8,-18),(8,18),(3,18)],181,185.8,7)
 # SAMOO60 seq3/59 seq4: the largely solid top screen is interrupted near
 # one upper corner by a dark opening and a blue window band beneath it.
 # Only these observed openings and their immediate return are reconstructed;
 # the unverified reverse face stays stone, not a repeated facade pattern.
 ca,cb=(-8,16),(-8,7);cn=(-1,0)
 glaze.panel(ca,cb,185.65,188.65,cn,.27,8)
 glaze.panel(ca,cb,182.3,184.9,cn,.27,7)
 for t in [.25,.5,.75]:
  fine_upright(glaze,edge(ca,cb,t),cn,185.65,188.65,.08,2,.33)
  fine_upright(glaze,edge(ca,cb,t),cn,182.3,184.9,.08,2,.33)
 crowns.panel(ca,cb,184.9,185.2,cn,.31,6)
 ra,rb=(-2.35,19),(-7.65,19);rn=(0,1)
 glaze.panel(ra,rb,182.3,184.9,rn,.26,7)
 for t in [1/3,2/3]:fine_upright(glaze,edge(ra,rb,t),rn,182.3,184.9,.08,2,.32)
 for x in [-7.6,7.6]:
  for j in range(24):
   t0=j/24;t1=(j+1)/24
   def arch(t):return (x,-18+36*t,183+7.75*math.sin(math.pi*t))
   arches.beam(arch(t0),arch(t1),.38,.42,9)
 for j in range(9):
  t=j/8;y=-18+36*t;z=183+7.75*math.sin(math.pi*t)
  arches.beam((-7.6,y,z),(7.6,y,z),.24,.25,9)
 # Crown top must include the documented191m datum, with no invented mast.
 for y in [-18,18]:crowns.box((-5,y,190.35),(6.5,.75,1.30),6)
 return [mass,bands,glaze,stone,crowns,arches,base]

def segment_distance(p,a,b):
 ax,ay=a;bx,by=b;dx,dy=bx-ax,by-ay;t=max(0,min(1,((p[0]-ax)*dx+(p[1]-ay)*dy)/(dx*dx+dy*dy)))
 return math.hypot(p[0]-ax-t*dx,p[1]-ay-t*dy)
def phase_three(b):
 mass=Mesh('G_01_three_unequal_Y_blades');lines=Mesh('G_02_fine_silver_horizontal_curtainwall');fins=Mesh('G_03_deep_vertical_blade_fins');glaze=Mesh('G_04_blue_glazing_and_spandrels');louvers=Mesh('G_05_reentrant_dark_louver_channels');crown=Mesh('G_06_independent_flat_blade_terminations');base=Mesh('G_07_green_stone_glazed_lobby')
 source=ccw(b['sourceFootprint'])
 for wi,wing in enumerate(b['wings']):
  p=wing['polygon'];h=wing['topM'];body=h-3.7;mass.prism(p,0,body,10)
  for ei,a,bb,L,no in each_edge(p):
   mid=edge(a,bb,.5);outside=min(segment_distance(mid,sa,sb) for sa,sb in zip(source,source[1:]+source[:1]))<.12
   # Partition seams become exposed glass only above the lower adjacent blade;
   # they are otherwise interior and must not create false fins at the core.
   zbase=7.3 if outside else 217
   if zbase>=body:continue
   short_return=L<3.7 and outside
   material_id=13 if short_return else 10
   glaze.panel(a,bb,zbase,body,no,.13,material_id)
   fh=3.64
   for f in range(int((body-7.3)/fh)):
    z=7.3+f*fh
    if z<zbase:continue
    glaze.panel(a,bb,z,z+.49,no,.22,12 if not short_return else 13)
    lines.panel(a,bb,z+.03,z+.19,no,.37,11)
    if short_return:
     for k in range(4):lines.panel(a,bb,z+.60+k*.64,z+.65+k*.64,no,.39,11)
    else:
     lines.panel(a,bb,z+fh*.56,z+fh*.56+.06,no,.28,11)
   if outside:
    # At each actual serrated bay break a strong white fin; broad glazing is
    # subdivided by quiet mullions rather than one repeated generic grid.
    fin_top=h if short_return else h-.35
    upright(fins,a,no,7.3,fin_top,.27,.64,11,.38)
    count=max(1,round(L/2.7))
    for k in range(1,count):upright(fins,edge(a,bb,k/count),no,7.3,body,.09,.15,11,.28)
    if L>5 and (abs(mid[0])<19 and abs(mid[1])<20):
     la,lb=edge(a,bb,.0),edge(a,bb,.18);louvers.panel(la,lb,7.3,body,no,.39,13)
     for z in range(8,int(body),2):louvers.panel(la,lb,z,z+.12,no,.47,11)
   # Fine metal screen extends to each lobe's own height, with no common spire.
   glazing_top=h-(2.2 if short_return else 1.35)
   crown.panel(a,bb,body,glazing_top,no,.12,13 if short_return else 10)
   crown.panel(a,bb,glazing_top-.12,glazing_top,no,.39,11)
   if outside:
    for j in range(max(1,round(L/3))+1):upright(crown,edge(a,bb,j/max(1,round(L/3))),no,body,glazing_top+.15,.12,.22,11,.30)
   for zz in [58.0,202.0]:
    if outside and zz+3.0<body:
     louvers.panel(a,bb,zz,zz+2.2,no,.40,13)
     for dz in [.4,.9,1.4,1.9]:louvers.panel(a,bb,zz+dz,zz+dz+.11,no,.46,11)
  crown.prism(offset_ring(p,.985),body-.2,body,15)
 for _,a,bb,L,no in each_edge(source):
  base.panel(a,bb,0,.9,no,.25,14)
  base.panel(a,bb,.9,6.9,no,.20,10 if L>4 else 14)
  base.panel(a,bb,6.9,7.3,no,.38,14)
  if L>4:
   for j in range(max(2,round(L/2.5))+1):upright(base,edge(a,bb,j/max(2,round(L/2.5))),no,.9,7.3,.13,.18,11,.33)
 return [mass,lines,fins,glaze,louvers,crown,base]

assets=[]
for b in recipe['buildings']:
 col=collection('TOWER_PALACE_'+b['tower']+'_PHASE_'+b['phase']);builders=phase_one(b) if b['phase']=='I' else phase_two(b) if b['phase']=='II' else phase_three(b)
 objects=[m.obj(col) for m in builders if m.v]
 for ob in objects:ob.rotation_euler.z=math.radians(b['yawDeg']);ob['tower']=b['tower'];ob['phase']=b['phase'];ob['basis']=b['featureBasis']
 bpy.ops.object.select_all(action='DESELECT')
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
 f=OUT/(b['id']+'.glb');bpy.ops.export_scene.gltf(filepath=str(f),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_extras=True)
 lo=[min(v.co[i] for ob in objects for v in ob.data.vertices) for i in range(3)];hi=[max(v.co[i] for ob in objects for v in ob.data.vertices) for i in range(3)]
 info={k:b[k] for k in ['id','nameKo','coordinate','footprintIds','supersedes','referenceUrl','heightM','heightBasis','floors','floorsBasis','uncertainties']}
 info.update(file=str(f),blendSource=str(OUT/'tower-palace-authored.blend'),category='apartment',components=[ob.name for ob in objects],triangles=sum(len(p.vertices)-2 for ob in objects for p in ob.data.polygons),
  bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),boundsBlenderXYZ=[lo,hi],dimensionsGlbXYZ=[hi[0]-lo[0],hi[2]-lo[2],hi[1]-lo[1]],minGlbY=lo[2],blendSceneOffsetEN=b['siteEN'])
 assets.append(info)
 for ob in objects:ob.location.x+=b['siteEN'][0];ob.location.y+=b['siteEN'][1]

# Review scene is never included in an individual exported GLB.
review=collection('REVIEW_ONLY_NOT_EXPORTED');ground=Mesh('Review grey ground');ground.box((0,0,-.5),(650,650,.5),16);ground.obj(review)
scene=bpy.context.scene;world=scene.world or bpy.data.worlds.new('Tower Palace daylight');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.73,.80,.90,1);world.node_tree.nodes['Background'].inputs[1].default_value=.8
ld=bpy.data.lights.new('Review daylight sun','SUN');ld.energy=2.5;ld.angle=.16;sun=bpy.data.objects.new('Review daylight sun',ld);review.objects.link(sun);sun.rotation_euler=(.55,-.48,-.65)
cd=bpy.data.cameras.new('Review camera');cam=bpy.data.objects.new('Review camera',cd);review.objects.link(cam);scene.camera=cam
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1500;scene.render.resolution_y=1200;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
def view(name,eye,target,scale):
 cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cd.type='ORTHO';cd.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
def tower_view(n,name,delta,target_z,scale):
 hidden=[]
 for col in bpy.data.collections:
  if col.name.startswith('TOWER_PALACE_') and not col.name.startswith('TOWER_PALACE_'+n+'_'):
   hidden.append((col,col.hide_render));col.hide_render=True
 b=next(b for b in recipe['buildings'] if b['tower']==n);x,y=b['siteEN'];view(name,(x+delta[0],y+delta[1],delta[2]),(x,y,target_z),scale)
 for col,state in hidden:col.hide_render=state
view('review-complex-south',(350,-680,325),(0,5,125),570)
view('review-complex-north',(-450,650,380),(0,8,122),560)
view('review-plan',(0,7,950),(0,7,0),575)
tower_view('B','review-I-penthouse',(-145,-135,260),206,145)
tower_view('A','review-I-open-gallery',(100,-150,123),107,80)
tower_view('B','review-I-courtyard-slot',(-190,-90,170),121,325)
tower_view('E','review-II-open-crown',(-160,-160,228),171,160)
tower_view('G','review-III-Y-blades',(165,-255,210),177,215)
tower_view('G','review-III-upper',(150,-200,301),230,125)
eye=Vector((350,-680,325));target=Vector((0,5,125))
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   sp=area.spaces.active;sp.shading.type='MATERIAL';sp.clip_end=3000;sp.region_3d.view_location=target;sp.region_3d.view_distance=620;sp.region_3d.view_rotation=(eye-target).to_track_quat('Z','Y');sp.region_3d.view_perspective='ORTHO'
bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'tower-palace-authored.blend'))
bundle={'siteId':'tower-palace','assets':assets,'sources':recipe['sources'],'recipeFiles':['recipe-input.json','claimed-source-buildings.json','source-observations.json'],'retainedUntouchedSourceFootprintIds':[],
 'places':[{'id':'bespoke-tower-palace','name':'도곡 타워팰리스 A–G','subtitle':'1·2·3차 일곱 동 · 공식 건축사진과 동별 위치 기반','center':recipe['origin'],'zoom':16.2,'source_url':'https://www.samoo.com/home/works/view.do?cntntsSn=59','supersedesPlaceIds':['model:reference-flight-tower-palace','model:apt-a13585402','model:apt-a13585403','seoul-apartment:A13585402','seoul-apartment:A13585403']}],
 'authoredVia':'Real Blender MCP execute_blender_code, dedicated port9877','blenderVersion':bpy.app.version_string,'sourcesAreEmbedded':False,
 'renders':['review-complex-south.png','review-complex-north.png','review-plan.png','review-I-penthouse.png','review-I-open-gallery.png','review-I-courtyard-slot.png','review-II-open-crown.png','review-III-Y-blades.png','review-III-upper.png'],
 'scope':'Only seven independently named residential towers. Unidentified sports centre, retail podia, landscapes and public roads remain unclaimed.'}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'siteId':bundle['siteId'],'assets':[{'id':a['id'],'triangles':a['triangles'],'heightM':a['heightM'],'bytes':a['bytes']} for a in assets]},ensure_ascii=False))
