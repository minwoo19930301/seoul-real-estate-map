"""One Pentas105/106. Individually mapped actual rings and official unit-height arms.
Geometryhelpers only are shared; façade assemblies/armcutsare specificto thissite.
"""
from pathlib import Path
import bpy,bmesh,json,math,hashlib
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
OUT=Path(__file__).resolve().parent;D=json.loads((OUT/'authored-input.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
 if c.name!='Collection':bpy.data.collections.remove(c)
for pool in (bpy.data.meshes,bpy.data.curves,bpy.data.materials,bpy.data.cameras,bpy.data.lights):
 for block in list(pool):
  if block.users==0:pool.remove(block)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.preferences.filepaths.save_version=0
palette={'glass':(.10,.19,.255,1),'glass_light':(.20,.30,.35,1),'dark_panel':(.17,.22,.26,1),'panel_gray':(.28,.31,.32,1),'granite':(.10,.115,.12,1),'pale_portal':(.67,.68,.63,1),'glass_silver':(.32,.40,.44,1),'bronze':(.49,.29,.115,1),'bronze_light':(.66,.43,.21,1),'stone':(.46,.46,.43,1),'silver':(.43,.49,.52,1),'opening':(.028,.040,.047,1),'roof':(.37,.40,.42,1)}
M={}
for name,color in palette.items():
 m=bpy.data.materials.new('OnePentas_'+name);m.diffuse_color=color;m.use_nodes=True;bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=color;bs.inputs['Roughness'].default_value=.26 if 'glass'in name else .48;bs.inputs['Metallic'].default_value=.36 if 'bronze'in name else .10;M[name]=m
COL={}
def col(n):
 if n not in COL:c=bpy.data.collections.new(n);bpy.context.scene.collection.children.link(c);COL[n]=c
 return COL[n]
class Batch:
 def __init__(self,n,m,c,asset):self.n=n;self.m=m;self.c=c;self.asset=asset;self.v=[];self.f=[]
 def prism(self,ring,z0,z1):
  if len(ring)<3 or z1-z0<.0001:return
  ring=[tuple(p) for p in ring]
  if sum(ring[i][0]*ring[(i+1)%len(ring)][1]-ring[(i+1)%len(ring)][0]*ring[i][1] for i in range(len(ring)))<0:ring.reverse()
  pts=[Vector((x,y,0)) for x,y in ring];N=len(pts);s=len(self.v);self.v += [(p.x,p.y,z) for z in (z0,z1) for p in pts];idx={tuple(p):i for i,p in enumerate(pts)}
  for tr in tessellate_polygon([pts]):
   ii=[p if isinstance(p,int) else idx[tuple(p)] for p in tr];self.f += [tuple(s+i for i in reversed(ii)),tuple(s+N+i for i in ii)]
  for i in range(N):j=(i+1)%N;self.f.append((s+i,s+j,s+N+j,s+N+i))
 def face(self,a,b,z0,z1,depth=.035,off=.06):
  a,b=Vector(a),Vector(b)
  if (b-a).length<1e-6:return
  u=(b-a).normalized();n=Vector((u.y,-u.x));self.prism([a+n*off,b+n*off,b+n*(off+depth),a+n*(off+depth)],z0,z1)
 def box(self,x,y,z,w,d,h,angle=0):
  c,s=math.cos(angle),math.sin(angle);self.prism([(x+a*c-b*s,y+a*s+b*c) for a,b in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]],z-h/2,z+h/2)
 def surface(self,ring3,thickness=.06):
  ring=[Vector((x,y,0)) for x,y,z in ring3];idx={tuple(p):i for i,p in enumerate(ring)};n=len(ring);st=len(self.v);self.v+=ring3+[(x,y,z-thickness) for x,y,z in ring3]
  for tr in tessellate_polygon([ring]):
   ii=[p if isinstance(p,int) else idx[tuple(p)] for p in tr];self.f += [tuple(st+i for i in ii),tuple(st+n+i for i in reversed(ii))]
  for i in range(n):j=(i+1)%n;self.f.append((st+i,st+j,st+n+j,st+n+i))
 def plate(self,points,normal,thickness=.045):
  unique=[]
  for p in points:
   if not unique or (Vector(p)-Vector(unique[-1])).length>.001:unique.append(p)
  if len(unique)>2 and (Vector(unique[0])-Vector(unique[-1])).length<.001:unique.pop()
  if len(unique)<3:return
  n=Vector(normal).normalized()*thickness;st=len(self.v);N=len(unique);self.v += [tuple(Vector(p)+n*.5) for p in unique]+[tuple(Vector(p)-n*.5) for p in unique]
  self.f += [tuple(st+i for i in range(N)),tuple(st+N+i for i in reversed(range(N)))]
  for i in range(N):j=(i+1)%N;self.f.append((st+i,st+j,st+N+j,st+N+i))
 def beam(self,a,b,width=.08):
  a,b=Vector(a),Vector(b);u=(b-a).normalized();n=u.cross(Vector((0,0,1)))
  if n.length<.01:n=u.cross(Vector((0,1,0)))
  n.normalize();v=u.cross(n);st=len(self.v)
  self.v += [tuple(p+n*x*width/2+v*y*width/2) for p in (a,b) for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
  self.f += [tuple(st+i for i in q) for q in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]]
 def finish(self):
  me=bpy.data.meshes.new(self.n);me.from_pydata(self.v,[],self.f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new(self.n,me);col(self.c).objects.link(o);me.materials.append(M[self.m]);o['asset_id']=self.asset;return o
B={}
def P(n,m,c,asset):
 if n not in B:B[n]=Batch(n,m,c,asset)
 return B[n]
def ccw(r):
 r=[tuple(q)for q in r]
 if sum(r[i][0]*r[(i+1)%len(r)][1]-r[(i+1)%len(r)][0]*r[i][1]for i in range(len(r)))<0:r.reverse()
 return r
def face_style(mid,rec):
 best=(1000,'stone',-1)
 for i,(a,b) in enumerate(zip(rec['ring'],rec['ring'][1:]+rec['ring'][:1])):
  a,b=Vector(a),Vector(b);v=b-a;t=max(0,min(1,(mid-a).dot(v)/v.length_squared));dist=(mid-a-v*t).length
  if dist<best[0]:best=(dist,rec['styles'][i],i)
 if rec['row']['name']=='105' and best[0]<.15 and best[2]==6:return '105_north_living'
 if rec['row']['name']=='106':
  if best[0]>=.15:return '106_upper_return'
  if best[2]==4:return '106_high_slot'
  if best[2]==6:return '106_low_glazing'
 return best[1]if best[0]<.15 else 'living'
def band_curve(batch,a,u,n,z,L,off=.25):
 # Actualcompletedphoto104/106: upturnedquartercurvesmeetingstraightbronzesills.
 R=min(1.85,L*.21);pts=[]
 for j in range(9):
  t=math.pi+math.pi/2*j/8;x=R+R*math.cos(t);zz=z+R+R*math.sin(t);p=a+u*x+n*off;pts.append((p.x,p.y,zz))
 p=a+u*L+n*off;pts.append((p.x,p.y,z))
 for aa,bb in zip(pts,pts[1:]):batch.beam(aa,bb,.20)
def facade_106_east(asset,a,b,zlo,zhi,style,tag):
 a,b=Vector(a),Vector(b);u=(b-a).normalized();L=(b-a).length;c='OnePentas_106_03_individually_mapped_east'
 dark=P(tag+'_deep_recess','opening',c,asset);glass=P(tag+'_blue_fixed_lights','glass',c,asset);silverglass=P(tag+'_silver_reflection_lights','glass_silver',c,asset);gray=P(tag+'_gray_punched_wall','panel_gray',c,asset);frame=P(tag+'_dark_mullions','dark_panel',c,asset);silver=P(tag+'_silver_openers','silver',c,asset);white=P(tag+'_continuous_pale_portal','pale_portal',c,asset);bronze=P(tag+'_projecting_copper_ribbons','bronze_light',c,asset)
 bounds=sorted(set([zlo,zhi]+[4.05+k*3.2 for k in range(36)if zlo<4.05+k*3.2<zhi]));dark.face(a,b,zlo,zhi,.04,.04)
 def span(t0,t1):return a+u*L*t0,a+u*L*t1
 def window_bank(t0,t1,tag_extra):
  aa,bb=span(t0,t1);width=(bb-aa).length;silverglass.face(aa,bb,zlo,zhi,.045,.13)
  for low,hi in zip(bounds,bounds[1:]):
   if hi-low<.7:continue
   gray.face(aa,bb,low+.08,min(hi,low+.66),.085,.18)
   # Fixedpane+darkopener+reflectivepanelwithrealsetbackdifference.
   q1=aa+u*width*.49;q2=aa+u*width*.69
   glass.face(aa,q1,low+.69,hi-.12,.035,.15)
   dark.face(q1,q2,low+.68,hi-.10,.035,.07)
   silverglass.face(q1+u*.07,q2-u*.04,low+.89,min(hi-.18,low+1.97),.025,.11)
   silver.face(q1,q2,low+1.95,min(hi-.13,low+2.02),.03,.16)
   for q in(aa,q1,q2,bb):frame.face(q-u*.050,q+u*.050,low+.65,hi-.08,.11,.23)
  for q in(aa,bb):silver.face(q-u*.07,q+u*.07,zlo,zhi,.13,.32)
 if style=='106_high_slot':
  # Sourceedge4→5: NOTsolidlefthalf. Narrowglazedbanksflankpunchedwall,
  # thenasubstantialdeepcontinuouscorestripontheinneredge.
  window_bank(.00,.15,'outer_vision');aa,bb=span(.15,.57);gray.face(aa,bb,zlo,zhi,.12,.43)
  for low,hi in zip(bounds,bounds[1:]):
   if hi-low<.8:continue
   for t0,t1 in[(.235,.34),(.395,.50)]:
    wa,wb=span(t0,t1);dark.face(wa-u*.07,wb+u*.07,low+1.13,min(hi-.30,low+1.90),.045,.60);glass.face(wa,wb,low+1.20,min(hi-.35,low+1.82),.03,.655);silver.face(wa,wb,low+1.20,low+1.26,.03,.70)
  window_bank(.585,.81,'inner_vision')
  ca,cb=span(.82,1.0);P(tag+'_continuous_dark_core','dark_panel',c,asset).face(ca,cb,zlo,zhi,.25,.49)
  for t in(.81,.995):
   q=a+u*L*t;frame.face(q-u*.12,q+u*.12,zlo,zhi,.22,.74)
  for z in bounds:
   bronze.face(a,a+u*L*.815,max(zlo,z-.12),min(zhi,z+.12),.42,.62)
 else:
  # Sourceedge6→7: paleportal/shaftontheinnerleft; threeunequal
  # glazedbankstotheright.Portalhascontinuousbrightjambs,notflooronlybands.
  portal=.17 if style=='106_low_glazing'else .055
  if style=='106_low_glazing':
   pa,pb=span(.025,portal);glass.face(pa,pb,zlo,zhi,.045,.08)
   for q in(pa,pb):white.face(q-u*.23,q+u*.23,zlo,zhi,.62,.30)
   for low,hi in zip(bounds,bounds[1:]):
    white.face(pa,pb,low+.04,min(hi,low+.55),.53,.34)
    silver.face(pa,pb,low+1.28,min(hi-.1,low+1.34),.06,.20)
  # Eachbandhasdifferentwidthandsplit.Thesearephotobanks,notbaysfitted
  # toanarbitrarygridcount;thelowarmhasnoinventedpairedpunchedwall.
  stops=[portal+.025,.46,.76,1]
  for k in range(3):window_bank(stops[k],stops[k+1]-.016,'bank'+str(k))
  for z in bounds:
   bronze.face(a+u*L*(portal+.01),b,max(zlo,z-.12),min(zhi,z+.12),.46,.53)
  for t in(stops[0],.46,.76,.995):
   q=a+u*L*t;white.face(q-u*.065,q+u*.065,zlo,zhi,.12,.34)

def facade_105_numbered_side(asset,a,b,zlo,zhi,tag):
 # Independentlyphoto53mappedsourceedge6→7.Thecurvednumber105panel
 # isonadjacentedge7→8;donotmistakeitforwindows.
 a,b=Vector(a),Vector(b);u=(b-a).normalized();L=(b-a).length;c='OnePentas_105_03_photo53_north_living'
 dark=P(tag+'_depth_joints','opening',c,asset);stone=P(tag+'_service_stone','stone',c,asset);glass=P(tag+'_living_glass','glass',c,asset);silverglass=P(tag+'_light_fixed_glass','glass_silver',c,asset);silver=P(tag+'_window_frames','silver',c,asset);bronze=P(tag+'_bronze_floor_ribbons','bronze_light',c,asset)
 bounds=sorted(set([zlo,zhi]+[4.05+k*3.2 for k in range(36)if zlo<4.05+k*3.2<zhi]));dark.face(a,b,zlo,zhi,.04,.05)
 split=a+u*L*.33;stone.face(a,split,zlo,zhi,.12,.18)
 for low,hi in zip(bounds,bounds[1:]):
  if hi-low<.7:continue
  for t in(.085,.245):
   aa=a+u*L*t;bb=aa+u*L*.045;dark.face(aa,bb,low+.7,hi-.48,.035,.33);glass.face(aa+u*.035,bb-u*.035,low+.78,hi-.55,.025,.38)
 for t in(.33,.385):
  q=a+u*L*t;P(tag+'_slender_stone_verticals','pale_portal',c,asset).face(q-u*.12,q+u*.12,zlo,zhi,.25,.24)
 stops=[.395,.57,.795,1]
 for j in range(3):
  aa=a+u*L*stops[j];bb=a+u*L*stops[j+1];w=(bb-aa).length;silverglass.face(aa,bb,zlo,zhi,.035,.12)
  for low,hi in zip(bounds,bounds[1:]):
   if hi-low<.7:continue
   P(tag+'_silverspandrel','panel_gray',c,asset).face(aa,bb,low+.08,min(hi,low+.72),.09,.16)
   for t in(.22,.69,.86):
    q=aa+u*w*t;dark.face(q-u*.04,q+u*.04,low+.72,hi-.10,.08,.25)
   # Unequalbluefixedpaneandnarrowsilvercasementbank.
   glass.face(aa+u*w*.22,aa+u*w*.69,low+.76,hi-.12,.02,.19)
   silver.face(aa+u*w*.69,aa+u*w*.86,low+1.4,min(hi-.15,low+1.46),.04,.26)
  for q in(aa,bb):silver.face(q-u*.09,q+u*.09,zlo,zhi,.17,.22)
 for z in bounds:bronze.face(a+u*L*.395,b,max(zlo,z-.11),min(zhi,z+.11),.43,.36)

def facade(n,asset,a,b,zlo,zhi,style,tag):
 if style=='105_north_living':
  facade_105_numbered_side(asset,a,b,zlo,zhi,tag);return
 if style.startswith('106_'):
  facade_106_east(asset,a,b,zlo,zhi,style,tag);return
 a,b=Vector(a),Vector(b);L=(b-a).length
 if L<.10:return
 u=(b-a)/L;normal=Vector((u.y,-u.x));c='OnePentas_'+n+'_03_'+style
 glass=P(tag+'_recessed_glass','glass',c,asset);metal=P(tag+'_bronze','bronze',c,asset);bright=P(tag+'_bronze_highlight','bronze_light',c,asset);stone=P(tag+'_stone','stone',c,asset);frame=P(tag+'_silver_frames','silver',c,asset);dark=P(tag+'_deep_joints','opening',c,asset)
 bounds=sorted(set([zlo,zhi]+[4.05+k*3.2 for k in range(36)if zlo<4.05+k*3.2<zhi]))
 if style=='recess':
  dark.face(a,b,zlo,zhi,.10,.03)
  for k in range(1,max(2,round(L/2))):
   q=a+u*L*k/max(2,round(L/2));frame.face(q-u*.08,q+u*.08,zlo,zhi,.10,.14)
  return
 glass.face(a,b,zlo,zhi,.035,.035)
 if style=='curve':
  # PHOTO53number105andPHOTO04number106areOPAQUEendpanels.
  # Theunequalvisionbanksareontheneighboringedge6→7,notonthisedge7→8.
  P(tag+'_opaque_numbered_end_panel','dark_panel',c,asset).face(a,b,zlo,zhi,.035,.09)
  extent=L*(.78 if n=='105'else .82);curve_end=a+u*extent
  for z in bounds[1:-1]:
   frame.face(a,b,z-.015,z+.015,.015,.14)
   # Actualcurve risesintotherightverticalrail(photo53),notleftcorner.
   band_curve(bright,curve_end,-u,normal,z,extent,.33)
  for t in((.02,.35,.78,.985)if n=='105'else(.02,.40,.82,.985)):
   q=a+u*L*t;metal.face(q-u*.11,q+u*.11,zlo,zhi,.32,.20)
 elif style in('rear','service','stone'):
  stone.face(a,b,zlo,zhi,.09,.08)
  bays=max(1,round(L/(3.2 if style=='rear'else 2.6)))
  for k in range(bays):
   center=a+u*L*(k+.5)/bays;ww=min(.92,L/bays*.40)
   for low,hi in zip(bounds,bounds[1:]):
    if hi-low<.8:continue
    aa=center-u*ww/2;bb=center+u*ww/2;dark.face(aa-u*.065,bb+u*.065,low+.9,hi-.6,.06,.20);glass.face(aa,bb,low+.96,hi-.66,.028,.275);frame.face(aa,bb,low+1.05,low+1.10,.035,.31)
  for t in(.02,.98):
   q=a+u*L*t;P(tag+'_vertical_service_reveal','dark_panel',c,asset).face(q-u*.16,q+u*.16,zlo,zhi,.06,.20)
  for z in bounds:frame.face(a,b,z-.013,z+.013,.02,.19)
 else:
  # Photo106eastlivingfacehasalargeopaquegraybankwithpairedsmallwindows
  # nexttoafulllargeglassbank.Thisisnotanallglassrepeatedwindowtemplate.
  split=L*.47;opaqueb=a+u*split
  P(tag+'_opaque_livingbank','dark_panel',c,asset).face(a,opaqueb,zlo,zhi,.09,.10)
  P(tag+'_gray_opaque_field','panel_gray',c,asset).face(a+u*.15,opaqueb-u*.15,zlo,zhi,.065,.205)
  # Thelivingwindowbankbeyondsplitkeepsbroadfixedpaneswithnarrowopeners.
  glazedL=L-split;count=max(2,round(glazedL/2.4))
  for j in range(count+1):
   q=opaqueb+u*glazedL*j/count;frame.face(q-u*.045,q+u*.045,zlo,zhi,.055,.16)
  for low,hi in zip(bounds,bounds[1:]):
   if hi-low<.6:continue
   # Horizontalpairedcasementsinopaquegraywall,occupyinglesshalfthestorey.
   for t in(.18,.57):
    aa=a+u*split*t;bb=aa+u*split*.25
    dark.face(aa-u*.065,bb+u*.065,low+1.0,min(hi-.25,low+1.86),.035,.31)
    glass.face(aa,bb,low+1.08,min(hi-.31,low+1.78),.025,.355)
    frame.face(aa,bb,low+1.07,low+1.12,.04,.39)
   P(tag+'_glass_bank_spandrel','dark_panel',c,asset).face(opaqueb,b,low+.1,min(hi,low+.72),.05,.11)
   for j in range(count):
    aa=opaqueb+u*glazedL*j/count;bb=aa+u*glazedL/count
    q=aa+u*glazedL/count*.72;frame.face(q-u*.026,q+u*.026,low+.73,hi-.08,.045,.21)
  for q in(a,opaqueb,b):stone.face(q-u*.18,q+u*.18,zlo,zhi,.17,.18)
  for z in bounds:
   metal.face(a,b,max(zlo,z-.12),min(zhi,z+.12),.48,.16)
   bright.face(a,b,max(zlo,z+.04),min(zhi,z+.10),.045,.65)
  for q in(a,b):metal.face(q-u*.12,q+u*.12,zlo,zhi,.24,.25)

for n,rec in D['towers'].items():
 asset='bespoke-raemian-onepentas-'+n;c='OnePentas_'+n;whole=ccw(rec['ring'])
 # Openpiloti: solidcoreonly, perimeterstructurebeginsat4.05m.
 center=sum((Vector(q)for q in whole),Vector((0,0)))/len(whole)
 P(n+'_ground_core','granite',c+'_01_piloti',asset).box(center.x,center.y,2.05,8,7,4.1,.33)
 for k,(a,b)in enumerate(zip(whole,whole[1:]+whole[:1])):
  a,b=Vector(a),Vector(b);u=(b-a).normalized();normal=Vector((-u.y,u.x))
  for j in range(max(1,round((b-a).length/7))):
   p=a+(b-a)*(j+.18)/max(1,round((b-a).length/7))+normal*.70
   P(n+'_piloti_stone_columns','granite',c+'_01_piloti',asset).box(p.x,p.y,2.10,1.40,1.65,4.20)
  P(n+'_continuous_base_bronze','bronze',c+'_01_piloti',asset).face(a,b,4.00,4.55,.62,.22)
 # Actual106photo04showsdarkstoneplinthbelowendface;105photo53
 # partlyoccludedgroundisnotproofthateveryarmstandsonthinsplayedlegs.
 # Broadpiersaboveplusboundedendwall;unverifieddiagonalbracesremoved.
 ends=[(rec['ring'][7],rec['ring'][8])]
 for ea,eb in ends:
  ea,eb=Vector(ea),Vector(eb)
  if n=='105':eb=ea+(eb-ea)*.62
  P(n+'_dark_stone_end_plinth','granite',c+'_01_piloti',asset).face(ea,eb,0,4.10,.85,-.55)
  P(n+'_end_plinth_coping','bronze',c+'_01_piloti',asset).face(ea,eb,3.85,4.13,.65,.08)
  # Large horizontalstonejoints only;no invented shop/doorfacade.
  for z in(.95,1.9,2.85):P(n+'_plinth_stone_courses','silver',c+'_01_piloti',asset).face(ea,eb,z,z+.025,.01,.31)
 for ri,reg in enumerate(rec['regions']):
  lo=reg.get('base',4.05);hi=reg['height']
  for pi,raw in enumerate(reg['rings']):
   r=ccw(raw);tag=n+'_'+reg['name']+str(pi)
   P(tag+'_floorplate_body','dark_panel',c+'_02_individual_arms',asset).prism(r,lo,hi)
   P(tag+'_roof_slab','roof',c+'_04_stepped_roofs',asset).prism(r,hi,hi+.12)
   for ei,(a,b)in enumerate(zip(r,r[1:]+r[:1])):
    style=face_style((Vector(a)+Vector(b))/2,rec)
    if lo>100:style='living'
    facade(n,asset,a,b,lo,hi,style,tag+'_e'+str(ei))
    P(tag+'_bronze_roof_fascia','bronze',c+'_04_stepped_roofs',asset).face(a,b,hi-.25,hi+.16,.32,.10)
    # Openrooftop safetyrail, transparent physicalgaps.
    aa,bb=Vector(a),Vector(b);L=(bb-aa).length
    if L<.1:continue
    normal=Vector(((bb-aa).y,-(bb-aa).x))/L
    for j in range(max(2,round(L/1.6))+1):
     q=aa+(bb-aa)*j/max(2,round(L/1.6))-normal*.24
     P(tag+'_rail_posts','silver',c+'_04_stepped_roofs',asset).beam((q.x,q.y,hi+.12),(q.x,q.y,hi+1.0),.045)
    aa-=normal*.24;bb-=normal*.24
    P(tag+'_rail_top','silver',c+'_04_stepped_roofs',asset).beam((aa.x,aa.y,hi+1.0),(bb.x,bb.y,hi+1.0),.045)
 # Individuallypositionedserviceheads visibleaboveflatsetbackroofs.
 specs={'105':[(-61,-11,8.4,7.2,112.85,118.65)],'106':[(-1,-9,8.5,7.0,112.85,118.65)]}[n]
 for k,(x,y,w,d,z,top)in enumerate(specs):
  angle=.33 if n=='105'else .365;u=Vector((math.cos(angle),math.sin(angle)));v=Vector((-u.y,u.x));ce=Vector((x,y));r=ccw([tuple(ce+u*xx+v*yy)for xx,yy in[(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]])
  P(n+'_roof_service'+str(k),'dark_panel',c+'_05_photo_serviceheads',asset).prism(r,z,top)
  for aa,bb in zip(r,r[1:]+r[:1]):
   aa,bb=Vector(aa),Vector(bb);L=(bb-aa).length;vv=(bb-aa).normalized()
   for j in range(max(3,round(L/.9))+1):
    q=aa+(bb-aa)*j/max(3,round(L/.9));P(n+'_roof_vertical_metal_fins','bronze',c+'_05_photo_serviceheads',asset).face(q-vv*.05,q+vv*.05,z,top,.15,.09)
   P(n+'_thin_copper_top','bronze_light',c+'_05_photo_serviceheads',asset).face(aa,bb,top-.12,top+.10,.35,.12)

objs=[b.finish()for b in B.values()if b.f]
for o in objs:o['evidence']='evidence-ledger.json';o['height_datum']=D['heightDatum']
validation=[]
for n in D['towers']:
 id='bespoke-raemian-onepentas-'+n;selected=[o for o in objs if o['asset_id']==id];bpy.ops.object.select_all(action='DESELECT');verts=[];faces=[];face_mats=[];used=[]
 for o in selected:
  offset=len(verts);verts += [tuple(o.matrix_world@v.co)for v in o.data.vertices];mat=o.data.materials[0]
  if mat not in used:used.append(mat)
  mi=used.index(mat)
  for f in o.data.polygons:faces.append(tuple(offset+i for i in f.vertices));face_mats.append(mi)
 me=bpy.data.meshes.new(id+'_export_batch');me.from_pydata(verts,[],faces);me.update()
 for mat in used:me.materials.append(mat)
 for f,mi in zip(me.polygons,face_mats):f.material_index=mi
 ob=bpy.data.objects.new(id+'_export_batch',me);bpy.context.scene.collection.objects.link(ob);ob.select_set(True);bpy.context.view_layer.objects.active=ob;glb=OUT/(id+'.glb');bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_yup=True,export_apply=True);bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(me)
 coords=[o.matrix_world@v.co for o in selected for v in o.data.vertices];bounds=[[min(v[i]for v in coords)for i in range(3)],[max(v[i]for v in coords)for i in range(3)]]
 validation.append({'id':id,'boundsBlender':bounds,'sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'bytes':glb.stat().st_size,'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons)for o in selected),'editableMeshes':len(selected),'materialCount':len(used),'finiteNormals':all(math.isfinite(v)for o in selected for p in o.data.polygons for v in p.normal)})
(OUT/'geometry-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=20;world=scene.world or bpy.data.worlds.new('OnePentas_review_world');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.82,.95,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65
ld=bpy.data.lights.new('OnePentas_review_sun','SUN');lo=bpy.data.objects.new('OnePentas_review_sun',ld);col('90_review_only').objects.link(lo);lo.rotation_euler=(.50,-.50,-.50);ld.energy=2.;ld.angle=.12
cam=bpy.data.cameras.new('OnePentas_comparison_camera');co=bpy.data.objects.new('OnePentas_comparison_camera',cam);col('90_review_only').objects.link(co);scene.camera=co;cam.type='PERSP';cam.lens=45;co.location=(200,155,85);co.rotation_euler=(Vector((-35,-12,58))-co.location).to_track_quat('-Z','Y').to_euler();scene.render.resolution_x=1600;scene.render.resolution_y=1300;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'raemian-onepentas.blend'));print(json.dumps(validation))
