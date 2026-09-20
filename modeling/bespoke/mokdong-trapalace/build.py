import bpy, math, json, bmesh, hashlib
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
REVIEW=coll('REVIEW_ONLY_NOT_EXPORTED')
def mat(name,c,rough=.5,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True;n=next(x for x in m.node_tree.nodes if x.type=='BSDF_PRINCIPLED');n.inputs['Base Color'].default_value=(*c,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal;return m
M=[mat('Trapalace warm pale stone piers',(.67,.65,.53),.65),mat('Built sea-green window glass',(.19,.34,.32),.22,.38),mat('Dark recessed openable panes',(.075,.16,.15),.27,.32),mat('Silver warm curtainwall mullions',(.53,.57,.51),.38,.45),mat('Muted turquoise opaque spandrel',(.27,.39,.35),.5,.15),mat('Reddish brown parkingpodium stone',(.43,.28,.22),.78),mat('Dark parking louver slots',(.07,.085,.075),.8),mat('Roof pale concrete slab',(.64,.64,.55),.72),mat('Helipad grey surface',(.36,.39,.35),.8),mat('Steel bridge braces',(.30,.33,.28),.44,.4),mat('Retail glazing',(.13,.23,.22),.25,.32),mat('Reviewground',(.30,.32,.30),.9),mat('Planter muted green',(.20,.26,.12),.9)]
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

def lerp(a,b,t):return [a[k]+(b[k]-a[k])*t for k in range(len(a))]
def strip(mesh,a,b,z0,z1,mi,offset=.06,depth=.08):mesh.edge(a,b,z0,z1,mi,offset,depth)
def bar(mesh,a,b,width,mi):
 a,b=Vector(a),Vector(b);d=b-a
 if d.length<.001:return
 u=d.cross(Vector((0,0,1)))
 if u.length<.01:u=d.cross(Vector((1,0,0)))
 u.normalize();v=d.normalized().cross(u);u*=width/2;v*=width/2
 q=[a-u-v,a+u-v,a+u+v,a-u+v,b-u-v,b+u-v,b+u+v,b-u+v]
 for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:mesh.face([tuple(q[i]) for i in ids],mi)
def ensureccw(pts):
 return list(reversed(pts)) if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts,pts[1:]+pts[:1]))<0 else pts

def facade(mesh,pts,z0,z1,bodyTop,step,upper=False):
 # SIAPLAN2: broad structural stonepiers bracket individual bluegreen window
 # pairs below; higher penthouse bays change to continuous tall glazing.
 pts=ensureccw(pts)
 for ei,(a,b) in enumerate(zip(pts,pts[1:]+pts[:1])):
  L=math.dist(a,b);n=max(1,round(L/5.7));slot=L/n
  # Short orthogonal rearstem sides are mostlystone with narrow servicewindows;
  # diamondlongfaces have different expression, not four identicalglazedfaces.
  narrow=L<9
  for k in range(n):
   ta=(k+.10)/n;tb=(k+.90)/n
   if narrow:ta=(k+.31)/n;tb=(k+.69)/n
   aa,bb=lerp(a,b,ta),lerp(a,b,tb)
   strip(mesh,aa,bb,z0+.3,z1-.2,1,.10,.08)
   # Lower stone spandrels vs uppercontinuous curtainwall panes.
   z=z0
   while z<z1-.15:
    zz=min(z+step,z1)
    if upper or z>bodyTop-23:
     strip(mesh,aa,bb,z,min(z+.09,z1),3,.26,.08)
     strip(mesh,aa,bb,min(z+.70,z1-.02),min(z+.79,z1),3,.26,.06)
    else:
     strip(mesh,aa,bb,z,min(z+.83,z1),0,.28,.15)
     strip(mesh,aa,bb,min(z+.85,z1-.02),min(z+.95,z1),3,.31,.06)
    # Paired window modules; deliberatelyallthe same realpattern ratherthanrandom.
    for t in [.0,.48,1.0]:
     v=lerp(aa,bb,t);w=.045/max(L*.8/n,.01);strip(mesh,lerp(aa,bb,max(0,t-w)),lerp(aa,bb,min(1,t+w)),z,zz,3,.29,.055)
    if zz-z>2:
     strip(mesh,lerp(aa,bb,.59),lerp(aa,bb,.92),z+1.07,min(z+1.91,zz),2,.32,.035)
     strip(mesh,aa,bb,z+1.88,min(z+1.95,zz),3,.31,.045)
    z+=step
  # broad piers give the stoneverticalrhythm visible in actual completedphoto.
  for k in range(n+1):
   t=k/n;w=(.87 if k in [0,n] else .55)/L
   strip(mesh,lerp(a,b,max(0,t-w)),lerp(a,b,min(1,t+w)),z0,z1+.28,0,.3,.20)
  if upper:
   strip(mesh,a,b,z0,z0+.5,0,.33,.40);strip(mesh,a,b,z1-.5,z1+.28,0,.33,.40)
  elif L>15:
   for z in [bodyTop-23,bodyTop]:strip(mesh,a,b,z-.65,z+.05,0,.33,.42)

