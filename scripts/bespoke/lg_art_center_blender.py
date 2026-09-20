"""Site-specific LG ArtsCenter/DiscoveryLab reconstruction through real Blender MCP."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/lg-art-center';INPUT=OUT/'authored-input.json';INPUT=INPUT if INPUT.exists() else ROOT/'modeling/bespoke/lg-art-center-seoul/authored-input.json';OUT.mkdir(parents=True,exist_ok=True);D=json.loads(INPUT.read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
C={'concrete':(.55,.53,.47,1),'pale':(.80,.80,.75,1),'roof':(.16,.20,.21,1),'frame':(.095,.12,.13,1),'glass':(.30,.39,.40,.12),'wood':(.66,.38,.13,1),'woodlight':(.76,.48,.18,1),'floor':(.43,.44,.40,1),'reveal':(.08,.10,.10,1),'grass':(.26,.33,.13,1),'soil':(.21,.19,.13,1)};M={}
for k,c in C.items():
 m=bpy.data.materials.new('LG_'+k);m.diffuse_color=c;m.use_nodes=True;s=m.node_tree.nodes.get('Principled BSDF');s.inputs['Base Color'].default_value=c;s.inputs['Roughness'].default_value=.3 if k=='glass' else .73
 if k=='glass':s.inputs['Alpha'].default_value=.12;m.surface_render_method='DITHERED'
 M[k]=m
class Mesh:
 def __init__(self,name,mat):self.name=name;self.mat=mat;self.v=[];self.f=[]
 def prism(self,ring,z0,z1):
  p=[Vector((x,y,0)) for x,y in ring];n=len(p);q=len(self.v);self.v += [(a.x,a.y,z) for z in [z0,z1] for a in p];idx={tuple(a):i for i,a in enumerate(p)}
  for tri in tessellate_polygon([p]):
   ids=[a if isinstance(a,int) else idx[tuple(a)] for a in tri];self.f += [tuple(q+i for i in reversed(ids)),tuple(q+n+i for i in ids)]
  for i in range(n):self.f.append((q+i,q+(i+1)%n,q+(i+1)%n+n,q+i+n))
 def box(self,x,y,z,w,d,h,ang=0):
  c,s=math.cos(ang),math.sin(ang);self.prism([(x+a*c-b*s,y+a*s+b*c) for a,b in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]],z-h/2,z+h/2)
 def wall(self,a,b,z0,z1,t=.18):
  a,b=Vector(a),Vector(b);u=(b-a).normalized();n=Vector((-u.y,u.x));self.prism([tuple(a+n*t/2),tuple(b+n*t/2),tuple(b-n*t/2),tuple(a-n*t/2)],z0,z1)
 def finish(self):
  me=bpy.data.meshes.new(self.name);me.from_pydata(self.v,[],self.f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new(self.name,me);bpy.context.collection.objects.link(o);me.materials.append(M[self.mat]);o['site']='LG ArtsCenter and DiscoveryLab';return o
parts={}
def P(n,m):
 key=(n,m)
 if key not in parts:parts[key]=Mesh('LG_'+n,m)
 return parts[key]
T=D['planTransform'];O=Vector(T['originEastNorth']);U=Vector(T['eastNorthPerPixelX']);V=Vector(T['eastNorthPerPixelY']);ang=math.atan2(U.y,U.x);ux=U.normalized();vy=V.normalized()
def xy(x,y):return O+U*(x-140)+V*(y-136)
def poly(r):return [tuple(xy(x,y)) for x,y in r]
def rect(n,m,x0,y0,x1,y1,z0,z1):P(n,m).prism(poly([(x0,y0),(x1,y0),(x1,y1),(x0,y1)]),z0,z1)
def face(n,m,a,b,z0,z1,t=.18):P(n,m).wall(tuple(xy(*a)),tuple(xy(*b)),z0,z1,t)
def ellipse(n,m,cx,cy,rx,ry,z0,z1,thick=None,start=0,end=2*math.pi,N=128):
 c=xy(cx,cy);pts=[c+ux*rx*math.cos(start+(end-start)*i/N)+vy*ry*math.sin(start+(end-start)*i/N) for i in range(N+1)]
 if thick:
  for i in range(N):
   a=start+(end-start)*i/N;b=start+(end-start)*(i+1)/N;ring=[pts[i],pts[i+1],c+ux*(rx-thick)*math.cos(b)+vy*(ry-thick)*math.sin(b),c+ux*(rx-thick)*math.cos(a)+vy*(ry-thick)*math.sin(a)];P(n,m).prism([tuple(x) for x in ring],z0,z1)
 else:P(n,m).prism([tuple(x) for x in pts[:-1]],z0,z1)
H=D['estimatedHeights'];h=H['main'];lo=H['lab'];ring=D['ring']
P('retained_complex_ground_slab','floor').prism(ring,0,.24)
P('DiscoveryLab_low_roof_plate','roof').prism(D['lowRoof'],lo-.25,lo+.12)
P('ArtsCenter_high_roof_plate','roof').prism(D['highRoof'],h-.25,h+.12)
# Inset pale waterproof roof fields retain deep dark projecting eaves, not a generic parapet box.
rect('main_pale_roof_field','pale',430,163,887,870,h+.12,h+.25)
# North-west atrium/Tube elevation at top of the architect floor plan.
# Individual ground entrances are left open through the concrete plinth.
for x0,x1 in [(402,458),(496,647),(686,850),(887,908)]:rect('NW_concrete_plinth','concrete',x0,144,x1,153,.25,4.8)
for x0,x1 in [(458,496),(647,686),(850,887)]:face('NW_recessed_ground_doors','glass',(x0,154),(x1,154),.25,3.5,.07)
face('NW_tall_atrium_glazing','glass',(402,150),(908,150),4.85,h-.35,.07)
face('NW_low_tube_glazing','glass',(151,150),(402,150),.25,lo-.3,.07)
for x in range(156,908,22):
 z1=lo-.25 if x<402 else h-.25;face('NW_glazing_vertical_frames','frame',(x,149),(x,151),.25,z1,.11)
for z in [1.7,3.3,4.8,6.4,8,9.6,11.2,12.8,14.4,16,17.6,19.2]:
 face('NW_glazing_horizontal_frames','frame',(402 if z>=lo else 151,149),(908,149),z,z+.075,.095)
# Tall atrium white columns behind the exterior glazing, visible in source06.
for x in range(428,910,60):rect('atrium_tall_concrete_columns','pale',x,171,x+5,176,.25,h-.3)
# West outer DiscoveryLab wall: large gallery wall and separately placed window fields.
for y0,y1 in [(150,228),(318,384),(466,585)]:rect('DiscoveryLab_west_concrete_wall','concrete',150,y0,157,y1,.24,lo-.25)
for y0,y1 in [(228,318),(384,466)]:
 face('DiscoveryLab_west_windows','glass',(153,y0),(153,y1),2.2,9.0,.07)
 face('DiscoveryLab_window_sill','concrete',(153,y0),(153,y1),.24,2.2,.35);face('DiscoveryLab_window_header','concrete',(153,y0),(153,y1),9,lo-.2,.35)
 for yy in range(y0,y1,16):face('DiscoveryLab_window_mullions','frame',(151,yy),(155,yy),2.2,9,.08)
# Actual clipped metro-side entrance is a separate glazed face; no solid wall plugs the Tube.
for j in [2,3]:
 a,b=Vector(ring[j]),Vector(ring[(j+1)%len(ring)]);P('metro_recess_glazing','glass').wall(a,b,.24,lo-.25,.07);length=(b-a).length;nn=max(2,int(length/2.5))
 for k in range(nn+1):
  q=a+(b-a)*k/nn;P('metro_recess_vertical_frames','frame').box(q.x,q.y,(lo+.24)/2,.10,.10,lo-.24)
 for z in [2,3.8,5.6,7.4,9.2,11]:P('metro_recess_horizontal_frames','frame').wall(a,b,z,z+.07,.11)
# Southeast back-of-house and east BlackBox faces: individually authored large bays/solid sections.
for y0,y1 in [(154,316),(538,895)]:rect('east_blackbox_service_wall','concrete',901,y0,909,y1,.24,h-.2)
face('east_blackbox_tall_glazed_bay','glass',(905,316),(905,538),.25,h-.2,.075)
for yy in range(324,538,21):face('east_tall_glazing_frames','frame',(903,yy),(907,yy),.25,h-.2,.1)
for z in range(2,21,2):face('east_tall_horizontal_frames','frame',(904,316),(904,538),z,z+.09,.12)
for x0,x1 in [(410,460),(564,636),(733,816),(887,907)]:rect('SE_service_concrete_piers','concrete',x0,889,x1,899,.25,h-.3)
for x0,x1 in [(460,564),(636,733),(816,887)]:
 face('SE_service_dark_bays','glass',(x0,894),(x1,894),3.0,13.2,.08)
 face('SE_service_bay_sill','concrete',(x0,894),(x1,894),.25,3,.5);face('SE_service_bay_header','concrete',(x0,894),(x1,894),13.2,h-.3,.5)
 for x in range(x0,x1,18):face('SE_service_window_frames','frame',(x,892),(x,896),3,13.2,.1)
# Roof-terrace elevation between lab and high theatre: asymmetric piers, deeply recessed openings.
for a,b in [(154,250),(312,393),(469,625),(710,888)]:rect('terrace_concrete_wall_piers','concrete',404,a,410,b,lo,h-.2)
for a,b in [(250,312),(393,469),(625,710)]:
 face('terrace_recessed_glazed_doors','glass',(409,a),(409,b),lo+.15,h-1.0,.07)
 face('terrace_opening_lintel','concrete',(406,a),(406,b),h-1,h-.2,.65)
 for yy in range(a,b,13):face('terrace_door_mullions','frame',(407,yy),(411,yy),lo+.15,h-1,.09)
# Low terrace over DiscoveryLab with photo-supported planted edge and glass balustrade.
terr=[(237,270),(391,270),(391,554),(237,554)]
rect('DiscoveryLab_rooftop_terrace_paving','pale',237,270,391,554,lo+.13,lo+.23)
rect('terrace_long_planter_earth','soil',237,278,263,549,lo+.24,lo+.62);rect('terrace_planted_strip','grass',239,280,261,547,lo+.62,lo+.76)
rect('terrace_end_planter','grass',264,526,381,548,lo+.23,lo+.67)
for a,b in [((237,270),(237,554)),((237,554),(391,554)),((237,270),(391,270))]:
 face('terrace_glass_balustrade','glass',a,b,lo+.3,lo+1.4,.05);face('terrace_top_handrail','frame',a,b,lo+1.4,lo+1.45,.055)
# Spiral stair found atplan~(281,600); separate open-top round enclosure fromthe ovalstagevolume.
ellipse('DiscoveryLab_circular_stair_turret','pale',281,600,4.1,4.1,lo,19.0,.22,N=80)
for i in range(27):
 aa=2*math.pi*i/27;c=xy(281,600);q=c+ux*2.2*math.cos(aa)+vy*2.2*math.sin(aa);P('stair_turret_visible_treads','concrete').box(q.x,q.y,lo+.2+i*.24,2.6,.55,.16,ang+aa)
# Mainstage upper OPEN oval enclosure, recessed inner roof and transverse steelbeams.
ellipse('upper_stage_oval_wall','pale',560,645,22.0,20.8,h+.2,H['ovalTop'],.32)
ellipse('upper_stage_recessed_inner_roof','roof',560,645,21.6,20.4,H['upperRecessedRoof']-.18,H['upperRecessedRoof'])
ellipse('upper_stage_oval_top_cap','pale',560,645,22.05,20.85,H['ovalTop'],H['ovalTop']+.12,.45)
for i in range(200):
 aa=2*math.pi*i/200;c=xy(560,645);q=c+ux*22.025*math.cos(aa)+vy*20.825*math.sin(aa);P('oval_vertical_cladding_seams','concrete').box(q.x,q.y,(h+.2+H['ovalTop'])/2,.016,.025,H['ovalTop']-h-.2,ang+aa)
for d in [-16,-12,-8,-4,0,4,8,12,16]:
 half=22*math.sqrt(1-(d/20.8)**2);c=xy(560,645)+vy*d;P('open_oval_visible_transverse_roof_beams','pale').box(c.x,c.y,29.7,half*2,.24,.48,ang)
# Small dark vent onthe exposed ovalwall,as completedaerial/roofphoto show.
c=xy(560,645)+ux*(-21.96);P('oval_exterior_small_rectangular_vent','reveal').box(c.x,c.y,26.2,.08,4.2,1.6,ang)
# Lower incomplete auditorium arc, distinctfromupper oval; shallow exposedconcrete roofrim.
ellipse('lower_auditorium_roof_arc','pale',560,489,22.7,23.5,h+.25,H['lowerArc'],.30,start=math.pi,end=2*math.pi,N=80)
rect('lower_auditorium_rectangular_roof','pale',411,483,706,580,h+.25,h+.5)
# Tube: a genuine80m hollow rolledellipse, axis individually aligned to floorplan.
a,b=[Vector(x) for x in D['tube']['endpoints']];axis=(b-a).normalized();mid=(a+b)/2;length=min(80,(b-a).length);a=mid-axis*length/2;b=mid+axis*length/2;side=Vector((-axis.y,axis.x));roll=math.radians(D['tube']['rollDegrees']);rx=3.6;rz=6.0;zc=4.4;wall=.24
N=128
def tubept(center,t,r0,r1):
 xx=r0*math.cos(t);zz=r1*math.sin(t);ss=xx*math.cos(roll)-zz*math.sin(roll);z=zc+xx*math.sin(roll)+zz*math.cos(roll);q=center+side*ss;return(q.x,q.y,z)
# Oneclosedquadprism perradialsegment; woodinnerwallandpalerouteredges.
mesh=P('rolled_elliptical_Tube_shell','wood')
mesh.v=[tubept(c,2*math.pi*i/N,r0,r1) for c in [a,b] for r0,r1 in [(rx+wall,rz+wall),(rx,rz)] for i in range(N)]
for i in range(N):
 j=(i+1)%N;mesh.f += [(i,j,2*N+j,2*N+i),(N+i,3*N+i,3*N+j,N+j),(i,N+i,N+j,j),(2*N+i,2*N+j,3*N+j,3*N+i)]
# Continuous closed elliptical rib rings, avoiding disconnected tangent-box artifacts.
for j in range(121):
 center=a+axis*length*j/120;mesh=P('Tube_fine_wood_section_ribs','woodlight');q=len(mesh.v);nr=96
 mesh.v += [tubept(cc,2*math.pi*i/nr,r0,r1) for cc in [center-axis*.03,center+axis*.03] for r0,r1 in [(rx,rz),(rx-.045,rz-.045)] for i in range(nr)]
 for i in range(nr):
  k=(i+1)%nr;mesh.f += [tuple(q+v for v in f) for f in [(i,k,2*nr+k,2*nr+i),(nr+i,3*nr+i,3*nr+k,nr+k),(i,nr+i,nr+k,k),(2*nr+i,2*nr+k,3*nr+k,3*nr+i)]]
P('Tube_level_walkway','floor').wall(a,b,.25,.39,5.5)
# Atrium: actual stepped circulation behindtallfrontglass, independentofTube.
for j in range(55):
 x=430+j*7.7;rect('StepAtrium_rising_stair','pale',x,161,x+7.7,185,.24+j*.26,.24+(j+1)*.26)
# CurvedGateArc behindatrium haslargeopenarch, omitinteriorfinishdetail.
ellipse('GateArc_upper_curved_wall','concrete',580,470,22.8,26.5,12.3,h-.35,.5,start=math.pi,end=2*math.pi,N=80)
objs=[m.finish() for m in parts.values()]
# Photo-observed lateral Tube openings into the theatre: positions are estimated,
# genuine boolean voids rather than black disks painted on its wall.
for j,(along,z,radius) in enumerate([(20,7.0,2.0),(42,2.5,2.25),(61,6.0,1.7)]):
 pt=a+axis*along+side*3.5;bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=radius,depth=6,location=(pt.x,pt.y,z));cut=bpy.context.object;cut.name='temporary_Tube_lateral_aperture_'+str(j);cut.rotation_euler=Vector((side.x,side.y,0)).to_track_quat('Z','Y').to_euler()
 for ob in [o for o in objs if o.name.startswith(('LG_rolled_elliptical_Tube_shell','LG_Tube_fine_wood_section_ribs'))]:
  bpy.context.view_layer.objects.active=ob;mod=ob.modifiers.new('actual_lateral_opening_'+str(j),'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;bpy.ops.object.modifier_apply(modifier=mod.name)
 bpy.data.objects.remove(cut,do_unlink=True)

# Ensureno tinycrosssection undercutfalls below ground plane.
for o in objs:
 for vv in o.data.vertices:
  if vv.co.z<0:vv.co.z=0
 o['evidence']='Gansam/KIRA plan+sections andcompletedphotos';o['limits']='Unmeasured dimensions andundocumentedservicefacesremainestimated'
bpy.ops.object.select_all(action='DESELECT')
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(OUT/(D['id']+'.glb')),export_format='GLB',use_selection=True,export_yup=True,export_apply=True)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.50,.56,.61,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.65;scene.view_settings.view_transform='AgX'
light=bpy.data.lights.new('LG_review_sun','SUN');light.energy=3;ob=bpy.data.objects.new('LG_review_sun',light);scene.collection.objects.link(ob);ob.rotation_euler=(.5,-.4,-.6)
def camera(n,location,target,scale):
 c=bpy.data.cameras.new(n);o=bpy.data.objects.new(n,c);scene.collection.objects.link(o);o.location=location;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();c.type='ORTHO';c.ortho_scale=scale;c.clip_end=2000;return o
camera('NW_aerial_reference',(-190,125,92),(0,0,11),183)
camera('west_aerial_source_match',(-220,-45,105),(0,0,11),182)
camera('NW_atrium_front',(-130,155,30),(-2,7,10),165)
camera('SE_service_and_oval',(140,-150,105),(0,0,13),180)
camera('south_Tube_entrance',(-72,-123,22),(-22,-27,7),114)
camera('roof_layout',(0,0,240),(0,0,0),185)
for nm,at,looking in [('Tube_north_portal',a-axis*22,a+axis*20),('Tube_south_portal',b+axis*22,b-axis*20),('Tube_through_interior',a+axis*2,b-axis*2)]:
 ob=camera(nm,(at.x,at.y,5.4),(looking.x,looking.y,5.3),26);ob.data.type='PERSP';ob.data.lens=24 if nm=='Tube_through_interior' else 36
# Warm reviewlights inside the actualvoid; geometry/material exportedwithoutlights.
for j in range(5):
 pt=a+axis*(6+j*16);ld=bpy.data.lights.new('Tube_review_light_'+str(j),'AREA');ld.energy=180;ld.color=(1,.70,.38);ld.shape='DISK';ld.size=3;ob=bpy.data.objects.new(ld.name,ld);scene.collection.objects.link(ob);ob.location=(pt.x,pt.y,8.8)

scene.camera=bpy.data.objects['NW_aerial_reference']
for ar in bpy.context.screen.areas:
 if ar.type=='VIEW_3D':sp=ar.spaces.active;sp.shading.type='MATERIAL';sp.overlay.show_overlays=False;sp.region_3d.view_location=(0,0,11);sp.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion();sp.region_3d.view_distance=220;sp.clip_end=2000
bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'lg-art-center-seoul.blend'))
bundle={'siteId':D['siteId'],'sources':D['sources'],'assets':[{'id':D['id'],'nameKo':D['nameKo'],'file':D['id']+'.glb','blendSource':'lg-art-center-seoul.blend','coordinate':D['coordinate'],'category':'cultural','district':'강서구','footprintIds':[D['footprintId']],'supersedes':[D['oldId']],'referenceUrl':D['sources'][0]['url'],'components':[o.name for o in objs],'uncertainties':D['limits'],'minZoom':14}],'places':[{'id':'bespoke-lg-art-center-seoul','name':D['nameKo'],'subtitle':'튜브 · 타원형 상부 · 옥상정원','center':[D['coordinate']['lon'],D['coordinate']['lat']],'zoom':17,'source_url':D['sources'][0]['url']}],'recipeFiles':['authored-input.json']};(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n');print('LG_AUTHORED',len(objs),'components','Tube',length)
