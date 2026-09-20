"""Trimage individual source-footprint / completed-photo reconstruction, real Blender MCP.
The recipe owns topology/height/face choices; this file shares only geometric primitives.
"""
import bpy,math,json,bmesh
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/trimage';OUT.mkdir(parents=True,exist_ok=True)
p=OUT/'authored-input.json'
if not p.exists():p=ROOT/'modeling/bespoke/trimage/authored-input.json'
R=json.loads(p.read_text());bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
 if not c.objects and not c.children:bpy.data.collections.remove(c)
def coll(name):
 c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c
REVIEW=coll('REVIEW_ONLY')
def mat(name,color,rough=.6,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;n=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal;return m
M=[mat('Trimage pale grey stone',(.69,.71,.69)),mat('White curved ribbons and frames',(.83,.84,.81)),mat('Deep blue silver low-emissivity glazing',(.07,.17,.235),.23,.45),mat('Slightly paler glass spandrel',(.125,.235,.30),.29,.38),mat('Pale opaque panel mosaic',(.55,.60,.59)),mat('Silver mullions',(.45,.51,.52),.38,.35),mat('Shadow in open mechanical level',(.026,.038,.043)),mat('Roof louver grey',(.27,.31,.32),.50,.28),mat('Lobby charcoal stone',(.12,.14,.14)),mat('Review earth',(.24,.28,.26))]
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
PATTERN=['000100000010','010000100000','000001000100','100000001000','000010000001','001000010000','000000100010','010010000000']
ST=[(0.10,.14),(.56,.60)]
assets=[];checks=[];sitecenter=[127.04491,37.538835]
for T in R['towers']:
 number=T['number'];col=coll(number+'_TRIMAGE_EDITABLE_COMPONENTS');body=Mesh(number+'_stepped_wing_masses');fac=Mesh(number+'_photo_specific_facades');roof=Mesh(number+'_louver_crowns');base=Mesh(number+'_pilotis_and_recessed_lobby');objects=[]
 parts=T['parts'];floor=(T['sourceHeightM']-12)/T['floors'];zbase=T['lobbyHeightM'];refuges=T['refugeZ']
 # Each mass is a separately authored footprint sector and height, including genuinely open belts.
 for pi,P in enumerate(parts):
  pts=P['polygon'];H=P['heightM'];screen=P['screenM'];h=H-screen;style=P['facade'];n=len(pts)
  if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts,pts[1:]+pts[:1]))<0:raise ValueError('Recipe requires CCW rings to preserve named edge mapping')
  bands=[(z,z+2.0) for z in refuges if z+4<h];ranges=[];lo=zbase
  for a,b in bands:ranges.append((lo,a));lo=b
  ranges.append((lo,h))
  for a,b in ranges:body.prism(pts,a,b,2 if style!='stone' else 0)
  # Real openings retain a narrow inset service core; individual piers are widely spaced.
  center=(sum(p[0] for p in pts)/n,sum(p[1] for p in pts)/n)
  for a,b in bands:
   inner=[(center[0]+(q[0]-center[0])*.43,center[1]+(q[1]-center[1])*.43) for q in pts];body.prism(inner,a,b,6)
   for j in range(n-1):
    p,q=pts[j],pts[(j+1)%n];L=math.dist(p,q)
    if L<4:continue
    for k in range(max(1,round(L/3.0))):
     v=lerp(p,q,(k+.5)/max(1,round(L/3.0)));base.box((v[0],v[1],(a+b)/2),(.72,.72,b-a),0)
   body.prism(pts,a-.30,a,1);body.prism(pts,b,b+.28,1)
  # Only the upper exposed segment of a shared internal wall is drawn.
  for ei,(a,b) in enumerate(zip(pts,pts[1:]+pts[:1])):
   L=math.dist(a,b);internal=ei>=n-2;zmin=zbase
   if ei==n-2:zmin=max(zmin,parts[(pi+1)%len(parts)]['heightM'])
   if ei==n-1:zmin=max(zmin,parts[(pi-1)%len(parts)]['heightM'])
   if zmin>=h:continue
   stone=internal or ei in P['stoneEdges'] or style=='stone'
   if internal and pi==0 and ei==n-2:stone=False
   if internal and pi in [1,2] and ei==n-1:stone=False
   # The photographed high stone cores include a glazed broad longitudinal face.
   if style=='stone' and ei in [2,4]:stone=False
   if stone:
    fac.edge(a,b,zmin,h,0,.05,.14)
    if L>4:
     count=max(1,round(L/5.1));width=min(1.05,L/count*.23)
     for lev in range(math.ceil(zmin/floor),int((h-2)/floor)):
      z=lev*floor+.6
      if any(z<b1 and z+1.7>a1 for a1,b1 in bands):continue
      # Paired narrow openings alternate by observed stone-core stack, not random distribution.
      for k in range(count):
       t=(k+.5+(.17 if lev%3==1 else -.08 if lev%3==2 else 0))/count
       aa=lerp(a,b,max(.03,t-width/(2*L)));bb=lerp(a,b,min(.97,t+width/(2*L)));fac.edge(aa,bb,z,z+1.7,6,.205,.015)
     for z in range(int(zmin)+3,int(h),3):fac.edge(a,b,z,z+.035,4,.205,.018)
   else:
    # Photographed broad flat glass differs from ribbons; wide pale edge pier only at long ends.
    if L>7 and style!='ribbon':
     for l,r in [(0,.065),(.93,1)]:fac.edge(lerp(a,b,l),lerp(a,b,r),zmin,h,0,.12,.22)
    cols=max(1,round(L/(1.30 if style=='ribbon' else 1.16)))
    for lev in range(max(1,math.floor(zmin/floor)),math.ceil(h/floor)):
     zl=max(zmin,lev*floor);zt=min(h,(lev+1)*floor)
     if zt<=zl or any(zl<b1 and zt>a1 for a1,b1 in bands):continue
     if style=='ribbon':
      fac.edge(a,b,zl,min(zl+.54,zt),1,.14,.16)
      # Rounded white aperture corners on the two exposed ends of each ribbon wing.
      if ei in [1,n-4] and L>1.2 and zt-zl>1.9:
       end=ei==n-4;r=.68;nx=(b[1]-a[1])/L;ny=-(b[0]-a[0])/L
       for upper in [False,True]:
        zedge=zt if upper else zl+.54;sg=-1 if upper else 1
        coords=[(0,zedge),(r,zedge)]
        coords += [(r-r*math.sin(t*math.pi/2),zedge+sg*(r-r*math.cos(t*math.pi/2))) for t in [1,.875,.75,.625,.5,.375,.25,.125,0]]
        pp=[]
        for u,z in coords:
         v=lerp(a,b,1-u/L if end else u/L);pp.append((v[0]+nx*.335,v[1]+ny*.335,z))
        fac.face(pp,1)
      fac.edge(a,b,zl+.58,min(zl+.64,zt),5,.15,.045)
     else:
      fac.edge(a,b,zl,min(zl+.105,zt),5,.13,.06)
      fac.edge(a,b,zl+.34,min(zl+.65,zt),3,.09,.035)
     for k in range(cols):
      aa=lerp(a,b,(k+.035)/cols);bb=lerp(a,b,(k+.965)/cols)
      # Ordered sparse opaque panels from the actual completed flat-facade mosaic.
      if style!='ribbon' and PATTERN[lev%len(PATTERN)][(k+ei*2)%12]=='1':fac.edge(aa,bb,zl+.72,zt-.12,4,.15,.035)
      x=lerp(a,b,(k+.5)/cols);d=.045/L;fac.edge(lerp(a,b,max(0,(k+.5)/cols-d)),lerp(a,b,min(1,(k+.5)/cols+d)),zl+.12,zt,5,.15,.025)
   # Ground glass entry recessed from footprint; lower columns follow each wing rather than a solid box.
   if not internal and L>5:
    for t in [.14,.85]:
     v=lerp(a,b,t);base.box((v[0],v[1],zbase/2),(.62,.62,zbase),0)
  # Roof edge remains narrow; actual high screen is a framed louver volume, not a solid extra floor.
  body.prism(pts,h,h+.25,1)
  if screen:
   center=(sum(q[0] for q in pts)/n,sum(q[1] for q in pts)/n);inset=[(center[0]+(q[0]-center[0])*.91,center[1]+(q[1]-center[1])*.91) for q in pts]
   roof.prism(inset,h+.25,H-.40,6)
   for a,b in zip(pts,pts[1:]+pts[:1]):
    L=math.dist(a,b)
    for j in range(max(2,round(screen/.48))):roof.edge(a,b,h+.38+j*.48,min(H-.3,h+.58+j*.48),7,.06,.24)
    for k in range(max(2,round(L/2.6))+1):
     t=k/max(2,round(L/2.6));aa=lerp(a,b,max(0,t-.10/L));bb=lerp(a,b,min(1,t+.10/L));roof.edge(aa,bb,h,H,1,.28,.12)
    roof.edge(a,b,H-.22,H,1,.20,.30)
   # Small roof service box sits behind the visible screen, with no unsupported mast silhouette.
  else:
   for a,b in zip(pts,pts[1:]+pts[:1]):roof.edge(a,b,h,h+.70,0,.03,.18)
 # Recessed central entrance lobby and canopy subordinate to the towers.
 ring=T['ring'];cx=sum(x for x,y in ring)/len(ring);cy=sum(y for x,y in ring)/len(ring)
 base.box((cx,cy,zbase/2),(8.5,7.5,zbase),8);base.box((cx,cy-3.85,zbase/2),(7.0,.07,3.6),2)
 for x in [cx-3.3,cx,cx+3.3]:base.box((x,cy-3.95,zbase/2),(.12,.18,3.8),5)
 base.box((cx,cy-4.4,zbase-.1),(10,3.8,.32),0)
 for mesh in [body,fac,roof,base]:objects.append(mesh.obj(col))
 for ob in objects:ob['sourceFootprintId']=T['footprintId'];ob['evidence']='authored-input.json: NOW completed view + firsthand completed photos; nonmeasured detail explicitly qualified'
 bpy.ops.object.select_all(action='DESELECT')
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
 bpy.ops.export_scene.gltf(filepath=str(OUT/(T['assetId']+'.glb')),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_texcoords=False,export_cameras=False,export_lights=False)
 lo=[min(v.co[k] for ob in objects for v in ob.data.vertices) for k in range(3)];hi=[max(v.co[k] for ob in objects for v in ob.data.vertices) for k in range(3)];tri=0
 for ob in objects:ob.data.calc_loop_triangles();tri+=len(ob.data.loop_triangles)
 checks.append({'id':T['assetId'],'triangles':tri,'blenderBounds':[lo,hi],'minHeight':lo[2],'footprintIds':[T['footprintId']],'parts':[p['name'] for p in parts]})
 # Translate only after the individual-origin export, keeping complete editable scene geographically coherent.
 dx=(T['anchor']['lon']-sitecenter[0])*111320*math.cos(math.radians(sitecenter[1]));dy=(T['anchor']['lat']-sitecenter[1])*111320
 for ob in objects:ob.location=(dx,dy,0)
 assets.append({'id':T['assetId'],'nameKo':T['nameKo'],'file':T['assetId']+'.glb','blendSource':'trimage.blend','coordinate':T['anchor'],'category':'apartment','district':'성동구','footprintIds':[T['footprintId']],'supersedes':['apt-a10026988'],'referenceUrl':R['sources'][0]['url'],'components':[p['name'] for p in parts]+['recessed ground lobby and pilotis','open mechanical/refuge bands','framed louver crown'],'uncertainties':R['uncertainties'],'floors':T['floors'],'heightBasis':R['heightBasis'],'floorsBasis':'Official Seoul OA-22424 matched individual building register '+T['registerId'],'registerId':T['registerId'],'householdCount':T['households']})
