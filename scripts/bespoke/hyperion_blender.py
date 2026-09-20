"""Photo-authored Mokdong Hyperion, executed in the dedicated Blender MCP scene.

This is the ivory framed, braced, flared-crown 2003 complex, not the green
six-wing SKY design. A/B/C have independent named-source anchors and recipes.
"""
import bpy,math,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/hyperion';OUT.mkdir(parents=True,exist_ok=True)
rp=OUT/'recipe-input.json'
if not rp.exists():rp=ROOT/'modeling/bespoke/hyperion/recipe-input.json'
recipe=json.loads(rp.read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)

def mat(name,color,metal=0,rough=.5):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
 return m
MAT=[mat('Hyperion ivory aluminium structural frame',(.78,.76,.68),.1,.57),
 mat('Hyperion daylight blue grey glazing',(.20,.35,.37),.38,.24),
 mat('Hyperion warm central limestone',(.50,.45,.34),.02,.69),
 mat('Hyperion slender bronze mullion',(.33,.31,.25),.5,.36),
 mat('Hyperion open parking shadow',(.035,.042,.041),0,.86),
 mat('Hyperion white crown cornice',(.87,.86,.79),.18,.38),
 mat('Hyperion roof sage mechanical glazing',(.24,.33,.29),.28,.43),
 mat('Hyperion podium light stone',(.65,.64,.58),.03,.72),
 mat('Hyperion roof planting',(.15,.23,.10),0,.9),
 mat('Hyperion spandrel neutral grey',(.37,.43,.42),.15,.62)]
class Mesh:
 def __init__(self,name):self.name=name;self.v=[];self.f=[];self.m=[]
 def face(self,p,mi):
  i=len(self.v);self.v.extend(p);self.f.append(tuple(range(i,i+len(p))));self.m.append(mi)
 def prism(self,p,z0,z1,mi):
  p=ccw(p)
  for a,b in zip(p,p[1:]+p[:1]):self.face([(a[0],a[1],z0),(b[0],b[1],z0),(b[0],b[1],z1),(a[0],a[1],z1)],mi)
  vs=[Vector((x,y,0)) for x,y in p]
  for tri in tessellate_polygon([vs]):
   t=[vs[v] if isinstance(v,int) else v for v in tri];self.face([(v.x,v.y,z1) for v in t],mi);self.face([(v.x,v.y,z0) for v in reversed(t)],mi)
 def box(self,c,s,mi):
  x,y,z=c;w,d,h=s;self.prism([(x-w/2,y-d/2),(x+w/2,y-d/2),(x+w/2,y+d/2),(x-w/2,y+d/2)],z-h/2,z+h/2,mi)
 def beam(self,a,b,w,d,mi):
  a,b=Vector(a),Vector(b);v=(b-a).normalized();s=v.cross(Vector((0,0,1)))
  if s.length<.01:s=Vector((1,0,0))
  s.normalize();t=v.cross(s).normalized();p=[a+s*w*i+t*d*j for i,j in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]]+[b+s*w*i+t*d*j for i,j in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]]
  for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([p[i] for i in f],mi)
 def panel(self,a,b,z0,z1,n,depth,mi):
  self.face([(a[0]+n[0]*depth,a[1]+n[1]*depth,z0),(b[0]+n[0]*depth,b[1]+n[1]*depth,z0),(b[0]+n[0]*depth,b[1]+n[1]*depth,z1),(a[0]+n[0]*depth,a[1]+n[1]*depth,z1)],mi)
 def obj(self,col):
  mesh=bpy.data.meshes.new(self.name);mesh.from_pydata(self.v,[],self.f);mesh.update()
  for m in MAT:mesh.materials.append(m)
  for p,mi in zip(mesh.polygons,self.m):p.material_index=mi
  ob=bpy.data.objects.new(self.name,mesh);col.objects.link(ob);return ob
def ccw(p):
 p=[tuple(v[:2]) for v in p]
 if p[0]==p[-1]:p=p[:-1]
 if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))<0:p.reverse()
 return p
def chamfer(w,d,c):return [(-w/2+c,-d/2),(w/2-c,-d/2),(w/2,-d/2+c),(w/2,d/2-c),(w/2-c,d/2),(-w/2+c,d/2),(-w/2,d/2-c),(-w/2,-d/2+c)]
def edge(a,b,t):return [a[k]+(b[k]-a[k])*t for k in [0,1]]
def collect(name):
 c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c
