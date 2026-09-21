"""Maple206 individually authored southern6lineL facades. Shared code below is neutral mesh/vector math only."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
O=Path(__file__).parent;NUMBER=globals().get('NUMBER',206);D=json.loads((O/f'input-{NUMBER}.json').read_text());V=[Vector(p)for p in D['ringEN']];N=len(V)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
colors={'pale':(.835,.83,.795,1),'metal':(.40,.455,.47,1),'glass':(.075,.125,.15,1),'shade':(.045,.075,.09,1),'stone':(.53,.515,.45,1),'grayfield':(.39,.435,.435,1),'seam':(.36,.37,.355,1),'roof':(.40,.415,.40,1),'solar':(.035,.058,.078,1),'pvtrim':(.35,.38,.39,1)};materials={}
for name,color in colors.items():
 m=bpy.data.materials.new(f'Maple{NUMBER}_'+name);m.diffuse_color=color;m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=color;p.inputs['Metallic'].default_value=.58 if name=='metal' else (.2 if name in ['glass','pvtrim'] else .015);p.inputs['Roughness'].default_value=.38 if name in ['metal','glass'] else .70;materials[name]=m
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
  me=bpy.data.meshes.new(self.name);me.from_pydata(self.verts,[],self.faces);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new(f'Maple{NUMBER}_'+self.name,me);bpy.context.collection.objects.link(o);me.materials.append(materials[self.mat]);o['asset_id']=D['id'];return o
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
# Shared representative family vocabulary; all extents/heights derive from this numbered tower.
base=D['baseM'];roof=D['bodyRoofM'];rows=D['rows'];pitch=(roof-base)/rows
part('inset_structural_body','pale').prism(inset(2.7),base,roof-.22)
part('individual_L_roof_slab','roof').prism(V,roof-.22,roof)
part('ground_recessed_lobby','stone').prism(inset(4.0),0,base)
window_samples=[]
def opening(e,l,r,z,sill,h,mat,name,depth=-.32,wide=False,offset=0):
 panel(e,l,r,z,z+sill,name+'_sill',mat,offset,.24)
 panel(e,l,r,z+sill+h,z+pitch,name+'_head',mat,offset,.24)
 panel(e,l+.001,r-.001,z+sill,z+sill+h,name+'_glass','glass',depth,.055)
 panel(e,l,r,z+sill-.04,z+sill+.03,name+'_silllip',mat,offset+.10,.32)
 if wide:post(e,l+(r-l)*.60,z+sill,z+sill+h,.066,name+'_sash','metal',depth+.10,.12)
 if len(window_samples)<100 and abs(z-(base+10*pitch))<.01:window_samples.append({'e':e,'t':l+(r-l)*.30,'z':z+sill+h*.5,'label':name})
# W22: two charcoal banks with smaller windows beside two large pale banks.
for k in range(rows):
 z=base+k*pitch;pm='stone'if k<3 else'pale';last=0
 cols=[(.06,.265,'grayfield','small'),(.31,.505,'grayfield','small'),(.58,.75,pm,'wide'),(.81,.96,pm,'wide')]
 for j,(l,r,m,kind) in enumerate(cols):
  panel(3,last,l,z,z+pitch,'NE_white_dividing_piers',pm,.02,.30);last=r
  opening(3,l,r,z,.80 if kind=='small'else .35,1.68 if kind=='small'else pitch-.65,m,'NE_'+kind+str(j),wide=True)
  if kind=='small':
   for dz in [.20,.34,.48]:panel(3,l+.03,r-.03,z+dz,z+dz+.019,'NE_gray_spandrel_seams','seam',.15,.02)
 panel(3,last,1,z,z+pitch,'NE_end_pier',pm,.02,.30)
# Unequal white grids: separate schedules for south-east and south-west elevations.
schedules={4:[(.025,.125,'wide'),(.166,.201,'small'),(.241,.276,'small'),(.325,.438,'wide'),(.48,.515,'small'),(.554,.591,'small'),(.64,.758,'wide'),(.80,.837,'small'),(.884,.967,'mid')],5:[(.026,.129,'wide'),(.17,.205,'small'),(.243,.278,'small'),(.318,.431,'wide'),(.47,.506,'small'),(.546,.582,'small'),(.626,.747,'wide'),(.784,.819,'small'),(.868,.968,'wide')]}
#205 broader physical arms keep comparable metre-sized bays, adding a service pair.
if NUMBER==205:schedules[4]=[(.02,.11,'wide'),(.14,.17,'small'),(.20,.23,'small'),(.27,.37,'wide'),(.40,.43,'small'),(.46,.49,'small'),(.53,.63,'wide'),(.66,.69,'small'),(.72,.75,'small'),(.79,.90,'wide'),(.94,.98,'small')]
for e,cols in schedules.items():
 for k in range(rows):
  z=base+k*pitch;pm='stone'if k<3 else'pale';last=0
  for l,r,kind in cols:
   panel(e,last,l,z,z+pitch,f'e{e}_unequal_white_piers',pm,.02,.25);last=r
   opening(e,l,r,z,.48 if kind=='wide'else .82,pitch-.80 if kind=='wide'else pitch-1.18,pm,f'e{e}_{kind}',wide=kind!='small')
  panel(e,last,1,z,z+pitch,f'e{e}_white_end_pier',pm,.02,.25)
# F21 projected blank core, deep full-height shaft and small service strips.
for e,banks in [(2,[(.055,.13,'wide'),(.175,.235,'mid'),(.295,.325,'small'),(.405,.44,'shaft'),(.80,.835,'small'),(.905,.94,'small')]),(1,[(.07,.15,'wide'),(.23,.30,'mid'),(.43,.465,'shaft'),(.72,.765,'small'),(.885,.925,'small')])]:
 for k in range(rows):
  z=base+k*pitch;pm='stone'if k<3 else'pale';last=0
  for l,r,kind in banks:
   panel(e,last,l,z,z+pitch,f'e{e}_projecting_white_core',pm,.60,.90);last=r
   sill=.18 if kind=='shaft'else(.85 if kind=='small'else .60);h=pitch-.36 if kind=='shaft'else(pitch-1.35 if kind=='small'else pitch-.97)
   opening(e,l,r,z,sill,h,pm,f'e{e}_{kind}',depth=-.82 if kind=='shaft'else-.32,wide=kind=='wide',offset=.10)
   for t in [l,r]:post(e,t,z,z+pitch,.15,f'e{e}_deep_reveal',pm,.13,1.05)
  panel(e,last,1,z,z+pitch,f'e{e}_projecting_white_core',pm,.60,.90)
  for l,r in [(0,.05),(.48,.69),(.95,1)]:
   panel(e,l,r,z+pitch-.025,z+pitch-.008,f'e{e}_cladding_horizontal_joint','seam',1.06,.018)
  for t in [.50,.59,.68]:post(e,t,z,z+pitch,.018,f'e{e}_cladding_vertical_joint','seam',1.06,.018)
# West short end is a continuous glass-and-metal face; top two rows return to white.
for k in range(rows):
 z=base+k*pitch;glasszone=k<rows-2;mat='metal'if glasszone else'pale'
 count=6 if NUMBER==206 else 7
 for j in range(count):
  l=(j+.045)/count;r=(j+.955)/count
  opening(0,l,r,z,.29 if glasszone else .6,pitch-.52 if glasszone else pitch-.94,mat,'west_glass_end'if glasszone else'west_upper_white',depth=-.22,wide=True,offset=.04)
 for j in range(count+1):post(0,j/count,z,z+pitch,.12,'west_vertical_metal_rib',mat,.12,.35)
# Ground stone base, tall portals, and open piloti beam supported by piers.
for e in range(N):
 if e==0:
  for j in range(6):
   l=(j+.07)/6;r=(j+.93)/6;panel(e,l,r,0,base,'glass_end_ground','glass',-.3,.06)
   post(e,j/6,0,base,.18,'glass_end_ground_mullion','metal',.02,.3)
 elif e in [4,5]:
  for l,r in [(0,.085),(.255,.31),(.49,.55),(.745,.80),(.94,1)]:panel(e,l,r,0,base,'piloti_stone_columns','stone',0,.85)
  panel(e,0,1,base-1.1,base,'piloti_head_beam','stone',0,.85)
 else:
  last=0
  for l,r in [(.09,.17),(.31,.39),(.55,.63),(.80,.89)]:
   panel(e,last,l,0,base,'ground_stone_piers','stone',0,.45);last=r
   panel(e,l,r,base-.9,base,'ground_stone_head','stone',0,.45)
   panel(e,l,r,.1,base-.9,'ground_tall_recess','glass',-.8,.06)
  panel(e,last,1,0,base,'ground_stone_end','stone',0,.45)
# Open edge rail, deliberately no factory-style tall crown.
for e in range(N):
 a=point(e,.02,-.22);b=point(e,.98,-.22);u,n,ang=basis(e);count=max(2,round((b-a).length/1.45))
 for j in range(count):part('roof_guardrail_posts','metal').box(a+(b-a)*j/(count-1),.06,.06,roof,roof+1.02,ang)
 for z in [roof+.25,roof+1.00]:part('roof_open_guardrail','metal').wall(a,b,z,z+.045,.045)
# Keep every plant/PV support inside the source roof polygon; metric placement remains inferred.
def inside(p):
 x,y=p;yes=False
 for a,b in zip(V,V[1:]+V[:1]):
  if (a.y>y)!=(b.y>y) and x<(b.x-a.x)*(y-a.y)/(b.y-a.y)+a.x:yes=not yes
 return yes
roof_support=[];plant_polygons=[]
def supported_box(name,mat,c,w,d,z0,z1,a):
 u=Vector((math.cos(a),math.sin(a)));n=Vector((-u.y,u.x));corners=[c+u*x+n*y for x,y in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]]
 assert all(inside(p)for p in corners),(name,[list(p)for p in corners]);
 if 'PV' in name:
  for poly in plant_polygons:
   separated=False
   for polygon in [corners,poly]:
    for q,r in zip(polygon,polygon[1:]+polygon[:1]):
     axis=Vector((-(r-q).y,(r-q).x)).normalized();aa=[v.dot(axis)for v in corners];bb=[v.dot(axis)for v in poly]
     if max(aa)<min(bb) or max(bb)<min(aa):separated=True
   assert separated,('PV intersects plant',name)
 elif name in ['west_service_plant','central_broad_plant','east_plant']:plant_polygons.append(corners)
 part(name,mat).box(c,w,d,z0,z1,a);roof_support.append({'component':name,'corners':[list(p)for p in corners],'insideRoof':True,'bottom':z0})
plants=[(5,.79,7.4,5.2,4.7,2.8,'west_service_plant'),(4,.67,7.0,6.0,4.6,4.35,'central_broad_plant'),(4,.16,7.3,5.5,4.4,3.55,'east_plant')]
for e,t,inn,w,d,h,name in plants:
 c=point(e,t,-inn);u,n,a=basis(e);supported_box(name,'pale',c,w,d,roof,roof+h,a)
 part(name+'_cap','seam').box(c,w+.08,d+.08,roof+h,roof+h+.08,a)
 part(name+'_vent','shade').wall(c-u*.6+n*(d/2+.035),c+u*.6+n*(d/2+.035),roof+h-1.65,roof+h-.75,.06)
 if name=='central_broad_plant':
  for j in range(3):part('central_roof_ducts','metal').box(c+u*(j*.6-1.8)-n*(d/2+.65),.38,1.0,roof,roof+1.2,a)
# Primary long bank follows individual NEwing. A smaller bank inferred from representative family.
for e,t,inn,length,width,name in [(4,.40,2.8,25.0 if NUMBER==206 else 33.0,3.3,'NE_long_PV'),(5,.53,4.0 if NUMBER==206 else 2.6,14.0 if NUMBER==206 else 20.0,3.9 if NUMBER==206 else 3.0,'SW_short_PV')]:
 u,n,a=basis(e);c=point(e,t,-inn);cols=round(length/1.35)
 for i in range(cols):
  for j in range(3):
   q=c+u*((i+.5)*length/cols-length/2)-n*((j+.5)*width/3-width/2);z=roof+.34+j*.25
   # Each individually supported panel checked against source roof, no floating arrays.
   supported_box(name+'_foot','metal',q,.08,.08,roof,z,a)
   supported_box(name+'_frame','pvtrim',q,length/cols-.025,width/3-.025,z,z+.075,a)
   supported_box(name+'_cell','solar',q,length/cols-.10,width/3-.10,z+.075,z+.11,a)
# Dishes represented as shallow low-poly pale satellite bowls, no photographs/textures.
for j in range(3):
 c=point(5,.89-j*.028,-3.1);a=basis(5)[2];supported_box('dish_support','metal',c,.1,.1,roof,roof+.7,a)
 poly=[c+Vector((math.cos(i*math.tau/12),math.sin(i*math.tau/12)))*.43 for i in range(12)];part('satellite_dish','pale').prism(poly,roof+.65,roof+.76)
objects=[s.finish()for s in parts.values()if s.verts]
for o in objects:o['modelingBasis']=D['modelingBasis'];o['inferredFromAssetIds']=','.join(D['inferredFromAssetIds'])
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0];bpy.ops.export_scene.gltf(filepath=str(O/f'bespoke-maple-xi-{NUMBER}.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_materials='EXPORT')
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=20;s.cycles.use_denoising=True;s.render.resolution_x=1000;s.render.resolution_y=1200;s.render.resolution_percentage=100;s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.69,.73,.79,1);s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65;s.view_settings.view_transform='AgX'
def camera(name,loc,target,scale,persp=False):
 d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='PERSP'if persp else'ORTHO';d.ortho_scale=scale;d.lens=44
camera('South_family',(140,-205,155),(0,0,roof*.48),148)
camera('North_core',(-120,185,130),(0,0,roof*.48),148)
camera('NE_street',(210,180,6),(0,0,roof*.48),145,True)
camera('West_glass',(-135,-65,70),(0,0,roof*.48),145)
camera('Roof_support',(70,-120,235),(0,0,roof),110 if NUMBER==205 else 91)
camera('Window_depth',(110,-100,48),(10,-1,47),37)
bpy.ops.object.light_add(type='SUN',location=(80,-60,150));bpy.context.object.rotation_euler=(.45,-.35,-.45);bpy.context.object.data.energy=1.7;bpy.context.object.data.angle=.14
bpy.ops.object.light_add(type='AREA',location=(-80,80,150));bpy.context.object.data.energy=80000;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=130
s.camera=bpy.data.objects['South_family'];bpy.ops.wm.save_as_mainfile(filepath=str(O/f'maple-{NUMBER}.blend'))
(O/f'build-summary-{NUMBER}.json').write_text(json.dumps({'id':D['id'],'components':[{'name':o.name,'vertices':len(o.data.vertices),'polygons':len(o.data.polygons)}for o in objects],'groundM':0,'roofM':roof,'heightM':D['heightM'],'windowSamples':window_samples,'roofSupport':roof_support},indent=2));print('MAPLE_BUILT',NUMBER,len(objects))
