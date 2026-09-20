"""Individually authored Maple 213 correction; run only through live Blender MCP.
Measured input is the 23F/74.5m register row. Roof datum convention and obscured
facades remain explicit estimates. No prior GLB is loaded or vertically scaled.
"""
from pathlib import Path
import bpy,bmesh,json,math,hashlib
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
OUT=Path(__file__).resolve().parent
# The self-contained research ledger is bundled with this script.
EVIDENCE=OUT/'source-evidence.json'
D=json.loads(EVIDENCE.read_text())
A=D['identity']['coordinate'];LAT=A['lat'];LON=A['lon']
R=[((x-LON)*111320*math.cos(math.radians(LAT)),(y-LAT)*111320) for x,y in D['identity']['groundFootprint']['coordinates'][0][:-1]]
H=74.5;BASE=3.9;STEP=(H-BASE)/22
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.preferences.filepaths.save_version=0
palette={'ivory':(.74,.74,.69,1),'warm_panel':(.47,.48,.44,1),'glass':(.07,.12,.115,1),'window_frame':(.38,.41,.39,1),'reveal':(.065,.075,.07,1),'stone':(.31,.32,.285,1),'joint':(.20,.22,.20,1),'roof':(.43,.43,.38,1),'rail':(.52,.53,.50,1),'solar':(.018,.040,.062,1),'solar_grid':(.34,.37,.36,1),'bluegray_panel':(.20,.28,.35,1),'bluegray_glass':(.13,.22,.29,1)}
M={}
for name,color in palette.items():
 m=bpy.data.materials.new('213_'+name);m.diffuse_color=color;m.use_nodes=True
 n=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');n.inputs['Base Color'].default_value=color;n.inputs['Roughness'].default_value=.32 if name in ('glass','solar') else .7
 M[name]=m
COL={}
def collection(name):
 if name not in COL:
  c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);COL[name]=c
 return COL[name]
