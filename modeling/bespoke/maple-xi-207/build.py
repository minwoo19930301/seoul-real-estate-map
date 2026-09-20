"""207 only. Fresh individually authored face layout; run via live Blender MCP."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
O=Path(__file__).parent;D=json.loads((O/'authored-input.json').read_text());bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
COL={'white':(.76,.755,.70,1),'glass':(.055,.12,.15,1),'metal':(.105,.145,.16,1),'paleMetal':(.34,.40,.415,1),'stone':(.56,.515,.425,1),'dark':(.115,.145,.15,1),'roof':(.38,.40,.38,1),'joint':(.40,.41,.39,1)};M={}
for n,c in COL.items():
 m=bpy.data.materials.new('Maple207_'+n);m.diffuse_color=c;m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=c;p.inputs['Roughness'].default_value=.29 if n=='glass' else .68;p.inputs['Metallic'].default_value=.35 if n in ['metal','paleMetal','glass'] else .03;M[n]=m
class Mesh:
 def __init__(s,n,m):s.n=n;s.m=m;s.v=[];s.f=[]
 def prism(s,p,z0,z1):
  if z1<=z0:return
  p=[Vector((x,y,0)) for x,y in p];q=len(s.v);l=len(p);s.v += [(v.x,v.y,z) for z in [z0,z1] for v in p];idx={tuple(v):i for i,v in enumerate(p)}
  for tr in tessellate_polygon([p]):
   ids=[v if isinstance(v,int) else idx[tuple(v)] for v in tr];s.f += [tuple(q+i for i in ids[::-1]),tuple(q+l+i for i in ids)]
  for i in range(l):s.f.append((q+i,q+(i+1)%l,q+(i+1)%l+l,q+i+l))
 def box(s,x,y,z,w,d,h,a=0):
  c,t=math.cos(a),math.sin(a);s.prism([(x+i*c-j*t,y+i*t+j*c) for i,j in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]],z-h/2,z+h/2)
 def wall(s,a,b,z0,z1,w=.1):
  a,b=Vector(a),Vector(b);t=(b-a).normalized();n=Vector((-t.y,t.x))*w/2;s.prism([a+n,b+n,b-n,a-n],z0,z1)
 def finish(s):
  me=bpy.data.meshes.new(s.n);me.from_pydata(s.v,[],s.f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new('Maple207_'+s.n,me);bpy.context.collection.objects.link(o);me.materials.append(M[s.m]);o['asset_id']=D['id'];return o
PART={}
def P(n,m):
 if (n,m) not in PART:PART[n,m]=Mesh(n,m)
 return PART[n,m]
V=[Vector(p) for p in D['ringEN']];roof=89.6;base=4.2;storey=3.05
# Polygon runs clockwise in east/north. Left normal is outward.
def fp(e,t,offset=0):
 a,b=V[e],V[(e+1)%6];ax=(b-a).normalized();n=Vector((-ax.y,ax.x));return a+(b-a)*t+n*offset
def panel(e,t0,t1,z0,z1,name,mat,offset=.04,depth=.1):P(name,mat).wall(fp(e,t0,offset),fp(e,t1,offset),z0,z1,depth)
def post(e,t,z0,z1,w,name,mat,offset=.1,depth=.14):
 a,b=V[e],V[(e+1)%6];v=fp(e,t,offset);P(name,mat).box(*v,(z0+z1)/2,w,depth,z1-z0,math.atan2((b-a).y,(b-a).x))
# Interior mass inset so balcony apertures genuinely recess beyond outer frames.
P('recessed_residential_mass','white').prism([tuple(v*.92) for v in V],base,roof-.30)
P('roof_deck','roof').prism([tuple(v) for v in V],roof-.24,roof)
P('ground_recessed_core','stone').prism([tuple(v*.54) for v in V],0,base)
# Facade5 SW return: official completed primary crop has FOUR unequal white-framed columns.
# W28's broad metal corner and balcony schedule do not belong to confirmed evidence and are excluded.
white_banks=[(.070,.155),(.235,.415),(.485,.715),(.790,.940)]
for k in range(28):
 z=base+k*storey;top=z+storey;mat='stone' if k<3 else 'white'
 panel(5,0,1,z,top,'e5_recessed_pale_wall_back',mat,-.55,.16)
 for j,(l,r) in enumerate(white_banks):
  panel(5,l,r,z+.58,z+2.63,'e5_four_unequal_window_reveals','dark',-.32,.12)
  panel(5,l+.008,r-.008,z+.64,z+2.57,'e5_four_unequal_glazed_groups','glass',-.21,.045)
  # The narrower corner opening is singlewide; the broadcenter columns have offsetmullions.
  if j in [1,2,3]:
   t=l+(r-l)*(.58 if j==2 else .48)
   post(5,t,z+.65,z+2.56,.070,'e5_internal_window_mullions','paleMetal',-.11,.16)
  panel(5,l,r,z+.50,z+.61,'e5_recess_sill','paleMetal',.035,.37)
  for t in [l,r]:post(5,t,z+.48,z+2.73,.16,'e5_reveal_side_returns',mat,.025,.36)
 # Thick unequal pale strips betweenwindowgroups, with muchthinner sashstructureinside.
 for l,r in [(0,.070),(.155,.235),(.415,.485),(.715,.790),(.940,1)]:
  panel(5,l,r,z,top,'e5_primary_white_vertical_piers',mat,.06,.30)
 panel(5,0,1,z,z+.50,'e5_primary_white_horizontal_beams',mat,.08,.34)
# Highway longface4: primary A/C show broad rooms separated by narrow services and opaque zones.
# Normalized widths are photo estimates, deliberately not seven equal panes.
banks=[(.175,.287,'narrow'),(.324,.486,'broad'),(.524,.576,'slot'),(.613,.805,'broad'),(.842,.990,'corner')]
for k in range(28):
 z=base+k*storey;top=z+storey
 panel(4,0,.16,z,top,'e4_NE_pale_band','white',.02,.2)
 panel(4,.035,.111,z+.68,z+2.55,'e4_NE_small_window','glass',.16,.06)
 # The opaque backs sit behind proud frames; window panes deeper again.
 panel(4,.16,1,z,top,'e4_opaque_dark_infill_back','metal',-.62,.18)
 for l,r,kind in banks:
  height=1.91 if kind in ['broad','corner'] else 1.65
  sill=.70 if kind in ['broad','corner'] else .93
  # Deep dark reveals and glass plane are separate solids.
  panel(4,l+.006,r-.006,z+sill-.06,z+sill+height+.08,'e4_window_recess_back','dark',-.43,.11)
  panel(4,l+.014,r-.014,z+sill,z+sill+height,'e4_recessed_window_glass','glass',-.35,.045)
  # Unequal opening lights. Broad banks combine fixedglass, narrow opaquevent and sash.
  if kind in ['broad','corner']:
   split=l+(r-l)*.68
   post(4,split,z+sill,z+sill+height,.095,'e4_asymmetric_window_mullion','paleMetal',-.18,.35)
   panel(4,split+.004,r-.014,z+sill,z+sill+.58,'e4_partial_opaque_window_infill','metal',-.13,.15)
   panel(4,l+.01,r-.01,z+.10,z+sill-.02,'e4_broad_gray_spandrel','paleMetal',.055,.22)
  else:
   split=(l+r)/2
   post(4,split,z+sill,z+sill+height,.07,'e4_service_window_mullion','metal',-.18,.28)
   # Visible service slit is dark and partially louvred, not a large glazed rectangle.
   panel(4,l+.005,r-.005,z+.14,z+sill-.10,'e4_service_opaque_panel','metal',.065,.22)
   for zz in [.25,.42,.59]:panel(4,l+.012,r-.012,z+zz,z+zz+.035,'e4_service_vent_slats','dark',.19,.035)
  for t in [l,r]:post(4,t,z,top,.14,'e4_projected_bay_jambs','paleMetal',.12,.34)
  panel(4,l-.002,r+.002,z+sill-.06,z+sill+.045,'e4_projected_sill_lip','paleMetal',.19,.53)
  panel(4,l,r,z+sill+height,z+sill+height+.10,'e4_projected_head_lip','metal',.14,.45)
 # Several solid strips of different widths interrupt the facade, visible in A.
 for l,r in [(.16,.175),(.287,.324),(.486,.524),(.576,.613),(.805,.842)]:
  panel(4,l,r,z,top,'e4_fullheight_opaque_separator','metal',.02,.28)
  panel(4,l+.003,r-.003,z+1.45,z+1.49,'e4_opaque_panel_joint','dark',.17,.02)
 panel(4,.16,1,z,z+.11,'e4_floor_horizontal_reveal','dark',.01,.21)
 panel(4,0,.16,z,z+.5,'e4_NE_white_beam','white',.16,.25)
# Obscured/rear: restrained lowconfidence placeholderwindowpattern, marked independently.
for e in [0,1,2,3]:
 length=(V[(e+1)%6]-V[e]).length
 panel(e,0,1,base,roof,'rear_'+str(e)+'_provisional_white','white',-.10,.24)
 if e==2:
  for k in range(28):panel(e,.42,.60,base+k*storey+.9,base+k*storey+2.1,'notch_core_small_opening','glass',.05,.06)
  continue
 bays={0:5,1:3,3:3}[e]
 for j in range(bays):
  t=(j+.5)/bays;w=.45/bays
  for k in range(28):
   z=base+k*storey
   panel(e,t-w/2,t+w/2,z+.7,z+2.55,'rear_'+str(e)+'_unverified_windows','glass',.06,.055)
 for k in range(29):panel(e,0,1,base+k*storey,base+k*storey+.04,'rear_panel_seams','joint',.045,.03)
# Completed C base: substantial stone portal lintels, pale jambs and low recessedlobby.
# No four identical freestanding cornerlegs and no ownership of outside communalplaza.
for e in [4,5]:
 panel(e,0,1,3.18,base,'ground_stone_continuous_header','stone',-.04,.68)
 # Low lobby behind the front portal, with one glazed door group and upper opaque band.
 panel(e,.12,.88,.20,2.75,'low_recessed_lobby_glass','glass',-2.05,.12)
 panel(e,.12,.88,2.75,3.25,'low_lobby_opaque_head','metal',-2.0,.15)
 for t in [.20,.40,.60,.80]:post(e,t,.22,2.77,.10,'recessed_lobby_door_frames','paleMetal',-1.96,.14)
# White portal turns aroundsouthcorner; otherdarkbasebays have broader stonepiers.
for e,interval in [(4,(.73,1.0)),(5,(0,.38))]:
 l,r=interval
 panel(e,l,r,3.0,base,'south_entry_white_portal_header','white',.13,.82)
 for t in [l,r]:post(e,t,0,3.2,.86,'south_entry_white_portal_jambs','white',.10,.84)
 post(e,(l+r)/2,0,3.0,.50,'south_entry_subdividing_stone_pier','stone',-.36,.64)
for e,positions in [(4,[.03,.29,.54]),(5,[.62,.96])]:
 for t in positions:post(e,t,0,base,1.05,'ground_solid_stone_wall_piers','stone',-.20,1.10)
# Roof crown thin OPEN fins. Rounded convexcorner transitions derived frompolygon, notopaque cap.
# Short segmentcutback createsroundedcornerbeadswithoutchanginggroundoutline.
crown=[]
for i,v in enumerate(V):
 prev=V[(i-1)%6];nxt=V[(i+1)%6];d=min(1.2,(v-prev).length*.15,(nxt-v).length*.15);p=v+(prev-v).normalized()*d;q=v+(nxt-v).normalized()*d
 for j in range(6):t=j/5;crown.append((1-t)*(1-t)*p+2*(1-t)*t*v+t*t*q)
for a,b in zip(crown,crown[1:]+crown[:1]):
 L=(b-a).length;steps=max(1,round(L/.55));ax=b-a
 for j in range(steps):
  p=a+ax*j/steps;P('open_roof_fins','paleMetal').box(*p,91.12,.08,.19,2.95,math.atan2(ax.y,ax.x))
 for z in [89.78,92.60]:P('rounded_crown_rails','paleMetal').wall(a,b,z,z+.09,.11)
# Inset small rooftopplant, deliberatelyseparatefromrearhigherneighbor.
# RooflocalbasisalignedwithSWedge andNEaxis.
u=(V[5]-V[0]).normalized();v=Vector((-u.y,u.x));center=Vector((-1.4,1.2));ang=math.atan2(u.y,u.x)
def roofbox(n,m,x,y,w,d,z0,z1):
 c=center+u*x+v*y;P(n,m).box(*c,(z0+z1)/2,w,d,z1-z0,ang)
roofbox('inset_rectangular_plant_high','white',0,1,12.3,8.7,roof,92.55)
roofbox('inset_plant_low_return','white',5.0,-1.8,4.0,4.8,roof,91.7)
roofbox('plant_cap_high','paleMetal',0,1,12.50,8.90,92.48,92.62)
# Front faceofplantvisibleinA: two darkunequalopenings.
for x,w,z0,z1 in [(-1.7,1.1,90.95,92.05),(1.8,.6,90.9,91.62)]:
 a=center+u*(x-w/2)+v*(-3.39);b=center+u*(x+w/2)+v*(-3.39);P('plant_front_vent_apertures','dark').wall(a,b,z0,z1,.06)
# Roof equipmentfloor pads lowanddiscreet.
roofbox('plant_service_pad','roof',-3,-6,4,3,roof,roof+.15)
objs=[p.finish() for p in PART.values() if p.v]
# Save physicalsingleasset; groundminZ0. No otherbuilding/contextmesh exported.
bpy.ops.object.select_all(action='DESELECT')
for ob in objs:ob.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
bpy.ops.export_scene.gltf(filepath=str(O/'bespoke-maple-xi-207.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_materials='EXPORT')
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.render.resolution_x=1200;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.65,.70,.78,1);scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.45
def camera(name,loc,target,ortho):
 d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='ORTHO';d.ortho_scale=ortho;return o
camera('SE_completed_match',(10,-240,126),(0,0,44),117)
camera('SW_primary_white_return',(-140,-165,41),(0,0,48),112)
camera('NE_unverified_back',(140,130,115),(0,0,45),120)
camera('Roof_detail',(65,-70,148),(0,0,89),63)
camera('Dark_face_detail',(70,-105,62),(10,-7,58),28)
camera('Base_front',(80,-90,21),(0,0,5),55)
light=bpy.data.lights.new('ReviewSun','SUN');ob=bpy.data.objects.new('ReviewSun',light);bpy.context.collection.objects.link(ob);ob.rotation_euler=(.45,-.6,-.65);light.energy=2
ld=bpy.data.lights.new('FrontSoftbox','AREA');lo=bpy.data.objects.new('FrontSoftbox',ld);bpy.context.collection.objects.link(lo);lo.location=(50,-100,140);lo.rotation_euler=(Vector((0,0,45))-lo.location).to_track_quat('-Z','Y').to_euler();ld.energy=60000;ld.shape='DISK';ld.size=100
scene.camera=bpy.data.objects['SE_completed_match'];scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-207.blend'))
(O/'build-summary.json').write_text(json.dumps({'blender':bpy.app.version_string,'components':[o.name for o in objs],'vertices':sum(len(o.data.vertices) for o in objs),'faces':sum(len(o.data.polygons) for o in objs),'bounds':{'min':[min((o.matrix_world@v.co)[i] for o in objs for v in o.data.vertices) for i in range(3)],'max':[max((o.matrix_world@v.co)[i] for o in objs for v in o.data.vertices) for i in range(3)]}},indent=2))
print('BUILT207',len(objs),'components')
