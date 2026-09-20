"""Execute through the dedicated Blender MCP port 9877.

Only this SKY-L65 site is authored: four separately traced plans, the official
64/65/63/65-storey stack, tall white end piers, green glass valleys, thin real
refuge-storey reveals and the photographed projecting crown canopies.
"""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Vector, Quaternion
from mathutils.geometry import tessellate_polygon

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/skyl65'
OUT.mkdir(parents=True,exist_ok=True)
recipe_path=OUT/'recipe-input.json'
if not recipe_path.exists():recipe_path=ROOT/'modeling/bespoke/skyl65/recipe-input.json'
recipe=json.loads(recipe_path.read_text())
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
 if c.name!='Collection' and c.users==0:bpy.data.collections.remove(c)

def material(name,color,metal=0,rough=.5):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
 m.diffuse_color=(*color,1);m.use_nodes=True
 bs=next(node for node in m.node_tree.nodes if node.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(*color,1)
 bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
 return m
M=[material('SKY warm white precast photographed end-pier',(.73,.76,.72),.05,.63),
 material('SKY dark blue green glazing',(.042,.105,.104),.38,.24),
 material('SKY shaded glazing recess',(.027,.061,.060),.3,.30),
 material('SKY anodised fine mullion',(.31,.36,.34),.55,.38),
 material('SKY podium limestone',(.39,.39,.34),.02,.70),
 material('SKY roof silver canopy',(.73,.75,.72),.38,.34),
 material('SKY louvre graphite',(.12,.17,.16),.32,.55),
 material('SKY low-rise clear storefront glass',(.08,.16,.16),.4,.22),
 material('SKY darker window in white pier',(.036,.076,.077),.25,.30)]

class Mesh:
 def __init__(self,name):self.name=name;self.v=[];self.f=[];self.mi=[]
 def face(self,points,mat):
  k=len(self.v);self.v.extend(points);self.f.append(tuple(range(k,k+len(points))));self.mi.append(mat)
 def box(self,center,size,mat):
  x,y,z=center; a,b,c=[v/2 for v in size]
  v=[(x-a,y-b,z-c),(x+a,y-b,z-c),(x+a,y+b,z-c),(x-a,y+b,z-c),(x-a,y-b,z+c),(x+a,y-b,z+c),(x+a,y+b,z+c),(x-a,y+b,z+c)]
  for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([v[i] for i in f],mat)
 def prism(self,points,z0,z1,mat):
  p=[tuple(x[:2]) for x in points]
  if p[0]==p[-1]:p=p[:-1]
  area=sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))
  if area<0:p.reverse()
  for a,b in zip(p,p[1:]+p[:1]):self.face([(a[0],a[1],z0),(b[0],b[1],z0),(b[0],b[1],z1),(a[0],a[1],z1)],mat)
  vertices=[Vector((x,y,0)) for x,y in p]
  for tri in tessellate_polygon([vertices]):
   points=[vertices[v] if isinstance(v,int) else v for v in tri]
   self.face([(v.x,v.y,z1) for v in points],mat);self.face([(v.x,v.y,z0) for v in reversed(points)],mat)
 def panel(self,a,b,z0,z1,normal,offset,mat):
  ax,ay=a[0]+normal[0]*offset,a[1]+normal[1]*offset
  bx,by=b[0]+normal[0]*offset,b[1]+normal[1]*offset
  self.face([(ax,ay,z0),(bx,by,z0),(bx,by,z1),(ax,ay,z1)],mat)
 def beam(self,a,b,width,depth,mat):
  av,bv=Vector(a),Vector(b);axis=(bv-av).normalized();side=axis.cross(Vector((0,0,1)))
  if side.length<.01:side=Vector((1,0,0))
  side.normalize();other=axis.cross(side).normalized()
  pts=[av+side*width*s+other*depth*t for s,t in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]]+[bv+side*width*s+other*depth*t for s,t in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]]
  for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([pts[i] for i in f],mat)
 def object(self,collection):
  if not self.f:return None
  mesh=bpy.data.meshes.new(self.name);mesh.from_pydata(self.v,[],self.f);mesh.update()
  for m in M:mesh.materials.append(m)
  for face,mat in zip(mesh.polygons,self.mi):face.material_index=mat
  obj=bpy.data.objects.new(self.name,mesh);collection.objects.link(obj)
  return obj

def ring(poly):return [list(p[:2]) for p in poly['coordinates'][0][:-1]]
def centroid(p):return [sum(v[0] for v in p)/len(p),sum(v[1] for v in p)/len(p)]
def ccw(p):
 if sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))<0:return list(reversed(p))
 return p
def subedge(a,b,t0,t1):return ([a[k]+(b[k]-a[k])*t0 for k in [0,1]],[a[k]+(b[k]-a[k])*t1 for k in [0,1]])

