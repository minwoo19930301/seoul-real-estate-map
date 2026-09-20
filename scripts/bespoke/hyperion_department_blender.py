"""Append only the photograph-authored department store to frozen Hyperion scene.
Rebuild after hyperion_blender.py. Uses department-recipe.json trace, no photo textures.
"""
import bpy,ast,json,math,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/hyperion'
rp=OUT/'department-recipe.json'
if not rp.exists():rp=ROOT/'modeling/bespoke/hyperion/department-recipe.json'
b=json.loads(rp.read_text());bundle=json.loads((OUT/'bundle.json').read_text())
if Path(bpy.data.filepath).resolve()!= (OUT/'hyperion-authored.blend').resolve():
 raise RuntimeError('Open hyperion-authored.blend in a preceding MCP call, then execute this append-only builder.')
# Reuse neutral mesh primitives only; no Hyperion residential facade generator.
tree=ast.parse((ROOT/'scripts/bespoke/hyperion_blender.py').read_text());subset=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ['mat','Mesh','ccw','edge','collect']]
exec(compile(ast.Module(body=subset,type_ignores=[]),'<shared mesh primitives>','exec'))
MAT=[mat('Department pale limestone',(.72,.70,.67),.02,.74),mat('Department recessed blue glazing',(.09,.28,.33),.32,.25),mat('Department projecting ivory mouldings',(.85,.82,.76),.05,.54),mat('Department stone joint shadow',(.40,.40,.38),0,.75),mat('Department bronze metal',(.18,.18,.14),.45,.38),mat('Department poster unprinted golden panel',(.70,.51,.09),0,.65),mat('Department roof slab',(.45,.46,.43),0,.82)]
for obj in list(bpy.data.objects):
 if obj.name.startswith('D_'):bpy.data.objects.remove(obj,do_unlink=True)
col=collect('DEPARTMENT_STORE_OFFICIAL_PHOTO');mass=Mesh('D_01_UPIS_traced_chamfered_stone_mass');mould=Mesh('D_02_arch_bays_and_classical_cornices');glass=Mesh('D_03_round_windows_upper_ribbon_entrance');corner=Mesh('D_04_raised_corner_clock_pediment');roof=Mesh('D_05_recessed_roof_and_service_faces')
p=ccw(b['localTrace']['coordinates'][0]);mass.prism(p,0,32.8,0)
# A coordinate frame along each wall places every feature on its own frontage.
def wall(a,bb):
 L=math.dist(a,bb);u=((bb[0]-a[0])/L,(bb[1]-a[1])/L);n=(u[1],-u[0]);return L,u,n

def q(a,u,n,s,z,off=0):return(a[0]+u[0]*s+n[0]*off,a[1]+u[1]*s+n[1]*off,z)
def strip(mesh,a,u,n,s0,s1,z0,z1,off,mi):
 aa=(a[0]+u[0]*s0,a[1]+u[1]*s0);bb=(a[0]+u[0]*s1,a[1]+u[1]*s1);mesh.panel(aa,bb,z0,z1,n,off,mi)
def ring(mesh,a,u,n,s,z,r,thick,off,mi,semi=False):
 num=20 if semi else 32;angle=math.pi if semi else math.tau
 for j in range(num):
  t0=angle*j/num;t1=angle*(j+1)/num
  v=[q(a,u,n,s+(r+d)*math.cos(t),z+(r+d)*math.sin(t),off) for d,t in [(0,t0),(0,t1),(thick,t1),(thick,t0)]];mesh.face(v,mi)
def disc(mesh,a,u,n,s,z,r,off,mi):
 mesh.face([q(a,u,n,s+r*math.cos(math.tau*k/40),z+r*math.sin(math.tau*k/40),off) for k in range(40)],mi)