g=Mesh('Review_ground');g.box((0,0,-.3),(280,280,.5),9);g.obj(REVIEW)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1800;scene.render.resolution_y=1400;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX';scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.63,.72,.84,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.65
sun=bpy.data.lights.new('Broad sun','SUN');ob=bpy.data.objects.new('Broad sun',sun);REVIEW.objects.link(ob);ob.rotation_euler=(.4,-.35,-.5);sun.energy=2.0;sun.angle=.14
views=[('river-source-match',(-480,-540,100),(0,0,77),250),('courtyard-opposite',(100,270,90),(0,0,78),245),('east-oblique',(240,-180,150),(0,0,75),280),('roof-plan',(0,0,380),(0,0,0),225),('101-ribbons',(65,-185,112),(-35,-25,80),230),('103-stone-crown',(-175,160,140),(-29,49,83),230)]
for name,loc,target,scale in views:
 cam=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,cam);REVIEW.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=scale
scene.camera=bpy.data.objects['river-source-match'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'trimage.blend'))
(OUT/'geometry-check.json').write_text(json.dumps({'assets':checks,'embeddedImages':len([im for im in bpy.data.images if im.packed_file]),'views':[v[0] for v in views]},indent=2)+'\n')
bundle={'siteId':'trimage','sources':R['sources'],'recipeFiles':['authored-input.json','source-footprints.json','official-register-source.json'],'assets':assets,'coverage':R['coverage'],'places':[{'id':'bespoke-trimage','siteId':'trimage','name':'서울숲 트리마제','subtitle':'성수동 · 688세대 · 101–104동 개별 외관','center':sitecenter,'zoom':17.2,'household_count':688,'source_url':'https://pluspp.co.kr/result/result_highend.asp','supersedesPlaceIds':['model:apt-a10026988','seoul-apartment:A10026988']}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n');print(json.dumps(checks))
