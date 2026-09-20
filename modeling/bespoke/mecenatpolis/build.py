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
def mat(name,c,rough=.5,metal=0,alpha=1):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,alpha);m.use_nodes=True;n=next(x for x in m.node_tree.nodes if x.type=='BSDF_PRINCIPLED');n.inputs['Base Color'].default_value=(*c,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal;n.inputs['Alpha'].default_value=alpha
 if alpha<1 and hasattr(m,'surface_render_method'):m.surface_render_method='DITHERED'
 return m
M=[mat('Mecenat completed blue-green curtain wall',(.16,.32,.36),.22,.42),mat('Paler opaque blue-green spandrel',(.24,.39,.42),.35,.28),mat('Warm pale aluminium mullions',(.66,.70,.67),.4,.45),mat('Recessed dark operable glazing',(.045,.14,.17),.28,.3),mat('Cream service-stack metal cladding',(.72,.73,.65),.52,.20),mat('Dark thin projecting storey ledge',(.105,.15,.155),.4,.35),mat('Podium pale limestone',(.69,.62,.47),.73),mat('Raised podium glazing',(.095,.19,.205),.3,.3),mat('Transparent roof screen glazing',(.18,.40,.45),.25,.20,.50),mat('Roof slab warm offwhite',(.68,.69,.65),.6),mat('Roof plant darkgrey',(.24,.27,.27)),mat('Landscaped podium muted green',(.21,.265,.15),.95),mat('Review ground',(.31,.33,.32)),mat('Canopy glass',(.25,.44,.47),.15,.15,.30)]
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
def facade(mesh,a,b,z0,z1,interval,edgeIndex):
 L=math.dist(a,b)
 if L<.2:return
 # One actual continuous glazed wall with close horizontal silver divisions,
 # not a repeated generic stone-window building. Fine3pane units, servicebands
 # only on long faces, as visible in architectphotos07–09 and elevations47/48.
 strip(mesh,a,b,z0,z1,0,.02,.06)
 n=max(1,round(L/1.38))
 for k in range(n+1):
  t=k/n;w=.09/L;strip(mesh,lerp(a,b,max(0,t-w/2)),lerp(a,b,min(1,t+w/2)),z0,z1,2,.14,.07)
 for f in range(round((z1-z0)/interval)+1):
  z=z0+f*interval
  if z>z1:continue
  strip(mesh,a,b,z,min(z+.10,z1+.03),2,.15,.06)
  if z+.80<z1:strip(mesh,a,b,z+.12,z+.77,1,.09,.025)
  # An intermediate transom and separated operable vent are architectural
  # regularity from the source, with no seeded random facade colours.
  if z+1.72<z1:strip(mesh,a,b,z+1.68,z+1.74,2,.15,.055)
  if f and f%8==0:strip(mesh,a,b,z-.04,z+.10,5,.24,.30)
  if L>3 and f<round((z1-z0)/interval):
   for k in range(n):
    if k%4==2:
     aa=lerp(a,b,(k+.67)/n);bb=lerp(a,b,(k+.94)/n)
     strip(mesh,aa,bb,z+1.87,min(z+2.71,z1),3,.19,.035)
     strip(mesh,aa,bb,z+1.85,min(z+1.92,z1),2,.25,.04)
 # The conspicuous narrow pale service/louver stacks interrupt full glass.
 if L>11:
  positions=[.24,.77] if L>24 else [.70]
  for t in positions:
   aa=lerp(a,b,t-.49/L);bb=lerp(a,b,t+.49/L)
   strip(mesh,aa,bb,z0,z1,4,.27,.15)
   for f in range(round((z1-z0)/interval)):
    z=z0+f*interval+.55
    strip(mesh,aa,bb,z,z+.94,3,.45,.045)
    for k in range(6):strip(mesh,aa,bb,z+.10+k*.14,z+.135+k*.14,2,.51,.028)
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
for T in R['towers']:
 num=T['number'];col=coll('MECENATPOLIS_'+num+'_RESIDENTIAL_EDITABLE');body=Mesh(num+'_traced_angular_floorplate');fac=Mesh(num+'_actual_glass_service_stacks');roof=Mesh(num+'_three_oblique_glass_screens_and_hex_roof');base=Mesh(num+'_entry_columns')
 pts=T['profile'];z0=T['bodyBottomM'];z1=T['bodyTopM'];interval=T['floorIntervalM']
 body.prism(pts,z0,z1,0)
 roof.prism(pts,z1+.035,z1+.16,10)
 # Continuous structural core, and the visible raised residential base.
 body.prism([[x*.29,y*.29] for x,y in pts],0,z0,9)
 for k,(a,b) in enumerate(zip(pts,pts[1:]+pts[:1])):
  facade(fac,a,b,z0,z1,interval,k)
  if math.dist(a,b)>8:
   for t in [.18,.80]:
    x,y=lerp(a,b,t);base.box((x*.82,y*.82,z0/2),(1.05,1.05,z0),6)
  strip(roof,a,b,z1-.12,z1+.13,2,.10,.13)
 # The famous crown consists of vertical angled glass screens, not solid
 # pitched roofs. Exact sloping silhouettes are transcribed from elevations.
 for si,S in enumerate(T['screens']):
  a,b=S['a'],S['b'];ha=z1+S['heightAtA'];hb=z1+S['heightAtB'];L=math.dist(a,b)
  roof.face([(*a,z1),(*b,z1),(*b,hb),(*a,ha)],8)
  bar(roof,(*a,ha),(*b,hb),.14,2);bar(roof,(*a,z1),(*b,z1),.17,2)
  for k in range(max(2,round(L/1.55))+1):
   t=k/max(2,round(L/1.55));p=lerp(a,b,t);h=ha+(hb-ha)*t;bar(roof,(*p,z1),(*p,h),.105,2)
  for q in range(1,8):
   z=z1+q*1.55
   if z>=max(ha,hb):continue
   t=(z-ha)/(hb-ha)
   if 0<t<1:
    cross=lerp(a,b,t);high=a if ha>hb else b;bar(roof,(*high,z),(*cross,z),.085,2)
  # Vertical projecting wingblade is attached down the facade edge, matching
  # completedphoto09; only the narrow blade, never an invented solid wall.
  dx,dy=b[0]-a[0],b[1]-a[1];n=(dy/L,-dx/L)
  for p in [a,b]:
   q=[p[0]+n[0]*.52,p[1]+n[1]*.52];bar(fac,(*p,z0),(*p,z1),.16,2)
   fac.face([(*p,z0),(*q,z0),(*q,z1),(*p,z1)],0)
 core=list(reversed(T['roofCore']));center=[sum(v[k] for v in core)/len(core) for k in [0,1]]
 small=[[center[0]+(x-center[0])*.59,center[1]+(y-center[1])*.59] for x,y in core]
 roof.prism(small,z1+.16,z1+7.35,9)
 # Several tall dark plant louvers, not fullheight residentialwindows.
 for a,b in zip(small,small[1:]+small[:1]):
  roof.edge(a,b,z1+.65,z1+7.05,10,.08,.08)
  for k in range(14):roof.edge(a,b,z1+.80+k*.44,z1+.88+k*.44,2,.23,.075)
 # Cantilevered pale hexagonal cap and visible diagonal underbracing.
 roof.prism(core,z1+9.95,z1+10.50,9)
 for a,b in zip(core,core[1:]+core[:1]):
  mid=lerp(a,b,.5);inner=lerp(center,mid,.60);bar(roof,(*inner,z1+7.1),(*a,z1+9.95),.34,10);bar(roof,(*inner,z1+7.1),(*b,z1+9.95),.34,10);bar(roof,(*a,z1+9.80),(*b,z1+9.80),.30,10)
  bar(roof,(*a,z1+10.55),(*b,z1+10.55),.09,2)
 # Simple H marking is authored geometry, no image decal/sourcephoto.
 x,y=center
 roof.box((x-2.2,y,z1+10.525),(.45,5.5,.025),2);roof.box((x+2.2,y,z1+10.525),(.45,5.5,.025),2);roof.box((x,y,z1+10.525),(4.4,.45,.025),2)
 for m in [body,fac,roof,base]:m.obj(col)
 A={'id':T['id'],'nameKo':'메세나폴리스 '+num+'동','file':T['id']+'.glb','blendSource':'mecenatpolis.blend','coordinate':T['anchor'],'category':'apartment','district':'마포구','footprintIds':[T['footprintId']],'supersedes':['apt-a12174601'],'referenceUrl':R['sources'][0]['url'],'components':['individually anchored drawingtraced triangular broken residentialplate','fullheight glazed wing edges','thin pale curtainwall mullions and narrow ventilated opaque vertical stacks','three asymmetrical inclinedtop vertical glass crown screens','smaller raised central core with pale hexagonal helipad overhang','independent groundcore/entry columns'],'uncertainties':R['uncertainties'],'floors':T['floors'],'floorsBasis':'EAWES supplied ANC2012.11 explicitly names101/10239F and10329F','heightBasis':T['heightBasis'],'modelEnvelopeM':T['envelopeM']}
 export(col,A)
# Simplified podium follows actual curving plan, maintaining the open paths and
# residential/office distinction. No office/rawsource ownership is claimed.
P=R['mall'];col=coll('RESIDENTIAL_SIDE_CURVED_MALL_SIMPLIFIED');mall=Mesh('limestone_curves_and_canyon_terraces');gl=Mesh('retail_windows_and_bridges');can=Mesh('central_circular_canopy')
def smooth(points,steps=5):
 out=[];n=len(points)
 for i in range(n):
  a,b,c,d=[points[j%n] for j in [i-1,i,i+1,i+2]]
  for k in range(steps):
   t=k/steps
   out.append([.5*((2*b[j])+(-a[j]+c[j])*t+(2*a[j]-5*b[j]+4*c[j]-d[j])*t*t+(-a[j]+3*b[j]-3*c[j]+d[j])*t*t*t) for j in [0,1]])
 return out
loops=[]
for i,raw in enumerate(P['loops']):
 pts=smooth(raw);loops.append(pts);cen=[sum(v[k] for v in pts)/len(pts) for k in [0,1]]
 for level in range(3):
  z=level*4.2;factor=[.95,1.0,.95][level];q=[[cen[0]+(x-cen[0])*factor,cen[1]+(y-cen[1])*factor] for x,y in pts]
  mall.prism(q,z,z+.65,6)
  inner=[[cen[0]+(x-cen[0])*.96,cen[1]+(y-cen[1])*.96] for x,y in q];gl.prism(inner,z+.65,z+2.6,7);mall.prism(q,z+2.6,z+4.2,6)
  for a,b in zip(q,q[1:]+q[:1]):
   gl.edge(a,b,z+2.55,z+2.65,5,.04,.03)
  # Actual stone panels visibly divide the broad curvingopaque bands.
  for k in range(0,len(q),2):
   a=q[k];b=q[(k+1)%len(q)];mid=lerp(a,b,.5);d=math.dist(a,b)
   if d>.1:gl.edge(lerp(a,b,.49),lerp(a,b,.51),z+2.65,z+4.1,9,.03,.018)
 # Green deck inset, retaining actual organicoutline without genericparkmeshes.
 top=[[cen[0]+(x-cen[0])*.93,cen[1]+(y-cen[1])*.93] for x,y in pts];mall.prism(top,12.6,12.69,11)
# Circular central plaza canopy: open bottom, shallow curvedglass roof and
# exposed curved/radial steel ribs, not a filled giantretailblock.
x,y=P['canopyCenter'];rad=P['canopyRadiusM'];N=64
for j in range(N):
 a=2*math.pi*j/N;b=2*math.pi*(j+1)/N
 pa=(x+rad*math.cos(a),y+rad*math.sin(a),12.9);pb=(x+rad*math.cos(b),y+rad*math.sin(b),12.9)
 can.face([(x,y,15.0),pa,pb],13);bar(can,pa,pb,.25,2)
 if j%8==0:
  bar(can,pa,(x,y,15.0),.18,2)
  bar(can,(pa[0],pa[1],0),pa,.24,10)
# Short glazedwalkway bridges follow gaps between podiumlobes; conservatively
# represented, not extended to excluded office/cultureparcel.
for ia,ib in [(0,1),(0,2),(1,2)]:
 a=min(loops[ia],key=lambda p:min(math.dist(p,q) for q in loops[ib]));b=min(loops[ib],key=lambda q:math.dist(a,q));d=math.dist(a,b)
 if d<2 or d>27:continue
 bar(gl,(*a,8.3),(*b,8.3),2.6,9)
 nx,ny=-(b[1]-a[1])/d,(b[0]-a[0])/d
 for sg in [-1,1]:
  aa=[a[0]+sg*nx*1.2,a[1]+sg*ny*1.2];bb=[b[0]+sg*nx*1.2,b[1]+sg*ny*1.2]
  gl.face([(*aa,8.5),(*bb,8.5),(*bb,9.6),(*aa,9.6)],13);bar(gl,(*aa,9.65),(*bb,9.65),.08,2)
for m in [mall,gl,can]:m.obj(col)
export(col,{'id':P['id'],'nameKo':'메세나폴리스 주거측 곡선상가·중앙캐노피','file':P['id']+'.glb','blendSource':'mecenatpolis.blend','coordinate':P['anchor'],'category':'landmark','district':'마포구','footprintIds':[],'supersedes':['apt-a12174601'],'referenceUrl':R['sources'][0]['url'],'components':['three simplified curved residentialside lowretailvolumes','open canyonwalks and shortglassbridges','circular centralcanopy'],'uncertainties':R['uncertainties']+['Mall commercialgeometry is deliberately simplified; no office,culturehall or neighboringbuilding footprintownership. Tierheights/shops/landscape not surveyed.']})
g=Mesh('review_ground');g.box((0,0,-.4),(380,380,.6),12);g.obj(REVIEW)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1800;scene.render.resolution_y=1500;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX';scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.68,.77,.85,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.8
sun=bpy.data.lights.new('Photo comparison daylight','SUN');ob=bpy.data.objects.new('Photo comparison daylight',sun);REVIEW.objects.link(ob);ob.rotation_euler=(.4,-.5,-.6);sun.energy=2.2;sun.angle=.15
views=[('SE-GS-photo',(240,-290,95),(0,0,65),225),('SW-street',(-270,-210,62),(0,0,65),225),('north-103',(40,290,105),(0,0,65),225),('roof-elevated',(215,-190,270),(0,0,55),225),('101-crown-detail',(130,-120,166),(35,-45,118),82),('roof-plan',(0,0,370),(0,0,0),215)]
for name,loc,target,scale in views:
 cam=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,cam);REVIEW.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=scale
scene.camera=bpy.data.objects['SE-GS-photo']
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'mecenatpolis.blend'))
(OUT/'geometry-check.json').write_text(json.dumps({'assets':checks,'views':[v[0] for v in views],'embeddedImages':0},ensure_ascii=False,indent=2))
bundle={'siteId':'mecenatpolis','sources':R['sources'],'assets':assets,'recipeFiles':['recipe.json','build.py','prepare.py','residential-source-footprints.json','register-rows.json','source-ledger.json','REFERENCE-NOTES.md','validate.py','render-v2.py'],'coverage':R['coverage'],'places':[{'id':'bespoke-mecenatpolis','siteId':'mecenatpolis','name':'메세나폴리스','subtitle':'617세대 · 주거101·102·103동','center':R['siteCenter'],'zoom':17.25,'household_count':617,'source_url':R['sources'][4]['url'],'supersedesPlaceIds':['model:apt-a12174601','seoul-apartment:A12174601']}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n');print(json.dumps(checks))
