"""Photo/plan authored Seokjojeon WEST wing; execute through dedicated Blender MCP.
Only flat Corinthian portico belongs here. No east-wing pediment or palace scenery.
"""
import bpy,math,json,hashlib,bmesh
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'data/model-source/bespoke/mmca-deoksugung';OUT.mkdir(parents=True,exist_ok=True)
def input_file(name):
 p=OUT/name
 return p if p.exists() else ROOT/'modeling/bespoke/mmca-deoksugung'/name
R=json.loads(input_file('authored-input.json').read_text()); S=json.loads(input_file('source-footprint.json').read_text()); angle=R['axis']['angleRadians'];cs=math.cos(angle);sn=math.sin(angle)
def world(p):
 u,v,z=p;return (v*cs-u*sn,u*cs+v*sn,z)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
 if not c.objects and not c.children:bpy.data.collections.remove(c)
def collection(name):
 c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c
COL=collection('MMCA_SEOKJOJEON_WEST_ONLY'); REVIEW=collection('REVIEW_ONLY_NOT_EXPORTED')
def mat(name,c,rough=.75,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True;n=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');n.inputs['Base Color'].default_value=(*c,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal;return m
MAT=[mat('warm grey granite ashlar',(.57,.55,.49)),mat('slightly lighter cut stone',(.66,.64,.57)),mat('recessed masonry joint',(.39,.38,.34)),mat('sculpted capital and cornice stone',(.64,.62,.55)),mat('shadowed black bronze sash',(.055,.071,.069),.48,.25),mat('dark desaturated blue green glazing',(.10,.18,.20),.22,.32),mat('recessed doorway darkness',(.020,.030,.028)),mat('roof zinc grey',(.43,.46,.43),.58,.22),mat('provisional pale rooflight cover',(.59,.62,.59),.6,.08),mat('pale step nosing',(.66,.64,.59)),mat('gallery interior shade',(.14,.16,.15)),mat('review ground',(.31,.35,.33))]
class Mesh:
 def __init__(self,name):self.name=name;self.v=[];self.f=[];self.mi=[]
 def face(self,points,mi):
  n=len(self.v);self.v.extend(points);self.f.append(tuple(range(n,n+len(points))));self.mi.append(mi)
 def box(self,c,s,mi=0):
  u,v,z=c;w,d,h=s
  if min(w,d,h)<=.0001:return
  p=[(u+w*a,v+d*b,z+h*c) for a,b,c in [(-.5,-.5,-.5),(.5,-.5,-.5),(.5,.5,-.5),(-.5,.5,-.5),(-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5)]]
  for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([p[i] for i in f],mi)
 def prism(self,p,z0,z1,mi=0):
  p=[tuple(q[:2]) for q in p]
  if p[0]==p[-1]:p=p[:-1]
  if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))<0:p.reverse()
  for a,b in zip(p,p[1:]+p[:1]):self.face([(a[0],a[1],z0),(b[0],b[1],z0),(b[0],b[1],z1),(a[0],a[1],z1)],mi)
  vs=[Vector((u,v,0)) for u,v in p]
  for tri in tessellate_polygon([vs]):
   t=[vs[i] if isinstance(i,int) else i for i in tri];self.face([(q.x,q.y,z1) for q in t],mi);self.face([(q.x,q.y,z0) for q in reversed(t)],mi)
 def tube(self,points,r,mi=3,sides=8):
  pts=[Vector(p) for p in points];rings=[]
  for i,p in enumerate(pts):
   t=(pts[min(i+1,len(pts)-1)]-pts[max(i-1,0)]).normalized();a=t.cross(Vector((0,0,1)))
   if a.length<.01:a=Vector((1,0,0))
   a.normalize();b=t.cross(a).normalized();rings.append([p+r*(math.cos(k*2*math.pi/sides)*a+math.sin(k*2*math.pi/sides)*b) for k in range(sides)])
  for a,b in zip(rings,rings[1:]):
   for k in range(sides):self.face([a[k],a[(k+1)%sides],b[(k+1)%sides],b[k]],mi)
 def lathe(self,u,v,profile,mi=3,segments=40):
  rings=[[(u+r*math.cos(k*2*math.pi/segments),v+r*math.sin(k*2*math.pi/segments),z) for k in range(segments)] for z,r in profile]
  self.face(list(reversed(rings[0])),mi);self.face(rings[-1],mi)
  for a,b in zip(rings,rings[1:]):
   for k in range(segments):self.face([a[k],a[(k+1)%segments],b[(k+1)%segments],b[k]],mi)
 def obj(self,col=COL):
  me=bpy.data.meshes.new(self.name);me.from_pydata([world(p) for p in self.v],[],[tuple(reversed(f)) for f in self.f]);me.update()
  for m in MAT:me.materials.append(m)
  for p,mi in zip(me.polygons,self.mi):p.material_index=mi
  ob=bpy.data.objects.new(self.name,me);col.objects.link(ob);return ob