def export_asset(info,objects,col):
 bpy.ops.object.select_all(action='DESELECT')
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
 bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
 f=OUT/(info['id']+'.glb');bpy.ops.export_scene.gltf(filepath=str(f),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_extras=True)
 lo=[min(v.co[i] for ob in objects for v in ob.data.vertices) for i in range(3)];hi=[max(v.co[i] for ob in objects for v in ob.data.vertices) for i in range(3)]
 out={'id':info['id'],'nameKo':info['nameKo'],'file':str(f),'blendSource':str(OUT/'hyperion-authored.blend'),'coordinate':info['coordinate'],'category':'apartment','footprintIds':info['footprintIds'],
 'supersedes':['reference-flight-hyperion','apt-a15805114'],'referenceUrl':'https://www.sfacade.net/dongtan-hyperion','components':[ob.name for ob in objects],
 'heightM':info['heightM'],'heightBasis':info.get('heightBasis',info.get('estimate')),'floors':info.get('floors'),'floorsBasis':info.get('floorsBasis'),
 'uncertainties':info.get('uncertainties',[info.get('estimate')]),'triangles':sum(len(p.vertices)-2 for ob in objects for p in ob.data.polygons),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size,
 'boundsBlenderXYZ':[lo,hi],'dimensionsGlbXYZ':[hi[0]-lo[0],hi[2]-lo[2],hi[1]-lo[1]],'minGlbY':lo[2]}
 for ob in objects:ob.location.x+=info['siteEN'][0];ob.location.y+=info['siteEN'][1]
 return out

