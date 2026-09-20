"""Independent215 model. Only abstract mesh primitives are shared; all facades and roof are215 inputs."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
O=Path(__file__).parent;D=json.loads((O/'authored-input.json').read_text());V=[Vector(p) for p in D['ringEN']]
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
colors={'pale':(.79,.79,.755,1),'aluminum':(.42,.46,.48,1),'glass':(.072,.135,.165,1),'dark':(.075,.095,.105,1),'stone':(.265,.29,.30,1),'baseframe':(.22,.285,.31,1),'roof':(.43,.44,.42,1),'solar':(.042,.065,.09,1),'pvframe':(.37,.40,.43,1),'joint':(.36,.38,.37,1)};materials={}
for name,color in colors.items():
 m=bpy.data.materials.new('Maple215_'+name);m.diffuse_color=color;m.use_nodes=True;shader=m.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=color;shader.inputs['Roughness'].default_value=.32 if name in ['glass','aluminum','solar'] else .67;shader.inputs['Metallic'].default_value=.65 if name=='aluminum' else (.25 if name in ['glass','pvframe'] else .02);materials[name]=m
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
  me=bpy.data.meshes.new(self.name);me.from_pydata(self.verts,[],self.faces);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new('Maple215_'+self.name,me);bpy.context.collection.objects.link(o);me.materials.append(materials[self.mat]);o['asset_id']=D['id'];return o
parts={}
def part(name,mat):
 if (name,mat) not in parts:parts[name,mat]=Solid(name,mat)
 return parts[name,mat]
def basis(e):
 u=(V[(e+1)%6]-V[e]).normalized();return u,Vector((-u.y,u.x)),math.atan2(u.y,u.x)
def point(e,t,offset=0):return V[e]+(V[(e+1)%6]-V[e])*t+basis(e)[1]*offset
def panel(e,l,r,z0,z1,name,mat,offset=0,thick=.12):part(name,mat).wall(point(e,l,offset),point(e,r,offset),z0,z1,thick)
def post(e,t,z0,z1,w,name,mat,offset=0,depth=.16):part(name,mat).box(point(e,t,offset),w,depth,z0,z1,basis(e)[2])
def inset(d):
 p=[]
 for i in range(6):
  a,b,c=V[(i-1)%6],V[i],V[(i+1)%6];u=(b-a).normalized();v=(c-b).normalized();x=b-Vector((-u.y,u.x))*d;y=b-Vector((-v.y,v.x))*d;q=y-x;den=u.x*v.y-u.y*v.x;t=(q.x*v.y-q.y*v.x)/den;p.append(x+u*t)
 return p
base=4.6;roof=76.6;pitch=3.;rows=24
part('inward_offset_inner_mass','pale').prism(inset(2.0),base,roof-.23)
part('individual_L_roof_slab','roof').prism(V,roof-.23,roof)
part('recessed_ground_core','stone').prism(inset(4.3),0,base)
# e4longSEwall. A whiteopeningsequenceisindependent of204or207.
# photo-left(SW) to-right(NE); theNE28%metal group is separate.
whitecols=[(.035,.059,'tiny'),(.080,.104,'tiny'),(.145,.196,'single'),(.224,.275,'single'),(.309,.332,'slot'),(.352,.403,'single'),(.447,.557,'wide'),(.594,.635,'single'),(.666,.706,'single')]
def front(l,r,z0,z1,name,mat,offset=0,thick=.12):panel(4,1-r,1-l,z0,z1,name,mat,offset,thick)
for k in range(rows):
 z=base+k*pitch;low=k<4;mat='baseframe' if low else 'pale'
 front(0,.72,z,z+pitch,'SE_pale_recessed_back','stone' if low else 'pale',-.61,.14)
 # Opaque verticalpaleintervals betweenunequalholes, nofullsheetinfrontofglass.
 last=0
 for j,(l,r,kind) in enumerate(whitecols):
  front(last,l,z,z+pitch,'SE_individual_white_piers',mat,.025,.18);last=r
  sill=1.14 if kind=='tiny' else .61;h=1.05 if kind=='tiny' else (1.65 if kind=='slot' else 1.93)
  front(l,r,z+sill-.03,z+sill+h+.05,'SE_white_window_reveals','dark',-.33,.12)
  front(l+.002,r-.002,z+sill,z+sill+h,'SE_white_window_glass','glass',-.22,.055)
  front(l,r,z+sill-.10,z+sill-.015,'SE_white_sills','baseframe' if low else 'aluminum',-.06,.31)
  if kind=='wide':post(4,1-(l+(r-l)*.60),z+sill,z+sill+h,.085,'SE_wide_living_sash','aluminum',-.12,.19)
 front(last,.72,z,z+pitch,'SE_white_terminal_pier',mat,.025,.18)
 for l,r,kind in whitecols:front(l,r,z,z+.50,'SE_pale_floor_bands',mat,.025,.18)
 # Thetinyservicecolumnhaslargeopaqueheaderbelowupperlittlewindows.
 for l,r,kind in whitecols:
  if kind=='tiny':front(l,r,z+.50,z+1.10,'SE_tiny_service_lower_infill',mat,.015,.16)
# MetalNEcorner on e4. A/W07 widecornerwindow+twonarrowservicecolumns.
# Its hue followsdaylight W06/07 silvercladding, not204darkpaintornightyellow.
def metal_face(e,banks,interval,name):
 left,right=interval
 for k in range(rows):
  z=base+k*pitch;panel(e,left,right,z,z+pitch,name+'_deep_opaque_back','dark',-.55,.16)
  last=left
  for l,r,kind in banks:
   panel(e,last,l,z,z+pitch,name+'_broad_metal_vertical_bands','aluminum',.06,.22);last=r
   # W06/W07: larger low-storey glazing, progressively larger opaque upper spandrels.
   if kind=='wide':sill,h=((.22,2.45) if k<7 else ((.40,2.18) if k<15 else (.60,1.93)))
   else:sill,h=((.24,2.37) if k<7 else ((.65,1.88) if k<15 else (1.06,1.24)))
   panel(e,l,r,z+.10,z+sill-.035,name+'_solid_spandrel_panels','aluminum',.045,.20)
   panel(e,l+.006,r-.006,z+sill,z+sill+h,name+'_recessed_window_glass','glass',-.21,.055)
   split=l+(r-l)*(.67 if kind=='wide' else .51);post(e,split,z+sill,z+sill+h,.075,name+'_sash_frames','aluminum',-.075,.19)
   panel(e,l,r,z+sill-.08,z+sill+.025,name+'_window_sill_lip','aluminum',.10,.36)
   panel(e,l,r,z+sill+h,z+2.80,name+'_deep_dark_head','dark',-.11,.16)
   for t in [l,r]:post(e,t,z,z+pitch,.12,name+'_reveal_jambs','aluminum',.09,.25)
   if kind=='service' and k>=7:
    # ActualnarrowlouverbetweenservicewindowsinW07; notuniformglazedcurtainwall.
    for zz in [.22,.38,.54,.70,.86]:
     if zz<sill-.08:panel(e,l+.012,r-.012,z+zz,z+zz+.030,name+'_vent_slats','dark',.16,.045)
  panel(e,last,right,z,z+pitch,name+'_broad_metal_vertical_bands','aluminum',.06,.22)
  panel(e,left,right,z,z+.09,name+'_storey_seams','dark',.005,.08)
  # Shallow horizontaljointsinthewideopaquecladding arevisibleW06/07.
  panel(e,left,right,z+.18,z+.208,name+'_panel_hairline','joint',.18,.018)
metal_face(4,[(.024,.139,'wide'),(.178,.215,'service'),(.242,.273,'narrow')],(0,.28),'SE_NE_metal_corner')
# e3NEend, seenfromoppositesidesW06/07. EdgedirectionNW→SE, broadbanknearSEt1.
metal_face(3,[(.49,.565,'narrow'),(.605,.68,'narrow'),(.805,.965,'wide')],(.43,1),'NE_metal_three_stacks_on_SEportion')
# Deepcornergutter betweenaluminumpilasters, distinctiveW07 bend.
for e,t in [(4,.008),(3,.992)]:
 post(e,t,2.0,roof,.32,'NE_corner_deep_vertical_joint','dark',.18,.30)
 post(e,t+( .012 if e==4 else-.033),2.0,roof,.48,'NE_corner_projecting_metal_cheek','aluminum',.33,.35)
# V2 corrected NE-end plane: white paired bedrooms share e3 with metal3stacks.
# W06 horizontal lines continue across material boundary; actual corner lies afterwhitepair.
for k in range(rows):
 z=base+k*pitch;mat='stone' if k<4 else 'pale'
 panel(3,0,.43,z,z+pitch,'NE_white_pair_deep_back',mat,-1.15,.18)
 for l,r in [(0,.035),(.18,.245),(.39,.43)]:panel(3,l,r,z,z+pitch,'NE_white_pair_broad_piers',mat,.025,.20)
 for l,r in [(.035,.18),(.245,.39)]:
  panel(3,l,r,z+.64,z+2.55,'NE_white_pair_recessed_glass','glass',-.60,.055)
  post(3,l+(r-l)*.60,z+.64,z+2.55,.08,'NE_white_pair_sash','aluminum',-.49,.14)
  panel(3,l,r,z,z+.48,'NE_white_pair_storey_band',mat,-.04,.23)
 if k>=4 and (k-4)%3==0:
  l,r=(.018,.198) if ((k-4)//3)%2==0 else(.225,.413)
  panel(3,l,r,z,z+.68,'NE_white_three_row_alternating_box_lip','pale',.34,1.64)
  for t in [l,r]:post(3,t,z+.68,min(z+9,roof),.20,'NE_white_three_row_side_returns','pale',.24,1.42)
# The adjoining e2 return is mostlyblank, partly hidden by trees inW06.
# Its deep inner slot is provisional; no214layout/pairedwindowsiscreditedhere.
for k in range(rows):
 z=base+k*pitch;mat='stone' if k<4 else 'pale'
 for l,r in [(0,.31),(.36,1)]:panel(2,l,r,z,z+pitch,'NW_provisional_plain_core',mat,.0,.22)
 panel(2,.31,.36,z,z+pitch,'NW_provisional_core_dark_slot','dark',-.65,.09)
 panel(2,.316,.354,z+.65,z+2.25,'NW_provisional_core_slot_glass','glass',-.52,.055)
 panel(2,.31,.36,z,z+.30,'NW_provisional_core_slot_floor','pale',-.04,.20)
 panel(2,0,1,z+.10,z+.125,'NW_pale_panel_joint','joint',.125,.012)
# Unverifiede0/e1/e5 keptseparate,sparseprovisional. No214or212shapeisimported.
for e,cols in [(0,[(.19,.31),(.52,.65)]),(1,[(.32,.42),(.70,.77)]),(5,[(.14,.31),(.48,.58),(.75,.88)])]:
 panel(e,0,1,base,roof,'e'+str(e)+'_unverified_pale_plane','pale',-.09,.18)
 for k in range(rows):
  z=base+k*pitch
  for l,r in cols:panel(e,l,r,z+.68,z+2.45,'e'+str(e)+'_provisional_glazing','glass',.035,.055)
  panel(e,0,1,z,z+.03,'unverified_back_panel_seams','joint',.02,.02)
#215ground differs byface. NEend isstonefoundationwithglazingabove, notfreepilotis.
panel(3,0,1,0,2.05,'NE_solid_stone_plinth','stone',.0,.70)
for l,r,kind in [(.035,.18,'white'),(.245,.39,'white'),(.49,.565,'narrow'),(.605,.68,'narrow'),(.805,.965,'wide')]:
 panel(3,l,r,2.1,4.38,'NE_ground_end_glass','glass',-.18,.07)
 for t in [l,r]:post(3,t,2.0,base,.15,'NE_ground_metal_jambs','aluminum',.08,.23)
panel(3,0,1,4.40,base,'NE_ground_metal_header','aluminum',.06,.20)
# SoutheasternNEquarter isclosedgranite belowthemetalface, clearinW07.
panel(4,0,.32,0,base,'SE_NE_closed_granite_base','stone',-.02,.66)
for zz in [1.1,2.2,3.3]:panel(4,0,.32,zz,zz+.023,'SE_NE_stone_horizontal_joints','joint',.32,.016)
for t in [.08,.19,.30]:post(4,t,0,base,.025,'SE_NE_stone_vertical_joints','joint',.32,.018)
# A confirmswidegroundopeningsontheSWwhitefacadeportion.
panel(4,.32,1,3.45,base,'SE_ground_portal_stone_header','stone',.015,.70)
for l,r in [(.36,.53),(.59,.76),(.83,.97)]:
 panel(4,l,r,.18,3.30,'SE_ground_recessed_lobby','glass',-1.32,.10)
 for t in [l,r]:post(4,t,0,3.5,.62,'SE_ground_visible_portal_jambs','stone',-.12,.82)
 post(4,(l+r)/2,.18,3.3,.085,'SE_lobby_door_mullions','aluminum',-1.20,.18)
# Shallowstonefoundationonpartiallyseenreturn, exteriorcommongroundnotclaimed.
for e in [0,1,2,5]:panel(e,0,1,0,base,'rear_ground_unverified_stone','stone',-.32,.40)
#215roof: twounlikeplants,longSE+shortSWsolar; allpositionsdrawnfrom215A.
def roofbox(e,t,inset_m,w,d,low,high,name,mat):
 c=point(e,t,-inset_m);u,n,a=basis(e);part(name,mat).box(c,w,d,low,high,a);return c,u,n
# PlantatSWjunctiontaller;NEplantlongandlower, eachowncap/aperture.
c,u,n=roofbox(5,.38,10.4,7.5,5.9,roof,80.30,'SW_junction_taller_plant','pale')
roofbox(5,.38,10.4,7.70,6.10,80.30,80.50,'SW_plant_flat_cap','joint')
part('SW_plant_small_vent','dark').wall(c+u*(-.3)+n*3.01,c+u*(.40)+n*3.01,78.5,79.7,.07)
c,u,n=roofbox(4,.235,9.0,9.7,4.4,roof,79.62,'NE_lower_rectangular_plant','pale')
roofbox(4,.235,9.0,9.90,4.6,79.62,79.79,'NE_plant_thin_cap','joint')
part('NE_plant_square_visible_vent','dark').wall(c+u*(-.50)+n*2.26,c+u*(.52)+n*2.26,77.75,78.93,.075)
def pv(e,t,length,inset_m,width,name):
 u,n,a=basis(e);c=point(e,t,-inset_m);nx=round(length/1.5);ny=4
 for i in range(nx):
  for j in range(ny):
   q=c+u*((i+.5)*length/nx-length/2)+n*((j+.5)*width/ny-width/2);z=roof+.36+j*.17;part(name+'_panel_frame','pvframe').box(q,length/nx-.04,width/ny-.04,z,z+.10,a);part(name+'_dark_cells','solar').box(q,length/nx-.11,width/ny-.11,z+.10,z+.14,a)
pv(4,.36,25.0,4.1,5.35,'SE_long_PV')
pv(5,.70,13.0,5.2,5.5,'SW_short_PV')
# Lowopenfinsfollow215L, withroundedconvexcorners andmetalNEsegmentseenA.
for e in range(6):
 a,b=V[e],V[(e+1)%6];u,n,ang=basis(e);length=(b-a).length;start=a+u*.95;end=b-u*.95;count=max(2,round((end-start).length/.49))
 for i in range(count):
  t=i/(count-1);q=start+(end-start)*t;metal=(e==3 and t>.43) or(e==4 and t<.28);part('NE_metal_roof_fins' if metal else 'pale_roof_fins','aluminum' if metal else 'pale').box(q,.078,.23,roof+.13,79.16,ang)
 for z in [roof+.14,79.16]:part('roof_horizontal_tie_rails','aluminum').wall(start,end,z,z+.08,.10)
 # Beziercornerconnectors, noopaqueclosedroofwall.
 v=b;nextu=(V[(e+2)%6]-b).normalized();p=b-u*.95;q=b+nextu*.95;pts=[]
 for j in range(9):
  t=j/8;pos=(1-t)**2*p+2*(1-t)*t*v+t*t*q;pts.append(pos)
  if j<8:part('rounded_corner_thin_fins','aluminum' if e==3 else 'pale').box(pos,.075,.22,roof+.13,79.16,ang+(basis((e+1)%6)[2]-ang)*t)
 for p,q in zip(pts,pts[1:]):
  for z in [roof+.14,79.16]:part('rounded_roof_corner_rails','aluminum').wall(p,q,z,z+.08,.10)
objects=[s.finish() for s in parts.values() if s.verts]
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
bpy.ops.export_scene.gltf(filepath=str(O/'bespoke-maple-xi-215.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_materials='EXPORT')
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=1200;s.render.resolution_y=1400;s.render.resolution_percentage=100;s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.69,.73,.79,1);s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.60;s.view_settings.view_transform='AgX'
def camera(name,loc,target,scale,persp=False,lens=40):
 d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='PERSP' if persp else 'ORTHO';d.ortho_scale=scale;d.lens=lens
camera('A_SE_primary_match',(240,-150,177),(0,0,39),109)
camera('W06_North_end',(-6,112,2),(8,12,37),105,True,39)
camera('W07_East_corner',(110,5,2),(7,3,38),105,True,38)
camera('Roof_individual_layout',(100,-70,147),(0,0,76),66)
camera('Ground_NE_stone',(85,35,13),(9,7,7),46)
camera('SW_unverified_return',(-125,-130,107),(0,0,39),110)
camera('W06_NE_detail',(25,110,49),(17,18,48),28)
camera('SE_white_detail',(150,-100,43),(8,-2,40),42)
ld=bpy.data.lights.new('ReviewSun','SUN');lo=bpy.data.objects.new('ReviewSun',ld);bpy.context.collection.objects.link(lo);lo.rotation_euler=(.5,-.55,-.50);ld.energy=1.8
ld=bpy.data.lights.new('Softbox','AREA');lo=bpy.data.objects.new('Softbox',ld);bpy.context.collection.objects.link(lo);lo.location=(100,75,135);lo.rotation_euler=(Vector((0,0,38))-lo.location).to_track_quat('-Z','Y').to_euler();ld.energy=75000;ld.size=110
s.camera=bpy.data.objects['A_SE_primary_match'];bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-215.blend'))
(O/'build-summary.json').write_text(json.dumps({'blender':bpy.app.version_string,'components':[o.name for o in objects],'vertices':sum(len(o.data.vertices) for o in objects),'faces':sum(len(o.data.polygons) for o in objects),'bounds':{'min':[min(v.co[i] for o in objects for v in o.data.vertices) for i in range(3)],'max':[max(v.co[i] for o in objects for v in o.data.vertices) for i in range(3)]}},indent=2));print('BUILT215',len(objects),'components')
