"""Maple 101–107 representative-family inference on each retained numbered plan. No individual photo-face identity claimed."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
O=Path(__file__).parent;NUMBER=globals().get('NUMBER',101);D=json.loads((O/f'input-{NUMBER}.json').read_text());V=[Vector(p)for p in D['ringEN']];N=len(V)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
colors={'pale':(.835,.83,.795,1),'metal':(.28,.36,.41,1),'glass':(.075,.145,.19,1),'blueglass':(.18,.32,.42,1),'shade':(.045,.075,.09,1),'stone':(.53,.515,.45,1),'grayfield':(.39,.435,.435,1),'seam':(.36,.37,.355,1),'roof':(.40,.415,.40,1),'solar':(.035,.058,.078,1),'pvtrim':(.35,.38,.39,1)};materials={}
for name,color in colors.items():
 m=bpy.data.materials.new(f'Maple{NUMBER}_'+name);m.diffuse_color=color;m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=color;p.inputs['Metallic'].default_value=.58 if name=='metal' else (.2 if name in ['glass','blueglass','pvtrim'] else .015);p.inputs['Roughness'].default_value=.38 if name in ['metal','glass','blueglass'] else .70;materials[name]=m
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
# All geometry uses this tower's exact retained polygon, not a scaled representative mesh.
assert sum(V[i].x*V[(i+1)%N].y-V[(i+1)%N].x*V[i].y for i in range(N))<0
base=D['baseM'];roof=D['bodyRoofM'];rows=D['rows'];pitch=(roof-base)/rows
part('numbered_plan_inset_body','pale').prism(inset(1.55),base,roof-.24)
part('numbered_plan_roof','roof').prism(V,roof-.24,roof)
part('recessed_stone_lobby','stone').prism(inset(2.2),0,base)
window_samples=[];schedule=[]
long_edges=sorted(range(N),key=lambda e:(V[(e+1)%N]-V[e]).length,reverse=True)[:2]
primary=4 if N==6 else long_edges[0]
family=D['family'];darkshare={'L-TALL':.34,'L-MID':.64,'LOW-MID':.34,'BAR-TALL':.78}[family]
for e in range(N):
 length=(V[(e+1)%N]-V[e]).length
 role=('outer'if e in [4,5]else('end'if e in [0,3]else'core'))if N==6 else('outer'if e in long_edges else'end')
 count=max(3,round(length/(4.65 if role=='outer'else 3.6)))
 cols=[]
 if role=='core':
  # Broad projecting service planes and sparse deeply inset shafts, not a repeated window grid.
  cols=[(.09,.135,False,True),(.56,.60,False,True),(.82,.88,False,False)]
 else:
  for j in range(count):
   dark=(e==primary and (j+.5)/count<darkshare)or(role=='end'and e==(3 if N==6 else min(set(range(N))-set(long_edges)))and j<count-1)
   small=(j%4==2 and not dark);width=.25 if small else(.89 if dark else .82)
   l=(j+(1-width)/2)/count;r=(j+(1+width)/2)/count;cols.append((l,r,dark,small))
 schedule.append({'edge':e,'lengthM':length,'role':role,'bayCount':len(cols),'banks':cols,'primary':e==primary,'family':family})
 for k in range(rows):
  z=base+k*pitch;last=0;pm='stone'if k<2 else'pale';offset=.65 if role=='core'else .025;thick=1.35 if role=='core'else .27
  for j,(l,r,dark,small) in enumerate(cols):
   mat='metal'if dark else pm;prefix=f'e{e}_'+('dark'if dark else role)
   panel(e,last,l,z,z+pitch,prefix+'_piers',mat,offset,thick);last=r
   sill=.33 if dark else(1.02 if small else .65);h=pitch-sill-(.24 if dark else .36)
   panel(e,l,r,z,z+sill,prefix+'_sill',mat,offset,thick)
   panel(e,l,r,z+sill+h,z+pitch,prefix+'_head',mat,offset,thick)
   depth=-.55 if role=='core'else(-.22 if dark else-.35)
   panel(e,l,r,z+sill,z+sill+h,prefix+'_glass','blueglass'if dark and family=='BAR-TALL'else'glass',depth,.055)
   for t in [l,r]:post(e,t,z+sill,z+sill+h,.11 if dark else .075,prefix+'_reveal','metal'if dark else pm,.06 if dark else(offset-.12),.48 if role!='core'else 1.4)
   if (r-l)*length>1.55:post(e,l+(r-l)*.61,z+sill,z+sill+h,.065,prefix+'_unequal_sash','metal',depth+.10,.14)
   panel(e,l,r,z+sill-.035,z+sill+.03,prefix+'_silllip',mat,offset+.12,.42)
   if k==rows//2:window_samples.append({'e':e,'t':l+(r-l)*.28,'z':z+sill+h*.5})
   if dark:
    panel(e,l,r,z+.12,z+.145,prefix+'_spandrel_joint','seam',.20,.018)
    # Continuous metallic double-frame, giving the blue-gray face actual depth.
    post(e,l,z,z+pitch,.15,prefix+'_projected_metal_rib','metal',.16,.36)
  panel(e,last,1,z,z+pitch,f'e{e}_end_pier',pm,offset,thick)
  if role=='core':
   panel(e,0,1,z+.1,z+.12,f'e{e}_cladding_joint','seam',1.335,.014)
   for t in [.24,.36,.46,.69,.75]:post(e,t,z,z+pitch,.014,f'e{e}_core_panel_joint','seam',1.335,.014)
 # Fewer stone piers and deeper glass plinth make the base independent of upper bay count.
 groundcount=max(3,round(length/6.5))
 for j in range(groundcount):
  l=(j+.12)/groundcount;r=(j+.88)/groundcount
  panel(e,j/groundcount,l,0,base,f'e{e}_base_pier','stone',0,.85)
  panel(e,r,(j+1)/groundcount,0,base,f'e{e}_base_pier','stone',0,.85)
  panel(e,l,r,base-.9,base,f'e{e}_base_head','stone',0,.85)
  panel(e,l,r,.1,base-.9,f'e{e}_lobby_glass','glass',-1.0,.055)
 crown=2.85 if e==primary else(2.3 if role=='end'else 1.75)
 if family=='LOW-MID':crown-=.25
 # Opaque shallow fascia plus deep vertical fins, with differentiated primary-plane height/material.
 panel(e,0,1,roof-.10,roof+.26,f'e{e}_roof_fascia','metal'if e==primary else'pale',0,.38)
 countfin=max(2,round((length-1)/.43))
 for j in range(countfin):
  t=(.5+(length-1)*j/(countfin-1))/length;darkfin=(e==primary and t<darkshare)
  post(e,t,roof+.22,roof+crown,.115,f'e{e}_deep_crown_fins','metal'if darkfin else'pale',-.08,.50)
 for z in [roof+.26,roof+crown]:panel(e,.5/length,1-.5/length,z,z+.07,f'e{e}_crown_rail','metal',-.08,.12)
def inside(p):
 x,y=p;yes=False
 for a,b in zip(V,V[1:]+V[:1]):
  if (a.y>y)!=(b.y>y) and x<(b.x-a.x)*(y-a.y)/(b.y-a.y)+a.x:yes=not yes
 return yes
roof_support=[];occupied=[];pv_polys=[]
def corners(c,w,d,a):
 u=Vector((math.cos(a),math.sin(a)));n=Vector((-u.y,u.x));return[c+u*x+n*y for x,y in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]]
def fits(c,w,d,a):
 poly=corners(c,w,d,a)
 if not all(inside(p)for p in poly):return False
 for q,radius in occupied:
  if (c-q).length<(math.hypot(w,d)/2+radius+.6):return False
 for other in pv_polys:
  separated=False
  for polygon in [poly,other]:
   for q,r in zip(polygon,polygon[1:]+polygon[:1]):
    axis=Vector((-(r-q).y,(r-q).x)).normalized();aa=[v.dot(axis)for v in poly];bb=[v.dot(axis)for v in other]
    if max(aa)+.08<min(bb)or max(bb)+.08<min(aa):separated=True
  if not separated:return False
 return True
def roofbox(name,mat,c,w,d,z0,z1,a):
 assert all(inside(p)for p in corners(c,w,d,a))
 part(name,mat).box(c,w,d,z0,z1,a);roof_support.append({'name':name,'insideRoof':True,'bottom':z0,'corners':[list(p)for p in corners(c,w,d,a)]})
# Find metric positions against each own outline; never copy representative plant coordinates.
roof_edges=[5,4]if N==6 else long_edges
for idx,e in enumerate(roof_edges):
 a=basis(e)[2];found=False
 for t in [.72,.28,.5,.84,.16]:
  for inn in [5.0,6.0,7.0,4.2]:
   c=point(e,t,-inn);w,d=(5.0,3.5)if idx==0 else(4.0,3.1)
   if fits(c,w+.2,d+.2,a):
    h=4.1 if idx==0 else 3.15
    roofbox(f'plant_{idx}','pale',c,w,d,roof,roof+h,a);roofbox(f'plant_{idx}_cap','seam',c,w+.16,d+.16,roof+h,roof+h+.12,a)
    u,n,_=basis(e);part(f'plant_{idx}_vent','shade').wall(c-u*.65+n*(d/2+.035),c+u*.65+n*(d/2+.035),roof+h-1.5,roof+h-.65,.06)
    occupied.append((c,math.hypot(w,d)/2));found=True;break
  if found:break
 assert found,('plant no fit',NUMBER,e)
for e in roof_edges:
 a=basis(e)[2];length=(V[(e+1)%N]-V[e]).length
 for j in range(max(2,int(length/2.2))):
  c=point(e,(j+.5)/max(2,int(length/2.2)),-2.6)
  if fits(c,1.75,2.25,a):
   roofbox('PV_feet','metal',c,.12,.12,roof,roof+.38,a);roofbox('PV_frame','pvtrim',c,1.75,2.25,roof+.38,roof+.47,a);roofbox('PV_cells','solar',c,1.64,2.14,roof+.47,roof+.51,a);pv_polys.append(corners(c,1.75,2.25,a))
objects=[s.finish()for s in parts.values()if s.verts]
for o in objects:o['modelingBasis']=D['modelingBasis'];o['inferredFromAssetIds']=','.join(D['inferredFromAssetIds'])
for im in list(bpy.data.images):bpy.data.images.remove(im)
for db in [bpy.data.meshes,bpy.data.materials,bpy.data.curves]:
 for item in list(db):
  if item.users==0:db.remove(item)
s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0];bpy.ops.export_scene.gltf(filepath=str(O/f'bespoke-maple-xi-{NUMBER}.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_materials='EXPORT')
s.render.engine='CYCLES';s.cycles.samples=12;s.cycles.use_denoising=True;s.render.resolution_x=720;s.render.resolution_y=900;s.render.resolution_percentage=100;s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.69,.73,.79,1);s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65;s.view_settings.view_transform='AgX'
cx=(min(p.x for p in V)+max(p.x for p in V))/2;cy=(min(p.y for p in V)+max(p.y for p in V))/2
span=max(max(p.x for p in V)-min(p.x for p in V),max(p.y for p in V)-min(p.y for p in V))
def camera(name,loc,target,scale):
 d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='ORTHO';d.ortho_scale=scale
camera('Street',(cx+155,cy-220,roof*.68),(cx,cy,roof*.48),max(D['heightM']*1.20,span*1.35))
camera('Opposite',(cx-155,cy+220,roof*.68),(cx,cy,roof*.48),max(D['heightM']*1.20,span*1.35))
camera('Close',(cx+110,cy-155,roof*.50),(cx,cy,roof*.50),26)
camera('Roof',(cx+80,cy-100,roof+150),(cx,cy,roof),span*1.45)
bpy.ops.object.light_add(type='SUN',location=(80,-60,150));bpy.context.object.rotation_euler=(.45,-.35,-.45);bpy.context.object.data.energy=1.7;bpy.context.object.data.angle=.14
s.camera=bpy.data.objects['Street'];bpy.ops.wm.save_as_mainfile(filepath=str(O/f'maple-{NUMBER}.blend'))
(O/f'build-summary-{NUMBER}.json').write_text(json.dumps({'id':D['id'],'components':[{'name':o.name,'vertices':len(o.data.vertices),'polygons':len(o.data.polygons)}for o in objects],'groundM':0,'roofM':roof,'heightM':D['heightM'],'windowSamples':window_samples,'roofSupport':roof_support,'facadeSchedule':schedule},indent=2));print('MAPLE_BUILT',NUMBER,len(objects))