def export(col,A):
 bpy.ops.object.select_all(action='DESELECT');obs=list(col.objects)
 for ob in obs:ob.select_set(True)
 bpy.context.view_layer.objects.active=obs[0]
 bpy.ops.export_scene.gltf(filepath=str(OUT/A['file']),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_texcoords=False,export_cameras=False,export_lights=False)
 lo=[min(v.co[k] for ob in obs for v in ob.data.vertices) for k in range(3)];hi=[max(v.co[k] for ob in obs for v in ob.data.vertices) for k in range(3)];tri=0
 for ob in obs:ob.data.calc_loop_triangles();tri+=len(ob.data.loop_triangles)
 checks.append({'id':A['id'],'blenderBounds':[lo,hi],'triangles':tri,'sha256':hashlib.sha256((OUT/A['file']).read_bytes()).hexdigest()})
 dx=(A['coordinate']['lon']-R['siteCenter'][0])*111320*math.cos(math.radians(R['siteCenter'][1]));dy=(A['coordinate']['lat']-R['siteCenter'][1])*111320
 for ob in obs:ob.location=(dx,dy,0)
 assets.append(A)
assets=[];checks=[]
for ti,T in enumerate(R['towers']):
 col=coll(T['label']+'_individual_tower');body=Mesh(T['label']+'_roofplan_body');fac=Mesh(T['label']+'_stone_and_green_window_bays');roof=Mesh(T['label']+'_stepped_crown_and_round_helipad');br=Mesh(T['label']+'_34F_bridge_if_A')
 pts=ensureccw(T['profile']);h=T['heightM'];zt=T['bodyTopM'];zb=T['bodyBottomM'];step=(T['occupiedM']-zb)/(T['floors']-9)
 body.prism(pts,0,zt,0);facade(fac,pts,zb,zt,zt,step)
 # The two staggered penthousevolumes stand above the broad mainwings.
 for si,S in enumerate(T['stages']):
  q=ensureccw(S['profile']);body.prism(q,zb if si==1 else S['bottom'],S['top'],0);facade(fac,q,S['bottom'],S['top'],zt,4.7,True)
  if si==1:facade(fac,q,zb,S['bottom'],zt,step)
  roof.prism(q,S['top'],S['top']+.22,7)
 # Open tallframe at rearshoulder: observed in SIAPLAN2. It is not filledin.
 rear=pts[:3]
 for a,b in zip(rear,rear[1:]):
  roof.edge(a,b,zt+8.2,zt+8.9,0,.1,.35)
 for q in rear:bar(roof,(*q,zt),(*q,zt+8.9),.85,0)
 # Strong uninterrupted stonepylons at the southcorner highcore: the source
 # uppercloseup has broadpalesides and a narrowdarkglazingrecess, not allglass.
 high=ensureccw(T['stages'][1]['profile'])
 for a,b in zip(high,high[1:]+high[:1]):
  L=math.dist(a,b)
  # A wide edge-pier on each corner continues past the lowerwindowgrid.
  for t0,t1 in [(0,.14),(.88,1.0)]:
   fac.edge(lerp(a,b,t0),lerp(a,b,t1),zb,h-1.12,0,.44,.23)
  # The highcore is onlyraised above the mainterrace; piersbelow areactual
  # facadedetail strips, no new freestanding tower mass.
 # Thin guardrail around main terrace, with open air behind it.
 for a,b in zip(pts,pts[1:]+pts[:1]):
  bar(roof,(*a,zt+1.05),(*b,zt+1.05),.06,9)
  n=max(1,round(math.dist(a,b)/2.3))
  for j in range(n+1):q=lerp(a,b,j/n);bar(roof,(*q,zt+.08),(*q,zt+1.05),.05,9)
 # Exact distinctive circularcap: solid centraldiamond and open radialannulus.
 # The primaryhighview shows light sky betweenouterringandcorneredslab.
 x,y=T['ringCenter'];rad=T['ringRadiusM'];N=80;z=h-.60
 ring=[]
 for j in range(N):
  a=2*math.pi*j/N;b=2*math.pi*(j+1)/N
  aa=(x+rad*math.cos(a),y+rad*math.sin(a));bb=(x+rad*math.cos(b),y+rad*math.sin(b));ai=(x+(rad-.48)*math.cos(a),y+(rad-.48)*math.sin(a));bi=(x+(rad-.48)*math.cos(b),y+(rad-.48)*math.sin(b))
  roof.prism([aa,bb,bi,ai],z-.25,z+.38,7);bar(roof,(*aa,h-.06),(*bb,h-.06),.045,9)
  if j%4==0:bar(roof,(*aa,z+.38),(*aa,h-.06),.045,9)
  if j%5==0:
   inner=(x+6*math.cos(a),y+6*math.sin(a));bar(roof,(*inner,z-.70),(*aa,z+.08),.48,7)
 core=T['stages'][1]['profile'];roof.prism(core,z-.10,z+.12,8)
 # Narrow paleHmarking on the insettop; authoredgeometry, no sourcedimage.
 roof.box((x-1.65,y,z+.14),(.35,4.4,.035),7);roof.box((x+1.65,y,z+.14),(.35,4.4,.035),7);roof.box((x,y,z+.14),(3.3,.35,.035),7)
 # Lower reddish exposedparking skin only below8F, no duplicatedtowerglass.
 for a,b in zip(pts,pts[1:]+pts[:1]):
  fac.edge(a,b,0,zb,5,.2,.15);L=math.dist(a,b);n=max(1,round(L/3.2))
  for k in range(n):
   aa,bb=lerp(a,b,(k+.20)/n),lerp(a,b,(k+.80)/n)
   for f in range(1,8):fac.edge(aa,bb,f*3.5,f*3.5+1.7,6,.40,.07)
  fac.edge(a,b,zb-.55,zb+.15,5,.42,.28)
 if ti in [0,2]:
  other=R['towers'][ti+1];dx=(other['coordinate']['lon']-T['coordinate']['lon'])*111320*math.cos(math.radians(R['siteCenter'][1]));dy=(other['coordinate']['lat']-T['coordinate']['lat'])*111320;dist=math.hypot(dx,dy);u=(dx/dist,dy/dist);v=(-u[1],u[0]);a=(u[0]*17,u[1]*17);b=(dx-u[0]*17,dy-u[1]*17);zbridge=114.0
  corners=[(a[0]+v[0]*2.5,a[1]+v[1]*2.5),(b[0]+v[0]*2.5,b[1]+v[1]*2.5),(b[0]-v[0]*2.5,b[1]-v[1]*2.5),(a[0]-v[0]*2.5,a[1]-v[1]*2.5)]
  br.prism(corners,zbridge-.5,zbridge,9);br.prism(corners,zbridge+3.3,zbridge+3.6,7)
  for sg in [-1,1]:
   aa=(a[0]+sg*v[0]*2.5,a[1]+sg*v[1]*2.5);bb=(b[0]+sg*v[0]*2.5,b[1]+sg*v[1]*2.5);br.face([(*aa,zbridge),(*bb,zbridge),(*bb,zbridge+3.3),(*aa,zbridge+3.3)],1)
   for j in range(7):q=lerp(aa,bb,j/6);bar(br,(*q,zbridge),(*q,zbridge+3.3),.18,9)
   for j in range(3):q=lerp(aa,bb,j/3);qq=lerp(aa,bb,(j+1)/3);bar(br,(*q,zbridge+.2),(*qq,zbridge+3.1),.21,9);bar(br,(*q,zbridge+3.1),(*qq,zbridge+.2),.21,9)
 for m in [body,fac,roof]:m.obj(col)
 if br.v:br.obj(col)
 A={'id':T['id'],'nameKo':'목동 트라팰리스 '+T['label']+'동','file':T['id']+'.glb','blendSource':'mokdong-trapalace.blend','coordinate':T['coordinate'],'category':'apartment','district':'양천구','footprintIds':[T['footprintId']],'supersedes':['apt-a15870101'],'referenceUrl':R['sources'][0]['url'],'components':['numberedplan diamondfloorplate withprojectingrearstem','broadpale piers andpairedbluegreen panes','tallglazedupperbays contrastedwithlowerstonespandrels','two staggeredpenthousevolumes','open radialringwithcentraldiamondhelipad','reddishlowerparkingfloors']+(['own34Fsteelbracedglazedbridge'] if ti in [0,2] else []),'uncertainties':R['uncertainties'],'floors':T['floors'],'heightBasis':'CTBUH architectural andhelipadtop, notregistersinglecompoundheight; intermediatelevelsphotointerpretation','modelEnvelopeM':h}
 export(col,A)