mass=Mesh('01_named_source_footprint_mass_and_floor_bands');stone=Mesh('02_east_cutstone_courses_and_openings');frames=Mesh('03_deep_reveals_stone_architraves_sashes');portico=Mesh('04_six_freestanding_Corinthian_columns');capitals=Mesh('05_acanthus_leaf_capitals_and_corner_volutes');cornice=Mesh('06_flat_entablature_modillions_and_parapets');stairs=Mesh('07_twenty_three_steps_stone_cheeks');roof=Mesh('08_provisional_low_rooflights');rear=Mesh('09_unverified_rear_and_terminal_service_faces')
# Individual volumes follow the named source topology, including narrowed end stairs.
shape=R['shape']
vols=[('south_gallery',shape['southGalleryU'],shape['galleryV']),('north_gallery',shape['northGalleryU'],shape['galleryV']),('south_end',shape['southStairEndU'],shape['stairEndV']),('north_end',shape['northStairEndU'],shape['stairEndV']),('centre',shape['centreU'],shape['centreV'])]
# Floor plates and opaque roof are separate, facade openings are actual gaps to a recessed inner wall.
for name,(u0,u1),(v0,v1) in vols:
 for z,h in [(0,.22),(3.3,.20),(8.15,.20),(12.70,.20)]:mass.box(((u0+u1)/2,(v0+v1)/2,z+h/2),(u1-u0,v1-v0,h),0)
 # Interior backing lies a full metre behind the facade and cannot fill the portico.
 mass.box(((u0+u1)/2,(v0+v1)/2,6.5),(u1-u0-1.5,v1-v0-2.0,12.4),10)

def wall_with_openings(mesh,u0,u1,v,z0,z1,openings,thick=.42,mi=0):
 xs=sorted(set([u0,u1]+[max(u0,min(u1,x)) for a,b,c,d in openings for x in [a,b]]));zs=sorted(set([z0,z1]+[max(z0,min(z1,z)) for a,b,c,d in openings for z in [c,d]]))
 for a,b in zip(xs,xs[1:]):
  for c,d in zip(zs,zs[1:]):
   x=(a+b)/2;z=(c+d)/2
   if not any(l<x<r and lo<z<hi for l,r,lo,hi in openings):mesh.box((x,v-thick/2,z),(b-a,thick,d-c),mi)

def ashlar_face(mesh,u0,u1,v,z0,z1,holes,course=.43,width=1.35):
 # Stone joints use face geometry recessed behind blocks, never coplanar overlays.
 wall_with_openings(mesh,u0,u1,v-.045,z0,z1,holes,.35,2)
 n=math.ceil((z1-z0)/course)
 for row in range(n):
  a=z0+row*course;b=min(z1,a+course);offset=(row%2)*width/2;x=u0-offset
  while x<u1:
   l=max(u0,x)+.009;r=min(u1,x+width)-.009
   cuts=[(l,r,a+.008,b-.008)]
   for hl,hr,hb,ht in holes:
    nxt=[]
    for L,H,B,T in cuts:
     if H<=hl or L>=hr or T<=hb or B>=ht:nxt.append((L,H,B,T));continue
     for q in [(L,min(H,hl),B,T),(max(L,hr),H,B,T),(max(L,hl),min(H,hr),B,min(T,hb)),(max(L,hl),min(H,hr),max(B,ht),T)]:
      if q[1]-q[0]>.012 and q[3]-q[2]>.012:nxt.append(q)
    cuts=nxt
   for L,H,B,T in cuts:
    if H-L>.012 and T-B>.012:mesh.box(((L+H)/2,v-.04,(B+T)/2),(H-L,.075,T-B),0)
   x+=width