class Batch:
 def __init__(self,n,m,c):self.n=n;self.m=m;self.c=c;self.v=[];self.f=[]
 def prism(self,ring,z0,z1):
  pts=[Vector((x,y,0)) for x,y in ring];N=len(pts);s=len(self.v);self.v += [(p.x,p.y,z) for z in (z0,z1) for p in pts];idx={tuple(p):i for i,p in enumerate(pts)}
  for tr in tessellate_polygon([pts]):
   ii=[p if isinstance(p,int) else idx[tuple(p)] for p in tr];self.f += [tuple(s+i for i in reversed(ii)),tuple(s+N+i for i in ii)]
  for i in range(N):j=(i+1)%N;self.f.append((s+i,s+j,s+N+j,s+N+i))
 def box(self,x,y,z,w,d,h,angle=0):
  c,s=math.cos(angle),math.sin(angle);self.prism([(x+a*c-b*s,y+a*s+b*c) for a,b in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]],z-h/2,z+h/2)
 def face(self,a,b,z0,z1,depth=.03,off=.04):
  a,b=Vector(a),Vector(b);u=(b-a).normalized();n=Vector((-u.y,u.x));self.prism([tuple(a+n*off),tuple(b+n*off),tuple(b+n*(off+depth)),tuple(a+n*(off+depth))],z0,z1)
 def plane(self,verts,thick=.05):
  s=len(self.v);self.v+=verts+[(x,y,z-thick) for x,y,z in verts];self.f.extend([tuple(s+i for i in f) for f in [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]])
 def finish(self):
  me=bpy.data.meshes.new(self.n);me.from_pydata(self.v,[],self.f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
  o=bpy.data.objects.new(self.n,me);collection(self.c).objects.link(o);me.materials.append(M[self.m]);return o
B={}
def P(n,m,c):
 if n not in B:B[n]=Batch(n,m,c)
 return B[n]
# One low continuous L envelope. Register height used as main-roof datum convention,
# not a claim that legal height equals decorative highest vertex.
# The April photograph has a genuine deep vertical separation in the pale core.
# Retain original exterior extent but articulate this one photographed face inward.
a2,b2=Vector(R[2]),Vector(R[3]);v2=b2-a2;n2=Vector((-v2.y,v2.x)).normalized()
coreA=a2+v2*.14;coreB=a2+v2*.26
RG=R[:3]+[tuple(coreA),tuple(coreA-n2*1.45),tuple(coreB-n2*1.45),tuple(coreB)]+R[3:]
P('213_individual_L_body_with_core_recess','ivory','01_213_23_storey_body').prism(RG,BASE,H)
P('213_obscured_ground_storey_conservative_mass','stone','02_213_unverified_ground').prism(R,0,BASE)
P('213_L_roof_slab','ivory','03_213_photo_roof').prism(RG,H-.20,H)
cent=sum((Vector(p) for p in R),Vector((0,0)))/len(R)
P('213_exposed_roof_surface','roof','03_213_photo_roof').prism([tuple(cent+(Vector(p)-cent)*.971) for p in RG],H,H+.015)
# Each face is its own authored program; unseen sides have an explicit limit.
faces=[
 {'edge':0,'basis':'April25 numbered213 photograph: NW road-facing end is broad blue-gray panel/window grid. Distinct from pale core behind.','windows':[(.035,.245),(.275,.485),(.515,.725),(.755,.965)],'warm':[(0,1)]},
 {'edge':1,'basis':'NE inside return not clearly visible; conservative window field, not photo-approved exact elevation.','windows':[(.06,.19),(.27,.40),(.53,.66),(.76,.90)],'warm':[(0,.055)]},
 {'edge':2,'basis':'April numbered213 view: recessed pale core face behind NW glass end, narrow dark square-window vertical slots and broad blank pale panel.','windows':[(.182,.218),(.82,.855)],'warm':[]},
 {'edge':3,'basis':'NE end largely blocked by 212 in March; restrained pale wall and two small core-slot groups, not old dark curtain-wall.','windows':[(.16,.22),(.70,.76)],'warm':[]},
 {'edge':4,'basis':'March partial southeast pale facade, broad outside stacks and narrower centre. Lower rows obscured by212; continuation estimated.','windows':[(.055,.20),(.27,.41),(.47,.53),(.59,.65),(.71,.85),(.90,.97)],'warm':[(.44,.68)]},
 {'edge':5,'basis':'March visible southwest white window bank, narrow paired central stacks; low floors partly hidden.','windows':[(.045,.19),(.25,.40),(.46,.52),(.58,.64),(.70,.84),(.895,.97)],'warm':[(.43,.67)]}
]
for f in faces:
 e=f['edge'];a,b=Vector(R[e]),Vector(R[(e+1)%6]);v=b-a;le=v.length;point=lambda t:tuple(a+v*t);c=f'04_213_e{e}_window_banks'
 for l,h in f['warm']:P(f'e{e}_pale_warm_infill','warm_panel',c).face(point(l),point(h),BASE,H-.14,off=.025)
 if e==0:
  P('213_NW_bluegray_numbered_end','bluegray_panel',c).face(point(0),point(1),BASE,H,.055,.04)
 if e==2:
  P('213_core_lower_stone_sleeve','stone','02_213_unverified_ground').face(point(0),point(1),BASE,13.5,.045,.04)
  P('213_observed_core_vertical_shadow_slot','reveal',c).face(point(.14),point(.26),13.5,H,.02,-1.44)
  for t in (.13,.27):P('213_core_slot_flanking_pale_jambs','ivory',c).face(point(t-.012),point(t+.012),13.5,H,.08,.0)
 for floor in range(22):
  z=BASE+floor*STEP;wh=STEP*(.50 if e in (2,3) else .78 if e==0 else .73);z0=z+(STEP-wh)*.48
  for k,(l,h) in enumerate(f['windows']):
   recess=-1.50 if e==2 and k==0 and z0>13.5 else 0
   P(f'e{e}_recesses','reveal',c).face(point(l),point(h),z0-.035,z0+wh+.035,off=.065+recess)
   P(f'e{e}_glass','bluegray_glass' if e==0 else 'glass',c).face(point(l+.028/le),point(h-.028/le),z0+.028,z0+wh-.028,off=.100+recess)
   for t in (l,h):P(f'e{e}_window_frames','window_frame',c).face(point(t-.025/le),point(t+.025/le),z0,z0+wh,.045,.115+recess)
   divisions=([3,2,1,1,3,2][k] if e in (4,5) else 2 if (h-l)*le>2.4 else 1)
   for div in range(1,divisions):
    t=l+(h-l)*div/divisions;P(f'e{e}_window_frames','window_frame',c).face(point(t-.023/le),point(t+.023/le),z0,z0+wh,.045,.115+recess)
   for zz in (z0,z0+wh):P(f'e{e}_window_frames','window_frame',c).face(point(l),point(h),zz-.022,zz+.022,.045,.115+recess)
 if e==0:
  for t in [0,.25,.5,.75,1]:P('213_NW_major_vertical_mullions','window_frame',c).face(point(max(0,t-.06/le)),point(min(1,t+.06/le)),BASE,H,.15,.23)
  for floor in range(23):
   zz=BASE+floor*STEP;P('213_NW_horizontal_spandrel_frames','window_frame',c).face(point(0),point(1),zz-.065,zz+.065,.10,.19)
 # April adjoining white facade has broad ground-storey lintel and a recessed stone field.
 if e==5:
  P('213_SW_observed_wide_ground_lintel','ivory','02_213_unverified_ground').face(point(.015),point(.985),BASE-.16,BASE+.30,.34,.03)
  for t in (.04,.52,.965):P('213_SW_ground_stone_piers','stone','02_213_unverified_ground').face(point(t-.02),point(t+.02),0,BASE,.24,.025)
 # Restrained ground cladding; no invented seven-metre portal.
 for zz in (1.0,2.0,3.0):P(f'e{e}_ground_stone_joints','joint','02_213_unverified_ground').face(point(0),point(1),zz,zz+.018,.01,.03)
 for k in range(1,int(le/1.7)):
  t=k*1.7/le;P(f'e{e}_ground_stone_joints','joint','02_213_unverified_ground').face(point(t),point(t+.014/le),0,BASE,.01,.03)
# Low, open railing. No broad fin crown lifted from neighbouring212.
for e in range(6):
 a,b=Vector(R[e]),Vector(R[(e+1)%6]);v=b-a;le=v.length;u=v/le;mid=(a+b)/2;ang=math.atan2(v.y,v.x)
 for z in (H+.48,H+.93):P('213_low_perimeter_rails','rail','03_213_photo_roof').box(mid.x,mid.y,z,le,.035,.035,ang)
 for k in range(max(2,round(le/1.5))+1):
  q=a+v*k/max(2,round(le/1.5));P('213_low_perimeter_posts','rail','03_213_photo_roof').box(q.x,q.y,H+.47,.037,.037,.94)
V=[Vector(p) for p in R]
# Place plant boxes near elbow, not on top of copied tall shafts.
rooms=[]
for wing,along,w,d,h in [(0,.73,5.4,3.6,3.2),(1,.70,5.0,3.3,2.75)]:
 start=(V[0]+V[1])/2 if wing==0 else (V[3]+V[4])/2;end=(V[2]+V[5])/2;direction=end-start;u=direction.normalized();n=Vector((-u.y,u.x));q=start+direction*along;ang=math.atan2(u.y,u.x)
 P(f'213_roof_service_{wing}','ivory','05_213_two_roof_rooms').box(q.x,q.y,H+h/2,w,d,h,ang)
 P(f'213_roof_service_{wing}_cap','ivory','05_213_two_roof_rooms').box(q.x,q.y,H+h+.07,w+.13,d+.13,.14,ang)
 for side in (-1,1):
  mid=q+n*(side*d/2+.015*side);p0=mid-u*.36;p1=mid+u*.36
  if side<0:p0,p1=p1,p0
  P(f'213_roof_service_{wing}_small_apertures','reveal','05_213_two_roof_rooms').face(tuple(p0),tuple(p1),H+1.20,H+2.0,.025,.018)
 rooms.append({'wing':wing,'center':list(q),'sizeM':[w,d,h],'source':'March2025 official east aerial, partially occluded213 roof behind212; room size and hidden sides estimated. WithdrawnFebruarycrop is not evidence.'})
# March-visible PV on southwest roof arm only; northeast roof is partly occluded.
# Array dimensions/tilt estimated independently; no old two-canopy recipe loaded.
start=(V[0]+V[1])/2;end=(V[2]+V[5])/2;u=(end-start).normalized();n=Vector((-u.y,u.x));q=start+(end-start)*.56+n*2.5;ang=math.atan2(u.y,u.x)
W=10.2;DEP=3.8;tilt=math.radians(10);cols=9;rows=3
for i in range(cols):
 for j in range(rows):
  x=-W/2+(i+.5)*W/cols;y=-DEP/2+(j+.5)*DEP/rows;p=q+u*x+n*y;ww=W/cols-.055;dd=DEP/rows-.045;z=H+.76+(y+DEP/2)*math.tan(tilt)
  points=[tuple((p+u*xx+n*yy))+ (z+yy*math.tan(tilt),) for xx,yy in [(-ww/2,-dd/2),(ww/2,-dd/2),(ww/2,dd/2),(-ww/2,dd/2)]]
  P('213_SW_visible_PV_modules','solar','06_213_single_PV_array').plane(points,.065)
  for yy in (-dd/2,dd/2):
   a=p-u*ww/2+n*yy;b=p+u*ww/2+n*yy;zz=z+yy*math.tan(tilt);P('213_PV_module_frames','solar_grid','06_213_single_PV_array').box((a.x+b.x)/2,(a.y+b.y)/2,zz+.015,ww,.022,.026,ang)
objs=[b.finish() for b in B.values()]
# Building number is actually legible on the photographed road end; not a logo.
from mathutils import Matrix
for edge,fraction,z,size in [(0,.44,43.5,1.15),(2,.44,23.0,.85)]:
 a,b=Vector(R[edge]),Vector(R[(edge+1)%6]);u=(b-a).normalized();n=Vector((-u.y,u.x));q=a+(b-a)*fraction+n*.50
 cu=bpy.data.curves.new('213_observed_number','FONT');cu.body='213';cu.align_x='CENTER';cu.align_y='CENTER';cu.size=size*1.20;cu.extrude=.018
 ob=bpy.data.objects.new('213_numbered_photo_identity_e'+str(edge),cu);collection('07_observed_number_marks').objects.link(ob);ob.location=(q.x,q.y,z)
 rot=Matrix((Vector((-u.x,-u.y,0)),Vector((0,0,1)),Vector((n.x,n.y,0)))).transposed();ob.rotation_euler=rot.to_euler();cu.materials.append(M['ivory'] if edge==0 else M['window_frame'])
 bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH');objs.append(bpy.context.object)

for o in objs:o['source_site']='Maple Xi 213 only';o['evidence_ledger']='source-evidence.json'
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ID='bespoke-maple-xi-213-corrected';glb=OUT/(ID+'.glb')
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_yup=True,export_apply=True)
coords=[o.matrix_world@v.co for o in objs for v in o.data.vertices]
bounds=[[min(v[i] for v in coords) for i in range(3)],[max(v[i] for v in coords) for i in range(3)]]
tris=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objs)
validation={'assetId':ID,'axis':'Blender eastX northY upZ; GLB eastX upY southZ','boundsBlender':bounds,'dimensionsGLB':[bounds[1][0]-bounds[0][0],bounds[1][2]-bounds[0][2],bounds[1][1]-bounds[0][1]],'triangles':tris,'meshCount':len(objs),'materials':len(M),'sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'normalFinite':all(all(math.isfinite(t) for t in p.normal) and p.normal.length>.99 for o in objs for p in o.data.polygons)}
assert validation['normalFinite'] and abs(bounds[0][2])<1e-7
(OUT/'geometry-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
recipe={'siteId':'maple-xi-213-corrected','coordinate':A,'ringEastNorthM':R,'articulatedCoreRingEastNorthM':RG,'coreRecessDepthMEstimate':1.45,'sourceRegister':D['register'],'storeys':23,'groundStoreyM':BASE,'estimatedUpperStoreyM':STEP,'mainRoofDatumM':H,'datumConvention':'Use register height as nominal main roof for draft; not measured highest parapet/plant. Roof excess is independent estimate.','roofTopM':bounds[1][2],'roofRooms':rooms,'PV':{'wing':'SW','columns':cols,'rows':rows,'estimatedSizeM':[W,DEP],'tiltDegreesEstimate':10},'faces':faces,'sourceLedgerSha256':hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),'uncertainties':D['unresolved']+['No old GLB loaded. Roof zero-step and nominal74.5m main-roof datum are provisional registry interpretation; wrong February identification withdrawn. March+numbered April photo now govern facade.','Ground/lobby simplified conservative solid; unseen openings not invented.','Facade photos not rectified, window widths and row heights estimates.']}
(OUT/'recipe.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n')
# Inspection camera/light only, never exported.
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
world=scene.world or bpy.data.worlds.new('213_review_world');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.73,.77,.82,1);world.node_tree.nodes['Background'].inputs[1].default_value=.7
ld=bpy.data.lights.new('213_review_sun','SUN');lo=bpy.data.objects.new('213_review_sun',ld);collection('90_review_only').objects.link(lo);lo.rotation_euler=(.5,-.45,-.5);ld.energy=2.2;ld.angle=.12
cam=bpy.data.cameras.new('213_comparison_camera');co=bpy.data.objects.new('213_comparison_camera',cam);collection('90_review_only').objects.link(co);scene.camera=co;cam.type='ORTHO';cam.ortho_scale=110
co.location=(100,150,125);co.rotation_euler=(Vector((0,0,40))-co.location).to_track_quat('-Z','Y').to_euler()
scene.render.resolution_x=1300;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-213-corrected.blend'))
print(json.dumps(validation))
