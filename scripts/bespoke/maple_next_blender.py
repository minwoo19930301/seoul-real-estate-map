"""Individual208/209/212/213 volumes and evidence-authored edge programs via liveMCP."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-next-towers';D=json.loads((OUT/'authored-input.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
colors={'white':(.76,.75,.70,1),'warm':(.43,.44,.43,1),'graphite':(.155,.20,.20,1),'glass':(.075,.18,.20,1),'metal':(.54,.56,.53,1),'roof':(.31,.32,.29,1),'stone':(.32,.31,.27,1),'reveal':(.055,.072,.07,1),'solar':(.035,.07,.105,1),'wood':(.19,.105,.058,1),'joint':(.23,.25,.23,1)};M={}
for n,c in colors.items():
 m=bpy.data.materials.new('MapleNext_'+n);m.diffuse_color=c;m.use_nodes=True;s=m.node_tree.nodes.get('Principled BSDF');s.inputs['Base Color'].default_value=c;s.inputs['Roughness'].default_value=.32 if n in ['glass','solar'] else .72;M[n]=m
class Mesh:
 def __init__(self,n,mat):self.n=n;self.mat=mat;self.v=[];self.f=[]
 def prism(self,ring,z0,z1):
  pts=[Vector((x,y,0)) for x,y in ring];n=len(pts);start=len(self.v);self.v += [(v.x,v.y,z) for z in [z0,z1] for v in pts];idx={tuple(p):i for i,p in enumerate(pts)}
  for tr in tessellate_polygon([pts]):
   ids=[p if isinstance(p,int) else idx[tuple(p)] for p in tr];self.f += [tuple(start+i for i in reversed(ids)),tuple(start+n+i for i in ids)]
  self.f += [(start+i,start+(i+1)%n,start+(i+1)%n+n,start+i+n) for i in range(n)]
 def box(self,x,y,z,w,d,h,angle=0):
  c,s=math.cos(angle),math.sin(angle);self.prism([(x+a*c-b*s,y+a*s+b*c) for a,b in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]],z-h/2,z+h/2)
 def face(self,a,b,z0,z1,depth=.08,offset=.08):
  a,b=Vector(a),Vector(b);u=(b-a).normalized();v=Vector((-u.y,u.x));self.prism([tuple(a+v*offset),tuple(b+v*offset),tuple(b+v*(offset+depth)),tuple(a+v*(offset+depth))],z0,z1)
 def tilted(self,x,y,z,w,d,t,angle,tilt):
  # Six closedfaces, panel plane rising along local depth.
  c,s=math.cos(angle),math.sin(angle);q=len(self.v)
  for dz in [-t/2,t/2]:
   for a,b in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]:self.v.append((x+a*c-b*s,y+a*s+b*c,z+b*math.tan(tilt)+dz))
  self.f += [tuple(q+i for i in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]]
 def finish(self):
  me=bpy.data.meshes.new(self.n);me.from_pydata(self.v,[],self.f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new(self.n,me);bpy.context.collection.objects.link(o);me.materials.append(M[self.mat]);return o
anchor=D['assets'][0]['coordinate'];exports=[];centers={};assetobjects={}
for A in D['assets']:
 dong=A['dong'];ring=A['ring'];V=[Vector(p) for p in ring];roof=A['roof'];heights=roof['heights'];base=A['baseHeight'];parts={}
 def P(n,m):
  key=(n,m)
  if key not in parts:parts[key]=Mesh(str(dong)+'_'+n,m)
  return parts[key]
 if len(ring)==4:wings=[ring];edgeheights=heights*4
 else:wings=[[ring[i] for i in [0,1,2,5]],[ring[i] for i in [2,3,4,5]]];edgeheights=[heights[0],heights[0],heights[1],heights[1],heights[1],heights[0]]
 for k,(wing,h) in enumerate(zip(wings,heights)):
  P('wing_'+str(k)+'_observed_massing','white').prism(wing,base,h)
  center=sum((Vector(p) for p in wing),Vector((0,0)))/len(wing);inset=[tuple(center+(Vector(p)-center)*.82) for p in wing];
  if dong!=208:P('unverified_solid_ground_mass','stone').prism(wing,0,base)
  else:P('208_deep_recessed_lobby_mass','stone').prism(inset,0,base)
  P('wing_'+str(k)+'_roof_slab','white').prism(wing,h-.16,h+.22)
  rr=[tuple(center+(Vector(p)-center)*.95) for p in wing];P('wing_'+str(k)+'_service_roof','roof').prism(rr,h+.22,h+.25)
  for aa,bb in zip(wing,wing[1:]+wing[:1]):
   a,b=Vector(aa),Vector(bb);v=b-a;le=v.length;mid=(a+b)/2;ang=math.atan2(v.y,v.x)
   P('wing_'+str(k)+'_roof_rail','metal').box(mid.x,mid.y,h+.98,le,.045,.06,ang)
   for j in range(int(le/1.8)+1):
    p=a+v*j/max(1,int(le/1.8));P('wing_'+str(k)+'_roof_rail','metal').box(p.x,p.y,h+.60,.045,.045,.75)
 # Individual outsideedges each have explicitlyrecorded window intervals.
 for e,(a,b,prog,h) in enumerate(zip(V,V[1:]+V[:1],A['faces'],edgeheights)):
  vec=b-a;le=vec.length;u=vec.normalized();normal=Vector((-u.y,u.x));pt=lambda f:tuple(a+vec*f);ang=math.atan2(vec.y,vec.x);name='e'+str(e)
  P(name+'_lower_stone_field','stone').face(pt(0),pt(1),base,A['stoneTop'],.07,.035)
  for lo,hi,col in prog['bands']:P(name+'_paint_zone_'+col,col).face(pt(lo),pt(hi),A['stoneTop'],h-.10,.075,.07)
  rows=round((h-base)/3.08);step=(h-base)/rows
  for f in range(rows):
   z=base+f*step
   for j,(f0,f1,hf) in enumerate(prog['windows']):
    lo=z+(step-step*hf)*.48;hi=lo+step*hf
    P(name+'_individually_sized_reveals','reveal').face(pt(f0),pt(f1),lo-.025,hi+.025,.04,.16)
    P(name+'_window_glass','glass').face(pt(f0+.035/le),pt(f1-.035/le),lo+.025,hi-.025,.025,.205)
    if (f1-f0)*le>1.30:
     middle=(f0+f1)/2;P(name+'_window_center_frames','metal').face(pt(middle-.026/le),pt(middle+.026/le),lo+.025,hi-.025,.04,.235)
   if prog['kind']=='curtain-look':
    P(name+'_curtainlook_spandrels','graphite').face(pt(.014),pt(.986),z,z+.34,.035,.20)
  if prog['kind']=='curtain-look':
   # Thin structural piers differentiate a framed residential wall from a glassbox.
   for lo,hi,_ in prog['windows']:
    for f in [lo-.018,hi+.018]:P(name+'_curtainlook_vertical_bars','metal').face(pt(max(0,f-.055/le)),pt(min(1,f+.055/le)),A['stoneTop'],h,.20,.25)
  if prog['kind']=='blank':
   for j in range(1,int(le/1.3)):
    f=j*1.3/le;P(name+'_blank_wall_joints','warm').face(pt(f-.0005),pt(f+.0005),A['stoneTop'],h-.2,.008,.006)
  # Stonebase articulation is separate from upper window field.
  for j in range(1,int(le/1.6)):
   f=j*1.6/le;P(name+'_stone_vertical_joints','joint').face(pt(f-.009/le),pt(f+.009/le),base,A['stoneTop'],.01,.11)
  for z in [base+.8,base+2.4,base+4.0,base+5.6]:
   if z<A['stoneTop']:P(name+'_stone_courses','joint').face(pt(0),pt(1),z,z+.025,.01,.115)
  # No copiedcornerlegs atobscured bases; conservativemass above isexplicitlyunverified.
 # Photo-specific rooftop screens only208/212, never used on209/213.
 for e in roof.get('screenEdges',[]):
  a,b=V[e],V[(e+1)%len(V)];v=b-a;le=v.length;h=edgeheights[e];ang=math.atan2(v.y,v.x);mid=(a+b)/2
  P('crown_screen_e'+str(e)+'_sill','white').box(mid.x,mid.y,h+.43,le+.1,.40,.42,ang)
  count=max(2,int(le/.43))
  for j in range(count+1):
   p=a+v*j/count;P('crown_screen_e'+str(e)+'_individual_fins','metal').box(p.x,p.y,h+.35+roof['screenHeight']/2,.11,.35,roof['screenHeight'],ang)
  P('crown_screen_e'+str(e)+'_toprail','white').box(mid.x,mid.y,h+roof['screenHeight']+.37,le+.1,.40,.10,ang)
 if 'darkHeaderEdge' in roof:
  e=roof['darkHeaderEdge'];a,b=V[e],V[(e+1)%len(V)];h=edgeheights[e]
  P('highway_crown_dark_header','graphite').face(tuple(a),tuple(b),h,h+roof['screenHeight'],.15,.10)
  for j in range(1,int((b-a).length/1.7)):
   f=j*1.7/(b-a).length;P('highway_crown_header_mullions','metal').face(tuple(a+(b-a)*(f-.02/(b-a).length)),tuple(a+(b-a)*(f+.02/(b-a).length)),h,h+roof['screenHeight'],.035,.27)
 def locate(spec):
  if 'center' in spec:return Vector(spec['center']),math.radians(spec['angle']),heights[0]
  k=spec['wing'];w=[Vector(p) for p in wings[k]]
  # Longdirection from outside shortend towardinnerdiagonal; place with explicitalongfraction.
  if k==0:start=(V[0]+V[1])/2;end=(V[2]+V[5])/2
  else:start=(V[3]+V[4])/2;end=(V[2]+V[5])/2
  v=end-start;p=start+v*spec['along'];return p,math.atan2(v.y,v.x),heights[k]
 for i,spec in enumerate(roof['plants']):
  p,ang,h=locate(spec);w,d,z=spec['size'];P('roof_service_volume_'+str(i),'white').box(p.x,p.y,h+z/2,w,d,z,ang);P('roof_service_cap_'+str(i),'white').box(p.x,p.y,h+z+.07,w+.18,d+.18,.14,ang)
  u=Vector((math.cos(ang),math.sin(ang)));v=Vector((-u.y,u.x))
  # Placeallpanels withverifiedoutwardnormal; old -v helperhadturned theminward.
  for j,(side,offset,ww,bottom,hh) in enumerate(spec['apertures']):
   axis,normal,reach=(u,v,d/2) if side=='+v' else (-u,-v,d/2) if side=='-v' else (-v,u,w/2) if side=='+u' else (v,-u,w/2)
   mid=p+normal*(reach+.012)+axis*offset;aa=mid-axis*ww/2;bb=mid+axis*ww/2
   P('roof_room_'+str(i)+'_aperture_'+str(j),'reveal').face(tuple(aa),tuple(bb),h+bottom,h+bottom+hh,.035,.008)
   # Thin projecting top/sill reveals readasrecessedopenings atmapscale.
   P('roof_room_'+str(i)+'_aperture_reveals','warm').face(tuple(aa-axis*.07),tuple(bb+axis*.07),h+bottom-.065,h+bottom,.065,.035)
   P('roof_room_'+str(i)+'_aperture_reveals','warm').face(tuple(aa-axis*.07),tuple(bb+axis*.07),h+bottom+hh,h+bottom+hh+.065,.065,.035)
   if ww>1.5:
    for k in range(max(1,int(hh/.18))):P('roof_room_'+str(i)+'_visible_vent_louvers','metal').face(tuple(aa),tuple(bb),h+bottom+.10+k*.18,h+bottom+.13+k*.18,.04,.048)
  capheight=spec['capStep'];side=spec['capSide'];mid=p+v*(d/2-.13)*(1 if side=='+v' else -1)
  P('roof_room_'+str(i)+'_individual_raised_cap_edge','white').box(mid.x,mid.y,h+z+.14+capheight/2,w+.18,.32,capheight,ang)
 for i,spec in enumerate(roof['panels']):
  p,ang,h=locate(spec);w,d=spec['size'];tilt=math.radians(spec.get('tilt',11));u=Vector((math.cos(ang),math.sin(ang)));v=Vector((-u.y,u.x))
  # Shift panel strips towardedge away fromplantcore, as aerial roofs show.
  if 'wing' in spec:p+=v*(2.1 if spec['wing']==0 else -2.0)
  z=h+1.0+d/2*math.tan(tilt);cols=max(2,round(w/1.10));rows=max(2,round(d/1.5))
  for x in range(cols):
   for y in range(rows):
    aa=-w/2+(x+.5)*w/cols;bb=-d/2+(y+.5)*d/rows;q=p+u*aa+v*bb
    P('individual_roof_panel_array_'+str(i),'solar').tilted(q.x,q.y,z+bb*math.tan(tilt),w/cols-.05,d/rows-.045,.09,ang,tilt)
  for f in [-.42,.42]:
   q=p+u*w*f;P('panel_array_supports_'+str(i),'metal').box(q.x,q.y,h+.6,.11,d,.12,ang)
 #208's verified deepstoneportal andslats, withorientationinference clearlyrecorded.
 if A['entry']:
  E=A['entry'];e=E['edge'];a,b=V[e],V[(e+1)%len(V)];v=(b-a).normalized();n=Vector((-v.y,v.x));p=a+(b-a)*E['fraction'];w=E['width'];hh=E['height'];ang=math.atan2(v.y,v.x)
  for f in [-w/2,w/2]:
   q=p+v*f+n*.8;P('208_numbered_entry_thick_stone_jambs','stone').box(q.x,q.y,hh/2,.95,3.3,hh,ang)
  q=p+n*.8;P('208_numbered_entry_lintel','stone').box(q.x,q.y,hh+.30,w+1.0,3.3,.60,ang)
  # The numberedphoto shows a thickcentraldivider plus a broadforeground slatscreen.
  q=p+v*.12+n*.55;P('208_entry_central_stone_divider','stone').box(q.x,q.y,hh/2,1.25,2.9,hh,ang)
  for j in range(9):
   q=p+v*(1.05+j*.15)+n*2.05;P('208_entry_brown_vertical_slats','wood').box(q.x,q.y,hh/2,.095,.26,hh,ang)
  for j in range(33):
   q=p+v*(-w*.45+j*w*.90/32)+n*.6;P('208_entry_ceiling_louvers','wood').box(q.x,q.y,hh-.08,.045,2.9,.16,ang)
  for f in [-1.6,2.5]:
   q=p+v*f+n*.7;P('208_entry_ceiling_light_strips','white').box(q.x,q.y,hh-.18,.13,2.7,.05,ang)
  q=p-v*1.65+n*(-1.15);P('208_entry_mailbox_bank','metal').box(q.x,q.y,1.8,2.0,.16,1.8,ang)
  for j in range(7):
   a0=q-v*1.0;b0=q+v*1.0;P('208_entry_mailbox_joints','joint').face(tuple(a0),tuple(b0),.90+j*.26,.92+j*.26,.015,.09)
  for j in range(1,4):
   a0=q+v*(-1.0+j*.50);P('208_entry_mailbox_joints','joint').face(tuple(a0-v*.007),tuple(a0+v*.007),.90,2.70,.015,.09)
 objs=[m.finish() for m in parts.values()];assetobjects[dong]=objs
 for o in objs:o['dong']=dong;o['basis']='Numbered Xi plan, opposing2025aerials andcompletedphotos';o['limits']='Photo-derived dimensions; floorcount andhiddenfaces unverified'
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True)
 bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(OUT/(A['id']+'.glb')),export_format='GLB',use_selection=True,export_yup=True,export_apply=True)
 exports.append({'id':A['id'],'nameKo':'메이플자이 '+str(dong)+'동','file':A['id']+'.glb','blendSource':'maple-next-towers.blend','coordinate':A['coordinate'],'category':'residential-apartment','footprintIds':[],'supersedes':[A['oldId']],'referenceUrl':D['sources'][1]['url'],'components':[o.name for o in objs],'uncertainties':D['uncertainties'],'minZoom':15})
 dx=(A['coordinate']['lon']-anchor['lon'])*111320*math.cos(math.radians(anchor['lat']));dy=(A['coordinate']['lat']-anchor['lat'])*111320
 for o in objs:o.location+=Vector((dx,dy,0))
 centers[dong]=Vector((dx,dy,max(heights)/2))
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=20;scene.render.resolution_x=1400;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.43,.48,.52,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8;scene.view_settings.view_transform='AgX'
light=bpy.data.lights.new('Review_sun','SUN');light.energy=3;o=bpy.data.objects.new('Review_sun',light);scene.collection.objects.link(o);o.rotation_euler=(.4,-.55,-.6)
for dong in [208,209,212,213]:
 for label,offset in [('east',Vector((180,0,90))),('west',Vector((-140,-170,100))),('roof',Vector((140,0,110)))]:
  name=f'{dong}_{label}';c=bpy.data.cameras.new(name);c.type='ORTHO';c.ortho_scale=157 if label!='roof' else 78;c.clip_end=4000;o=bpy.data.objects.new(name,c);scene.collection.objects.link(o);target=centers[dong].copy()
  if label=='roof':target.z=centers[dong].z*2-4
  o.location=target+offset;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
scene.camera=bpy.data.objects['208_east'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-next-towers.blend'))
B={'siteId':D['siteId'],'sources':D['sources'],'assets':exports,'places':[{'id':'bespoke-maple-next-towers','name':'메이플자이 동별 외관','subtitle':'208·209·212·213동','center':[127.0142,37.5127],'zoom':17,'source_url':D['sources'][1]['url']}],'recipeFiles':['authored-input.json']};(OUT/'bundle.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n');print('MAPLE_NEXT_AUTHORED',len(exports),'assets',sum(len(x) for x in assetobjects.values()),'namedcomponents')