def window(u,v,z0,z1,w,style='main',back=False):
 sign=-1 if back else 1
 # A deep dark reveal and inset glass; front stone frame steps outward at sill/lintel.
 frames.box((u,v-sign*.20,(z0+z1)/2),(w+.05,.035,z1-z0+.03),6)
 frames.box((u,v-sign*.16,(z0+z1)/2),(w-.12,.035,z1-z0-.10),5)
 for x in [u-w/2,u+w/2]:frames.box((x,v+sign*.07,(z0+z1)/2),(.12,.24,z1-z0+.28),1)
 for z in [z0,z1]:frames.box((u,v+sign*.10,z),(w+.30,.30,.13),1)
 if style=='main':
  frames.box((u,v+sign*.18,z0-.14),(w+.55,.48,.15),1)
  frames.box((u,v+sign*.12,z1+.15),(w+.52,.36,.15),1)
  frames.box((u,v+sign*.16,z1+.29),(w+.65,.44,.095),3)
 for x in [u-w/2+.10,u+w/2-.10,u]:frames.box((x,v-sign*.105,(z0+z1)/2),(.045,.06,z1-z0-.12),4)
 for z in ([z0+.50,z0+(z1-z0)*.48] if style=='basement' else [z0+.46,z1-.32]):frames.box((u,v-sign*.08,z),(w-.12,.08,.045),4)
 if style=='main':
  for z in [z0+.22,z0+.42]:frames.box((u,v+.27,z),(w-.12,.04,.032),4)

# East gallery wings have one tall window bank with a broad unbroken wall ABOVE it.
for name,ur,vr in vols[:2]:
 u0,u1=ur;v0,v1=vr;span=u1-u0;centres=[u0+1.18+i*(span-2.36)/9 for i in range(10)];holes=[]
 for u in centres:holes.extend([(u-.70,u+.70,4.55,7.80),(u-.61,u+.61,.88,2.27)])
 ashlar_face(stone,u0,u1,v1,0,12.40,holes)
 for u in centres:window(u,v1,4.55,7.80,1.40);window(u,v1,.88,2.27,1.22,'basement')
 for z,w,h in [(3.18,.32,.16),(3.40,.44,.19),(8.00,.07,.06)]:mass.box(((u0+u1)/2,v1+w/2,z),(span,w,h),1)
 # Conservative rear: very limited basement openings, no fictitious grand facade.
 backholes=[]
 for u in [u0+3.1+i*(span-6.2)/5 for i in range(6)]:backholes.append((u-.55,u+.55,.95,2.10))
 wall_with_openings(rear,u0,u1,v0+.4,0,12.45,backholes,.4,0)
 for l,h,b,t in backholes:window((l+h)/2,v0,b,t,h-l,'basement',True)
 for z in [0.3,3.4,12.35]:rear.box(((u0+u1)/2,v0-.08,z),(span,.18,.16),1)
 # Narrow end faces of gallery volumes.
 for u in [u0,u1]:mass.box((u,(v0+v1)/2,6.20),(.35,v1-v0,12.4),0)
# Central recessed front entry behind six actual free-standing columns.
u0,u1=shape['centreU'];v0,v1=shape['centreV'];door=(-1.26,.74,3.4,7.2)
centralholes=[door,(-5.02,-3.55,4.3,7.7),(3.1,4.57,4.3,7.7),(-5.05,-3.55,9.50,11.55),(-1.0,.50,9.50,11.55),(3.10,4.60,9.50,11.55)]
ashlar_face(stone,u0,u1,v1,0,12.68,centralholes,course=.57,width=1.33)
for a,b,c,d in centralholes:
 if (a,b,c,d)==door:continue
 window((a+b)/2,v1,c,d,b-a,'main' if c<8 else 'upper')