# Simplified independentlowretailfront + peripheralparkingwings, retaining the
# centralpublicpedestrianstreet ratherthan a solid whole-sitepodiumblock.
col=coll('LOW_COMMERCIAL_AND_PARKING_WINGS');m=Mesh('reddishstone_podium_and_shopfronts');g=Mesh('retail_glass_windows')
for P in R['podiums']:
 for q in P['loops']:
  q=ensureccw(q);m.prism(q,0,28.4,5)
  for a,b in zip(q,q[1:]+q[:1]):
   L=math.dist(a,b);n=max(1,round(L/3.4))
   for j in range(n):
    aa=lerp(a,b,(j+.17)/n);bb=lerp(a,b,(j+.82)/n)
    for f in range(1,8):g.edge(aa,bb,3.5*f,3.5*f+1.75,6,.20,.08)
   m.edge(a,b,27.8,28.6,5,.25,.30)
 # Existing8Fretailoutline, no nearbybuildingownership.
 poly=P['retailGeometry']['coordinates'][0]
 q=ensureccw([[(x-R['siteCenter'][0])*111320*math.cos(math.radians(R['siteCenter'][1])),(y-R['siteCenter'][1])*111320] for x,y in poly[:-1]])
 m.prism(q,0,27.6,5)
 for a,b in zip(q,q[1:]+q[:1]):
  L=math.dist(a,b);n=max(1,round(L/4.8))
  for f in range(8):
   z=f*3.45
   for j in range(n):g.edge(lerp(a,b,(j+.05)/n),lerp(a,b,(j+.94)/n),z+.32,z+2.92,10,.22,.08)
   m.edge(a,b,z+2.93,z+3.4,5,.30,.15)
  for j in range(n+1):t=j/n;w=.25/L;m.edge(lerp(a,b,max(0,t-w)),lerp(a,b,min(1,t+w)),0,28.4,5,.40,.27)