assets=[]
for b in recipe['buildings']:
 n=b['tower'];collection=bpy.data.collections.new('SKYL65_'+n+'_official-plan');bpy.context.scene.collection.children.link(collection)
 structure=Mesh(n+'_01_six-wing_concave_structure');facade=Mesh(n+'_02_large_white_end_piers');glass=Mesh(n+'_03_glass_bays_and_recessed_windows');trim=Mesh(n+'_04_fine_mullions_and_refuge_reveals');roof=Mesh(n+'_05_asymmetric_penthouse_and_crown');base=Mesh(n+'_06_three-storey_retail_and_entries')
 p=ccw(ring(b['footprint']));wings=[ring(w) for w in b['wings']];core=ring(b['core']);wc=[centroid(w) for w in wings]
 height=b['heightM'];fh=2.95;body_top=height-8.0;lower_penthouse=body_top-fh
 structure.prism(p,0,lower_penthouse,1)
 # The top residential storey occupies different side-wing/circulation masses.
 high_wings={'A':[0,5],'B':[0,2,3,5],'C':[0,2,3,5],'D':[0,5]}[n]
 for wi,w in enumerate(wings):
  roof.prism(w,lower_penthouse,body_top if wi in high_wings else lower_penthouse+.18,1)
 # Central plant head and open, projecting silver canopy observed in the three
 # July-2023 photographs. Dimensions above the last occupied storey are estimates.
 cp=centroid(core);plant=[(cp[0]+(x-cp[0])*.45,cp[1]+(y-cp[1])*.45) for x,y in core]
 roof.prism(plant,lower_penthouse,body_top+4.1,6)
 plant_ring=ccw(plant)
 for i,(a,bb) in enumerate(zip(plant_ring,plant_ring[1:]+plant_ring[:1])):
  v=Vector((bb[0]-a[0],bb[1]-a[1]));length=v.length
  if length<1:continue
  normal=(v.y/length,-v.x/length)
  for z in [body_top+j*.5 for j in range(8)]:roof.panel(a,bb,z,z+.11,normal,.16,3)
 canopy=[(cp[0]+(x-cp[0])*.67,cp[1]+(y-cp[1])*.67) for x,y in core]
 roof.prism(canopy,height-.6,height,5)
 for idx in [0,len(plant)//3,2*len(plant)//3]:
  a=plant[idx];dest=canopy[min(idx,len(canopy)-1)]
  roof.beam((a[0],a[1],body_top+1.8),(dest[0],dest[1],height-.6),.65,.65,0)
 # Penthouse wing parapets are discontinuous, with photographed taller green
 # corner fins; they are not the previous flat, saw-toothed roof sheet.
 for wi,w in enumerate(wings):
  z=body_top if wi in high_wings else lower_penthouse
  c=centroid(w)
  for a,bb in zip(w,w[1:]+w[:1]):
   L=math.dist(a,bb)
   if L<4.5:continue
   dx,dy=bb[0]-a[0],bb[1]-a[1];normal=(dy/L,-dx/L)
   roof.panel(a,bb,z,z+1.1,normal,.14,0 if wi in [0,5] else 3)
  if wi in [0,5]:
   furthest=max(w,key=lambda pt:math.dist(pt,cp))
   roof.beam((furthest[0],furthest[1],z-1),(furthest[0],furthest[1],z+3.3),.6,1.3,0)

 face_recipes=[]
 for ei,(a,bb) in enumerate(zip(p,p[1:]+p[:1])):
  dx,dy=bb[0]-a[0],bb[1]-a[1];L=math.hypot(dx,dy)
  if L<.40:continue
  normal=(dy/L,-dx/L);mid=((a[0]+bb[0])/2,(a[1]+bb[1])/2)
  wi=min(range(6),key=lambda j:math.dist(mid,wc[j]));rad=Vector((wc[wi][0]-cp[0],wc[wi][1]-cp[1]));rad.normalize()
  endface=(normal[0]*rad.x+normal[1]*rad.y)>.70 and L>2.2
  small_jog=L<2.35
  ztop=body_top if wi in high_wings else lower_penthouse
  # The completed photograph shows slender bright piers within much wider
  # dark glazed faces, not the full-width white end walls of the first review.
  # Explicit middle-pier/side-glazing segments retain this large-scale ratio.
  if small_jog:segments=[(0,1,True)]
  elif endface:
   frac=min(.58,max(2.3,L*.35)/L);left=(1-frac)/2
   segments=[(0,left,False),(left,1-left,True),(1-left,1,False)]
  else:
   edge=min(.66/L,.17)
   segments=[(0,edge,True),(edge,1-edge,False),(1-edge,1,True)]
  # The lower A rental stack is visibly lighter and is explicitly different
  # from B/C/D's occupied floors starting at4F in the official floor chart.
  if L<1.1:continue
  for start,end,white in segments:
   sa,sb=subedge(a,bb,start,end);sl=L*(end-start)
   if sl<.15:continue
   white_top=ztop
   if endface and white:
    # Different-height bright faces are directly visible in the completed
    # photo. Their exact termination storeys are an explicit visual estimate.
    trim_floors={'A':[2,3,5,5,3,2],'B':[2,3,4,4,3,2],'C':[2,3,4,4,2,2],'D':[2,3,8,8,3,2]}[n]
    white_top=ztop-trim_floors[wi]*fh
   if white:facade.panel(sa,sb,9.3,white_top,normal,.20,0)
   if n=='A' and wi in [2,3,4] and white:facade.panel(sa,sb,9.3,11*fh,normal,.24,4)
   if sl<1.25:continue
   margin=.35 if white else .10
   columns=max(1,int((sl-2*margin)/(1.55 if white else 1.42)))
   pitch=(sl-2*margin)/columns
   win_w=min(.80,pitch*.65) if white else max(.22,pitch-.12)
   for floor in range(4,b['floors']+1):
    z=(floor-1)*fh+.34
    if z+2.23>ztop or floor in b['refugeFloors']:continue
    bright=white and z+2.23<=white_top
    for col in range(columns):
     centre=margin+pitch*(col+.5);q,r=subedge(sa,sb,(centre-win_w/2)/sl,(centre+win_w/2)/sl)
     glass.panel(q,r,z+.17 if bright else z,z+2.08 if bright else z+2.44,normal,.42 if bright else .23,8 if bright else (1 if normal[0]>.1 else 2))
     if not bright:
      q2,r2=subedge(sa,sb,(centre+win_w/2)/sl,(centre+win_w/2+.065)/sl);trim.panel(q2,r2,z,z+2.44,normal,.28,3)
      trim.panel(q,r,z+1.42,z+1.47,normal,.28,3)
    if not bright:trim.panel(*subedge(sa,sb,margin/sl,1-margin/sl),z-.14,z-.065,normal,.28,3)
   face_recipes.append({'edge':ei,'wing':wi+1,'lengthM':round(sl,3),'style':'slender white window pier' if white else 'green glass bay','columns':columns,'whitePierTopM':white_top if white else None})
  for refuge in b['refugeFloors']:
   z=(refuge-1)*fh
   trim.panel(a,bb,z+.45,z+1.16,normal,.27,6)
   trim.panel(a,bb,z+.36,z+.46,normal,.30,3)
  # Stone plinth and separate shopfront vertical bays, no raised shared slab.
  base.panel(a,bb,.08,.65,normal,.25,4)
  base.panel(a,bb,8.8,9.32,normal,.30,4)
  nbase=max(1,int(L/2.7))
  for col in range(nbase):
   q,r=subedge(a,bb,(col+.13)/nbase,(col+.88)/nbase)
   base.panel(q,r,.72,8.7,normal,.28,7)
   q,r=subedge(a,bb,col/nbase,(col+.10)/nbase);base.panel(q,r,.65,8.8,normal,.32,4)
 # One low projecting entry canopy per true tower, separate from public roads.
 entry=min(p,key=lambda v:v[1]);base.box((entry[0],entry[1]-.85,4.5),(6,3.2,.35),5)
 objs=[m.object(collection) for m in [structure,facade,glass,trim,roof,base]];objs=[o for o in objs if o]
 for o in objs:o['site']='SKY-L65';o['tower']=n;o['source']='official plan + July 2023 completion photographs'
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True)
 bpy.context.view_layer.objects.active=objs[0]
 file=OUT/(b['id']+'.glb')
 bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_materials='EXPORT',export_extras=True)
 tris=sum(len(poly.vertices)-2 for o in objs for poly in o.data.polygons)
 bbmin=[min(v.co[i] for o in objs for v in o.data.vertices) for i in range(3)];bbmax=[max(v.co[i] for o in objs for v in o.data.vertices) for i in range(3)]
 assets.append({'id':b['id'],'nameKo':b['nameKo'],'file':str(file),'blendSource':str(OUT/'skyl65-authored.blend'),'coordinate':b['coordinate'],'category':'apartment','footprintIds':b['footprintIds'],
  'supersedes':['reference-flight-cheongnyangni-skyl65','apt-a10023083']+(['residential-'+b['footprintIds'][0]] if n=='D' else []),
  'referenceUrl':recipe['planUrl'],'floors':b['floors'],'heightM':b['heightM'],'heightBasis':b['heightBasis'],'floorsBasis':b['floorsBasis'],
  'components':[o.name for o in objs],'triangles':tris,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
  'boundsBlenderXYZ':[bbmin,bbmax],'dimensionsGlbXYZ':[bbmax[0]-bbmin[0],bbmax[2]-bbmin[2],bbmax[1]-bbmin[1]],'minGlbY':bbmin[2],
  'uncertainties':[b['heightBasis'],b['floorplanAccuracy'],'Facade subdivisions and crown dimensions manually estimated from low-resolution completed photos, not measured CAD.','OSM source centroids may differ from surveyed building centres.','Business tower and shared landscape not modelled or claimed.'],
  'sourceFootprintOverlapIoU':b['sourceFootprintOverlapIoU'],'facadeRecipe':face_recipes})
 for o in objs:o.location.x+=b['siteEN'][0];o.location.y+=b['siteEN'][1]

