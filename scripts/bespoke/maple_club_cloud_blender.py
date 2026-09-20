"""210/211 bespoke reconstruction; independently authored faces, roof volumes and junctions."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-club-cloud';D=json.loads((OUT/'authored-input.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
colors={'white':(.73,.73,.69,1),'warm':(.40,.41,.39,1),'graphite':(.245,.275,.275,1),'glass':(.095,.22,.26,1),'lounge_glass':(.13,.36,.42,1),'metal':(.42,.48,.49,1),'cap':(.77,.77,.71,1),'roof':(.19,.205,.20,1),'stone':(.265,.28,.265,1),'reveal':(.075,.09,.095,1),'paver':(.36,.35,.32,1)}
M={}
for n,c in colors.items():
 m=bpy.data.materials.new('ClubCloud_'+n);m.diffuse_color=c;m.use_nodes=True;shader=m.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=c;shader.inputs['Roughness'].default_value=.30 if 'glass' in n else .77;shader.inputs['Metallic'].default_value=.15 if 'glass' in n or n=='metal' else 0;M[n]=m
class Mesh:
 def __init__(self,n,mat):self.n=n;self.mat=mat;self.v=[];self.f=[]
 def prism(self,ring,z0,z1):
  pts=[Vector((x,y,0)) for x,y in ring];n=len(pts);start=len(self.v);self.v += [(v.x,v.y,z) for z in [z0,z1] for v in pts];tris=tessellate_polygon([pts]);idx={tuple(p):i for i,p in enumerate(pts)}
  for tr in tris:
   ids=[p if isinstance(p,int) else idx[tuple(p)] for p in tr];self.f += [tuple(start+i for i in reversed(ids)),tuple(start+n+i for i in ids)]
  self.f += [(start+i,start+(i+1)%n,start+(i+1)%n+n,start+i+n) for i in range(n)]
 def box(self,x,y,z,sx,sy,sz,angle=0):
  c,s=math.cos(angle),math.sin(angle);ring=[(x+a*c-b*s,y+a*s+b*c) for a,b in [(-sx/2,-sy/2),(sx/2,-sy/2),(sx/2,sy/2),(-sx/2,sy/2)]];self.prism(ring,z-sz/2,z+sz/2)
 def face(self,a,b,lo,hi,depth=.12,offset=.08):
  a=Vector(a);b=Vector(b);u=(b-a).normalized();normal=Vector((-u.y,u.x));ring=[tuple(a+normal*offset),tuple(b+normal*offset),tuple(b+normal*(offset+depth)),tuple(a+normal*(offset+depth))];self.prism(ring,lo,hi)
 def finish(self):
  mesh=bpy.data.meshes.new(self.n);mesh.from_pydata(self.v,[],self.f);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();o=bpy.data.objects.new(self.n,mesh);bpy.context.collection.objects.link(o);o.data.materials.append(M[self.mat]);return o
reference=D['assets'][0]['coordinate'];scene_parts=[];exported=[]
for A in D['assets']:
 dong=A['dong'];ring=A['ring'];top=A['top'];bodytop=top-4.6;parts={}
 def P(name,mat):
  key=(name,mat)
  if key not in parts:parts[key]=Mesh(str(dong)+'_'+name,mat)
  return parts[key]
 P('retained_numbered_plan_body','white').prism(ring,6.6,bodytop)
 center=sum((Vector(p) for p in ring),Vector((0,0)))/len(ring)
 lobby=[tuple(center+(Vector(p)-center)*.81) for p in ring];P('recessed_stone_pilotis_lobby','stone').prism(lobby,0,6.6)
 # Face programs differ for210 and211, including actual blank ends and different gray stacks.
 for edge,(aa,bb,program) in enumerate(zip(ring,ring[1:]+ring[:1],A['faces'])):
  a,b=Vector(aa),Vector(bb);v=b-a;length=v.length;point=lambda t:tuple(a+v*t)
  kind=program['kind'];P('lower_stone_face_'+str(edge),'stone').face(point(0),point(1),6.6,14.0,.08,.10)
  if kind=='observed-211-e4':
   for f0,f1,col in program['bands']:P('observed_e4_'+col+'_zone',col).face(point(f0),point(f1),6.6,bodytop,.08,.12)
   for f in program['frames']:P('e4_specific_zone_dividers','white').face(point(f-.11/length),point(f+.11/length),6.6,bodytop,.13,.21)
   # Source photograph has one broad pale field with small openings, followed by
   # four unequal graystacks and a darker rightgroup: no repeated pairedbay template.
   for floor in range(2,28):
    z=6.6+(floor-2)*(bodytop-6.6)/26
    for f0,f1,z0,z1,mulls in program['openings']:
     P('e4_source_mapped_reveals','reveal').face(point(f0-.025/length),point(f1+.025/length),z+z0-.03,z+z1+.03,.045,.205)
     P('e4_source_mapped_window_sizes','glass').face(point(f0),point(f1),z+z0,z+z1,.025,.252)
     for k in range(1,mulls+1):
      f=f0+(f1-f0)*k/(mulls+1);P('e4_window_mullions','metal').face(point(f-.025/length),point(f+.025/length),z+z0,z+z1,.035,.28)
    f0,f1=program['darkVentStrip'];P('e4_recessed_service_slot','reveal').face(point(f0),point(f1),z+.12,z+2.7,.025,.21)
    for k in range(3):P('e4_slot_louvers','graphite').face(point(f0),point(f1),z+.24+k*.16,z+.29+k*.16,.04,.25)
   P('e4_darkgroup_header','warm').face(point(0),point(.33),bodytop-1.8,bodytop,.08,.25)
  elif kind in ['observed-210-e1','observed-210-e2']:
   for floor in range(2,28):
    z=6.6+(floor-2)*(bodytop-6.6)/26
    for f0,f1 in program['columns']:
     P('e'+str(edge)+'_large_grid_window_reveals','reveal').face(point(f0),point(f1),z+.37,z+2.49,.035,.075)
     P('e'+str(edge)+'_large_grid_windows','glass').face(point(f0+.04/length),point(f1-.04/length),z+.43,z+2.43,.025,.115)
     mid=(f0+f1)/2;P('e'+str(edge)+'_fine_window_mullions','metal').face(point(mid-.035/length),point(mid+.035/length),z+.43,z+2.43,.025,.145)
  elif kind=='blank-slits':
   for t in program['slits']:
    P('end_wall_recess_strips','warm').face(point(t-.036),point(t+.036),6.6,bodytop,.035,.10)
    for floor in range(2,28):
     z=6.6+(floor-2)*(bodytop-6.6)/26
     P('end_wall_slit_windows','glass').face(point(t-.020),point(t+.020),z+.6,z+1.7,.04,.16)
   # Shallow vertical stone joints on broad blank wall; no borrowed window grid.
   for i in range(1,int(length/.8)):
    t=i*.8/length;P('fine_blank_wall_joints','warm').face(point(t-.0008),point(t+.0008),14,bodytop,.014,.015)
  else:
   bs=program['bounds']
   for j,(f0,f1) in enumerate(zip(bs,bs[1:])):
    span=f1-f0;zone='glass' if kind=='glazed' else program['zones'][j]
    P('individual_face_'+str(edge)+'_'+zone,zone).face(point(f0+.004),point(f1-.004),6.6,bodytop,.08,.12)
    # Large structural piers frame complete vertically differentiated bays.
    fw=.28/length;P('projecting_ivory_vertical_frames','white').face(point(max(0,f0-fw)),point(min(1,f0+fw)),6.6,bodytop,.24,.15)
    for floor in range(2,28):
     z=6.6+(floor-2)*(bodytop-6.6)/26
     if kind=='glazed':
      P('highway_fine_spandrels','graphite').face(point(f0+.005),point(f1-.005),z,z+.48,.06,.25)
      mid=(f0+f1)/2;P('highway_mullions','metal').face(point(mid-.035/length),point(mid+.035/length),z+.48,z+2.8,.07,.27)
     else:
      opening=program['openings'][j]
      for k in [0,2]:
       w0=f0+span*opening[k];w1=f0+span*opening[k+1]
       P('dark_inset_window_reveals','reveal').face(point(w0-.065/length),point(w1+.065/length),z+.40,z+2.48,.06,.24)
       P('face_'+str(edge)+'_unequal_windows','glass').face(point(w0),point(w1),z+.49,z+2.40,.05,.31)
       if (w1-w0)*length>1.6:
        mid=(w0+w1)/2;P('window_mullions_and_sills','metal').face(point(mid-.03/length),point(mid+.03/length),z+.49,z+2.40,.05,.38)
       P('window_mullions_and_sills','white').face(point(w0-.065/length),point(w1+.065/length),z+.36,z+.46,.14,.24)
      P('thin_floor_joints','white' if zone=='white' else zone).face(point(f0+.004),point(f1-.004),z,z+.12,.045,.21)
   P('projecting_ivory_vertical_frames','white').face(point(.99),point(1),6.6,bodytop,.24,.15)
  # Heavy entrance piers are part of actual base mass, not free-floating thin sticks.
  for t in [.10,.90]:
   pp=point(t);P('ground_stone_portal_piers','stone').box(*pp,3.3,.95,1.25,6.6,math.atan2(v.y,v.x))
  if length>23:
   P('entrance_canopy_'+str(edge),'cap').face(point(.40),point(.61),4.9,5.3,1.5,.2)
 # The lounge is a genuinely separate glazed top volume with rounded corner returns.
 P('Club_Cloud_glazed_roof_lounge','lounge_glass').prism(A['loungeRing'],bodytop,top-.45)
 P('Club_Cloud_deep_projecting_canopy','cap').prism(A['canopyRing'],top-.45,top+.18)
 P('Club_Cloud_canopy_shadow_band','graphite').prism(A['canopyRing'],top-.48,top-.36)
 # Dark inset roof surface, opaque equipment zones and two distinct enclosures.
 inset=[tuple(center+(Vector(p)-center)*.96) for p in A['loungeRing']]
 P('inset_service_roof','roof').prism(inset,top+.18,top+.22)
 lr=A['loungeRing']
 # These rings may be CCW/CW; glass frames are thin volumetric rods.
 for a,b in zip(lr,lr[1:]+lr[:1]):
  a,b=Vector(a),Vector(b);v=b-a;le=v.length
  for j in range(max(1,int(le/1.5))):
   p=a+v*(j/max(1,int(le/1.5)));P('lounge_fine_vertical_mullions','metal').box(p.x,p.y,(bodytop+top-.45)/2,.07,.07,top-.45-bodytop)
  if le>.15:
   mid=(a+b)/2;angle=math.atan2(v.y,v.x)
   P('lounge_horizontal_transoms','metal').box(mid.x,mid.y,bodytop+1.9,le,.07,.075,angle)
   P('roof_perimeter_rail','metal').box(mid.x,mid.y,top+.77,le,.045,.045,angle)
   for j in range(max(1,int(le/2.1))):
    p=a+v*(j/max(1,int(le/2.1)));P('roof_perimeter_rail','metal').box(p.x,p.y,top+.48,.045,.045,.55)
 for i,(x,y) in enumerate(A['roofPlantCenters']):
  spec=A['roofPlants'][i];w,d,h=spec['width'],spec['depth'],spec['height'];angle=math.radians(spec['angleDeg'])
  P('distinct_roof_plant_'+str(i+1),'white').box(x,y,top+h/2,w,d,h,angle)
  P('plant_cap_'+str(i+1),'cap').box(x,y,top+h+.06,w+.25,d+.25,.12,angle)
  if spec.get('steppedAnnex'):P('210_stepped_plant_annex','white').box(x+2.4,y+2.2,top+1.05,4.4,3.2,2.1,angle)
  u=Vector((math.cos(angle),math.sin(angle)));v=Vector((-u.y,u.x));a=Vector((x,y))+v*(-d/2-.02)-u*w*.31;b=Vector((x,y))+v*(-d/2-.02)+u*w*.31
  P('plant_vent_'+str(i+1),'graphite').face(tuple(a),tuple(b),top+.7,top+h-.6,.05,.02)
  for k in range(7):P('plant_louvers_'+str(i+1),'metal').face(tuple(a),tuple(b),top+.8+k*.35,top+.85+k*.35,.045,.08)
 # 210owns theconnector, preserving existing source ownership and exact geographic endpoint relation.
 if dong==210:
  bridge=D['bridgeRing'];P('210_211_skybridge_lower_box','cap').prism(bridge,bodytop-.30,bodytop+.10);P('210_211_skybridge_continuous_glazing','lounge_glass').prism(bridge,bodytop+.1,top-.43);P('210_211_skybridge_canopy','cap').prism(bridge,top-.43,top+.16)
  for a,b in zip(bridge,bridge[1:]+bridge[:1]):
   a,b=Vector(a),Vector(b);v=b-a;le=v.length;mid=(a+b)/2;ang=math.atan2(v.y,v.x)
   for j in range(max(1,int(le/1.45))):
    p=a+v*(j/max(1,int(le/1.45)));P('skybridge_mullions','metal').box(p.x,p.y,(bodytop+top)/2,.08,.08,top-bodytop-.3)
   P('skybridge_horizontal_transom','metal').box(mid.x,mid.y,bodytop+1.85,le,.09,.085,ang)
 objs=[p.finish() for p in parts.values()]
 for o in objs:o['site']='Maple Xi Club Cloud';o['dong']=dong;o['basis']='Completed Xi magazine2025 photos; retained numbered plan and geographic anchor';o['uncertainty']='facade proportions, plant sizes and metric heights estimated'
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True)
 bpy.context.view_layer.objects.active=objs[0]
 bpy.ops.export_scene.gltf(filepath=str(OUT/(A['id']+'.glb')),export_format='GLB',use_selection=True,export_yup=True,export_apply=True)
 export={'id':A['id'],'nameKo':'메이플자이 '+str(dong)+'동 · 클럽클라우드','file':A['id']+'.glb','blendSource':'maple-club-cloud.blend','coordinate':A['coordinate'],'category':'residential-apartment','footprintIds':[],'supersedes':[A['oldId']],'referenceUrl':'https://beyondapartment.kr/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja','components':[o.name for o in objs],'uncertainties':D['uncertainties'],'minZoom':15}
 exported.append(export)
 dx=(A['coordinate']['lon']-reference['lon'])*111320*math.cos(math.radians(reference['lat']));dy=(A['coordinate']['lat']-reference['lat'])*111320
 for o in objs:o.location+=Vector((dx,dy,0));scene_parts.append(o)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=20;scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.4,.46,.52,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7;scene.view_settings.view_transform='AgX'
sun=bpy.data.lights.new('Review_sun','SUN');sun.energy=3;ob=bpy.data.objects.new('Review_sun',sun);scene.collection.objects.link(ob);ob.rotation_euler=(.45,-.55,-.6)
for name,loc,target,scale in [('Courtyard',(-170,-230,145),(10,2,47),168),('Highway',(190,-150,140),(10,2,48),170),('Roof_close',(140,-100,160),(10,2,88),118),('Under_bridge',(-5,-30,18),(5,5,89),None),('Source2_east',(165,-60,130),(25,14,80),None)]:
 c=bpy.data.cameras.new(name);c.clip_end=5000;o=bpy.data.objects.new(name,c);scene.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
 if scale:c.type='ORTHO';c.ortho_scale=scale
 else:c.type='PERSP';c.lens=52 if name=='Source2_east' else 20
scene.camera=bpy.data.objects['Courtyard'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-club-cloud.blend'))
bundle={'siteId':'maple-club-cloud','sources':D['sources'],'assets':exported,'places':[{'id':'bespoke-maple-club-cloud','name':'메이플자이 클럽클라우드','subtitle':'210·211동 개별 재제작 · 29층 연결교','center':[127.01415,37.51274],'zoom':17,'source_url':exported[0]['referenceUrl']}],'recipeFiles':['authored-input.json']};(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
print('MAPLE_BESPOKE_PAIR_EXPORTED',len(scene_parts),'named editable components')
