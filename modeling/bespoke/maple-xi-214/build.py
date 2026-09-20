"""Maple214 individually authored H2 facades. Shared code below is neutral mesh/vector math only."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
O=Path(__file__).parent;D=json.loads((O/'authored-input.json').read_text());V=[Vector(p)for p in D['ringEN']];N=len(V)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
colors={'pale':(.82,.815,.78,1),'metal':(.45,.49,.51,1),'glass':(.075,.125,.15,1),'shade':(.045,.075,.09,1),'stone':(.31,.325,.32,1),'grayfield':(.39,.435,.435,1),'seam':(.36,.37,.355,1),'roof':(.40,.415,.40,1),'solar':(.035,.058,.078,1),'pvtrim':(.35,.38,.39,1)};materials={}
for name,color in colors.items():
 m=bpy.data.materials.new('Maple214_'+name);m.diffuse_color=color;m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=color;p.inputs['Metallic'].default_value=.58 if name=='metal' else (.2 if name in ['glass','pvtrim'] else .015);p.inputs['Roughness'].default_value=.38 if name in ['metal','glass'] else .70;materials[name]=m
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
  me=bpy.data.meshes.new(self.name);me.from_pydata(self.verts,[],self.faces);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new('Maple214_'+self.name,me);bpy.context.collection.objects.link(o);me.materials.append(materials[self.mat]);o['asset_id']=D['id'];return o
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
base=4.8;pitch=3.1;rows=26;roof=85.4
part('214_inner_parallel_offset_body','pale').prism(inset(2.1),base,roof-.24)
part('214_L_roof_plate','roof').prism(V,roof-.24,roof)
part('214_ground_inset_core','stone').prism(inset(3.0),0,base)
# NE end: W05 five stacks share one plane. Actual corner follows the white pair.
for k in range(rows):
 z=base+k*pitch;pm='stone' if k<6 else 'pale'
 panel(3,0,.415,z,z+pitch,'NE_pale_bedroom_recess_back',pm,-1.05,.18)
 for l,r in [(0,.025),(.175,.245),(.395,.415)]:panel(3,l,r,z,z+pitch,'NE_two_bedroom_opaque_piers',pm,.025,.22)
 for l,r in [(.025,.175),(.245,.395)]:
  wh=2.32 if k<6 else 1.94;sill=.50 if k<6 else .76
  panel(3,l,r,z+sill,z+sill+wh,'NE_bedroom_glass','glass',-.63,.06)
  panel(3,l,r,z,z+.52,'NE_bedroom_floor_band',pm,-.03,.28)
  post(3,l+(r-l)*.63,z+sill,z+sill+wh,.08,'NE_bedroom_unequal_sash','metal',-.51,.16)
 if k>=6 and (k-6)%3==0:
  l,r=(.005,.198)if ((k-6)//3)%2 else(.225,.414)
  panel(3,l,r,z,z+.69,'NE_three_row_box_projected_lintel','pale',.27,1.70)
  for t in [l,r]:post(3,t,z+.69,min(z+3*pitch,roof),.22,'NE_three_row_box_vertical_return','pale',.17,1.50)
 # Independent214metal section: low seven rows bigger, uppernine smaller services.
 panel(3,.415,1,z,z+pitch,'NE_metal_deep_back','shade',-.70,.12)
 metalbanks=[(.47,.545,'small'),(.595,.672,'small'),(.81,.963,'wide')]
 last=.415
 for l,r,kind in metalbanks:
  panel(3,last,l,z,z+pitch,'NE_metal_broad_piers','metal',.08,.22);last=r
  if kind=='wide':sill,h=((.22,2.57)if k<7 else(.57,2.10))
  else:sill,h=((.27,2.34)if k<7 else((.68,1.74)if k<17 else(1.15,1.12)))
  panel(3,l,r,z+.09,z+sill-.015,'NE_metal_opaque_spandrels','metal',.06,.20)
  panel(3,l+.004,r-.004,z+sill,z+sill+h,'NE_metal_window_glass','glass',-.28,.055)
  post(3,l+(r-l)*(.63 if kind=='wide'else .49),z+sill,z+sill+h,.07,'NE_metal_window_sash','metal',-.15,.18)
  panel(3,l,r,z+sill-.06,z+sill+.035,'NE_metal_sill_projection','metal',.08,.30)
  panel(3,l,r,z+sill+h,z+2.95,'NE_metal_dark_upper_recess','shade',-.14,.12)
  for t in [l,r]:post(3,t,z,z+pitch,.115,'NE_metal_reveal_edges','metal',.105,.24)
 panel(3,last,1,z,z+pitch,'NE_metal_broad_piers','metal',.08,.22)
 panel(3,.415,1,z+.08,z+.107,'NE_metal_floor_panel_joint','seam',.195,.015)
# e2 faces NW into courtyard: broad blank core, NOT bedroom pair.
# ActualW05 corner isat e3t0 before this broadplane.
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<6 else'pale'
 for l,r in [(0,.29),(.355,.48),(.515,1)]:panel(2,l,r,z,z+pitch,'NW_long_blank_core_panels',pm,.015,.25)
 panel(2,.29,.355,z,z+pitch,'NW_vertical_core_channel_back','shade',-.92,.12)
 panel(2,.301,.345,z+.65,z+2.54,'NW_core_channel_glass','glass',-.65,.055)
 panel(2,.29,.355,z,z+.32,'NW_core_channel_floor','pale',-.10,.18)
 post(2,.322,z+.65,z+2.54,.065,'NW_core_channel_mullion','metal',-.53,.12)
 panel(2,.48,.515,z,z+1.21,'NW_small_slot_lower_opaque',pm,.015,.25)
 panel(2,.48,.515,z+2.02,z+pitch,'NW_small_slot_upper_opaque',pm,.015,.25)
 panel(2,.483,.512,z+1.24,z+1.99,'NW_small_square_glass','glass',-.19,.055)
 for l,r in [(0,.29),(.355,1)]:panel(2,l,r,z+.12,z+.137,'NW_horizontal_panel_joint','seam',.148,.012)
for t in [.06,.15,.23,.41,.57,.66,.75,.84,.93]:post(2,t,base,roof,.017,'NW_large_panel_vertical_joints','seam',.148,.012)
# Inside ofshortSWarm: W04/W05 show slot cluster at innercorner and a broadwhiteblank.
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<6 else'pale'
 for l,r in [(0,.62),(.72,.84),(.885,1)]:panel(1,l,r,z,z+pitch,'NE_inner_shortarm_blank_wall',pm,.015,.24)
 for l,r,sill,h in [(.62,.72,.60,1.84),(.84,.885,1.20,.76)]:
  panel(1,l,r,z,z+sill-.03,'NE_inner_slot_bottom',pm,.015,.24)
  panel(1,l,r,z+sill+h+.03,z+pitch,'NE_inner_slot_top',pm,.015,.24)
  panel(1,l+.005,r-.005,z+sill,z+sill+h,'NE_inner_core_slot_glass','glass',-.24,.055)
 panel(1,0,1,z+.14,z+.159,'NE_inner_horizontal_seam','seam',.14,.012)
# Obliqueshowsthree unequalgroups ontheNWoutershortarm; precise return remainsapproximate.
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<6 else'pale';last=0
 for l,r in [(.09,.255),(.36,.535),(.68,.91)]:
  panel(0,last,l,z,z+pitch,'NW_shortarm_white_verticals',pm,.01,.22);last=r
  panel(0,l,r,z,z+.65,'NW_shortarm_floor_spandrel','grayfield',-.025,.15)
  panel(0,l,r,z+.70,z+2.58,'NW_shortarm_glass','glass',-.24,.055)
  panel(0,l,r,z+2.63,z+pitch,'NW_shortarm_upper_frame',pm,.01,.22)
  post(0,(l+r)/2,z+.70,z+2.58,.07,'NW_shortarm_sash','metal',-.13,.14)
 panel(0,last,1,z,z+pitch,'NW_shortarm_white_verticals',pm,.01,.22)
# A longSEfront: darkSWband and graydoublebank then five differently sizedwhitegroups.
# FractionxfromSWleft toNEright; no214groundphoto ofthisface claimed.
def front(l,r,z0,z1,name,mat,offset=0,thick=.12):panel(4,1-r,1-l,z0,z1,name,mat,offset,thick)
frontcols=[(.25,.305,'gray'),(.34,.455,'gray'),(.495,.555,'pale'),(.59,.646,'pale'),(.681,.710,'service'),(.755,.822,'pale'),(.858,.969,'pale')]
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<6 else'pale';last=.22
 front(.22,1,z,z+pitch,'SE_white_and_gray_back',pm,-.65,.14)
 for l,r,kind in frontcols:
  front(last,l,z,z+pitch,'SE_primary_photo_pale_piers',pm,.02,.22);last=r
  mat='grayfield' if kind=='gray'or k<6 else'pale';sill=.96 if kind=='service' else.69;h=1.18 if kind=='service'else 1.91
  front(l,r,z,z+sill-.025,'SE_individual_opaque_spandrels',mat,.01,.20)
  front(l+.003,r-.003,z+sill,z+sill+h,'SE_primary_photo_glass','glass',-.28,.06)
  front(l,r,z+sill+h+.04,z+pitch,'SE_individual_opaque_headers',mat,.01,.20)
  if r-l>.095:post(4,1-(l+(r-l)*.59),z+sill,z+sill+h,.08,'SE_broad_bank_sash','metal',-.16,.17)
 front(last,1,z,z+pitch,'SE_primary_photo_terminal_pier',pm,.02,.22)
 # Dark band isrecessed opaque framed windows, notunbroken tintedglass.
 front(0,.22,z,z+pitch,'SE_dark_band_recess_back','shade',-1.05,.16)
 for l,r in [(.020,.089),(.127,.203)]:
  front(l,r,z+.65,z+2.59,'SE_dark_band_individual_glass','glass',-.66,.055)
  for t in [l,r]:post(4,1-t,z,z+pitch,.16,'SE_dark_band_vertical_metal','metal',-.34,.24)
  front(l,r,z,z+.60,'SE_dark_band_opaque_spandrel','grayfield',-.40,.22)
  front(l,r,z+2.65,z+pitch,'SE_dark_band_head','shade',-.37,.16)
 front(.22,.237,z,z+pitch,'SE_dark_to_pale_edge','pale',.055,.34)
# e5 shallowkinkatSWfront hasthreecompactwindowsvisibleA.
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<6 else'pale';last=0
 for l,r in [(.08,.235),(.365,.51),(.64,.845)]:
  panel(5,last,l,z,z+pitch,'SE_short_kink_white_piers',pm,.02,.22);last=r
  panel(5,l,r,z,z+.72,'SE_short_kink_window_sill',pm,.02,.22)
  panel(5,l+.003,r-.003,z+.76,z+2.61,'SE_short_kink_glass','glass',-.23,.06)
  panel(5,l,r,z+2.65,z+pitch,'SE_short_kink_window_head',pm,.02,.22)
 panel(5,last,1,z,z+pitch,'SE_short_kink_white_piers',pm,.02,.22)
# SWlongback: noidentified directphoto. Plainprovisionalwall isnotcompletioncredit.
panel(6,0,1,base,roof,'SW_unverified_plain_wall','pale',-.09,.18)
for k in range(rows):
 z=base+k*pitch
 for l,r in [(.13,.22),(.37,.48),(.66,.75),(.86,.93)]:panel(6,l,r,z+.83,z+2.46,'SW_unverified_window_estimates','glass',.05,.045)
 panel(6,0,1,z+.12,z+.139,'SW_unverified_storey_seams','seam',.02,.018)
# GroundW04: continuousstonebase+recessedwindows, notgenericcornerstilts.
for e in [0,1,4,5,6]:panel(e,0,1,0,base,'ground_unseen_stone_enclosure','stone',-.21,.45)
for e,banks in [(3,[(.025,.175),(.245,.395),(.47,.545),(.595,.672),(.81,.963)]),(2,[(.30,.35),(.48,.515)])]:
 last=0
 for l,r in banks:
  panel(e,last,l,0,base,'ground_stone_window_piers','stone',-.08,.40);last=r
  panel(e,l,r,0,1.08,'ground_stone_window_low_wall','stone',-.08,.40)
  panel(e,l,r,3.81,base,'ground_stone_window_top_wall','stone',-.08,.40)
  panel(e,l+.002,r-.002,1.12,3.76,'ground_observed_recessed_window','glass',-.27,.055)
  panel(e,l,r,1.05,1.13,'ground_stone_window_sill','stone',-.02,.48)
 panel(e,last,1,0,base,'ground_stone_window_piers','stone',-.08,.40)
for e in [1,2,3]:
 banks={1:[],2:[(.30,.35),(.48,.515)],3:[(.025,.175),(.245,.395),(.47,.545),(.595,.672),(.81,.963)]}[e]
 for z in [1.10,2.20,3.30,4.40]:
  intervals=[];last=0
  if 1.10 <= z < 3.76:
   for l,r in banks:intervals.append((last,l));last=r
  intervals.append((last,1))
  for l,r in intervals:panel(e,l,r,z,z+.026,'ground_visible_stone_course_joint','seam',.027,.018)
#214'sroof plants andPVlayoutdrawnfromA; independentpositionsandproportions.
def roofbox(e,t,inward,w,d,z0,z1,name,mat):
 c=point(e,t,-inward);u,n,a=basis(e);part(name,mat).box(c,w,d,z0,z1,a);return c,u,n
c,u,n=roofbox(6,.52,9.4,6.4,6.3,roof,89.40,'SW_junction_plant_taller','pale')
roofbox(6,.52,9.4,6.58,6.48,89.40,89.60,'SW_plant_thin_flat_cap','seam')
part('SW_plant_small_visible_slot','shade').wall(c-u*.48+n*3.20,c+u*.24+n*3.20,87.3,88.25,.065)
c,u,n=roofbox(4,.24,8.9,10.1,4.8,roof,88.45,'NE_plant_broad_lower_rectangle','pale')
roofbox(4,.24,8.9,10.30,5.0,88.45,88.62,'NE_plant_shallow_cap','seam')
part('NE_plant_square_dark_aperture','shade').wall(c-u*.5+n*2.47,c+u*.52+n*2.47,86.42,87.60,.065)
for e,t,length,width,inward,name in [(4,.42,26.2,4.6,4.6,'long_SE_PV'),(6,.79,12.6,5.25,5.4,'short_SW_PV')]:
 u,n,ang=basis(e);c=point(e,t,-inward);count=round(length/1.45)
 for i in range(count):
  for j in range(4):
   p=c+u*((i+.5)*length/count-length/2)+n*((j+.5)*width/4-width/2);z=roof+.30+j*.19;part(name+'_frame','pvtrim').box(p,length/count-.025,width/4-.025,z,z+.09,ang);part(name+'_cells','solar').box(p,length/count-.10,width/4-.10,z+.09,z+.13,ang)
for e in range(N):
 a,b=V[e],V[(e+1)%N];u,n,ang=basis(e);start=a+u*.85;end=b-u*.85;count=max(2,round((end-start).length/.46))
 for i in range(count):
  t=i/(count-1);q=start+(end-start)*t;metal=(e==3 and t>.415);part('NE_metal_upper_fins'if metal else'white_open_roof_fins','metal'if metal else'pale').box(q,.078,.22,roof+.15,88.16,ang)
 for z in [roof+.18,88.16]:part('roof_thin_horizontal_tie','metal').wall(start,end,z,z+.075,.10)
 p=b-u*.85;q=b+(V[(e+2)%N]-b).normalized()*.85;pts=[]
 for j in range(9):
  t=j/8;v=(1-t)**2*p+2*(1-t)*t*b+t*t*q;pts.append(v)
  if j<8:part('rounded_roof_corner_fins','pale').box(v,.075,.22,roof+.15,88.16,ang+(basis((e+1)%N)[2]-ang)*t)
 for p,q in zip(pts,pts[1:]):
  for z in [roof+.18,88.16]:part('rounded_roof_corner_rail','metal').wall(p,q,z,z+.075,.10)
objects=[s.finish()for s in parts.values()if s.verts]
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0];bpy.ops.export_scene.gltf(filepath=str(O/'bespoke-maple-xi-214.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_materials='EXPORT')
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=1200;s.render.resolution_y=1400;s.render.resolution_percentage=100;s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.69,.73,.79,1);s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.60;s.view_settings.view_transform='AgX'
def camera(name,loc,target,scale,persp=False,lens=42):
 d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='PERSP'if persp else'ORTHO';d.ortho_scale=scale;d.lens=lens
camera('A_SE_primary_match',(240,-150,192),(0,0,43),119)
camera('W05_north_coplanar_end',(8,140,2),(0,0,43),115,True,42)
camera('NE_end_detail',(30,110,50),(18,17,49),31)
camera('NW_core_courtyard',(-100,75,65),(-2,5,46),104)
camera('Roof_two_individual_plants',(110,-75,163),(0,0,85),70)
camera('Ground_north_stone',(30,105,12),(8,12,11),42)
camera('SW_unverified_return',(-110,-125,120),(0,0,43),116)
camera('SE_primary_detail',(170,-70,60),(8,-1,60),40)
ld=bpy.data.lights.new('ReviewSun','SUN');lo=bpy.data.objects.new('ReviewSun',ld);bpy.context.collection.objects.link(lo);lo.rotation_euler=(.5,-.55,-.50);ld.energy=1.8
ld=bpy.data.lights.new('Softbox','AREA');lo=bpy.data.objects.new('Softbox',ld);bpy.context.collection.objects.link(lo);lo.location=(100,75,150);lo.rotation_euler=(Vector((0,0,43))-lo.location).to_track_quat('-Z','Y').to_euler();ld.energy=75000;ld.size=110
s.camera=bpy.data.objects['A_SE_primary_match'];bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-214.blend'));(O/'build-summary.json').write_text(json.dumps({'blender':bpy.app.version_string,'components':[o.name for o in objects],'vertices':sum(len(o.data.vertices)for o in objects),'faces':sum(len(o.data.polygons)for o in objects),'bounds':{'min':[min(v.co[i]for o in objects for v in o.data.vertices)for i in range(3)],'max':[max(v.co[i]for o in objects for v in o.data.vertices)for i in range(3)]}},indent=2));print('BUILT214',len(objects),'components')