# Review-only presentation elements are excluded from all exported GLBs.
review=bpy.data.collections.new('REVIEW_ONLY_not_exported');bpy.context.scene.collection.children.link(review)
floor_mat=material('Review neutral ground',(.69,.72,.69),0,.95)
mesh=bpy.data.meshes.new('Review plane');mesh.from_pydata([(-220,-260,-.12),(270,-260,-.12),(270,230,-.12),(-220,230,-.12)],[],[(0,1,2,3)]);mesh.materials.append(floor_mat)
floor_obj=bpy.data.objects.new('REVIEW_ONLY_ground',mesh);review.objects.link(floor_obj)
world=bpy.context.scene.world or bpy.data.worlds.new('SKY daylight');bpy.context.scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.73,.79,.86,1);world.node_tree.nodes['Background'].inputs[1].default_value=.5
sun_data=bpy.data.lights.new('Review soft sun','SUN');sun_data.energy=2.5;sun_data.angle=.15
sun=bpy.data.objects.new('Review soft sun',sun_data);review.objects.link(sun);sun.rotation_euler=(math.radians(25),math.radians(-30),math.radians(-35))
camera_data=bpy.data.cameras.new('Review camera');camera=bpy.data.objects.new('Review camera',camera_data);review.objects.link(camera);bpy.context.scene.camera=camera
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1500;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.render.film_transparent=False
def view(name,pos,target,scale):
 camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera_data.type='ORTHO';camera_data.ortho_scale=scale
 scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