# Frontages are recognized geometrically from the traced outline: south, east,
# diagonal southeast entrance. The unseen northern/western service sides differ.
for a,bb in zip(p,p[1:]+p[:1]):
 L,u,n=wall(a,bb);south=n[1]<-.85;east=n[0]>.85;chamfer=n[0]>.4 and n[1]<-.4
 H=38.5 if chamfer else 34.5
 if chamfer:
  # Raised corner facade and roof, confined to a shallow inward wedge.
  inn=10.;poly=[a,bb,(bb[0]-n[0]*inn,bb[1]-n[1]*inn),(a[0]-n[0]*inn,a[1]-n[1]*inn)];mass.prism(poly,32.8,37.7,0)
 else:strip(mass,a,u,n,0,L,32.8,33.9,.03,0)
 for z,thick,off in [(H-1.15,.28,.36),(H-.70,.32,.62),(H-.26,.26,.85)]:
  mould.beam(q(a,u,n,0,z+thick/2,off),q(a,u,n,L,z+thick/2,off),thick,.65,2)
 # Fine limestone joints do not create apartment-storey window grids.
 for z in [1.0+i*.9 for i in range(int((H-2)/.9))]:strip(mass,a,u,n,0,L,z,z+.023,.045,3)
 for j in range(1,max(2,int(L/2.2))):
  s=L*j/max(2,int(L/2.2));mould.beam(q(a,u,n,s,.5,.055),q(a,u,n,s,H-1.3,.055),.023,.018,3)
 if south or east:
  bays=5 if south else 3;left=7.5 if south else 5.2;right=L-7.5 if south else L-5.2
  # Broad clear upper ribbon below a multi-layer projecting belt.
  strip(glass,a,u,n,left,right,26.5,28.6,.15,1)
  for s in [left+(right-left)*i/(bays*3) for i in range(bays*3+1)]:mould.beam(q(a,u,n,s,26.5,.24),q(a,u,n,s,28.6,.24),.10,.14,4)
  for z,width in [(26.15,.4),(29.0,.40),(30.0,.75)]:mould.beam(q(a,u,n,0,z,.46),q(a,u,n,L,z,.46),width,.65,2)
  # Tall stone recessed panels capped by distinct arches and oculus windows.
  for k in range(bays):
   s=left+(right-left)*(k+.5)/bays;half=(right-left)/bays*.42
   strip(mass,a,u,n,s-half+.25,s+half-.25,5.0,21.8,.10,0)
   for side in [-1,1]:
    ss=s+side*half;mould.beam(q(a,u,n,ss,4.8,.25),q(a,u,n,ss,21.4,.25),.33,.50,2)
    mould.beam(q(a,u,n,ss,20.8,.45),q(a,u,n,ss,21.35,.45),.72,.55,2)
   mould.beam(q(a,u,n,s-half,5.0,.35),q(a,u,n,s+half,5.0,.35),.20,.38,2)
   ring(mould,a,u,n,s,21.25,half-.12,.30,.28,2,True)
   ring(mould,a,u,n,s,21.25,half+.32,.16,.42,2,True)
   disc(glass,a,u,n,s,21.25,1.07,.22,1);ring(mould,a,u,n,s,21.25,1.07,.18,.30,2)
   mould.beam(q(a,u,n,s-1.04,21.25,.34),q(a,u,n,s+1.04,21.25,.34),.08,.10,4);mould.beam(q(a,u,n,s,20.2,.34),q(a,u,n,s,22.3,.34),.08,.10,4)
   mould.beam(q(a,u,n,s,half+21.25,.42),q(a,u,n,s,half+21.95,.42),.60,.45,2)
  for s in [2.3,L-2.3]:
   for x in [s-.7,s+.7]:mould.beam(q(a,u,n,x,6,.19),q(a,u,n,x,23.9,.19),.14,.23,2)
   for z in [6,23.9]:mould.beam(q(a,u,n,s-.7,z,.19),q(a,u,n,s+.7,z,.19),.14,.23,2)
 elif chamfer:
  mid=L/2;half=L*.34
  # A neutral unprinted panel preserves frame geometry without copying artwork.
  strip(corner,a,u,n,mid-4.3,mid+4.3,19.5,29.6,.25,5)
  for s in [mid-4.7,mid+4.7]:corner.beam(q(a,u,n,s,19.1,.45),q(a,u,n,s,30.0,.45),.36,.48,2)
  for z in [19.1,30.0]:corner.beam(q(a,u,n,mid-4.7,z,.45),q(a,u,n,mid+4.7,z,.45),.36,.48,2)
  strip(glass,a,u,n,mid-half,mid+half,.2,9.2,.36,1)
  for j in range(9):
   ss=mid-half+2*half*j/8;corner.beam(q(a,u,n,ss,.2,.49),q(a,u,n,ss,8.8,.49),.14,.20,4)
  # Columned entry and actual triangular clock pediment silhouette.
  for ss in [mid-half-.4,mid+half+.4]:
   corner.beam(q(a,u,n,ss,.2,1.25),q(a,u,n,ss,9.7,1.25),.85,.85,2)
   for z in [.7,9.45]:corner.beam(q(a,u,n,ss-.60,z,1.25),q(a,u,n,ss+.60,z,1.25),.35,1.3,2)
  corner.face([q(a,u,n,mid-half-1,10.1,1.25),q(a,u,n,mid+half+1,10.1,1.25),q(a,u,n,mid,15.0,1.25)],2)
  for ss0,z0,ss1,z1 in [(mid-half-1,10.1,mid,15.0),(mid,15,mid+half+1,10.1),(mid-half-1,10.1,mid+half+1,10.1)]:corner.beam(q(a,u,n,ss0,z0,1.43),q(a,u,n,ss1,z1,1.43),.38,.50,3)
  disc(corner,a,u,n,mid,12.1,1.0,1.51,4);ring(corner,a,u,n,mid,12.1,1,.10,1.55,5)
  for ss,zz in [(mid,12.9),(mid+.58,12.1)]:corner.beam(q(a,u,n,mid,12.1,1.57),q(a,u,n,ss,zz,1.57),.09,.08,5)
  # Shallow sloped entrance canopy below the pediment.
  corner.face([q(a,u,n,mid-half,4.1,.6),q(a,u,n,mid+half,4.1,.6),q(a,u,n,mid+half,3.7,2.6),q(a,u,n,mid-half,3.7,2.6)],4)
 else:
  for z in [6,15,24]:
   for k in range(max(1,int(L/10))):
    ss=4+k*10;strip(glass,a,u,n,ss,min(ss+3,L-.5),z,z+1.4,.09,1)