for mesh in [m,g]:mesh.obj(col)
export(col,{'id':'bespoke-mokdong-trapalace-podium','nameKo':'목동 트라팰리스 동서 저층상가·주거주차장','file':'bespoke-mokdong-trapalace-podium.glb','blendSource':'mokdong-trapalace.blend','coordinate':{'lon':R['siteCenter'][0],'lat':R['siteCenter'][1]},'category':'landmark','district':'양천구','footprintIds':[p['retailFootprintId'] for p in R['podiums']],'supersedes':['apt-a15870101'],'referenceUrl':R['sources'][0]['url'],'components':['two separate8Ffrontretailbars onexistingoutlines','simplifiedterracotta parkingwings','open publiccentrepassage'],'uncertainties':R['uncertainties']+['Commercialheight27.6m estimatedfrom8levels; retailandparkingfacadedetails simplified.']})
ground=Mesh('review_ground');ground.box((0,0,-.5),(330,330,.7),11);ground.obj(REVIEW)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1800;scene.render.resolution_y=1500;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX';scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.68,.77,.85,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.8
sun=bpy.data.lights.new('Daylight','SUN');ob=bpy.data.objects.new('Daylight',sun);REVIEW.objects.link(ob);ob.rotation_euler=(.4,-.5,-.6);sun.energy=2.2;sun.angle=.15
views=[('SW-full',(-240,-280,110),(0,0,90),245),('SE-full',(250,-230,110),(0,0,90),245),('north-reverse',(30,290,115),(0,0,90),245),('elevated-source',(-260,-170,230),(-23,10,155),120),('western-crown',(-120,-125,215),(-39,24,169),82),('roof-plan',(0,0,430),(0,0,0),215),('helipad-low-angle',(-100,-90,160),(-38,23,183),58)]
for name,loc,target,scale in views:
 cam=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,cam);REVIEW.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=scale
scene.camera=bpy.data.objects['SW-full'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'mokdong-trapalace.blend'))
(OUT/'geometry-check.json').write_text(json.dumps({'assets':checks,'views':[v[0] for v in views],'embeddedImages':0},ensure_ascii=False,indent=2))
bundle={'siteId':'mokdong-trapalace','sources':R['sources'],'assets':assets,'recipeFiles':['recipe.json','build.py','prepare.py','source-buildings.json','source-register.json','source-ledger.json','REFERENCE-NOTES.md','validate.py','render-v3.py'],'coverage':R['coverage'],'places':[{'id':'bespoke-mokdong-trapalace','siteId':'mokdong-trapalace','name':'목동 트라팰리스','subtitle':'522세대 · 웨스턴A/B·이스턴A/B','center':R['siteCenter'],'zoom':17.25,'household_count':522,'source_url':R['sources'][2]['url'],'supersedesPlaceIds':['model:apt-a15870101','seoul-apartment:A15870101']}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n');print(json.dumps(checks))
