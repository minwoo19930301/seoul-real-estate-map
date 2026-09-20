"""204 individually authored from P/A/B/C evidence. Run only on owned Blender MCP9878.
No neighboring model or prior tower facade/crown is imported.
"""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
O=Path(__file__).parent;D=json.loads((O/'authored-input.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
COL={'white':(.76,.755,.71,1),'glass':(.045,.105,.13,1),'metal':(.10,.145,.16,1),'gray':(.31,.35,.36,1),'stone':(.24,.265,.26,1),'baseMetal':(.105,.17,.195,1),'dark':(.065,.09,.095,1),'roof':(.38,.40,.38,1),'joint':(.45,.46,.43,1),'solar':(.045,.066,.09,1),'solarFrame':(.32,.36,.40,1)};M={}
for n,c in COL.items():
 m=bpy.data.materials.new('Maple204_'+n);m.diffuse_color=c;m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=c;p.inputs['Roughness'].default_value=.30 if n in ['glass','solar'] else .68;p.inputs['Metallic'].default_value=.3 if n in ['metal','glass','solarFrame'] else .02;M[n]=m
# Neutral geometry primitives shared in method only, not prior tower components or layouts.
class Mesh:
 def __init__(s,n,m):s.n=n;s.m=m;s.v=[];s.f=[]
 def prism(s,p,z0,z1):
  if z1<=z0:return
  p=[Vector((x,y,0)) for x,y in p];q=len(s.v);l=len(p);s.v += [(v.x,v.y,z) for z in [z0,z1] for v in p];idx={tuple(v):i for i,v in enumerate(p)}
  for tr in tessellate_polygon([p]):
   ids=[v if isinstance(v,int) else idx[tuple(v)] for v in tr];s.f += [tuple(q+i for i in ids[::-1]),tuple(q+l+i for i in ids)]
  for i in range(l):s.f.append((q+i,q+(i+1)%l,q+(i+1)%l+l,q+i+l))
 def box(s,x,y,z,w,d,h,a=0):
  c,t=math.cos(a),math.sin(a);s.prism([(x+i*c-j*t,y+i*t+j*c) for i,j in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]],z-h/2,z+h/2)
 def wall(s,a,b,z0,z1,w=.1):
  a,b=Vector(a),Vector(b);n=Vector((-(b-a).y,(b-a).x)).normalized()*w/2;s.prism([a+n,b+n,b-n,a-n],z0,z1)
 def finish(s):
  me=bpy.data.meshes.new(s.n);me.from_pydata(s.v,[],s.f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new('Maple204_'+s.n,me);bpy.context.collection.objects.link(o);me.materials.append(M[s.m]);o['asset_id']=D['id'];return o
PART={}
def P(n,m):
 if (n,m) not in PART:PART[n,m]=Mesh(n,m)
 return PART[n,m]
V=[Vector(p) for p in D['ringEN']];base=4.3;roof=82.3;storey=3.;levels=26
# Originalplanclockwise; e4SE,e5SW, e0/e2NW,e1/e3NE.
def fp(e,t,offset=0):
 a,b=V[e],V[(e+1)%6];n=Vector((-(b-a).y,(b-a).x)).normalized();return a+(b-a)*t+n*offset
def panel(e,l,r,z0,z1,n,m,offset=.03,depth=.12):P(n,m).wall(fp(e,l,offset),fp(e,r,offset),z0,z1,depth)
def post(e,t,z0,z1,w,n,m,offset=.07,depth=.20):
 d=V[(e+1)%6]-V[e];v=fp(e,t,offset);P(n,m).box(*v,(z0+z1)/2,w,depth,z1-z0,math.atan2(d.y,d.x))
# Correct inward parallel-edge offset; scaling around origin is invalid for concave L.
def inset_ring(distance):
 result=[]
 for i in range(len(V)):
  a,b,c=V[(i-1)%len(V)],V[i],V[(i+1)%len(V)];u=(b-a).normalized();v=(c-b).normalized();n1=Vector((-u.y,u.x));n2=Vector((-v.y,v.x));p=b-n1*distance;q=b-n2*distance;w=q-p;den=u.x*v.y-u.y*v.x;t=(w.x*v.y-w.y*v.x)/den;result.append(tuple(p+u*t))
 return result
# Mass sits behind glazing and recess. Deepercentral SW void is not blocked by fill.
P('interior_inset_volume','white').prism(inset_ring(2.1),base,roof-.25)
P('L_plan_roof_slab','roof').prism([tuple(v) for v in V],roof-.25,roof)
P('ground_internal_core','stone').prism(inset_ring(5.0),0,base)
# White SW e5. Define photo-left to-right coordinates x; edgeparameter is1-x.
def sw(l,r,z0,z1,n,m,offset=.02,depth=.15):panel(5,1-r,1-l,z0,z1,n,m,offset,depth)
def swpost(x,z0,z1,w,n,m,offset=.06,depth=.22):post(5,1-x,z0,z1,w,n,m,offset,depth)
# Independently measured relative positions in completedC/B, not207four-window groups.
# Smallservicecolumns beside largewindows, centralwidegraybay + pairednarrowgraystack.
banks=[(.035,.165,'living'),(.205,.305,'paired'),(.322,.350,'small'),(.405,.445,'service'),(.482,.520,'service'),(.565,.675,'gray_living'),(.695,.780,'gray_pair'),(.825,.865,'service'),(.905,.978,'living')]
for k in range(levels):
 z=base+k*storey;top=z+storey;low=k<4;wm='baseMetal' if low else 'white'
 
 for bl,br in [(0,.382),(.466,1)]:sw(bl,br,z,top,'SW_recessed_backing','baseMetal' if low else 'white',-.88,.13)
 # Center chimney/service slot recedes, with pale deep jambs on both sides.
 sw(.385,.463,z,top,'SW_central_recess_back','gray',-1.42,.20)
 for x in [.383,.466]:swpost(x,z,top,.25,'SW_central_recess_return',wm,-.47,1.10)
 # Grayfields haveunequalwidth; relativelyproudslenderwhitejambsseparate.
 for l,r in [(.551,.689),(.684,.794)]:sw(l,r,z,top,'SW_two_gray_continuous_strips','baseMetal' if low else 'gray',-.78,.20)
 # Fullheightopaqueintervalsarekeptseparatefromglazedopenings.
 for l,r in [(0,.035),(.165,.205),(.305,.322),(.350,.382),(.466,.482),(.520,.551),(.794,.825),(.865,.905),(.978,1)]:
  sw(l,r,z,top,'SW_unequal_white_vertical_bands',wm,.025,.18)
 for j,(l,r,kind) in enumerate(banks):
  off=-1.18 if j==3 else -.24
  sill=.58 if 'living' in kind else .66;ht=1.92 if kind!='small' else 1.05
  if kind=='small':sill=1.26
  # topfloor haslarger combinedwindowatsecondbank, visibleB/C.
  if j==1 and k==levels-1:kind='living';ht=1.88
  sw(l,r,z+sill-.05,z+sill+ht+.08,'SW_window_reveals','dark',off-.11,.15)
  sw(l+.003,r-.003,z+sill,z+sill+ht,'SW_individual_window_glass','glass',off,.055)
  sw(l,r,z+sill-.12,z+sill-.015,'SW_projecting_window_sills','baseMetal' if low else 'gray',off+.18,.30)
  for x in [l,r]:swpost(x,z+sill-.12,z+sill+ht+.12,.11,'SW_window_side_returns',wm if (low or 'gray' not in kind) else 'gray',off+.12,.25)
  if kind in ['living','gray_living','paired','gray_pair']:
   split=l+(r-l)*(.63 if 'living' in kind else .52)
   swpost(split,z+sill,z+sill+ht,.09,'SW_unequal_sash_mullions','gray',off+.15,.29)
  # Thinhorizontalstone/whitebands, continuous exceptdeepcentralslot.
 for l,r in [(0,.382),(.466,.551),(.794,1)]:sw(l,r,z,z+.53,'SW_pale_floor_spandrels',wm,.025,.18)
 for l,r in [(.551,.689),(.684,.794)]:sw(l,r,z,z+.57,'SW_gray_floor_spandrels','baseMetal' if low else 'gray',.00,.18)
 # Majorhighcontrastverticalseams flankingcentralgraywindows are narrowerthanopaquewhitebands.
 for x in [.551,.684,.794]:swpost(x,z,top,.24,'SW_grayfield_pale_raised_jamb',wm,.065,.21)
# Dark SE e4: paleNEborder visible A ~18%, asymmetricopaqueandglazedbankselsewhere.
darkbanks=[(.209,.294,'slot'),(.325,.463,'wide'),(.490,.538,'service'),(.570,.740,'wide'),(.770,.958,'corner')]
for k in range(levels):
 z=base+k*storey;top=z+storey;wm='stone' if k<4 else 'white'
 panel(4,0,.19,z,top,'SE_pale_NE_end_band',wm,-.03,.27)
 for l,r in [(.030,.075),(.105,.159)]:
  panel(4,l,r,z+.66,z+2.46,'SE_end_unequal_windows','glass',.13,.055)
  panel(4,l,r,z+.52,z+.62,'SE_end_sills','gray',.23,.25)
 panel(4,.19,1,z,top,'SE_dark_opaque_back','metal',-.82,.16)
 for l,r,kind in darkbanks:
  sill=.72 if kind in ['wide','corner'] else .90;ht=1.89 if kind!='service' else 1.49
  panel(4,l+.004,r-.004,z+sill-.04,z+sill+ht+.07,'SE_deep_reveal_back','dark',-.57,.16)
  panel(4,l+.012,r-.012,z+sill,z+sill+ht,'SE_recessed_glazed_windows','glass',-.44,.055)
  split=l+(r-l)*(.66 if kind=='wide' else .46)
  post(4,split,z+sill,z+sill+ht,.09,'SE_window_mullions','gray',-.23,.35)
  panel(4,l,r,z+.12,z+sill-.05,'SE_opaque_silvergray_spandrels','gray' if kind!='service' else 'metal',.045,.25)
  if kind in ['wide','corner']:
   panel(4,split+.005,r-.011,z+sill,z+sill+.49,'SE_asymmetric_sash_infill','metal',-.19,.18)
  else:
   for zz in [.24,.41,.58]:panel(4,l+.01,r-.01,z+zz,z+zz+.035,'SE_narrow_service_vent_slits','dark',.21,.055)
  for t in [l,r]:post(4,t,z,top,.15,'SE_projected_bay_jambs','gray',.14,.40)
  panel(4,l,r,z+sill-.09,z+sill+.015,'SE_deep_projected_sills','gray',.17,.59)
  panel(4,l,r,z+sill+ht,z+sill+ht+.10,'SE_window_head_return','metal',.10,.51)
 for l,r in [(.19,.209),(.294,.325),(.463,.490),(.538,.570),(.740,.770),(.958,1)]:
  panel(4,l,r,z,top,'SE_unequal_opaque_vertical_panels','metal',.04,.26)
 panel(4,.19,1,z,z+.11,'SE_horizontal_floor_reveal','dark',.01,.23)
# Rear hasnotbeenconfidentlyidentified. Theseareexplicitlowconfidencefill, no specialborrowedarchitecture.
for e in [0,1,2,3]:
 panel(e,0,1,base,roof,'e'+str(e)+'_unverified_pale_back','white',-.14,.22)
 openings={0:[(.17,.30),(.53,.64)],1:[(.15,.22),(.72,.80)],2:[(.36,.43),(.63,.70)],3:[(.24,.35),(.61,.71)]}[e]
 for k in range(levels):
  z=base+k*storey
  for l,r in openings:panel(e,l,r,z+.8,z+2.30,'e'+str(e)+'_provisional_openings','glass',.035,.055)
  panel(e,0,1,z,z+.035,'rear_estimated_panel_seam','joint',.03,.02)
# GroundC: lowdarkstoneheader,paleentryframes, clearrecessedopening; outsideplazaexcluded.
for e in [4,5]:
 panel(e,0,1,3.20,base,'ground_continuous_stone_lintel','stone',-.02,.64)
 panel(e,.03,.97,.10,3.12,'ground_recessed_glazed_lobby','glass',-1.72,.12)
 for t in [.08,.25,.43,.64,.84,.97]:post(e,t,0,3.28,.58,'ground_stone_portal_piers','stone',-.20,.86)
 for t in [.16,.35,.55,.74,.90]:post(e,t,.12,3.12,.095,'ground_lobby_sash','gray',-1.62,.18)
# C broadcentralentry distinctfromcommunalstaircourtyard.
for l,r in [(.46,.62),(.70,.84)]:
 sw(l,r,3.0,4.30,'SW_entry_pale_header','white',.18,.83)
 for x in [l,r]:swpost(x,0,3.18,.65,'SW_entry_pale_jamb','white',.14,.82)
# Roof204: independentLfinpathwithshallowSWgap/Cnotch, no207crown reuse.
# Whitefinsroundedatoutsidecorners; north/innerreturnarmslowconfidenceextentmarkedinput.
path=[]
for i,v in enumerate(V):
 prev,nxt=V[(i-1)%6],V[(i+1)%6];cut=.95 if i!=2 else .30;a=v+(prev-v).normalized()*cut;b=v+(nxt-v).normalized()*cut
 for j in range(7):t=j/6;path.append((1-t)**2*a+2*(1-t)*t*v+t*t*b)
for a,b in zip(path,path[1:]+path[:1]):
 d=b-a;L=d.length;steps=max(1,round(L/.48));ang=math.atan2(d.y,d.x)
 for j in range(steps):
  p=a+d*j/steps
  # PhotographicSWslot openscrown near e5t~.60. Omit verticalfinsacrossnarrowrecess.
  e=V[0]-V[5];t=(p-V[5]).dot(e)/e.length_squared;dist=abs((p-V[5]).x*e.y-(p-V[5]).y*e.x)/e.length
  if dist<.18 and .537<t<.615:continue
  P('204_open_roof_vertical_fins','white').box(*p,83.68,.075,.22,2.5,ang)
 for z in [82.46,84.86]:P('204_rounded_fin_rails','gray').wall(a,b,z,z+.08,.10)
# PV banks andplantsindividuallypositionedalongtwoarms.
def basis(e):
 u=(V[(e+1)%6]-V[e]).normalized();return u,Vector((-u.y,u.x)),math.atan2(u.y,u.x)
def roofbox(e,t,inset,w,d,z0,z1,n,m):
 u,norm,a=basis(e);c=fp(e,t,-inset);P(n,m).box(*c,(z0+z1)/2,w,d,z1-z0,a);return c,u,norm
# longnarrowarrays, lowtilesatroofplane withthin gridseams; tiltapproximate0.8m across6m.
def solar(e,t,length,inset,width,name):
 c,u,n=basis(e)[0],None,None
 u,n,a=basis(e);center=fp(e,t,-inset);nx=round(length/1.55);ny=4
 for i in range(nx):
  for j in range(ny):
   p=center+u*((i+.5)/nx*length-length/2)+n*((j+.5)/ny*width-width/2);z=roof+.42+j*.18
   P(name+'_frame','solarFrame').box(*p,z,length/nx-.035,width/ny-.035,.10,a)
   P(name+'_photovoltaic_cells','solar').box(*p,z+.06,length/nx-.105,width/ny-.10,.045,a)
solar(5,.72,18.5,5.0,6.4,'SW_arm_PV_bank')
solar(4,.39,23.0,4.8,6.2,'SE_arm_PV_bank')
# Two unequalplants set towardinnernotch, tallerwesternroom has narrowstairreturn.
c,u,n=roofbox(5,.66,12.3,7.1,5.2,roof,86.60,'west_plant_tall_rectangular','white')
roofbox(5,.66,12.3,7.35,5.45,86.60,86.80,'west_plant_thin_cap','gray')
roofbox(5,.51,11.4,2.4,3.4,roof,85.35,'west_plant_lower_stair_return','white')
# frontwestvent atface-2.65normal fromplantcenter.
for x,w,z0,z1 in [(-1.7,.80,84.3,85.45),(1.4,.47,83.7,85.8)]:
 a=c+u*(x-w/2)+n*2.66;b=c+u*(x+w/2)+n*2.66;P('west_plant_unequal_dark_vents','dark').wall(a,b,z0,z1,.07)
c,u,n=roofbox(4,.29,9.5,8.6,4.8,roof,85.70,'east_plant_lower_broad_rectangle','white')
roofbox(4,.29,9.5,8.82,5.02,85.70,85.88,'east_plant_cap','gray')
a=c+u*(-.70)+n*2.44;b=c+u*(.20)+n*2.44;P('east_plant_visible_square_aperture','dark').wall(a,b,83.6,84.72,.07)
# RoofsignseenCisdaylightwhitelettersonthedarkpanel, notnightyellowmaterial.
panel(4,.61,.98,roof+.25,84.83,'SE_Xi_sign_support','metal',.0,.20)
# StylizedphysicalXi lettering: noembeddedimage; approximatebrandinggeometry.
u,n,a=basis(4);center=fp(4,.80,.20)
# Localfacadeglyph strokes fromsimplethickprisms, enoughreadatmapscale.
def stroke(x0,z0,x1,z1,w):
 p=center+u*x0;q=center+u*x1;vv=[(p.x,p.y,roof+z0),(q.x,q.y,roof+z1)]
 # rectangular3Drodviaeightverts, circumferentialcrosssection.
 ax=Vector((q.x-p.x,q.y-p.y,z1-z0)).normalized();side=Vector((n.x,n.y,0))*w/2;up=ax.cross(side).normalized()*w/2;v0=Vector(vv[0]);v1=Vector(vv[1]);part=P('SE_Xi_roof_lettering','white');baseidx=len(part.v)
 for v in [v0,v1]:
  for s,t in [(-1,-1),(1,-1),(1,1),(-1,1)]:part.v.append(tuple(v+side*s+up*t))
 part.f += [tuple(baseidx+i for i in [3,2,1,0]),tuple(baseidx+i for i in [4,5,6,7])]+[tuple(baseidx+i for i in [j,(j+1)%4,(j+1)%4+4,j+4]) for j in range(4)]
stroke(-3.3,.57,-.3,2.10,.26);stroke(-3.3,2.10,-.3,.57,.26);stroke(.65,.55,.65,1.85,.26);stroke(.65,2.05,.65,2.20,.29)
objs=[p.finish() for p in PART.values() if p.v]
bpy.ops.object.select_all(action='DESELECT')
for ob in objs:ob.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
bpy.ops.export_scene.gltf(filepath=str(O/'bespoke-maple-xi-204.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_materials='EXPORT')
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=1200;s.render.resolution_y=1400;s.render.resolution_percentage=100;s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.66,.71,.79,1);s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.55;s.view_settings.view_transform='AgX'
def camera(name,loc,target,scale):
 d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='ORTHO';d.ortho_scale=scale
camera('A_SE_aerial_match',(180,-150,175),(0,0,41),112)
camera('C_SW_completed_match',(-75,-240,112),(0,0,43),109)
camera('Roof_two_plants',(-75,-110,153),(0,0,82),67)
camera('White_face_detail',(-95,-160,54),(-9,-6,53),46)
camera('Dark_face_detail',(150,-95,54),(16,-6,53),45)
camera('Base_completed_match',(-65,-130,17),(0,0,6),61)
camera('NW_unverified_back',(-145,130,115),(0,0,42),117)
ld=bpy.data.lights.new('ReviewSun','SUN');lo=bpy.data.objects.new('ReviewSun',ld);bpy.context.collection.objects.link(lo);lo.rotation_euler=(.45,-.60,-.65);ld.energy=2
ld=bpy.data.lights.new('FrontSoftbox','AREA');lo=bpy.data.objects.new('FrontSoftbox',ld);bpy.context.collection.objects.link(lo);lo.location=(50,-100,140);lo.rotation_euler=(Vector((0,0,42))-lo.location).to_track_quat('-Z','Y').to_euler();ld.energy=60000;ld.size=100
s.camera=bpy.data.objects['C_SW_completed_match'];bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-204.blend'))
(O/'build-summary.json').write_text(json.dumps({'blender':bpy.app.version_string,'components':[o.name for o in objs],'vertices':sum(len(o.data.vertices) for o in objs),'faces':sum(len(o.data.polygons) for o in objs),'bounds':{'min':[min(v.co[i] for o in objs for v in o.data.vertices) for i in range(3)],'max':[max(v.co[i] for o in objs for v in o.data.vertices) for i in range(3)]}},indent=2));print('BUILT204',len(objs),'individual components')