roof.prism([(x*.94,y*.94) for x,y in p],32.8,33.0,6)
objects=[m.obj(col) for m in [mass,mould,glass,corner,roof]]
for ob in objects:ob.rotation_euler.z=math.radians(b['yawDegFromEast']);ob['basis']='Hyundai department store official exterior photo and UPIS ground trace; heights manually estimated'
bpy.ops.object.select_all(action='DESELECT')
for ob in objects:ob.select_set(True)
bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
f=OUT/(b['id']+'.glb');bpy.ops.export_scene.gltf(filepath=str(f),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_extras=True)
lo=[min(v.co[i] for ob in objects for v in ob.data.vertices) for i in range(3)];hi=[max(v.co[i] for ob in objects for v in ob.data.vertices) for i in range(3)]
asset={**{k:b[k] for k in ['id','nameKo','coordinate','footprintIds','referenceUrl','heightM','heightBasis','floors','floorsBasis','uncertainties']},'category':'commercial','file':str(f),'blendSource':str(OUT/'hyperion-authored.blend'),'supersedes':['reference-flight-hyperion','survey-upis-32702773'],'components':[ob.name for ob in objects],'triangles':sum(len(p.vertices)-2 for ob in objects for p in ob.data.polygons),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size,'boundsBlenderXYZ':[lo,hi],'dimensionsGlbXYZ':[hi[0]-lo[0],hi[2]-lo[2],hi[1]-lo[1]],'minGlbY':lo[2]};asset['heightM']=hi[2]-lo[2]
for ob in objects:ob.location.x+=b['siteEN'][0];ob.location.y+=b['siteEN'][1]
bundle['assets']=[a for a in bundle['assets'] if a['id']!=b['id']]+[asset];bundle['retainedUntouchedSourceFootprintIds']=[]
review=b['invalidGenericModelReview'];bundle['invalidGenericModelReviews']=[review]
podium=next(a for a in bundle['assets'] if a['id']=='bespoke-hyperion-parking-podium');podium['supersedes']=list(dict.fromkeys(podium['supersedes']+['survey-upis-32702773']));podium['supersessionReviews']=[review]
bundle['recipeFiles']=list(dict.fromkeys(bundle['recipeFiles']+['department-recipe.json']))
for url,obs in [(b['floorsReferenceUrl'],'Official floor guide1F through7F; no measured height.'),(b['referenceUrl'],'Official branch homepage exterior photo: classical stone facades and southeast clock-pediment entrance; capture date unspecified.'),(b['imageUrl'],'Direct official exterior photo visually reviewed; used only as reference, never embedded.')]:
 if not any(s['url']==url for s in bundle['sources']):bundle['sources'].append({'url':url,'observations':obs})
scene=bpy.context.scene;cam=scene.camera;cam.data.type='ORTHO';scene.render.resolution_x=1600;scene.render.resolution_y=1200
for name,eye,target,scale in [('review-department-front',(160,-195,92),(15,-48,19),133),('review-department-source-view',(160,-230,44),(15,-48,19),139),('review-with-department',(365,-410,278),(-6,-10,117),405)]:
 cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
 if name+'.png' not in bundle['renders']:bundle['renders'].append(name+'.png')
bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'hyperion-authored.blend'));bundle['blendSourceSha256']=hashlib.sha256((OUT/'hyperion-authored.blend').read_bytes()).hexdigest()
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n');print(json.dumps(asset,ensure_ascii=False))
