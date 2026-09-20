"""Individual as-built Banpo/Jamsu reconstruction through the live Blender MCP.

Primary shape evidence: Seoul 2023 brief PDF pp15-16 (PDF pages18-19).
No factory bridge mesh, source photograph texture, or design competition proposal.
"""
import bpy, bmesh, math, json, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/banpo-jamsu'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for d in list(bpy.data.materials): bpy.data.materials.remove(d)
# Geographic anchor and northward bridge axis, fitted to OSM straight main deck.
LON,LAT=126.996466,37.514546
north=Vector((-0.3589,0.9334,0));north.normalize()
east=Vector((north.y,-north.x,0))
def world(s,t,z): return north*s+east*t+Vector((0,0,z))
def ll(lon,lat): return Vector(((lon-LON)*111320*math.cos(math.radians(LAT)),(lat-LAT)*111320,0))
def local(v): return (v.dot(north),v.dot(east))
M={}
for name,col in {'aged_concrete':(.64,.66,.63,1),'leg_recess':(.43,.47,.46,1),'steel_box_pale':(.56,.63,.64,1),'steel_lower_ochre':(.39,.34,.23,1),'asphalt':(.16,.18,.18,1),'line_white':(.83,.83,.74,1),'line_yellow':(.86,.57,.13,1),'bike_red':(.44,.20,.18,1),'walk_green':(.13,.35,.31,1),'rail':(.48,.53,.54,1),'fountain_pipe':(.28,.37,.39,1)}.items():
 m=bpy.data.materials.new(name);m.diffuse_color=col;m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=col;p.inputs['Roughness'].default_value=.83;M[name]=m