assets=[]
for b in recipe['buildings']:
 n=b['tower'];col=collect('HYPERION_'+n+'_photo-authored');w,d=b['widthM'],b['depthM'];H=b['heightM'];body=H-b['crownHeightM'];pod=b['podiumHeightM'];fh=(body-pod)/(b['floors']-8)
 # Explicit three-part silhouette: chamfered corner wings, central stone axis,
 # stepped penthouse and an open, outward-flaring crown.
 footprint=ccw(chamfer(w,d,b['cornerCutM']))
 mass=Mesh(n+'_01_chamfered_corner_wings');frame=Mesh(n+'_02_ivory_floor_and_column_frames');glazing=Mesh(n+'_03_blue_grey_window_divisions');spine=Mesh(n+'_04_warm_stone_central_axis');braces=Mesh(n+'_05_engineer_documented_white_diagonal_belts');crown=Mesh(n+'_06_flared_colonnade_and_stepped_penthouse')
 mass.prism(chamfer(w*.94,d*.94,2.5),0,pod,4)
 mass.prism(footprint,pod,body-4.8,1)
 # Two tall stone spines reach the crown; crosswise shoulders step down.
 sw=b['spineWidthM']
 for sign in [-1,1]:
  spine.box((0,sign*(d/2+.45),(pod+body)/2),(sw,1.25,body-pod),2)
  for z in [pod+fh*(i+.40) for i in range(b['floors']-8)]:
   for x in [-sw*.27,sw*.27]:spine.box((x,sign*(d/2+1.13),z+.70),(.53,.14,1.4),1)
 for sign in [-1,1]:
  spine.box((sign*(w/2+.40),0,(pod+body-3)/2),(1.10,sw*.82,body-3-pod),2)
 # Project participant Table7 supplies the belt-storey numbers. Exact datum
 # interpolation and exposed member widths are photographic approximations.
 belt_z=[pod+(floor-9)*fh for floor in b['beltFloors']]
 for ei,(a,bb) in enumerate(zip(footprint,footprint[1:]+footprint[:1])):
  L=math.dist(a,bb);normal=((bb[1]-a[1])/L,-(bb[0]-a[0])/L)
  diagonal=abs(a[0]-bb[0])>.1 and abs(a[1]-bb[1])>.1
  top=body-4.8
  count=max(2,round(L/(2.6 if n=='B' else 3.1)))
  pitch=L/count
  # Major ivory frame subdivides whole apartment bays. Each bay has slender
  # bronze window divisions, not a continuous green ribbon around the tower.
  for f in range(b['floors']-8):
   z=pod+f*fh
   if z+fh>top:continue
   inbelt=any(abs(z-bz)<fh*.65 for bz in belt_z)
   frame.panel(a,bb,z,z+.43,normal,.27,0)
   if inbelt:continue
   glazing.panel(a,bb,z+.44,z+fh-.12,normal,.12,1)
   glazing.panel(a,bb,z+fh-.47,z+fh-.12,normal,.15,9)
   for j in range(count):
    left,right=edge(a,bb,(j+.09)/count),edge(a,bb,(j+.91)/count)
    mid=edge(a,bb,(j+.50)/count)
    glazing.beam((mid[0]+normal[0]*.30,mid[1]+normal[1]*.30,z+.43),(mid[0]+normal[0]*.30,mid[1]+normal[1]*.30,z+fh-.12),.075,.12,3)
    glazing.panel(left,right,z+fh*.53,z+fh*.53+.075,normal,.3,3)
  for j in range(count+1):
   pt=edge(a,bb,j/count);frame.beam((pt[0]+normal[0]*.29,pt[1]+normal[1]*.29,pod),(pt[0]+normal[0]*.29,pt[1]+normal[1]*.29,top),.39 if diagonal else .55,.33,0)
  for z in belt_z:
   if z>=top:continue
   low=z+.5;high=min(z+fh*1.20,top)
   braces.panel(a,bb,low,high,normal,.37,9)
   # Two broad wing triangles, separated by the wider stone axis. The
   # photograph shows structural-bay braces, not a fine window-bay zigzag.
   if diagonal:segments=[(0.,1.)]
   else:
    centre_width=sw if abs(bb[0]-a[0])>abs(bb[1]-a[1]) else sw*.82
    gap=centre_width/L
    segments=[(0.,.5-gap/2),(.5+gap/2,1.)]
   for t0,t1 in segments:
    spans=max(1,round(L*(t1-t0)/13.5))
    for j in range(spans):
     x=edge(a,bb,t0+(t1-t0)*j/spans);y=edge(a,bb,t0+(t1-t0)*(j+.5)/spans);zz=edge(a,bb,t0+(t1-t0)*(j+1)/spans)
     def pt(q,zv):return (q[0]+normal[0]*.82,q[1]+normal[1]*.82,zv)
     braces.beam(pt(x,low),pt(y,high),.82,.46,0);braces.beam(pt(y,high),pt(zz,low),.82,.46,0)
    aa,bbb=edge(a,bb,t0),edge(a,bb,t1)
    for zc in [low,high]:braces.beam((aa[0]+normal[0]*.80,aa[1]+normal[1]*.80,zc),(bbb[0]+normal[0]*.80,bbb[1]+normal[1]*.80,zc),.5,.4,0)
 # Distinct step heights/widths in A/B/C are specified separately, not a scaled
 # copy of the entire taller tower and not the old round-corner game extrusion.
 pent_w={'A':w*.69,'B':w*.63,'C':w*.64}[n];pent_d={'A':d*.66,'B':d*.64,'C':d*.58}[n]
 crown.prism(chamfer(pent_w,pent_d,1.8),body-4.8,body+1.3,1)
 for x in [-pent_w/2,pent_w/2]:
  for zz in [body-4.4,body-.9,body+1.0]:crown.box((x,0,zz),(.5,pent_d,.55),0)
  for y in [-pent_d/2,-pent_d*.25,0,pent_d*.25,pent_d/2]:crown.box((x,y,body-1.5),(.5,.6,6),0)
 for y in [-pent_d/2,pent_d/2]:
  for zz in [body-4.4,body-.9,body+1.0]:crown.box((0,y,zz),(pent_w,.5,.55),0)
  for x in [-pent_w/2,-pent_w*.25,0,pent_w*.25,pent_w/2]:crown.box((x,y,body-1.5),(.6,.5,6),0)
 # Actual crown reads as a classical open colonnade flaring outwards beneath
 # two shallow cream cornices, with a recessed green mechanical enclosure.
 cw=b['crownWidthM'];cd=cw*{'A':.89,'B':.85,'C':.88}[n];crown_bottom=body+1.5;crown_top=H-1.4
 crown.prism(chamfer(cw*.79,cd*.79,1.1),crown_bottom,crown_top-.45,6)
 for orient in [0,1]:
  for sign in [-1,1]:
   span=cw*.80 if orient==0 else cd*.80
   for k in range(6 if n=='A' else 5):
    nk=6 if n=='A' else 5;tang=-span/2+span*k/(nk-1)
    last=None
    for j in range(9):
     t=j/8;outward=(cd*.40 if orient==0 else cw*.40)+1.2*t*t
     q=(tang,sign*outward,crown_bottom+t*(crown_top-crown_bottom)) if orient==0 else (sign*outward,tang,crown_bottom+t*(crown_top-crown_bottom))
     if last:crown.beam(last,q,.63,.60,5)
     last=q
 crown.prism(chamfer(cw,cd,1.5),H-1.4,H-.65,5)
 crown.prism(chamfer(cw+1.0,cd+1.0,1.8),H-.65,H-.13,5)
 crown.prism(chamfer(cw-.5,cd-.5,1.3),H-.13,H,2)
 # Air-handling heads sit below the crown top on the real upper terraces.
 for side in [-1,1]:
  crown.box((side*w*.34,0,body-3.9),(3.4,7.0,1.8),9)
  for i in range(6):crown.box((side*w*.34,-3+i*1.15,body-2.96),(3.0,.12,.12),3)
 objects=[builder.obj(col) for builder in [mass,frame,glazing,spine,braces,crown]]
 for ob in objects:ob.rotation_euler.z=math.radians(b['yawDegFromEast']);ob['tower']=n;ob['basis']='Primary contractor photographs and source named footprint; manual estimated perimeter detail'
 asset=export_asset(b,objects,col);asset['beltFloors']=b['beltFloors'];asset['sourceYawDegFromEast']=b['yawDegFromEast'];assets.append(asset)