frames.box((-.26,v1-.7,5.28),(2.0,.04,3.7),6)
for u in [-1.18,-.27,.65]:frames.box((u,v1-.39,4.95),(.065,.10,3.08),4)
for z in [3.50,4.14,6.46]:frames.box((-.26,v1-.39,z),(1.93,.10,.065),4)
frames.box((-.26,v1-.45,5.01),(1.79,.03,2.55),5)
for u in [-1.47,.95]:frames.box((u,v1+.18,5.37),(.34,.38,4.10),1)
for z,w,h in [(7.38,2.84,.28),(7.64,3.11,.14),(7.81,3.25,.15)]:frames.box((-.26,v1+.24,z),(w,.52,h),3)
# Centre rear: occupied broad hall instead of an invented open courtyard.
wall_with_openings(rear,u0,u1,v0+.45,0,13.65,[],.45,0)
for u in [u0,u1]:mass.box((u,(v0+v1)/2,6.55),(.32,v1-v0,13.10),0)
# Low narrower terminal stair/service bays are distinct in the official visitor plans.
for name,ur,vr in vols[2:4]:
 a,b=ur;c,d=vr
 for v,back in [(d,False),(c,True)]:
  holes=[((a+b)/2-.65,(a+b)/2+.65,.45,2.55)]
  ashlar_face(rear,a,b,v,0,12.45,holes) if not back else wall_with_openings(rear,a,b,v+.4,0,12.45,holes,.4,0)
  window((a+b)/2,v,.45,2.55,1.3,'service',back)
 for u in [a,b]:rear.box((u,(c+d)/2,6.4),(.35,d-c,12.8),0)
# Six columns: smooth tapered shafts with subtle entasis, moulded Attic bases and leaf capitals.
pc=R['facades']['portico']
for idx,u in enumerate(pc['columnCentresU']):
 v=pc['columnCentreV'];portico.box((u,v,3.53),(1.19,1.19,.26),1)
 profile=[(3.65,.57),(3.71,.57),(3.76,.51),(3.81,.55),(3.89,.54),(3.97,.47),(4.10,.465),(5.5,.464),(7.5,.449),(9.8,.423),(11.70,.40),(11.76,.45),(11.85,.46)]
 portico.lathe(u,v,profile)
 # Horizontal shaft stone joints are shallow rings, not spiral grooves.
 for z in [5.32,7.10,8.87,10.63]:portico.lathe(u,v,[(z-.009,.447-(z-7)*.009),(z+.009,.447-(z-7)*.009)],2)
 capitals.lathe(u,v,[(11.79,.43),(11.92,.45),(12.12,.53),(12.41,.66),(12.49,.62)],3)
 for row in [0,1]:
  for k in range(8):
   a=k*math.pi/4+row*math.pi/8;z=11.80+row*.24;leaf=[];height=.43 if row==0 else .49
   for j in range(7):
    t=j/6;r=.43+.26*math.sin(t*math.pi*.72);w=.18*math.sin(math.pi*t)**.7
    lobe=1.0 if j%2 else .64
    for side in [-1,1]:leaf.append((u+r*math.cos(a)+side*w*lobe*math.sin(a),v+r*math.sin(a)-side*w*lobe*math.cos(a),z+t*height))
   for j in range(6):capitals.face([leaf[j*2],leaf[j*2+1],leaf[j*2+3],leaf[j*2+2]],3)
   capitals.tube([(u+(.43+.26*math.sin(t*math.pi*.72))*math.cos(a),v+(.43+.26*math.sin(t*math.pi*.72))*math.sin(a),z+t*height) for t in [0,.2,.4,.6,.8,1]],.025,1,5)
 for a in [math.pi/4,3*math.pi/4,5*math.pi/4,7*math.pi/4]:
  centre=Vector((u+.57*math.cos(a),v+.57*math.sin(a),12.39));tangent=Vector((-math.sin(a),math.cos(a),0));points=[]
  for k in range(24):
   t=k/23;ang=t*2*math.pi*1.1;r=.16*(1-.78*t);points.append(centre+tangent*(r*math.cos(ang))+Vector((0,0,r*math.sin(ang))))
  capitals.tube(points,.036,3)
 capitals.box((u,v,12.57),(1.40,1.40,.18),3)
# Open portico ceiling/entablature. No wall is inserted between the six columns.
portico.box((-.23,8.1,12.72),(15.5,4.4,.20),1)
for z,w,d,h in [(12.84,15.70,4.52,.14),(13.06,15.90,4.65,.30),(13.30,16.25,4.89,.14),(13.46,16.6,5.12,.20),(13.65,16.8,5.23,.16),(13.97,15.6,4.30,.56),(14.23,15.90,4.50,.11)]:cornice.box((-.23,8.1,z),(w,d,h),3)
# Visible modillions beneath the strongly projecting cornice, wrapping only returns.
for i in range(36):cornice.box((-7.98+i*15.5/35,10.58,13.34),(.19,.40,.18),1)
for u in [-8.14,7.68]:
 for i in range(7):cornice.box((u,5.72+i*.66,13.34),(.38,.19,.18),1)