class Mesh:
 def __init__(self,name,mat):self.name=name;self.mat=mat;self.v=[];self.f=[]
 def add(self,v,f):
  n=len(self.v);self.v += [tuple(x) for x in v];self.f += [tuple(n+i for i in face) for face in f]
 def box(self,s,t,z,ds,dt,dz):
  self.add([world(s+a*ds/2,t+b*dt/2,z+c*dz/2) for a,b,c in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
 def sweep(self,stations,section):
  n=len(section);v=[world(s,t,z+height) for s,height in stations for t,z in section];f=[tuple(range(n-1,-1,-1)),tuple((len(stations)-1)*n+i for i in range(n))]
  for j in range(len(stations)-1):
   for i in range(n):f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
  self.add(v,f)
 def finish(self):
  if not self.v:return
  me=bpy.data.meshes.new(self.name);me.from_pydata(self.v,[],self.f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new(self.name,me);bpy.context.collection.objects.link(o);o.data.materials.append(M[self.mat]);return o
parts={}
def part(n,m):parts[n]=Mesh(n,m);return parts[n]
def strip(mesh,stations,ta,tb,za,zb):mesh.sweep(stations,[(ta,za),(tb,za),(tb,zb),(ta,zb)])
# Deck envelope includes original northern viaduct and both ramp branches.
g=json.loads((ROOT/'public/bridge-outlines.geojson').read_text())
f=next(f for f in g['features'] if f['properties']['sourceId']=='osm:way/1085504592')
ring=[ll(*p) for p in f['geometry']['coordinates'][0][:-1]]
def upper(s):return 19.4 if s<500 else 19.4-(min(s,930)-500)*.020
for name,mat,off,thick in [('Banpo_entire_OSM_deck_and_approach_branches','aged_concrete',-.65,.65),('Banpo_asphalt_on_source_envelope','asphalt',.006,.035)]:
 mesh=part(name,mat);verts=[]
 for dz in (off,off+thick):verts += [Vector((v.x,v.y,upper(local(v)[0])+dz)) for v in ring]
 n=len(ring);faces=[]
 # Tessellation indexes preserve actual geographic ramp polygon.
 tris=tessellate_polygon([ring]);idx={tuple(v):i for i,v in enumerate(ring)}
 for tri in tris:
  inds=tuple(v if isinstance(v,int) else idx[tuple(v)] for v in tri);faces.extend([tuple(reversed(inds)),tuple(i+n for i in inds)])
 for i in range(n):faces.append((i,(i+1)%n,(i+1)%n+n,i+n))
 mesh.add(verts,faces)
# Upper main crossing30m portal rhythm; start/end fitting is explicitly estimated.
portal=part('Banpo_30m_twin_leg_haunched_portal_frames','aged_concrete');recess=part('Banpo_I_profile_leg_recesses','leg_recess');caps=part('Banpo_bearing_pads','rail')
for s in range(-450,511,30):
 h=upper(s)-3.2
 for t in [-10.45,10.45]:
  portal.box(s,t,h/2,2.25,2.4,h)
  # Twin ribs create observed recessed vertical face, not cylindrical stock piers.
  for side in [-1,1]:portal.box(s+side*1.17,t,h/2,.23,2.65,h)
  recess.box(s,t-1.215,h/2,1.45,.025,h-.25);recess.box(s,t+1.215,h/2,1.45,.025,h-.25)
  portal.box(s,t,.40,3.9,3.7,.8)
 # Haunched header in crosssection, extruded along bridge.
 cross=[(-11.75,h-1.65),(-10.3,h-1.65),(-7.8,h-.5),(7.8,h-.5),(10.3,h-1.65),(11.75,h-1.65),(11.75,h+1),(-11.75,h+1)]
 portal.sweep([(s-1.1,0),(s+1.1,0)],cross)
 for t in [-8.1,-2.7,2.7,8.1]:caps.box(s,t,h+1.16,1.45,2.9,.3)
# Four light steel box girders beneath slab, with transverse diaphragms.
girders=part('Banpo_four_longitudinal_steel_box_girders','steel_box_pale');diaph=part('Banpo_cross_diaphragms','steel_box_pale')
for t in [-8.1,-2.7,2.7,8.1]:strip(girders,[(-480,0),(500,0)],t-1.6,t+1.6,17.35,18.78)
for s in range(-465,500,15):diaph.box(s,0,18.0,.25,21,1.20)
# Full lower route plus land approaches. Crossing length795m from official brief.
# Crest height, lateral lane allocations, endpoints and transition profile are photo estimates.
def lower(s):
 d=abs(s-72.5)
 return 5.35+(5.7*.5*(1+math.cos(math.pi*d/120)) if d<120 else 0)
st=[(s,lower(s)) for s in range(-470,486,3)]
slab=part('Jamsu_18m_low_deck_with_navigation_crest','aged_concrete');strip(slab,st,-9,9,-.45,0)
asph=part('Jamsu_two_lane_road','asphalt');strip(asph,st,-7.3,2.7,.015,.045)
bike=part('Jamsu_one_sided_red_cycleway','bike_red');strip(bike,st,3,6.4,.03,.055)
walk=part('Jamsu_green_walk_and_west_walk','walk_green');strip(walk,st,6.6,8.75,.03,.055);strip(walk,st,-8.8,-7.6,.03,.055)
curb=part('Jamsu_cycleway_curbs','aged_concrete')
for ta,tb in [(2.75,3),(6.4,6.6)]:strip(curb,st,ta,tb,.04,.19)
lowgirder=part('Jamsu_visible_plate_girders_follow_crest','steel_lower_ochre')
for t in [-7.5,-3.75,0,3.75,7.5]:
 lowgirder.sweep(st,[(t-.38,-1.20),(t+.38,-1.20),(t+.38,-1.05),(t+.08,-1.05),(t+.08,-.45),(t+.38,-.45),(t+.38,-.32),(t-.38,-.32),(t-.38,-.45),(t-.08,-.45),(t-.08,-1.05),(t-.38,-1.05)])
lowpier=part('Jamsu_15m_pier_rhythm_and_open_navigation_bays','aged_concrete')
# Intermediate piers disappear within navigation crest; upper piers remain30m.
# Exact surveyed current pier count is not claimed.
for s in range(-390,406,15):
 if -30<s<180 and s%30!=0:continue
 h=lower(s)-1.3
 lowpier.box(s,0,h-.35,1.35,17.8,.7)
 for t in [-6.8,0,6.8]:lowpier.box(s,t,(h-.7)/2,1.5,1.25,h-.7)
# Rails, center markings and separate fountainhardware on each upper side.
rail=part('Banpo_and_Jamsu_edge_rails','rail');posts=part('Jamsu_safety_rail_posts','rail');mark=part('Deck_lane_lines','line_white');yellow=part('Jamsu_centre_and_cycle_markings','line_yellow')
for t in [-8.9,8.9]:
 for dz in [.55,1.05]:strip(rail,st,t-.05,t+.05,dz,dz+.06)
 for s in range(-468,487,4):posts.box(s,t,lower(s)+.55,.07,.09,1.1)
for t in [-12,12]:
 strip(rail,[(-480,0),(500,0)],t-.08,t+.08,19.8,20.45)
for t in [-8,-4,4,8]:
 for s in range(-475,500,12):mark.box(s,t,19.451,5,.12,.015)
for t in [-2.3,4.7]:strip(yellow,st,t-.06,t+.06,.059,.072)
for t in [-7.25,2.65]:strip(mark,st,t-.06,t+.06,.058,.072)
fountain=part('Banpo_570m_each_side_fountain_manifold','fountain_pipe')
for t in [-12.4,12.4]:
 strip(fountain,[(-320,0),(250,0)],t-.12,t+.12,18.4,18.64)
 for s in range(-320,251,3):fountain.box(s,t+(.26 if t>0 else -.26),18.52,.16,.5,.15)
# Upper lamppost silhouettes, reconstructed curved arms from photos.
lamps=part('Banpo_curved_street_lamp_arms','rail')
for s in range(-460,501,30):
 for t in [-11.4,11.4]:
  lamps.box(s,t,23.2,.12,.12,7.6)
  sign=-1 if t>0 else 1
  points=[(t,27),(t+sign*.15,27.5),(t+sign*.55,27.7),(t+sign*1.2,27.65),(t+sign*2,27.25)]
  for (a,z),(b,w) in zip(points,points[1:]):
   lamps.sweep([(s-.07,0),(s+.07,0)],[(a,z-.07),(b,w-.07),(b,w+.07),(a,z+.07)])
  lamps.box(s,t+sign*2,27.15,.4,.65,.17)
objs=[m.finish() for m in parts.values()];objs=[o for o in objs if o]
for o in objs:o['site']='Banpo Bridge / Jamsu Bridge';o['authorship']='Individual evidence-based reconstruction; Seoul2023 existing-condition photos and diagram';o['dimensions_status']='30m upper /15m lower rhythm and18m width documented; heights and end fitting estimated'
bpy.ops.object.select_all(action='DESELECT')
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
bpy.ops.export_scene.gltf(filepath=str(OUT/'banpo-jamsu.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=1600;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.world.color=(.65,.65,.65)
scene.view_settings.view_transform='AgX'
light=bpy.data.lights.new('Review_sun','SUN');light.energy=3;sun=bpy.data.objects.new('Review_sun',light);scene.collection.objects.link(sun);sun.rotation_euler=(.35,-.5,-.7)
# Cameras are local bridge oriented: full geographic deck and detailed silhouette.
for name,loc,target,scale in [('Overview',(300,-1100,850),(200,0,8),1730),('Navigation_side',(85,-230,42),(85,0,9),330),('Underdeck',(235,0,10),(55,0,9),None)]:
 cam=bpy.data.cameras.new(name);cam.clip_end=5000;ob=bpy.data.objects.new(name,cam);scene.collection.objects.link(ob);ob.location=world(*loc);aim=world(*target);ob.rotation_euler=(aim-ob.location).to_track_quat('-Z','Y').to_euler()
 if scale:cam.type='ORTHO';cam.ortho_scale=scale
 else:cam.type='PERSP';cam.lens=25
scene.camera=bpy.data.objects['Navigation_side']
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  area.spaces.active.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion();area.spaces.active.region_3d.view_distance=440;area.spaces.active.region_3d.view_location=world(70,0,8);area.spaces.active.clip_end=5000;area.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'banpo-jamsu.blend'))
recipe={'siteId':'banpo-jamsu','anchor':[LON,LAT],'axisNorth':list(north),'verified':{'jamsuRiverCrossingLengthM':795,'jamsuWidthM':18,'banpoTypicalPierRhythmM':30,'jamsuTypicalPierRhythmM':15,'fountainPerSideM':570},'estimated':{'upperDeckM':19.4,'lowerDeckM':5.35,'crestAdditionalRiseM':5.7,'crestCenterStationM':72.5,'crestHalfLengthM':120,'portalCapSection':'photo proportion','endSpanFit':'OSM main deck and approaches'},'sourceEnvelope':'public/bridge-outlines.geojson osm:way/1085504592 retained incl branches','lowerWidthNote':'Official18m corrected source lower polygon narrow width; route aligned under upper deck','components':[o.name for o in objs],'blenderVersion':bpy.app.version_string}
(OUT/'recipe.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2))
print('BANPO_JAMSU_EXPORTED',len(objs),'components',sum(len(o.data.polygons) for o in objs),'faces')