view('review-railway-southeast',(365,-470,290),(0,-42,101),340)
view('review-northwest',(-350,365,285),(0,-42,101),340)
view('review-plan',(0,-40,700),(0,-40,0),300)
view('review-crown-A',(125,-30,260),(45,10,180),100)
# Leave the actual MCP viewport at the railway-side oblique review view.
view_target=Vector((0,-40,92));view_eye=Vector((365,-470,290))
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   space=area.spaces.active;space.shading.type='MATERIAL';space.clip_end=3000
   space.region_3d.view_location=view_target;space.region_3d.view_distance=410
   space.region_3d.view_rotation=(view_eye-view_target).to_track_quat('Z','Y');space.region_3d.view_perspective='ORTHO'
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'skyl65-authored.blend'))
bundle={'siteId':'skyl65','householdCount':1425,'assets':assets,'recipeFiles':['recipe-input.json','claimed-source-buildings.json'],
 'sources':[{'url':recipe['planUrl'],'observations':'2022-uploaded official diagram; separately traced six dwelling wings in each A/B/C/D plan. Not measured as-built CAD.'},{'url':recipe['floorChartUrl'],'observations':'A64F B65F C63F D65F; A refuge23/44, B/C/D24/45.'}]+[{'url':u,'observations':'Official construction progress page labels these completed aerial photographs 2023.07; long white end piers, dark green side glazing, open projecting crown canopies and low storefront stone observed.'} for u in recipe['photoUrls']],
 'georeference':recipe['georeference'],'retainedUntouchedSourceFootprintIds':['604860f1-8f91-4420-8769-69f9d09b059f','ccde143f-4ead-46da-97b5-873021cf0e49'],
 'places':[{'id':'bespoke-skyl65','name':'청량리역 롯데캐슬 SKY-L65','subtitle':'공식 배치도·준공사진으로 개별 모델링 · 1,425세대','center':[127.04525970389179,37.5789],'zoom':16.4,'household_count':1425,'source_url':'https://www.lottecastle.co.kr/APT/AT00174/1449/summary/view.do','supersedesPlaceIds':['reference-flight-cheongnyangni-skyl65','apt-a10023083']}],
 'authoredVia':'Real Blender MCP execute_blender_code; dedicated port9877','blenderVersion':bpy.app.version_string,'sourcesAreEmbedded':False,'renders':['review-railway-southeast.png','review-northwest.png','review-plan.png','review-crown-A.png']}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'siteId':'skyl65','assets':[{'id':a['id'],'triangles':a['triangles'],'bytes':a['bytes'],'heightM':a['heightM']} for a in assets],'blend':str(OUT/'skyl65-authored.blend')},ensure_ascii=False))