# Wing cornice hierarchy and flat parapet, subordinate to raised central portico.
for name,(u0,u1),(v0,v1) in vols:
 if name=='centre':continue
 for z,pad,h in [(12.43,.10,.16),(12.60,.31,.17),(12.80,.47,.18),(12.99,.20,.20),(13.21,.26,.18)]:cornice.box(((u0+u1)/2,(v0+v1)/2,z),(u1-u0,v1-v0+pad*2,h),3)
 if 'gallery' in name:
  for i in range(round((u1-u0)/.50)):cornice.box((u0+.27+i*.50,v1+.21,12.59),(.18,.28,.17),1)
# Raised entry base,23individual steps and heavy cheek walls; fountain/approach path excluded.
stairs.box((-.23,8.08,1.70),(15.5,3.80,3.4),0)
for i in range(23):
 z=(i+1)*3.4/23;end=16.3-i*6.3/23
 stairs.box((-.23,(10.0+end)/2,z/2),(14.65,end-10.0,z),0)
 stairs.box((-.23,end-.028,z-.015),(14.73,.09,.035),9)
# Two front-side solid plinths with stepped cornice. Only low sloping walls flank lower steps.
for u in [-8.17,7.71]:
 stairs.box((u,10.14,2.16),(1.27,2.00,4.32),0)
 for z,w,d,h in [(3.99,1.46,2.13,.16),(4.18,1.61,2.24,.17),(4.38,1.66,2.34,.18)]:stairs.box((u,10.14,z),(w,d,h),3)
 for i in range(23):
  z=(i+1)*3.4/23+.48;end=16.3-i*6.3/23
  stairs.box((u,(10+end)/2,z/2),(.58,end-10,z),0)
# Roof covers on source inner rings: intentionally labelled provisional rooflight geometry.
for n,ring in enumerate(S['localUVRings'][1:]):
 u0=min(p[0] for p in ring);u1=max(p[0] for p in ring);v0=min(p[1] for p in ring);v1=max(p[1] for p in ring);base=13.30 if n==1 else 13.04;peak=14.50 if n==1 else 13.49
 roof.box(((u0+u1)/2,(v0+v1)/2,base+.07),(u1-u0,v1-v0,.14),7)
 vm=(v0+v1)/2
 roof.face([(u0,v0,base),(u1,v0,base),(u1,vm,peak),(u0,vm,peak)],1 if n==1 else 8);roof.face([(u0,vm,peak),(u1,vm,peak),(u1,v1,base),(u0,v1,base)],1 if n==1 else 8)
 if n==1:
  # Worksheet p3 shows opaque pale gable and one small dark northern end opening.
  roof.face([(u0,v0,base),(u0,vm,peak),(u0,v1,base)],1)
  l=vm-.38;r=vm+.38;zb=base+.23;zt=base+.63
  roof.face([(u1,v0,base),(u1,l,base),(u1,l,zt),(u1,vm,peak)],1)
  roof.face([(u1,r,base),(u1,v1,base),(u1,vm,peak),(u1,r,zt)],1)
  roof.face([(u1,l,zt),(u1,r,zt),(u1,vm,peak)],1)
  roof.face([(u1,l,base),(u1,r,base),(u1,r,zb),(u1,l,zb)],1)
  roof.box((u1-.055,vm,(zb+zt)/2),(.055,r-l,zt-zb),6)
  roof.tube([(u0,vm,peak+.025),(u1,vm,peak+.025)],.045,1,6)
 else:
  for u in [u0,u1]:roof.face([(u,v0,base),(u,vm,peak),(u,v1,base)],7)
  for j in range(max(2,round((u1-u0)/1.6))+1):
   u=u0+(u1-u0)*j/max(2,round((u1-u0)/1.6))
   roof.tube([(u,v0,base+.035),(u,vm,peak+.035),(u,v1,base+.035)],.038,7,5)
objects=[m.obj() for m in [mass,stone,frames,portico,capitals,cornice,stairs,roof,rear]]
# Apply local shapes to east/north metres; glTF exporter subsequently yields east/up/south.
for ob in objects:
 ob['evidenceBasis']='MMCA official photos/visitor plan; authored-input.json states measured versus estimated';ob['sourceFootprintId']=R['footprintId']
