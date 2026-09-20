import bpy,math,json,bmesh
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
REVIEW=coll('REVIEW_ONLY')
def mat(name,color,rough=.6,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;n=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal;return m
M=[mat('Ivy completed pale teal vision glass',(.14,.31,.30),.26,.36),mat('Ivy muted sea green spandrel',(.20,.35,.34),.32,.28),mat('White aluminium vertical frames',(.76,.78,.75),.40,.3),mat('Window horizontal silver members',(.48,.57,.55),.36,.4),mat('Deep inset opening and louver shadow',(.055,.12,.115),.55,.12),mat('Light aluminium ventilation grilles',(.55,.62,.59),.4,.4),mat('Grey podium limestone',(.31,.34,.31)),mat('Transparent bluegreen sloped roof glass',(.16,.34,.33),.14,.16),mat('Podium dark grey window surround',(.12,.16,.15)),mat('Review ground',(.25,.28,.26)),mat('Darker operable glazing',(.09,.235,.23),.30,.32)]
M[7].diffuse_color=(.16,.34,.33,.48)
n=next(n for n in M[7].node_tree.nodes if n.type=='BSDF_PRINCIPLED');n.inputs['Alpha'].default_value=.48
if hasattr(M[7],'surface_render_method'):M[7].surface_render_method='DITHERED'
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

def lerp(a,b,t):return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
def point(u,v):return (u*.626+v*.780,-u*.780+v*.626)
def edge(mesh,a,b,z0,z1,mi,out=.0,depth=.04):mesh.edge(point(*a),point(*b),z0,z1,mi,out,depth)
def prism(mesh,pts,z0,z1,mi):mesh.prism([point(*p) for p in pts],z0,z1,mi)
def roofbar(mesh,a,b,z0,z1,mi=3):
 A=Vector((*point(*a),z0+.075));B=Vector((*point(*b),z1+.075));d=(B-A).normalized();q=d.cross(Vector((0,0,1)))
 if q.length<.01:q=Vector((1,0,0))
 q.normalize();q*=.045;up=Vector((0,0,.045))
 mesh.face([tuple(A-q),tuple(B-q),tuple(B+q),tuple(A+q)],mi)
 mesh.face([tuple(A-q),tuple(A-q+up),tuple(B-q+up),tuple(B-q)],mi)
 mesh.face([tuple(A+q),tuple(B+q),tuple(B+q+up),tuple(A+q+up)],mi)
def facade(mesh,a,b,z0,z1,floor,major=False,roof=False):
 L=math.dist(a,b)
 if L<.2 or z1<=z0:return
 edge(mesh,a,b,z0,z1,7 if roof else 0,.02,.05)
 n=max(1,round(L/(1.95 if major else 2.55)))
 # Long planar faces have broad light strips at their edges, not a copy of the V-facade.
 if L>7 and not major:
  for ta,tb in [(0,.042),(.958,1)]:edge(mesh,lerp(a,b,ta),lerp(a,b,tb),z0,z1,2,.11,.12)
 for k in range(n+1):
  t=k/n;w=(.14 if major else .115)/L
  edge(mesh,lerp(a,b,max(0,t-w/2)),lerp(a,b,min(1,t+w/2)),z0,z1,2 if major or k in [0,n] else 3,.12,.1)
 for lev in range(math.ceil(z0/floor),math.ceil(z1/floor)):
  z=lev*floor
  if z<z0:continue
  edge(mesh,a,b,z,min(z+.12,z1),3,.10,.095)
  if z+.9<z1:edge(mesh,a,b,z+.13,z+.90,1,.055,.04)
  if z+1.2<z1:edge(mesh,a,b,z+1.07,z+1.12,3,.115,.05)
  if z+2.25<z1:edge(mesh,a,b,z+2.20,z+2.25,3,.115,.05)
 # Operable pane divisions form narrow vertical stacks visible in the real facade.
 # This is a fixed architectural layout; no seeded/random window illumination.
 if L>3:
  for col in range(n):
   t0=(col+.66)/n;t1=(col+.94)/n
   for lev in range(math.ceil(z0/floor),int(z1/floor)):
    z=lev*floor+1.18
    if z+1.00>z1:continue
    aa=lerp(a,b,t0);bb=lerp(a,b,t1);edge(mesh,aa,bb,z,z+1.0,10,.145,.035)
    edge(mesh,aa,bb,z,z+.045,3,.19,.045);edge(mesh,aa,bb,z+.955,z+1.,3,.19,.045)
 # Actual full-height pale ventilated strips flank the bay creases. Each floor has a dark louver recess.
 if major:
  for t in [.02,.98]:
   w=min(1.12,L*.25);aa=lerp(a,b,max(0,t-w/(2*L)));bb=lerp(a,b,min(1,t+w/(2*L)))
   edge(mesh,aa,bb,z0,z1,2,.23,.12)
   for lev in range(math.ceil(z0/floor),int(z1/floor)):
    z=lev*floor+.5
    if z+1.7>z1:continue
    edge(mesh,aa,bb,z,z+1.7,4,.365,.05)
    for q in range(8):edge(mesh,aa,bb,z+.11+q*.19,z+.14+q*.19,5,.43,.025)
def export_asset(asset,col):
 obs=list(col.objects);bpy.ops.object.select_all(action='DESELECT')
 for o in obs:o.select_set(True)
 bpy.context.view_layer.objects.active=obs[0]
 bpy.ops.export_scene.gltf(filepath=str(OUT/(asset['id']+'.glb')),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_texcoords=False,export_cameras=False,export_lights=False)
 lo=[min(v.co[k] for ob in obs for v in ob.data.vertices) for k in range(3)];hi=[max(v.co[k] for ob in obs for v in ob.data.vertices) for k in range(3)];tri=0
 for ob in obs:ob.data.calc_loop_triangles();tri+=len(ob.data.loop_triangles)
 checks.append({'id':asset['id'],'triangles':tri,'blenderBounds':[lo,hi],'footprintIds':asset['footprintIds']})
 lon=asset['coordinate']['lon'];lat=asset['coordinate']['lat'];dx=(lon-R['siteCenter'][0])*111320*math.cos(math.radians(R['siteCenter'][1]));dy=(lat-R['siteCenter'][1])*111320
 for ob in obs:ob.location=(dx,dy,0)
 assets.append(asset)
assets=[];checks=[]
for T in R['towers']:
 num=T['number'];col=coll('IVY_'+num+'_EDITABLE');body=Mesh(num+'_individual_stepped_masses');fac=Mesh(num+'_broad_faces_and_V_end');roofs=Mesh(num+'_sloped_glass_terraces_and_crown');floor=T['floorIntervalM'];parts=T['parts']
 # Subgrade/core volume retained within the shared podium to preserve each independent terrain datum.
 prism(body,[[-3,-3],[3,-3],[3,3],[-3,3]],0,8,8)
 prism(body,T['originalRing'],8,30,0)
 for a,b in zip(T['originalRing'],T['originalRing'][1:]+T['originalRing'][:1]):
  if T['creaseSign']*(a[0]+b[0])/2>19:facade(fac,a,b,8,30,floor,major=False)
 for k,P in enumerate(parts):
  pts=P['polygon'];H=P['heightM'];prism(body,pts,30,H,0)
  v0,v1=P['vRange'];rise=P['slopeRiseM'];roofpts=P['roofPolygon'];vmin=min(p[1] for p in roofpts);vmax=max(p[1] for p in roofpts)
  def zh(p):return H+rise*((p[1]-vmin)/(vmax-vmin) if k<3 else (vmax-p[1])/(vmax-vmin)) if rise else H
  for a,b in zip(pts,pts[1:]+pts[:1]):
   boundary=abs(a[1]-b[1])<1e-4 and (abs(a[1]-v0)<1e-4 or abs(a[1]-v1)<1e-4)
   zmin=8
   if boundary:
    neighbor=k-1 if abs(a[1]-v0)<1e-4 else k+1
    if 0<=neighbor<len(parts):zmin=parts[neighbor]['heightM']
   outer=T['creaseSign']*(a[0]+b[0])/2>19
   facade(fac,a,b,max(30 if outer else 8,zmin),H,floor,major=outer)
   edge(roofs,a,b,H-.08,H+.12,3,.0,.10)
  if rise:
   # Glazed sloping enclosure is inset from the upright facade edge. The individual
   # vertical window walls end in a small level coping, as in the completed street photo.
   # The .85m end-face setback is a photo estimate, not a surveyed architectural dimension.
   vv=[Vector((*p,0)) for p in roofpts]
   for tri in tessellate_polygon([vv]):
    q=[vv[x] if isinstance(x,int) else x for x in tri];roofs.face([(*point(p.x,p.y),zh((p.x,p.y))) for p in q],7)
   for a,b in zip(roofpts,roofpts[1:]+roofpts[:1]):
    roofs.face([(*point(*a),H),(*point(*b),H),(*point(*b),zh(b)),(*point(*a),zh(a))],7)
    roofbar(roofs,a,b,zh(a),zh(b))
    count=max(2,round(math.dist(a,b)/1.1))
    for j in range(1,count):
     q=lerp(a,b,j/count)
     if zh(q)>H+.12:roofbar(roofs,q,q,H,zh(q))
    for zoff in [2.1,4.2,6.3]:
     za=zh(a)-H;zb=zh(b)-H
     if min(za,zb)<zoff<max(za,zb) and abs(za-zb)>.01:
      cross=lerp(a,b,(zoff-za)/(zb-za));high=a if za>zb else b
      roofbar(roofs,cross,high,H+zoff,H+zoff)
   for aa,bb in P['roofGlazingLines']:roofbar(roofs,aa,bb,zh(aa),zh(bb))
 # Highest photographed crown has a low hipped glazed roof, not the CG mast.
 out=T['outerSign'];u0,u1=(-23.8,-11) if out<0 else (11,22.5);v0,v1=-5.8,5.8;H=T['highRoofM'];top=H+T['crownRiseM']
 ru0=u0+(.6 if out<0 else 3);ru1=u1-(3 if out<0 else .6)
 p0,p1,p2,p3=[point(*q) for q in [(u0,v0),(u1,v0),(u1,v1),(u0,v1)]];r0=point(ru0,0);r1=point(ru1,0)
 for verts in [[(*p0,H),(*p1,H),(*r1,top),(*r0,top)],[(*p1,H),(*p2,H),(*r1,top)],[(*p2,H),(*p3,H),(*r0,top),(*r1,top)],[(*p3,H),(*p0,H),(*r0,top)]]:roofs.face(verts,7)
 # Sloping crown ribs retain the actual pitched silhouette in distant views.
 for u in [ru0+(ru1-ru0)*i/8 for i in range(9)]:
  for sign in [-1,1]:
   A=Vector((*point(u,sign*5.8),H));B=Vector((*point(u,0),top));d=(B-A).normalized();perp=Vector((-.780,-.626,0))*.055
   roofs.face([tuple(A-perp+Vector((0,0,.07))),tuple(A+perp+Vector((0,0,.07))),tuple(B+perp+Vector((0,0,.07))),tuple(B-perp+Vector((0,0,.07)))],3)
 for frac in [.33,.66]:
  for sign in [-1,1]:
   vv=sign*5.8*(1-frac);aa=(u0+(ru0-u0)*frac,vv);bb=(u1+(ru1-u1)*frac,vv);roofbar(roofs,aa,bb,H+(top-H)*frac,H+(top-H)*frac)
 for uend,uridge in [(u0,ru0),(u1,ru1)]:
  for vv in [-4.5,-2.2,0,2.2,4.5]:roofbar(roofs,(uend,vv),(uridge,0),H,top)
 for m in [body,fac,roofs]:m.obj(col)
 asset={'id':T['id'],'nameKo':'여의도 롯데캐슬아이비 '+num+'동','file':T['id']+'.glb','blendSource':'lotte-castle-ivy.blend','coordinate':T['anchor'],'category':'apartment','district':'영등포구','footprintIds':[T['footprintId']],'supersedes':['apt-a15088915'],'referenceUrl':'https://kbland.kr/se/otd/1238381','components':['individual original footprint','stepped broad SW/NE facade','deep connector-facing V creases, explicit multi-view interpretation','white vertical ventilation bands','sloped glass terrace roofs','photo-estimated pitched glazed crown'],'uncertainties':R['uncertainties']+['KB2024 exact tower assignment unresolved. Inner connector-facing V ends are a multi-view interpretation of the central 2026 photo and both flat outer ends in2014/2023/2024 photographs; not an as-built drawing measurement.'],'floors':35,'floorsBasis':'single compound register35F, not separate per-tower measurement','heightBasis':T['heightBasis']}
 export_asset(asset,col)
C=R['connector'];col=coll('IVY_LOW_CONNECTOR_AND_SHARED_PODIUM');body=Mesh('shared_podium_exact_source_polygon');fac=Mesh('retail_glazing_and_connector');roof=Mesh('simplified_retail_terrace')
ring=C['podiumRing'];prism(body,C['recessedGroundRing'],0,4.45,6);prism(body,ring,4.45,8,6)
# This is the separately mapped raw8mcommercial base, not an extra residentialtower.
for a,b in zip(ring,ring[1:]+ring[:1]):
 L=math.dist(a,b)
 if L<.6:continue

 if a[1]>20 and b[1]>20 and min(a[0],b[0])<5.2 and max(a[0],b[0])>-5.2:
  # Front entrance is genuinely recessed: omit lower front glazing across its opening.
  edge(fac,a,b,4.45,7.6,0,.06,.06)
  dx=b[0]-a[0]
  if abs(dx)>.01:
   ts=sorted([0,1]+[max(0,min(1,(u-a[0])/dx)) for u in [-5.2,5.2]])
   for t0,t1 in zip(ts,ts[1:]):
    aa=lerp(a,b,t0);bb=lerp(a,b,t1)
    if abs((aa[0]+bb[0])/2)>5.2:edge(fac,aa,bb,.65,4.45,0,.06,.06)
 else:edge(fac,a,b,.65,7.6,0,.06,.06)
 for z in [3.65,7.65]:edge(fac,a,b,z,z+.3,8,.14,.12)
 cols=max(1,round(L/3.4))
 for k in range(cols+1):
  t=k/cols;pt=lerp(a,b,t);bottom=4.45 if pt[1]>20 and abs(pt[0])<5.2 else 0;edge(fac,lerp(a,b,max(0,t-.10/L)),lerp(a,b,min(1,t+.10/L)),bottom,8,6,.15,.3)
 edge(roof,a,b,8,8.35,6,.03,.20)
edge(fac,[-5.2,20.5],[5.2,20.5],.1,4.35,4,.06,.1)
for u in [-4.8,-2.4,0,2.4,4.8]:edge(fac,[u-.06,20.5],[u+.06,20.5],.1,4.35,3,.18,.1)
q=C['ring'];prism(body,q,8,30,0)
for a,b in zip(q,q[1:]+q[:1]):facade(fac,a,b,8,30,2.85,major=False);edge(roof,a,b,29.75,30.35,3,.04,.14)
# Entrance canopy facing the broad NE road: independent visible lowstructure inferred from photos.
prism(roof,[[-8,22.2],[8,22.2],[8,25.2],[-8,25.2]],4.25,4.5,6)
for u in [-7.6,7.6]:
 x,y=point(u,24.6);body.box((x,y,2.15),(.4,.4,4.3),6)
for m in [body,fac,roof]:m.obj(col)
export_asset({'id':C['id'],'nameKo':'롯데캐슬아이비 중앙 연결부·상가기단','file':C['id']+'.glb','blendSource':'lotte-castle-ivy.blend','coordinate':C['anchor'],'category':'landmark','district':'영등포구','footprintIds':C['footprintIds'],'supersedes':['apt-a15088915'],'referenceUrl':'https://realty.chosun.com/site/data/html_dir/2026/09/07/2026090702660.html','components':['central approx8storey glazed connector','separate original8m retail podium outline','simplified storefront piers and roadfront canopy'],'uncertainties':R['uncertainties']+[C['heightBasis']]},col)
g=Mesh('review_ground');g.box((0,0,-.35),(240,240,.5),9);g.obj(REVIEW)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1800;scene.render.resolution_y=1500;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX';scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.63,.72,.80,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.7
sun=bpy.data.lights.new('Photo review daylight','SUN');o=bpy.data.objects.new('Photo review daylight',sun);REVIEW.objects.link(o);o.rotation_euler=(.5,-.4,-.6);sun.energy=2.;sun.angle=.16
# Cameras in planUV frame. Street SW oblique matches appraiser101foreground102behind.
views=[('SW-appraiser-101-foreground',(-185,-220,77),(0,0,57),177),('NE-connector-frontal',(0,260,72),(0,0,57),182),('SE-end-102-Vface',(215,-80,85),(20,0,60),170),('NW-end-101',( -220,80,85),(-20,0,60),170),('roof-elevated',(-150,-190,210),(0,0,55),182),('roof-plan',(0,0,300),(0,0,0),165)]
for n,l,t,s in views:
 cam=bpy.data.cameras.new(n);o=bpy.data.objects.new(n,cam);REVIEW.objects.link(o);o.location=(*point(l[0],l[1]),l[2]);target=Vector((*point(t[0],t[1]),t[2]));o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=s
cam=bpy.data.cameras.new('SW-photo-ground');o=bpy.data.objects.new('SW-photo-ground',cam);REVIEW.objects.link(o);o.location=(*point(-113,-77),2.2);target=Vector((*point(-12,0),61));o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();cam.type='PERSP';cam.lens=32
scene.camera=bpy.data.objects[views[0][0]]
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'lotte-castle-ivy.blend'))
(OUT/'geometry-check.json').write_text(json.dumps({'assets':checks,'views':[x[0] for x in views],'embeddedImages':0},indent=2))
b={'siteId':'lotte-castle-ivy','sources':R['sources'],'assets':assets,'recipeFiles':['recipe.json','source-footprints.json','prepare.py','build.py'],'coverage':R['coverage'],'places':[{'id':'bespoke-lotte-castle-ivy','siteId':'lotte-castle-ivy','name':'여의도 롯데캐슬아이비','subtitle':'445세대 · 주거101·102동과 중앙연결부','center':R['siteCenter'],'zoom':17.4,'household_count':445,'source_url':R['sources'][-1]['url'],'supersedesPlaceIds':['model:apt-a15088915','seoul-apartment:A15088915']}]}
(OUT/'bundle.json').write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n');print(json.dumps(checks))
