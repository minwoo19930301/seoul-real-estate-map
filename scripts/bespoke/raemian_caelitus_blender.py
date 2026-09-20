"""Individually traced Caelitus towers; execute inside the dedicated Blender MCP scene."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/raemian-caelitus';OUT.mkdir(parents=True,exist_ok=True)
INPUT=OUT/'authored-input.json'
if not INPUT.exists():INPUT=ROOT/'modeling/bespoke/raemian-caelitus/authored-input.json'
D=json.loads(INPUT.read_text());bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
colors={'glass':(.026,.145,.245,1),'blue':(.045,.24,.34,1),'silver':(.64,.68,.69,1),'stone':(.64,.63,.59,1),'white':(.78,.78,.72,1),'dark':(.10,.13,.15,1),'roof':(.30,.32,.31,1),'grass':(.17,.27,.11,1),'wood':(.41,.30,.19,1)};materials={}
for key,c in colors.items():
 m=bpy.data.materials.new('Caelitus_'+key);m.diffuse_color=c;m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=c;p.inputs['Roughness'].default_value=.22 if key=='glass' else .56;p.inputs['Metallic'].default_value=.32 if key in ['glass','silver','blue'] else .05;materials[key]=m
class Mesh:
 def __init__(self,name,mat,owner):self.name=name;self.mat=mat;self.owner=owner;self.v=[];self.f=[]
 def prism(self,ring,lo,hi):
  if hi<=lo:return
  p=[Vector((x,y,0)) for x,y in ring];n=len(p);off=len(self.v);self.v += [(q.x,q.y,z) for z in [lo,hi] for q in p];lookup={tuple(v):i for i,v in enumerate(p)}
  for tr in tessellate_polygon([p]):
   ids=[v if isinstance(v,int) else lookup[tuple(v)] for v in tr];self.f.extend([tuple(off+i for i in ids[::-1]),tuple(off+n+i for i in ids)])
  for i in range(n):self.f.append((off+i,off+(i+1)%n,off+(i+1)%n+n,off+i+n))
 def box(self,x,y,z,w,d,h,ang=0):
  c,s=math.cos(ang),math.sin(ang);self.prism([(x+a*c-b*s,y+a*s+b*c) for a,b in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]],z-h/2,z+h/2)
 def wall(self,a,b,lo,hi,width=.1):
  a,b=Vector(a),Vector(b);axis=(b-a).normalized();n=Vector((-axis.y,axis.x))*width/2;self.prism([tuple(a+n),tuple(b+n),tuple(b-n),tuple(a-n)],lo,hi)
 def cylinder(self,x,y,r,lo,hi,n=20):self.prism([(x+r*math.cos(i*math.tau/n),y+r*math.sin(i*math.tau/n)) for i in range(n)],lo,hi)
 def finish(self):
  me=bpy.data.meshes.new(self.name);me.from_pydata(self.v,[],self.f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new(self.name,me);bpy.context.collection.objects.link(o);me.materials.append(materials[self.mat]);o['caelitus_owner']=self.owner;return o
parts={}
def P(owner,name,mat):
 k=(owner,name,mat)
 if k not in parts:parts[k]=Mesh(f'Caelitus_{owner}_{name}',mat,owner)
 return parts[k]
T={t['number']:t for t in D['towers']};S=D['plan']['pixelsPerMetre'];ox,oy=D['plan']['originPixel']
def xy(n,p):
 t=T[n];x=(p[0]-ox)/S;y=(oy-p[1])/S;c,s=math.cos(t['rotationRad']),math.sin(t['rotationRad']);return Vector((t['siteEN'][0]+x*c-y*s,t['siteEN'][1]+x*s+y*c))
def ring(n,p):return [tuple(xy(n,v)) for v in p]
def rect(n,name,mat,x0,y0,x1,y1,z0,z1):P(n,name,mat).prism(ring(n,[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]),z0,z1)
def face(n,name,mat,a,b,z0,z1,width=.1):P(n,name,mat).wall(xy(n,a),xy(n,b),z0,z1,width)
def col(n,x,y,r=0.44):a=xy(n,(x,y));P(n,'piloti_columns','stone').cylinder(*a,r,0,9,16)
def floorlevels(roof,floors):
 # Published elevations have9m piloti and a9m community level; ordinary bays
 # are3m/3.1m. Interpolation preserves the dimensioned level endpoints.
 return [9+i*45.3/15 for i in range(16)]+[63.3+i*(roof-63.3)/(floors-17) for i in range(floors-16)]
def curtain(n,label,poly,roof,floors,skip_edges=()):
 levels=floorlevels(roof,floors);pts=ring(n,poly)
 P(n,label+'_occupied_mass','glass').prism(pts,9,roof)
 P(n,label+'_roof_slab','roof').prism(pts,roof-.22,roof)
 for edge,(a,b) in enumerate(zip(pts,pts[1:]+pts[:1])):
  if edge in skip_edges:continue
  a,b=Vector(a),Vector(b);length=(b-a).length
  if length<.18:continue
  axis=(b-a).normalized();panes=max(1,round(length/1.22))
  # Recessed/jog wall returns are broad pale stone strips visible in photo22,
  # not additional tiny panes of the blue curtainwall.
  if .3<length<2.2:
   P(n,label+'_solid_bay_returns','white').wall(a,b,9,roof,.18)
   continue
  # Continuous narrow vertical framing, actual repeating curtainwall module.
  for j in range(panes+1):
   at=a+(b-a)*j/panes;P(n,label+'_silver_mullions','silver').box(*at,(9+roof)/2,.065,.105,roof-9,math.atan2(axis.y,axis.x))
  for z in levels:
   if z>=roof:continue
   P(n,label+'_blue_spandrels','blue').wall(a,b,z,z+.50,.105)
   for zz in [z,z+.55]:P(n,label+'_silver_transoms','silver').wall(a,b,zz,zz+.055,.135)
  # Window sash positions follow each broad glazed bay, not randomized colours.
  if length>3:
   for j in [max(0,panes//3),max(0,2*panes//3)]:
    left=a+(b-a)*(j+.08)/panes;right=a+(b-a)*(j+.88)/panes
    for k,z in enumerate(levels[:-1]):
     if 53<z<64:continue
     P(n,label+'_opening_sashes','dark').wall(left,right,z+1.88,z+2.62,.15)
     P(n,label+'_sash_headers','silver').wall(left,right,z+2.60,z+2.67,.18)
  for at in [a,b]:P(n,label+'_bay_edge_fins','white').box(*at,(9+roof)/2,.30,.32,roof-9,math.atan2(axis.y,axis.x))
for n,t in T.items():
 front=D['plan']['front'];nw=D['plan']['northwest'];ne=D['plan']['northeast'];roof=t['roof'];top=t['crownTop']
 curtain(n,'riverfront_notched_pair',front,roof,t['floors'],[0,18,19])
 curtain(n,'northwest_'+str(t['northwestFloors'])+'storey_arm',nw,t['northwestRoof'],t['northwestFloors'],[0,1,2,3])
 curtain(n,'northeast_'+str(t['northeastFloors'])+'storey_arm',ne,t['northeastRoof'],t['northeastFloors'],[0])
 # Four dominant south-facing stone axes are separate from the thin window
 # mullions. Their recessed/forward relationship follows the stepped plan bays.
 for x in [505,653,1062,1190]:
  at=xy(n,(x,979));P(n,'four_primary_riverfront_stone_axes','white').box(*at,(9+roof)/2,.78,.62,roof-9,t['rotationRad'])
 for x in [816,878]:
  at=xy(n,(x,885));P(n,'deep_central_slot_sidewalls','stone').box(*at,(9+roof)/2,.33,8.4,roof-9,t['rotationRad'])
 face(n,'NW_exposed_internal_wall_above_NE','white',(883,319),(883,516),t['northeastRoof'],t['northwestRoof'],.20)
 # The exposed back of the tall paired riverfront block is pale solid cladding,
 # not a fourth generic glass face. Most lower wall is hidden by stepped arms.
 face(n,'exposed_rear_core_cladding','white',(475,572),(1218,572),9,roof,.23)
 face(n,'rear_core_narrow_slot','dark',(806,572),(830,572),max(t['northwestRoof'],t['northeastRoof'])-.01,roof-.35,.32)
 for z in range(12,int(roof),3):face(n,'rear_core_slot_transoms','silver',(806,572),(830,572),z,z+.12,.37)
 # Completed rear photo03 shows a quiet grid of shallow panel joints.
 # Gray narrow seams have their own geometry; occupied stepped arms conceal
 # the low portion naturally, as in the photo.
 for x in range(478,1218,39):face(n,'rear_cladding_vertical_panel_joints','stone',(x,572),(x+.45,572),9,roof,.26)
 for z in [9+i*1.50 for i in range(int((roof-9)/1.50))]:face(n,'rear_cladding_horizontal_panel_joints','stone',(475,572),(1218,572),z,z+.025,.26)
 face(n,'rear_core_slot_glazing','glass',(801,572),(830,572),max(t['northwestRoof'],t['northeastRoof']),roof-.45,.34)
 for z in [max(t['northwestRoof'],t['northeastRoof'])+i*1.5 for i in range(int((roof-max(t['northwestRoof'],t['northeastRoof']))/1.5))]:face(n,'rear_slot_horizontal_frames','silver',(800,572),(831,572),z,z+.09,.4)
 # Central south slot remains an8.7m-deep real recess in the plan.
 face(n,'central_recess_backwall','stone',(816,773),(878,773),0,roof,.3)
 for z in [i*.9 for i in range(int(roof/.9))]:face(n,'central_recess_stair_louvres','silver',(821,782),(873,782),z,z+.12,.32)
 # Main roof enclosure is an open crown screen and recessed plant, not a cube.
 crown=ring(n,front)
 for edge,(a,b) in enumerate(zip(crown,crown[1:]+crown[:1])):
  a,b=Vector(a),Vector(b);length=(b-a).length
  if length<.2:continue
  for j in range(max(1,round(length/1.22))+1):
   at=a+(b-a)*j/max(1,round(length/1.22));P(n,'open_crown_verticals','silver').box(*at,(roof+top)/2,.09,.12,top-roof,t['rotationRad'])
  # Completed photos show blue front/side crown screens and a much denser
  # rear metal grille, with the roof volume open above and behind them.
  if edge!=0:P(n,'crown_blue_screen','glass').wall(a,b,roof,top,.035)
  spacing=.30 if edge==0 else .85
  for k in range(int((top-roof)/spacing)+1):P(n,'open_crown_louvres','silver').wall(a,b,roof+k*spacing,min(top,roof+k*spacing+.13),.12)
 rect(n,'recessed_roof_plant','stone',682,574,1013,836,roof,top-2.3)
 rect(n,'helipad_roof','roof',682,574,1013,836,top-2.3,top-2.14)
 if n==101:
  # White H and ring are geometric marks on the small roof plant slab.
  c=xy(n,(849,705));r=4.7
  for j in range(64):
   a=c+Vector((math.cos(j*math.tau/64)*r,math.sin(j*math.tau/64)*r));b=c+Vector((math.cos((j+1)*math.tau/64)*r,math.sin((j+1)*math.tau/64)*r));P(n,'helipad_ring','white').wall(a,b,top-2.13,top-2.10,.09)
  for a,b in [((803,652),(803,752)),((895,652),(895,752)),((803,702),(895,702))]:face(n,'helipad_H','white',a,b,top-2.13,top-2.10,.25)
 # Lower roofs have thin rails and their own small plant grouping.
 for arm,height,poly in [('NW',t['northwestRoof'],nw),('NE',t['northeastRoof'],ne)]:
  rp=ring(n,poly)
  for a,b in zip(rp,rp[1:]+rp[:1]):P(n,arm+'_roof_guard','silver').wall(a,b,height,height+.8,.055)
 # 101 first-floor columns traced from plan36; corresponding102/103 site25
 # confirms perimeter columns and core but concealed glazing remains estimated.
 for i,(x0,y0,x1,y1) in enumerate([(477,278,517,297),(502,268,517,294),(628,286,654,318),(724,317,745,364),(873,323,897,505),(1039,305,1075,328),(1197,305,1234,328),(1315,312,1349,330),(1315,435,1349,454),(1310,327,1320,439),(496,397,517,434),(496,569,616,591),(496,705,517,746),(496,819,517,853),(478,946,513,963),(502,959,514,984),(628,948,666,969),(1030,941,1065,969),(1180,939,1216,963),(1180,959,1194,985),(1170,818,1197,853),(1170,705,1197,748),(1178,440,1197,478),(1087,570,1198,591)]):
  rect(n,'piloti_stone_wall_piers','stone',x0,y0,x1,y1,0,9)
 rect(n,'ground_elevator_core','stone',668,508,1032,798,0,9)
 rect(n,'ground_lounge_glazing','glass',1040,573,1197,952,0,8.8)
 for y in range(575,954,34):face(n,'ground_lounge_mullions','silver',(1198,y),(1198,y+1),0,8.9,.07)
 for z in [0,3,6,8.9]:face(n,'ground_lounge_transoms','silver',(1198,574),(1198,951),z,z+.07,.1)
 # Drawn17F pavilion differs at each tower; the101/102 front bar projects east.
 if n in [101,102]:
  pod=[(878,783),(1293,317),(1245,1028),(878,1028)] if n==101 else [(879,803),(1250,803),(1250,1030),(879,1030)]
  if n==101:pod=[(878,783),(1252,783),(1332,320),(1342,320),(1230,1030),(878,1030)]
 else:pod=[(475,840),(630,840),(630,982),(505,982),(505,954),(475,954)]
 pp=ring(n,pod);P(n,'17F_community_glass','glass').prism(pp,54.6,62.3)
 P(n,'17F_community_lower_frame','stone').prism(pp,54.3,55.0);P(n,'17F_community_upper_frame','white').prism(pp,62.3,63.1)
 for a,b in zip(pp,pp[1:]+pp[:1]):
  a,b=Vector(a),Vector(b);length=(b-a).length
  for j in range(max(1,round(length/1.3))+1):
   at=a+(b-a)*j/max(1,round(length/1.3));P(n,'17F_community_window_frames','silver').box(*at,58.65,.1,.15,7.3,t['rotationRad'])
 if n==103:
  for x0,x1 in [(505,816),(878,1190)]:
   for z in [54.3,62.6]:face(n,'103_17F_readingroom_front_frames','white',(x0,983),(x1,983),z,z+.5,.35)
 # Photo03: low northeast community front has a white picture-frame,
 # dark horizontal service louvres immediately above/below the glazing.
 if n==103:
  for a,b in [((921,285),(1328,285))]:
   for low,high in [(54.3,55.75),(60.8,63.3)]:
    face(n,'103_17F_NE_dark_vent_backing','dark',a,b,low,high,.29)
    for k in range(int((high-low)/.24)):face(n,'103_17F_NE_horizontal_vent_blades','silver',a,b,low+k*.24,low+k*.24+.09,.38)
   for z in [55.7,60.45]:face(n,'103_17F_NE_white_pavilion_frame','white',a,b,z,z+.40,.52)
  for x in [922,1328]:face(n,'103_17F_NE_white_pavilion_jambs','white',(x-5,285),(x+5,285),55.7,60.85,.52)
 # Rear17F plant louvres of102/103 distinguish the community storey from homes.
 if n!=101:
  for z in [54.5+i*.27 for i in range(26)]:face(n,'17F_rear_plant_louvres','silver',(485,304),(867,332),z,z+.12,.22)
# The two bridge arms have different directions and both meet103. Endpoints
# trace their junctions on the numbered17F plan, not a centroid triangle.
def bridge(name,a,b,width):
 owner=103;a,b=Vector(a),Vector(b);axis=(b-a).normalized();normal=Vector((-axis.y,axis.x));poly=[tuple(a+normal*width/2),tuple(b+normal*width/2),tuple(b-normal*width/2),tuple(a-normal*width/2)]
 P(owner,name+'_soffit','stone').prism(poly,55.3,56.0);P(owner,name+'_roof','stone').prism(poly,60.8,61.1)
 for sign in [-1,1]:
  aa=a+normal*sign*width/2;bb=b+normal*sign*width/2;P(owner,name+'_blue_glazing','glass').wall(aa,bb,56,60.8,.09)
  for j in range(round((b-a).length/1.4)+1):
   t=j/round((b-a).length/1.4);at=aa+(bb-aa)*t;P(owner,name+'_vertical_frames','silver').box(*at,58.4,.08,.12,4.8,math.atan2(axis.y,axis.x))
  for z in [56,58.6,60.75]:P(owner,name+'_transoms','silver').wall(aa,bb,z,z+.07,.13)
 for j in range(round((b-a).length/4)+1):
  at=a+(b-a)*j/round((b-a).length/4);P(owner,name+'_underside_panels','blue').wall(at-normal*(width/2-.05),at+normal*(width/2-.05),55.27,55.31,.08)
bridge('bridge_101_to_103',xy(101,(1260,320)),xy(103,(555,983)),4.5)
bridge('bridge_103_to_102',xy(103,(1350,458)),xy(102,(1060,290)),4.5)
# Site-plan affine registration from the three known source/tower centres.
# x/y are the displayed1805x1376 KIRA site-plan25 pixels (north is up).
A=Matrix([[*T[n]['sitePlanCenter'],1] for n in [101,102,103]]);inv=A.inverted();ex=inv@Vector([T[n]['siteEN'][0] for n in [101,102,103]]);ey=inv@Vector([T[n]['siteEN'][1] for n in [101,102,103]])
def site(x,y):p=Vector((x,y,1));return Vector((ex.dot(p),ey.dot(p)))
podium=[[410,1055],[530,1066],[572,956],[596,877],[628,867],[653,803],[653,747],[639,705],[613,705],[590,735],[572,733],[556,709],[513,732],[475,731],[450,755],[443,811],[405,847],[384,916],[389,979]]
pp=[tuple(site(*p)) for p in podium]
center=sum((Vector(p) for p in pp),Vector((0,0)))/len(pp)
glazing=[tuple(center+(Vector(p)-center)*.92) for p in pp]
P(103,'west_community_podium','glass').prism(glazing,0,4.65)
P(103,'west_podium_metal_fascia','silver').prism(pp,4.65,5.8)
P(103,'west_podium_wood_soffit','wood').prism(pp,4.60,4.65)
inner=[tuple(center+(Vector(p)-center)*.88) for p in pp];P(103,'west_podium_roof_planting','grass').prism(inner,5.8,5.95)
for a,b in zip(glazing,glazing[1:]+glazing[:1]):
 a,b=Vector(a),Vector(b);length=(b-a).length
 for j in range(max(1,round(length/1.3))+1):
  at=a+(b-a)*j/max(1,round(length/1.3));P(103,'podium_glazing_frames','silver').box(*at,2.325,.075,.075,4.65)
 P(103,'podium_window_crossbars','silver').wall(a,b,1.05,1.12,.09)
# The long roof path and small shaded seating deck are drawn on roofplan26
# and visible in completed photo08. Furniture and planting species omitted.
patha,pathb=site(464,1005),site(580,761)
P(103,'roof_garden_straight_walk','white').wall(patha,pathb,5.96,6.04,2.3)
P(103,'roof_garden_wood_deck','wood').prism([tuple(site(*p)) for p in [(498,865),(552,885),(587,803),(535,785)]],5.97,6.05)
perg=[site(*p) for p in [(541,824),(558,830),(570,801),(553,794)]]
for at in perg:P(103,'roof_garden_pergola_posts','dark').box(*at,7.5,.18,.18,3)
for a,b in zip(perg,perg[1:]+perg[:1]):P(103,'roof_garden_pergola_beams','dark').wall(a,b,8.86,9.10,.20)
for i in range(9):
 a=perg[0]+(perg[1]-perg[0])*i/8;b=perg[3]+(perg[2]-perg[3])*i/8;P(103,'roof_garden_pergola_slats','wood').wall(a,b,8.84,8.94,.12)
for a,b in [(site(449,997),site(565,753)),(site(478,1012),site(534,895))]:P(103,'roof_garden_raised_bed_wood_edges','wood').wall(a,b,5.85,6.35,.16)
# Exterior stair at the curved northern return, aligned with roofplan26.
a,b=site(650,742),site(618,783);axis=(b-a).normalized();normal=Vector((-axis.y,axis.x));width=2.2
for i in range(30):
 at=a+(b-a)*i/30;nxt=a+(b-a)*(i+1)/30
 P(103,'podium_exterior_roof_stair','stone').prism([tuple(at+normal*width/2),tuple(nxt+normal*width/2),tuple(nxt-normal*width/2),tuple(at-normal*width/2)],0,5.8*(1-i/30))
canopy=[[648,689],[770,648],[884,609],[1045,561],[1070,565],[1078,580],[1054,594],[906,649],[796,713],[695,742],[655,741]];cp=[tuple(site(*p)) for p in canopy];P(103,'canopy_with_two_oval_openings','silver').prism(cp,4.85,5.8)
P(103,'canopy_wood_soffit_with_two_oval_openings','wood').prism(cp,4.80,4.85)
for p in [(680,716),(723,698),(785,676),(821,661),(875,642),(924,615),(978,593),(1040,580)]:at=site(*p);P(103,'canopy_round_columns','stone').cylinder(*at,.34,0,4.80,16)
objects=[p.finish() for p in parts.values() if p.v]
# Actual visible canopy oculi; boolean cuts are through-holes.
for canopyobj in [o for o in objects if 'with_two_oval_openings' in o.name]:
 for pixel in [(778,683),(860,651)]:
  at=site(*pixel);bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=1,depth=3,location=(*at,5.6));cut=bpy.context.object;cut.scale=(5.2,2.35,1);cut.rotation_euler.z=math.radians(23);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);bpy.context.view_layer.objects.active=canopyobj;mod=canopyobj.modifiers.new('photo_confirmed_oval_opening','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
# Export individual anchors, then restore the editable assembly positions.
assets=[]
for n,t in T.items():
 objs=[o for o in objects if o['caelitus_owner']==n];bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True);o.location.x-=t['siteEN'][0];o.location.y-=t['siteEN'][1]
 file=t['id']+'.glb';bpy.ops.export_scene.gltf(filepath=str(OUT/file),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_cameras=False,export_lights=False)
 for o in objs:o.location.x+=t['siteEN'][0];o.location.y+=t['siteEN'][1]
 assets.append({'id':t['id'],'nameKo':f'래미안 첼리투스 {n}동'+('·스카이브리지·포디움' if n==103 else ''),'file':file,'blendSource':'raemian-caelitus.blend','coordinate':t['coordinate'],'category':'apartment-complex','district':'용산구','footprintIds':[t['sourceId']],'supersedes':['apt-a10027908'] if n in [102,103] else ['fallback-caelitus-101'],'referenceUrl':D['sources'][1]['url'],'components':[o.name for o in objs],'buildingFacts':{'floors':t['floors'],'heightBasis':'KIRA numbered elevation dimensions, separate from conflicting2017builderarticle.','apartmentCode':'A10027908','complexHouseholds':460,'register':t.get('register',{})},'uncertainties':D['limitations'],'minZoom':14.5,'siteEN':t['siteEN']})
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.render.resolution_x=1400;scene.render.resolution_y=1400;scene.render.resolution_percentage=100;scene.world.color=(.65,.65,.65)
scene.view_settings.view_transform='AgX';scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.60,.69,.80,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.7
sun=bpy.data.lights.new('REVIEW_sun','SUN');sun.energy=2.3;sun.angle=.12;so=bpy.data.objects.new(sun.name,sun);bpy.context.collection.objects.link(so);so.rotation_euler=(math.radians(27),math.radians(-18),math.radians(-25))
# Render-only floor and lamps are outside the exported assets.
bpy.ops.mesh.primitive_plane_add(size=520,location=(0,-15,-.12));ground=bpy.context.object;ground.name='REVIEW_ONLY_ground';ground.data.materials.append(materials['roof'])
for name,loc,power,size in [('key',(-170,-240,360),430000,180),('fill',(150,100,200),260000,140)]:
 data=bpy.data.lights.new('REVIEW_'+name,'AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new(data.name,data);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,70))-o.location).to_track_quat('-Z','Y').to_euler()
def camera(name,loc,target,ortho):
 c=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();c.type='ORTHO';c.ortho_scale=ortho;return o
camera('southwest_completed_photo',(180,-520,160),(0,-20,96),255)
camera('northwest_rear_steps',(-245,240,205),(0,-20,102),260)
camera('east_completed_photo',(270,125,165),(0,-20,92),260)
camera('roof_and_bridges',(180,-220,330),(0,-20,78),245)
camera('bridge_and_piloti',(145,-155,92),(0,-18,42),160)
camera('podium_canopy_ovals',(-130,-130,94),(-39,-20,13),155)
scene.camera=bpy.data.objects['southwest_completed_photo'];bpy.ops.object.select_all(action='DESELECT')
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':area.spaces.active.region_3d.view_distance=290;area.spaces.active.region_3d.view_location=Vector((0,-20,90))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'raemian-caelitus.blend'))
bundle={'siteId':D['siteId'],'sources':D['sources'],'assets':assets,'places':[{'id':'bespoke-raemian-caelitus','name':'래미안 첼리투스','subtitle':'460세대 · 101–103동 · 17층 스카이브리지','center':D['coordinate'],'zoom':17,'source_url':D['sources'][0]['url']}],'recipeFiles':['authored-input.json','building-register-rows.json'],'integrationRequirement':'Use root footprint-preserving legacy overlay:101 supersedes fallback-caelitus-101 only; neighboring6Wanggungcompoundbuildings remain.'}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n');print('CAELITUS_BUILT',len(objects),'namedcomponents',bpy.app.version_string)