# Explicitly fix normals for independent closed primitives; no photographic image data.
for ob in objects:
 bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(ob.data);bm.free();ob.data.update()
bpy.ops.object.select_all(action='DESELECT')
for ob in objects:ob.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
bpy.ops.export_scene.gltf(filepath=str(OUT/(R['assetId']+'.glb')),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_normals=True,export_texcoords=False,export_materials='EXPORT',export_cameras=False,export_lights=False)
# Review ground/cameras are excluded from asset export and remain independently editable.
g=Mesh('review_ground');g.box((0,0,-.15),(110,65,.20),11);g.obj(REVIEW)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=28;scene.cycles.use_denoising=True
scene.world.color=(.65,.65,.65);scene.view_settings.view_transform='AgX';scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
worldnodes=scene.world.node_tree if scene.world.use_nodes else None
scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.62,.68,.77,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.50
light=bpy.data.lights.new('review broad sky','AREA');ob=bpy.data.objects.new('review broad sky',light);REVIEW.objects.link(ob);ob.location=world((-30,40,60));light.energy=5200;light.size=50
sun=bpy.data.lights.new('review sun','SUN');ob=bpy.data.objects.new('review sun',sun);REVIEW.objects.link(ob);ob.rotation_euler=(math.radians(24),math.radians(-20),math.radians(-30));sun.energy=2.0;sun.angle=.12
views=[('front-whole',(0,95,18),(0,0,6),90),('front-portico',(-.2,42,10),(-.2,7,8),28),('elevated-official-worksheet',(54,58,40),(0,0,6),92),('source-roof-plan',(0,0,125),(0,0,0),145),('rear-limit',(46,-55,30),(0,0,6),90)]
for name,loc,target,scale in views:
 cam=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,cam);REVIEW.objects.link(ob);ob.location=world(loc);ob.rotation_euler=(Vector(world(target))-ob.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=scale
scene.camera=bpy.data.objects['front-whole'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'mmca-deoksugung.blend'))
# Geometry inspection before reviewed publication.
lo=[float('inf')]*3;hi=[-float('inf')]*3;tris=0
for ob in objects:
 ob.data.calc_loop_triangles();tris+=len(ob.data.loop_triangles)
 for v in ob.data.vertices:
  for k,val in enumerate(v.co):lo[k]=min(lo[k],val);hi[k]=max(hi[k],val)
report={'assetId':R['assetId'],'objects':len(objects),'triangles':tris,'blenderBoundsENZ':[lo,hi],'dimensionsGLBXupYsouthZ':[hi[0]-lo[0],hi[2]-lo[2],hi[1]-lo[1]],'minHeight':lo[2],'embeddedImages':len([im for im in bpy.data.images if im.packed_file]),'columnCount':6,'stairCount':23,'sourceFootprintIds':[R['footprintId']],'renderViews':[x[0] for x in views]}
(OUT/'geometry-check.json').write_text(json.dumps(report,indent=2)+'\n')
bundle={'siteId':R['siteId'],'sources':R['sources'],'recipeFiles':['authored-input.json','source-footprint.json'],'assets':[{'id':R['assetId'],'nameKo':R['nameKo'],'file':R['assetId']+'.glb','blendSource':'mmca-deoksugung.blend','coordinate':R['anchor'],'category':'heritage','district':'중구','footprintIds':[R['footprintId']],'supersedes':[R['oldAssetId']],'referenceUrl':R['sources'][0]['url'],'components':['Source-shaped north/south galleries and narrowed stair ends','Six freestanding smooth Corinthian columns with authored acanthus leaf capitals','Raised23step stair and stone cheeks','Flat layered portico entablature and modillion cornice','Recessed doorway and distinct upper/lower window programs','Provisional low rooflight covers; no ground courtyard cutouts'],'uncertainties':R['uncertainties']}],'places':[{'id':'bespoke-mmca-deoksugung','name':'국립현대미술관 덕수궁','subtitle':'석조전 서관 · 개별 석재 입면과 기둥 현관','center':[R['anchor']['lon'],R['anchor']['lat']],'zoom':18,'source_url':R['sources'][0]['url'],'supersedesPlaceIds':['model:'+R['oldAssetId']]}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report))