# Connecting parking podium is explicitly described in the project paper and
# directly visible in the facade consultant photograph. The separate Hyundai
# department store polygon was subtracted during preparation and is not claimed.
pb=recipe['podium'];col=collect('HYPERION_L_PARKING_PODIUM');p=ccw(pb['footprint']['coordinates'][0]);slabs=Mesh('P_01_light_stone_slabs_and_piers');slots=Mesh('P_02_recessed_open_parking_slots');garden=Mesh('P_03_rooftop_planters');breaks=Mesh('P_04_solid_end_recess_and_vertical_stair_glazing')
slabs.prism(p,0,4.8,7);slabs.prism(p,29.0,30.0,7)
roles=pb['facadeInterpretation']
for ei,(a,bb) in enumerate(zip(p,p[1:]+p[:1])):
 L=math.dist(a,bb)
 if L<.5:continue
 normal=((bb[1]-a[1])/L,-(bb[0]-a[0])/L)
 # Each observed break is assigned to a single site-facing facade, not
 # repeated around the whole podium. The unseen faces remain approximate.
 stone=[];glass=[]
 if ei==roles['solidEndEdge']:stone=[(0.,1.)]
 elif ei==roles['stoneEndReturnEdge']:stone=[roles['stoneEndReturnInterval']]
 elif ei==roles['stairGlassEdge']:glass=[roles['stairGlassInterval']]
 cuts=sorted(set([0.,1.]+[v for ab in stone+glass for v in ab]));open_segments=[(lo,hi) for lo,hi in zip(cuts,cuts[1:]) if not any(x<=((lo+hi)/2)<=y for x,y in stone+glass)]
 for t0,t1 in open_segments:
  aa,bbb=edge(a,bb,t0),edge(a,bb,t1);run=L*(t1-t0)
  for z in [5,8.4,11.8,15.2,18.6,22]:
   slots.panel(aa,bbb,z+1.7,z+2.65,normal,-.80,4)
   slabs.panel(aa,bbb,z,z+1.70,normal,.16,7)
   slabs.panel(aa,bbb,z+1.70,z+1.78,normal,.19,2)
  count=max(1,round(run/12.))
  for k in range(count+1):
   pt=edge(aa,bbb,k/count);slabs.beam((pt[0],pt[1],4.8),(pt[0],pt[1],25.4),.85,.65,7)
  # Upper ribbon is a separate glazed level, with solid header and sill.
  slabs.panel(aa,bbb,24.65,25.6,normal,.2,7);slots.panel(aa,bbb,25.6,28.2,normal,.21,1);slabs.panel(aa,bbb,28.2,29.8,normal,.24,7)
  for k in range(max(2,round(run/2.5))+1):
   q=edge(aa,bbb,k/max(2,round(run/2.5)));breaks.beam((q[0]+normal[0]*.30,q[1]+normal[1]*.30,25.6),(q[0]+normal[0]*.30,q[1]+normal[1]*.30,28.2),.10,.10,0)
 for t0,t1 in stone:
  aa,bbb=edge(a,bb,t0),edge(a,bb,t1)
  breaks.panel(aa,bbb,4.8,29.8,normal,.40,7)
  for q in [aa,bbb]:breaks.beam((q[0],q[1],4.8),(q[0],q[1],29.8),1.15,1.15,7)
  # Fine stone coursing remains quieter than the deep parking openings.
  for z in [6+i*1.8 for i in range(13)]:breaks.panel(aa,bbb,z,z+.045,normal,.425,2)
  joints=max(2,round(L*(t1-t0)/3.0))
  for k in range(1,joints):
   q=edge(aa,bbb,k/joints);breaks.beam((q[0]+normal[0]*.425,q[1]+normal[1]*.425,4.8),(q[0]+normal[0]*.425,q[1]+normal[1]*.425,29.8),.035,.015,2)
  if ei==roles['solidEndEdge']:
   # Large rectangular relief: dark recessed reveal with a light inner face.
   ra,rb=edge(aa,bbb,.23),edge(aa,bbb,.77)
   breaks.panel(ra,rb,11.0,24.2,normal,.46,3)
   ra,rb=edge(aa,bbb,.24),edge(aa,bbb,.76)
   breaks.panel(ra,rb,11.3,23.9,normal,.48,7)
   for z in [13.1,14.9,16.7,18.5,20.3,22.1]:breaks.panel(ra,rb,z,z+.035,normal,.50,2)
 for t0,t1 in glass:
  aa,bbb=edge(a,bb,t0),edge(a,bb,t1)
  breaks.panel(aa,bbb,2.8,25.6,normal,.38,1)
  for k in range(6):
   q=edge(aa,bbb,k/5);breaks.beam((q[0]+normal[0]*.55,q[1]+normal[1]*.55,2.8),(q[0]+normal[0]*.55,q[1]+normal[1]*.55,25.7),.32,.44,7)
  for z in [5,8.4,11.8,15.2,18.6,22]:breaks.panel(aa,bbb,z,z+.12,normal,.44,3)
  breaks.panel(aa,bbb,25.6,29.8,normal,.46,7)
 if L>8:
  garden.panel(a,bb,30,30.9,normal,-.5,7)
  for k in range(max(1,int(L/4))):
   pt=edge(a,bb,(k+.5)/max(1,int(L/4)));garden.box((pt[0]-normal[0]*1.0,pt[1]-normal[1]*1.0,31.2),(2.2,1.8,1.1),8)
