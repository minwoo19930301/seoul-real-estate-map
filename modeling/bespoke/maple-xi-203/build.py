"""Maple203 individually authored southern6lineL facades. Shared code below is neutral mesh/vector math only."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
O=Path(__file__).parent;D=json.loads((O/'authored-input.json').read_text());V=[Vector(p)for p in D['ringEN']];N=len(V)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
colors={'pale':(.835,.83,.795,1),'metal':(.40,.455,.47,1),'glass':(.075,.125,.15,1),'shade':(.045,.075,.09,1),'stone':(.53,.515,.45,1),'grayfield':(.39,.435,.435,1),'seam':(.36,.37,.355,1),'roof':(.40,.415,.40,1),'solar':(.035,.058,.078,1),'pvtrim':(.35,.38,.39,1)};materials={}
for name,color in colors.items():
 m=bpy.data.materials.new('Maple203_'+name);m.diffuse_color=color;m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=color;p.inputs['Metallic'].default_value=.58 if name=='metal' else (.2 if name in ['glass','pvtrim'] else .015);p.inputs['Roughness'].default_value=.38 if name in ['metal','glass'] else .70;materials[name]=m
class Solid:
 def __init__(self,name,mat):self.name=name;self.mat=mat;self.verts=[];self.faces=[]
 def prism(self,polygon,low,high):
  p=[Vector((x,y,0)) for x,y in polygon];n=len(p);start=len(self.verts);self.verts.extend((q.x,q.y,z) for z in [low,high] for q in p);index={tuple(q):i for i,q in enumerate(p)}
  for tr in tessellate_polygon([p]):
   ids=[q if isinstance(q,int) else index[tuple(q)] for q in tr];self.faces.extend([tuple(start+i for i in ids[::-1]),tuple(start+n+i for i in ids)])
  for i in range(n):self.faces.append((start+i,start+(i+1)%n,start+(i+1)%n+n,start+i+n))
 def wall(self,a,b,low,high,thick):
  a,b=Vector(a),Vector(b);u=(b-a).normalized();n=Vector((-u.y,u.x))*thick/2;self.prism([a+n,b+n,b-n,a-n],low,high)
 def box(self,c,w,d,low,high,angle):
  u=Vector((math.cos(angle),math.sin(angle)));n=Vector((-u.y,u.x));c=Vector(c);self.prism([c+u*x+n*y for x,y in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]],low,high)
 def finish(self):
  me=bpy.data.meshes.new(self.name);me.from_pydata(self.verts,[],self.faces);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new('Maple203_'+self.name,me);bpy.context.collection.objects.link(o);me.materials.append(materials[self.mat]);o['asset_id']=D['id'];return o
parts={}
def part(name,mat):
 if (name,mat) not in parts:parts[name,mat]=Solid(name,mat)
 return parts[name,mat]
def basis(e):
 u=(V[(e+1)%N]-V[e]).normalized();return u,Vector((-u.y,u.x)),math.atan2(u.y,u.x)
def point(e,t,offset=0):return V[e]+(V[(e+1)%N]-V[e])*t+basis(e)[1]*offset
def panel(e,l,r,z0,z1,name,mat,offset=0,thick=.12):part(name,mat).wall(point(e,l,offset),point(e,r,offset),z0,z1,thick)
def post(e,t,z0,z1,w,name,mat,offset=0,depth=.16):part(name,mat).box(point(e,t,offset),w,depth,z0,z1,basis(e)[2])
def inset(d):
 p=[]
 for i in range(N):
  a,b,c=V[(i-1)%N],V[i],V[(i+1)%N];u=(b-a).normalized();v=(c-b).normalized();x=b-Vector((-u.y,u.x))*d;y=b-Vector((-v.y,v.x))*d;q=y-x;den=u.x*v.y-u.y*v.x;t=(q.x*v.y-q.y*v.x)/den;p.append(x+u*t)
 return p
base=4.9;pitch=2.95;rows=18;roof=58.0
part('203_inset_structural_body','pale').prism(inset(2.7),base,roof-.22)
part('203_L_roof_slab','roof').prism(V,roof-.22,roof)
part('203_ground_recessed_body','stone').prism(inset(4.2),0,base)
# Each list below was authored against this203photograph, notanother building's array.
def openbank(e,l,r,z,sill,h,material,name,depth=-.28,mullion=None):
 panel(e,l,r,z,z+sill,name+'_sillwall',material,-.02,.24)
 panel(e,l,r,z+sill+h,z+pitch,name+'_headwall',material,-.02,.24)
 panel(e,l+.002,r-.002,z+sill,z+sill+h,name+'_glass','glass',depth,.055)
 panel(e,l,r,z+sill-.035,z+sill+.035,name+'_silllip',material,.055,.34)
 if mullion is not None:post(e,l+(r-l)*mullion,z+sill,z+sill+h,.066,name+'_sash','metal',depth+.10,.12)
def metalbank(e,l,r,z,sill,h,name,wide=False):
 panel(e,l,r,z,z+sill,name+'_solid_spandrel','metal',.08,.24)
 panel(e,l,r,z+sill+h,z+pitch,name+'_solid_upperpanel','metal',.08,.24)
 panel(e,l+.003,r-.003,z+sill,z+sill+h,name+'_recessed_glass','glass',-.31,.055)
 for t in [l,r]:post(e,t,z,z+pitch,.115,name+'_projecting_rib','metal',.15,.36)
 post(e,l+(r-l)*(.61 if wide else .44),z+sill,z+sill+h,.065,name+'_offcentre_sash','metal',-.13,.17)
 panel(e,l,r,z+sill-.06,z+sill+.025,name+'_projected_sill','metal',.13,.38)
 panel(e,l,r,z+sill+h-.04,z+sill+h+.025,name+'_head_recess','shade',-.09,.17)
# NEend W41/W43: threealuminumwindowstacks shareplane withtwo plainbedrooms.
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<4 else'pale'
 panel(3,0,1,z,z+pitch,'NE_end_recess_back','shade',-.90,.13)
 white=[(.035,.19),(.265,.425)];last=0
 for l,r in white:
  panel(3,last,l,z,z+pitch,'NE_bedroom_opaque_piers',pm,.015,.25);last=r
  openbank(3,l,r,z,.45,2.27,pm,'NE_plain_bedroom',-.32,.59)
 panel(3,last,.465,z,z+pitch,'NE_bedroom_opaque_piers',pm,.015,.25)
 # W41 services have unevenopaque panel/glassheights; noalternate215box motif.
 last=.465
 for j,(l,r) in enumerate([(.505,.605),(.638,.73),(.775,.973)]):
  panel(3,last,l,z,z+pitch,'NE_metal_opaque_piers','metal',.09,.25);last=r
  sill,h=((.28,2.37)if j==2 else((.43,2.08)if k<6 else(.86,1.62)))
  metalbank(3,l,r,z,sill,h,'NE_metal_'+str(j),j==2)
 panel(3,last,1,z,z+pitch,'NE_metal_opaque_piers','metal',.09,.25)
# SElong B/W43: sourcephoto order SWleft→NEright. Physicaledge runsopposite.
def se(l,r):return 1-r,1-l
secols=[(.02,.129,'wide'),(.164,.192,'small'),(.234,.256,'small'),(.289,.304,'slot'),(.415,.521,'wide'),(.554,.583,'small'),(.623,.646,'small'),(.677,.692,'slot'),(.716,.794,'mid')]
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<4 else'pale'
 panel(4,0,1,z,z+pitch,'SE_recess_back','shade',-.91,.13)
 last=0
 for l,r,kind in secols:
  if l>last:
   intervals=[(last,l)]
   if last<.396 and l>.325:intervals=[(last,min(l,.325)),(max(last,.396),l)]
   for aa,bb in intervals:
    if bb>aa:a,b=se(aa,bb);panel(4,a,b,z,z+pitch,'SE_unequal_pale_piers',pm,.0,.24)
  a,b=se(l,r);sill,h=(.59,2.01)if kind=='wide'else((.81,1.73)if kind=='small'else((1.18,.83)if kind=='slot'else(.62,1.99)))
  if k==17 and l==.164:r=.256;a,b=se(l,r);h=2.01;sill=.59
  if not(k==17 and l==.234):openbank(4,a,b,z,sill,h,pm,'SE_'+kind, -.30,.59 if kind=='wide'else None)
  last=r
 a,b=se(last,.813);panel(4,a,b,z,z+pitch,'SE_pale_glass_boundary',pm,.0,.24)
 # Narrowdeepcentralshaft belongswithinSWwhitegroup range. Overridewhiteback withactualinsetglass.
 a,b=se(.325,.396);panel(4,a,b,z+.12,z+2.75,'SE_central_dark_infill_glass','glass',-.45,.065)
 for t in [.325,.396]:post(4,1-t,z,z+pitch,.14,'SE_central_shaft_lateral_reveal','metal',.10,.32)
 panel(4,a,b,z+.10,z+.64,'SE_central_shaft_opaque_spandrel','metal',.10,.24)
 # BroadNEdarkwrap hasfourunequalglasslanes; continuousframebutrealspandrels.
 last=.813
 for j,(l,r) in enumerate([(.821,.864),(.87,.91),(.917,.951),(.958,.99)]):
  a,b=se(last,l);panel(4,a,b,z,z+pitch,'SE_wrap_metal_piers','metal',.08,.22)
  a,b=se(l,r);metalbank(4,a,b,z,.43 if k%3 else .64,2.16 if k%3 else 1.95,'SE_wrap_'+str(j),j==0);last=r
 a,b=se(last,1);panel(4,a,b,z,z+pitch,'SE_wrap_edge_pier','metal',.09,.24)
# SWlong B: eightunequalwhitebanks thenthree-columnmetalcorner. Edge runsSE→NW.
swcols=[(.021,.071,'mid'),(.09,.197,'wide'),(.228,.263,'small'),(.299,.334,'small'),(.375,.410,'small'),(.444,.551,'wide'),(.584,.619,'small'),(.658,.693,'small')]
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<4 else'pale';panel(5,0,1,z,z+pitch,'SW_recess_back','shade',-.72,.13);last=0
 for l,r,kind in swcols:
  panel(5,1-l,1-last,z,z+pitch,'SW_unequal_white_piers',pm,.025,.24)
  openbank(5,1-r,1-l,z,.56 if kind=='wide'else .72,2.10 if kind=='wide'else 1.84,pm,'SW_'+kind,-.25,.61 if kind=='wide'else None);last=r
 panel(5,1-.726,1-last,z,z+pitch,'SW_white_end_pier',pm,.025,.24)
 for j,(l,r) in enumerate([(.736,.81),(.822,.876),(.89,.986)]):metalbank(5,1-r,1-l,z,.42,2.18,'SW_corner_metal_'+str(j),j==2)
 for l,r in [(.726,.736),(.81,.822),(.876,.89),(.986,1)]:panel(5,1-r,1-l,z,z+pitch,'SW_corner_opaque_piers','metal',.1,.24)
# InnerNEwing NWface: roundedblankcore nextNEbedrooms;fullheightcentralshaft andpairedinnerwindows W41.
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<4 else'pale'
 # e2 startsinnerL towardNEend; slots near both coreprojections.
 banks=[(.08,.155,'window'),(.205,.28,'window'),(.385,.439,'shaft'),(.47,.502,'slot'),(.875,.92,'slot')];last=0
 panel(2,0,1,z,z+pitch,'NW_core_deep_back','shade',-1.12,.13)
 for l,r,kind in banks:
  panel(2,last,l,z,z+pitch,'NW_blank_core_wall',pm,.055,.36);last=r
  if kind=='shaft':openbank(2,l,r,z,.29,2.32,pm,'NW_deep_core_shaft',-.82,.55)
  elif kind=='slot':openbank(2,l,r,z,1.02,1.07,pm,'NW_small_core_slot',-.30,None)
  else:openbank(2,l,r,z,.70,1.96,pm,'NW_inner_pair',-.30,.62)
 panel(2,last,1,z,z+pitch,'NW_blank_core_wall',pm,.055,.36)
 for zz in [z+.13,z+pitch-.018]:
  last=0
  for l,r,_ in banks:
   panel(2,last,l,zz,zz+.017,'NW_core_horizontal_panel_joint','seam',.245,.018);last=r
  panel(2,last,1,zz,zz+.017,'NW_core_horizontal_panel_joint','seam',.245,.018)
 for t in [.32,.57,.69,.80]:post(2,t,z,z+pitch,.018,'NW_core_vertical_panel_joint','seam',.245,.018)
# InnerSWarm partialW41/A: blankprojection+threeunequalstacks andsmallslots.
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<4 else'pale';last=0
 banks=[(.095,.165),(.27,.35),(.49,.565),(.79,.837),(.90,.932)]
 for j,(l,r) in enumerate(banks):
  panel(1,last,l,z,z+pitch,'NE_inner_SWarm_blankwall',pm,.02,.30);last=r
  openbank(1,l,r,z,.77 if j<3 else 1.20,1.89 if j<3 else .83,pm,'NE_inner_SWarm_windows',-.31,.6 if j<3 else None)
 panel(1,last,1,z,z+pitch,'NE_inner_SWarm_blankwall',pm,.02,.30)
# FarNWend isobscuredinretainedgroundphotos: restrained provisionalpale/windowface.
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<4 else'pale';last=0
 for l,r in [(.08,.225),(.34,.49),(.65,.9)]:
  panel(0,last,l,z,z+pitch,'NW_end_unverified_piers',pm,.01,.24);last=r;openbank(0,l,r,z,.71,1.90,pm,'NW_end_provisional_opening',-.25,.61)
 panel(0,last,1,z,z+pitch,'NW_end_unverified_piers',pm,.01,.24)
# Ground: actualW41/W43stoneplinth andsmallwindows; BSWface openpiloti intervals.
for e in [0,1,2]:panel(e,0,1,0,base,'partially_unseen_ground_stone','stone',-.08,.45)
for e,banks in [(3,[(.07,.13),(.30,.355),(.62,.76)]),(4,[(.12,.19),(.28,.325),(.36,.41),(.47,.51),(.57,.61),(.675,.90)])]:
 last=0
 for j,(l,r) in enumerate(banks):
  panel(e,last,l,0,base,'observed_ground_stone_piers','stone',.01,.40);last=r
  big=(e==4 and j==5)
  sill=0 if big else 1.28;head=3.2 if big else 2.17
  if sill:panel(e,l,r,0,sill,'ground_window_lowerwall','stone',.01,.4)
  panel(e,l,r,head,base,'ground_window_headwall','stone',.01,.4)
  panel(e,l+.002,r-.002,sill,head,'ground_recessed_glass','glass',-1.85 if big else-.33,.065)
 panel(e,last,1,0,base,'observed_ground_stone_piers','stone',.01,.4)
# SWpiloti isseeninB; openings are between photoestimatedwidepairedpiers.
for l,r in [(0,.09),(.235,.29),(.45,.51),(.68,.73),(.93,1)]:panel(5,l,r,0,base,'SW_photo_piloti_stone_piers','stone',-.08,.72)
panel(5,0,1,3.9,base,'SW_piloti_horizontal_stone_beam','stone',-.08,.70)
# Threeindividuallyplacedplants, metricheightestimatedwithinregisterenvelope.
def roofbox(e,t,inward,w,d,z0,z1,name):
 c=point(e,t,-inward);u,n,a=basis(e);part(name,'pale').box(c,w,d,z0,z1,a);return c,u,n,a
for e,t,inward,w,d,top,name,slot in [(5,.83,8.5,5.8,5.4,62.15,'SW_outer_plant',(.0,1.0)),(4,.58,9.1,5.5,5.2,62.35,'central_L_junction_plant',(.25,.70)),(4,.13,8.5,7.1,5.1,61.95,'NE_end_plant',(-.7,.8))]:
 c,u,n,a=roofbox(e,t,inward,w,d,roof,top-.14,name);part(name+'_cap','seam').box(c,w+.13,d+.13,top-.14,top,a)
 x,width=slot;part(name+'_visible_aperture','shade').wall(c+u*(x-width/2)+n*(d/2+.02),c+u*(x+width/2)+n*(d/2+.02),top-2.1,top-1.13,.04)
 if name=='central_L_junction_plant':part('central_plant_lower_tall_slot','shade').wall(c-u*.44+n*(d/2+.02),c+u*.22+n*(d/2+.02),roof+.3,roof+2.1,.04)
# SourceB longSWbank andNEhalfSEbank distinctlengths. Panelrowsraise towardinnerroof.
for e,t,inn,length,width,name in [(5,.56,4.7,32.8,5.2,'SW_long_PV'),(4,.235,4.4,18.4,6.5,'NE_half_SE_PV')]:
 u,n,ang=basis(e);c=point(e,t,-inn);count=round(length/1.45)
 for i in range(count):
  for j in range(4):
   q=c+u*((i+.5)*length/count-length/2)-n*((j+.5)*width/4-width/2);z=roof+.32+j*.27;part(name+'_frame','pvtrim').box(q,length/count-.025,width/4-.025,z,z+.10,ang);part(name+'_cells','solar').box(q,length/count-.10,width/4-.10,z+.10,z+.145,ang)
#203 roundedthickwhiteuprights withroundfoldedheads visibleB; endsmetalrail+openfins.
for e in range(N):
 a,b=V[e],V[(e+1)%N];u,n,ang=basis(e);start=a+u*.65;end=b-u*.65;count=max(2,round((end-start).length/.47))
 if e in [1,2]:
  #A/BinnerLedgesarethinmetalguardrails, notfrontwhitefins.
  count=max(2,round((end-start).length/1.25))
  for i in range(count):part('inner_L_thin_guardrail_posts','metal').box(start+(end-start)*(i/(count-1)),.055,.055,roof+.05,roof+1.16,ang)
  for z in [roof+.18,roof+.62,roof+1.14]:part('inner_L_horizontal_guardrail','metal').wall(start,end,z,z+.045,.045)
  continue
 for i in range(count):
  t=i/(count-1);q=start+(end-start)*t;top=60.55
  #SEcentralopennotch aroundnarrowshaft leavesclearbetweenbanks, no inventedextra floor.
  if e==4 and .59<t<.68:continue
  part('203_thick_rounded_roof_fins','pale').box(q,.15,.28,roof+.10,top-.12,ang)
  part('203_folded_fin_roundhead','pale').box(q-n*.10,.15,.46,top-.17,top,ang)
 for z in [roof+.10,60.38]:part('203_open_crown_thin_ties','metal').wall(start,end,z,z+.055,.07)
 p=b-u*.65;q=b+(V[(e+2)%N]-b).normalized()*.65;pts=[]
 for j in range(7):
  t=j/6;v=(1-t)**2*p+2*(1-t)*t*b+t*t*q;pts.append(v)
  if j<6:part('203_rounded_corner_uprights','pale').box(v,.14,.25,roof+.10,60.50,ang+(basis((e+1)%N)[2]-ang)*t)
 for p,q in zip(pts,pts[1:]):part('203_rounded_corner_rail','metal').wall(p,q,60.38,60.44,.065)
objects=[s.finish()for s in parts.values()if s.verts]
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0];bpy.ops.export_scene.gltf(filepath=str(O/'bespoke-maple-xi-203.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_materials='EXPORT')
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=1200;s.render.resolution_y=1400;s.render.resolution_percentage=100;s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.69,.73,.79,1);s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.60;s.view_settings.view_transform='AgX'
def camera(name,loc,target,scale,persp=False):
 d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='PERSP'if persp else'ORTHO';d.ortho_scale=scale;d.lens=46
camera('B_south_primary_match',(90,-165,150),(0,0,29),98)
camera('A_east_primary_match',(210,45,145),(0,0,29),98)
camera('W41_North_end',(5,135,3),(0,0,29),95,True)
camera('W43_East_corner',(155,15,3),(0,0,29),95,True)
camera('Roof_three_individual_plants',(90,-165,180),(0,0,58),86)
camera('Ground_NE_stone',(110,80,10),(15,10,8),43)
camera('Inner_L_core',(-70,140,100),(0,0,29),98)
camera('SE_window_depth_detail',(140,-100,35),(7,-2,34),39)
bpy.ops.object.light_add(type='SUN',location=(80,-60,150));bpy.context.object.rotation_euler=(.45,-.35,-.45);bpy.context.object.data.energy=1.8;bpy.context.object.data.angle=.14
bpy.ops.object.light_add(type='AREA',location=(-80,80,150));bpy.context.object.data.energy=75000;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=130
s.camera=bpy.data.objects['B_south_primary_match'];bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-203.blend'))
(O/'build-summary.json').write_text(json.dumps({'id':D['id'],'components':[{'name':o.name,'vertices':len(o.data.vertices),'polygons':len(o.data.polygons)}for o in objects],'groundM':0,'roofM':roof,'maxEnvelopeM':62.35},indent=2));print('MAPLE203_BUILT',len(objects))