assets.append(export_asset(pb,[m.obj(col) for m in [slabs,slots,garden,breaks]],col))

review=collect('REVIEW_ONLY_NOT_EXPORTED');ground=Mesh('Review neutral ground');ground.box((0,0,-.4),(550,550,.5),7);ground.obj(review)
world=bpy.context.scene.world or bpy.data.worlds.new('Hyperion daylight');bpy.context.scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.79,.83,.9,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65
light=bpy.data.lights.new('Review afternoon sun','SUN');light.energy=2.4;light.angle=.13;sun=bpy.data.objects.new('Review afternoon sun',light);review.objects.link(sun);sun.rotation_euler=(.45,-.65,-.4)
camdata=bpy.data.cameras.new('Review camera');cam=bpy.data.objects.new('Review camera',camdata);review.objects.link(cam);scene=bpy.context.scene;scene.camera=cam
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1500;scene.render.resolution_y=1200;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
def view(name,eye,target,scale):
 cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
view('review-southwest',(-330,-420,265),(-7,-12,119),395)
view('review-northeast',(370,390,265),(-7,-12,119),370)
view('review-plan',(0,0,600),(0,0,0),225)
a=recipe['buildings'][0];x,y=a['siteEN'];view('review-A-crown',(x+95,y-145,285),(x,y,226),108)
view('review-podium-front',(230,-175,72),(10,6,19),167)
view('review-A-braces',(x+88,y-160,178),(x,y,129),105)
target=Vector((-7,-12,110));eye=Vector((-330,-420,265))
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   sp=area.spaces.active;sp.shading.type='MATERIAL';sp.clip_end=3000;sp.region_3d.view_location=target;sp.region_3d.view_distance=440;sp.region_3d.view_rotation=(eye-target).to_track_quat('Z','Y');sp.region_3d.view_perspective='ORTHO'
bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'hyperion-authored.blend'))
bundle={'siteId':'hyperion','assets':assets,'sources':recipe['sources'],'recipeFiles':['recipe-input.json','claimed-source-buildings.json'],'retainedUntouchedSourceFootprintIds':recipe['retainedUntouchedSourceFootprintIds'],
 'places':[{'id':'bespoke-hyperion','name':'목동 현대하이페리온','subtitle':'실제 위치·시공사 사진 기반 개별 모델 · 아파트466세대','center':[126.87497,37.52697],'zoom':16.6,'household_count':466,'source_url':'https://www.sfacade.net/dongtan-hyperion','supersedesPlaceIds':['reference-flight-hyperion','apt-a15805114']}],
 'authoredVia':'Real Blender MCP execute_blender_code, dedicated port9877','blenderVersion':bpy.app.version_string,'sourcesAreEmbedded':False,'renders':['review-southwest.png','review-northeast.png','review-plan.png','review-A-crown.png','review-podium-front.png','review-A-braces.png']}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'siteId':'hyperion','assets':[{'id':a['id'],'triangles':a['triangles'],'heightM':a['heightM'],'bytes':a['bytes']} for a in assets]},ensure_ascii=False))
