"""Photo-authored Lotte Castle Empire, individual two-tower and low wing reconstruction.
Run through the isolated live Blender MCP. Evidence/source rings live beside this file.
No source photo textures or pre-existing GLB is loaded. Invisible roof details remain estimates.
"""
from pathlib import Path
import bpy,bmesh,json,math,hashlib
from mathutils import Vector,Matrix
from mathutils.geometry import tessellate_polygon
OUT=Path(__file__).resolve().parent;D=json.loads((OUT/'source-evidence.json').read_text());A=D['coordinate'];LON=A['lon'];LAT=A['lat']
U=Vector((.61,-.792401413));U.normalize();V=Vector((-U.y,U.x));PITCH=118/37
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
 if c.name!='Collection':bpy.data.collections.remove(c)
for pool in (bpy.data.meshes,bpy.data.curves,bpy.data.materials,bpy.data.cameras,bpy.data.lights):
 for block in list(pool):
  if block.users==0:pool.remove(block)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.preferences.filepaths.save_version=0
palette={'glass_teal':(.22,.39,.39,1),'glass_blue':(.20,.32,.37,1),'glass_light':(.35,.47,.46,1),'spandrel':(.16,.29,.30,1),'frame':(.66,.68,.62,1),'major_frame':(.74,.74,.65,1),'dark_recess':(.045,.074,.078,1),'vent':(.13,.16,.145,1),'roof':(.29,.32,.29,1),'stone':(.49,.48,.40,1),'shop_glass':(.18,.30,.29,1),'brass':(.48,.34,.14,1)}
M={}
for n,color in palette.items():
 m=bpy.data.materials.new('Empire_'+n);m.diffuse_color=color;m.use_nodes=True;bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=color;bs.inputs['Roughness'].default_value=.30 if 'glass' in n else .57;bs.inputs['Metallic'].default_value=.15 if 'frame' in n else .08;M[n]=m
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
  a,b=Vector(a),Vector(b);u=(b-a).normalized();n=Vector((u.y,-u.x));self.prism([a+n*off,b+n*off,b+n*(off+depth),a+n*(off+depth)],z0,z1)
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
def ring(row):
 r=[((x-LON)*111320*math.cos(math.radians(LAT)),(y-LAT)*111320) for x,y in row['geometry']['coordinates'][0][:-1]]
 if sum(r[i][0]*r[(i+1)%len(r)][1]-r[(i+1)%len(r)][0]*r[i][1] for i in range(len(r)))<0:r.reverse()
 return r
def centroid(r):
 cr=[r[i][0]*r[(i+1)%len(r)][1]-r[(i+1)%len(r)][0]*r[i][1] for i in range(len(r))];a=sum(cr)*3
 return Vector((sum((r[i][0]+r[(i+1)%len(r)][0])*cr[i] for i in range(len(r)))/a,sum((r[i][1]+r[(i+1)%len(r)][1])*cr[i] for i in range(len(r)))/a))
def clip(r,axis,limit,less=True):
 out=[]
 for a,b in zip(r,r[1:]+r[:1]):
  da=Vector(a).dot(axis)-limit;db=Vector(b).dot(axis)-limit;ina=da<=1e-7 if less else da>=-1e-7;inb=db<=1e-7 if less else db>=-1e-7
  if ina:out.append(a)
  if ina!=inb:out.append(tuple(Vector(a)+(Vector(b)-Vector(a))*(da/(da-db))))
 return out
recipe={'siteId':D['siteId'],'coordinate':A,'roofConvention':'126m jointregister height used nominalhighestglazedroof; steppedfloors inferredfromphotos notmeasuredper-arm. No additional tallroofroom invented.','towerBands':[],'slopedRoofConnections':{'basis':'Visibletrianglebehindsteppedfrontof101inMitsubishifullphotocrop;onlyapproximateconnectinggeometry,notmeasuredwholeroof.','riseOverRunEstimate':1.18,'sideInsetVLimitM':16.9,'hiddenRearGeometry':'Simplified;exactplantandaccesspathsnotasserted'},'uncertainties':D['unresolved']}
for row,sign,num in [(D['footprints'][0],-1,'101'),(D['footprints'][1],1,'102')]:
 asset='bespoke-lotte-castle-empire-'+num;r=ring(row);cen=centroid(r);axis=U;origin=cen.dot(axis);cs='Empire_'+num
 # Photo-visible open slot cut out of the body, not a dark decal.
 slot_original_edge=1 if num=='101' else 0;sa=Vector(r[slot_original_edge]);sb=Vector(r[(slot_original_edge+1)%len(r)]);su=(sb-sa).normalized();sn=Vector((su.y,-su.x));sq=(sa+sb)/2;sw=1.35;depth=1.05
 q0=sq-su*sw/2;q1=sq+su*sw/2;slot_front_a=q0.copy();slot_front_b=q1.copy();d0=q0-sn*depth;d1=q1-sn*depth
 r=r[:slot_original_edge+1]+[tuple(q0),tuple(d0),tuple(d1),tuple(q1)]+r[slot_original_edge+1:]
 slot_pairs={(tuple(round(t,5) for t in a),tuple(round(t,5) for t in b)) for a,b in [(q0,d0),(d0,d1),(d1,q1)]}

 # Both towers rise toward the sameSEworlddirection: pairedphotos reject mirrored101draft.
 bands=[(-100,-12,126-7*PITCH),(-12,-3,126-5*PITCH),(-3,6,126-3*PITCH),(6,15,126-PITCH),(15,100,126)]
 recipe['towerBands'].append({'tower':num,'footprintId':row['id'],'roofRiseAxisEastNorth':list(axis),'centerEastNorth':list(cen),'bandsOutwardMHeightM':bands,'basis':'Mitsubishi labeledSEfront102andbehind101 plusoppositeauction2023-13bothsupportsameworldSErise;exactstepplanesestimated.','openSlotWidthDepthMEstimate':[1.35,1.05]})
 P(num+'_ground_support_inside_shared_plinth','stone',cs+'_01_support',asset).prism([tuple(cen+(Vector(p)-cen)*.96) for p in r],0,8)
 for bi,(lo,hi,h) in enumerate(bands):
  rr=clip(clip(r,axis,origin+lo,False),axis,origin+hi,True)
  if len(rr)<3:continue
  P(num+'_stepped_curtainwall_body','glass_teal',cs+'_02_stepped_envelope',asset).prism(rr,8,h)
  P(num+'_exposed_terrace_'+str(bi),'roof',cs+'_03_roof_terraces',asset).prism(rr,h+.012,h+.05)
  # Horizontal parapet line deliberately thin; photos have no giant solid crown.
  for a,b in zip(rr,rr[1:]+rr[:1]):P(num+'_roof_edge_silver_lines','major_frame',cs+'_03_roof_terraces',asset).face(a,b,h-.13,h+.16,.10,.01)
 # At each terrace the newly exposed set-back vertical wall is glazed, not a blank box riser.
 for j in range(1,len(bands)):
  cut=bands[j][0];zlow=bands[j-1][2];zhigh=bands[j][2];rr=clip(clip(r,axis,origin+cut,False),axis,origin+bands[j][1],True)
  for aa,bb in zip(rr,rr[1:]+rr[:1]):
   aa,bb=Vector(aa),Vector(bb)
   if abs(aa.dot(axis)-origin-cut)>.001 or abs(bb.dot(axis)-origin-cut)>.001:continue
   uu=(bb-aa).normalized();le=(bb-aa).length;bay=max(1,round(le/1.62))
   P(num+'_terrace_riser_glass','glass_blue',cs+'_03_roof_terraces',asset).face(aa,bb,zlow+.10,zhigh,.035,.07)
   for k in range(bay+1):
    q=aa+(bb-aa)*k/bay;P(num+'_terrace_riser_vertical_frames','frame',cs+'_03_roof_terraces',asset).face(q-uu*.04,q+uu*.04,zlow+.08,zhigh,.09,.13)
   for f in range(37):
    zz=8+f*PITCH
    if zlow<zz<zhigh:P(num+'_terrace_riser_horizontal_frames','frame',cs+'_03_roof_terraces',asset).face(aa,bb,zz-.04,zz+.04,.07,.13)
 # Photographed triangularglazed roofconnections; runs/slope are estimates, not an as-builtsection.
 for j in range(1,len(bands)):
  cut=bands[j][0];zl=bands[j-1][2];zh=bands[j][2];run=(zh-zl)/1.18;lo=origin+cut-run;hi=origin+cut
  rr=clip(clip(r,axis,lo,False),axis,hi,True)
  # Keepouterwallstep silhouette; the roof slope sits justbehindits curtainwallplane.
  rr=clip(clip(rr,V,cen.dot(V)-16.9,False),V,cen.dot(V)+16.9,True)
  if len(rr)<3:continue
  elev=lambda p:zl+.11+(Vector(p).dot(axis)-lo)/(hi-lo)*(zh-zl)
  points=[(p[0],p[1],elev(p)) for p in rr]
  P(num+'_photo_triangular_glazed_roof_connections','glass_blue',cs+'_07_sloped_roof_glass',asset).surface(points,.06)
  for a,b in zip(points,points[1:]+points[:1]):
   P(num+'_sloped_roof_edge_frames','major_frame',cs+'_07_sloped_roof_glass',asset).beam(a,b,.095)
   if abs(a[2]-b[2])>.1:
    n=Vector((b[1]-a[1],a[0]-b[0],0)).normalized()
    side=[(a[0],a[1],zl+.11),(b[0],b[1],zl+.11),b,a]
    P(num+'_photo_triangular_glass_side_closures','glass_blue',cs+'_07_sloped_roof_glass',asset).plate(side,n,.05)
    P(num+'_triangular_roof_side_lower_frame','frame',cs+'_07_sloped_roof_glass',asset).beam(side[0],side[1],.07)
  # Parallelglasspanelmullions clippedagainstactualroofpolygon.
  for vv in [cen.dot(V)-16+i*1.7 for i in range(20)]:
   crosses=[]
   for a,b in zip(rr,rr[1:]+rr[:1]):
    aa,bb=Vector(a),Vector(b);da=aa.dot(V)-vv;db=bb.dot(V)-vv
    if da*db<0 or abs(da)<1e-7:
     t=da/(da-db) if abs(da-db)>1e-7 else 0;pt=aa+(bb-aa)*t;crosses.append(pt)
   if len(crosses)>=2:
    aa=min(crosses,key=lambda p:p.dot(axis));bb=max(crosses,key=lambda p:p.dot(axis))
    if (bb-aa).length>.1:P(num+'_sloped_roof_panel_mullions','frame',cs+'_07_sloped_roof_glass',asset).beam((aa.x,aa.y,elev(aa)+.04),(bb.x,bb.y,elev(bb)+.04),.06)
 # Perimeter broken at actualroofband boundaries; glazing follows its individual chamfered polygon.
 for ei,(aa,bb) in enumerate(zip(r,r[1:]+r[:1])):
  aa,bb=Vector(aa),Vector(bb)
  if (tuple(round(t,5) for t in aa),tuple(round(t,5) for t in bb)) in slot_pairs:continue
  seg=bb-aa;L=seg.length;u=seg.normalized();p=lambda t:aa+seg*t
  cuts=[0.,1.];du=seg.dot(axis)
  if abs(du)>1e-8:
   for cut in [-12,-3,6,15]:
    t=(origin+cut-aa.dot(axis))/du
    if 0<t<1:cuts.append(t)
  cuts.sort()
  for ta,tb in zip(cuts,cuts[1:]):
   mid=p((ta+tb)/2).dot(axis)-origin;h=next(h for lo,hi,h in bands if lo<=mid<=hi);a=p(ta);b=p(tb);le=(b-a).length
   P(num+'_e'+str(ei)+'_lower_glass','glass_teal',cs+'_04_facade_'+str(ei),asset).face(a,b,8,h-.18,.03,.055)
   # Single curtainwall floor rhythm is observed, not a catalogue window template.
   for f in range(37):
    z=8+f*PITCH
    if z>=h-.2:break
    P(num+'_e'+str(ei)+'_opaque_spandrels','spandrel',cs+'_04_facade_'+str(ei),asset).face(a,b,z,z+.56,.026,.09)
    for zz in (z,z+.56,z+PITCH*.81):
     if zz<h-.1:P(num+'_e'+str(ei)+'_floor_mullions','frame',cs+'_04_facade_'+str(ei),asset).face(a,b,zz-.035,zz+.035,.065,.13)
   bays=max(1,round(le/1.62))
   for k in range(bays):
    q0=a+(b-a)*k/bays;q1=a+(b-a)*(k+1)/bays
    # Sparse horizontal openable panels and pale reflected strips are photograph-specific interpretation.
    if (ei+k)%4==0:P(num+'_e'+str(ei)+'_pale_pane_stripes','glass_light',cs+'_04_facade_'+str(ei),asset).face(q0+u*.08,q1-u*.08,8,h-.2,.023,.095)
    for f in range(37):
     z=8+f*PITCH
     if z+PITCH>h+.01:break
     if (k%4==1 and f%3==1) or (k%5==3 and f%4==0):
      P(num+'_e'+str(ei)+'_operable_dark_panes','glass_blue',cs+'_04_facade_'+str(ei),asset).face(q0+u*.16,q1-u*.16,z+.76,z+1.36,.028,.14)
      P(num+'_e'+str(ei)+'_pane_sills','frame',cs+'_04_facade_'+str(ei),asset).face(q0+u*.16,q1-u*.16,z+.72,z+.77,.09,.13)
   for k in range(bays+1):
    q=a+(b-a)*k/bays;P(num+'_e'+str(ei)+'_vertical_mullions','frame',cs+'_04_facade_'+str(ei),asset).face(q-u*.042,q+u*.042,8,h+.12,.09,.14)
   for q in (a,b):P(num+'_e'+str(ei)+'_corner_silver_spines','major_frame',cs+'_04_facade_'+str(ei),asset).face(q-u*.075,q+u*.075,8,h+.15,.16,.16)
 # Floor slabs span the actualopennotch; the dark back is a metre behind the facade.
 q0,q1=slot_front_a,slot_front_b
 slotmid=sq.dot(axis)-origin;slotheight=next(h for lo,hi,h in bands if lo<=slotmid<=hi)
 P(num+'_deep_open_slot_back','dark_recess',cs+'_05_identifying_slots',asset).face(d0,d1,8,slotheight,.025,.015)
 for a,b in [(q0,d0),(d1,q1)]:P(num+'_deep_slot_pale_side_returns','major_frame',cs+'_05_identifying_slots',asset).face(a,b,8,slotheight,.05,.015)
 for f in range(1,37):
  zz=8+f*PITCH
  if zz>slotheight:break
  P(num+'_open_slot_individual_floor_slabs','major_frame',cs+'_05_identifying_slots',asset).prism([tuple(q0+sn*.06),tuple(q1+sn*.06),tuple(d1),tuple(d0)],zz-.16,zz+.06)
 for q in [q0,q1]:P(num+'_open_slot_outer_pale_jambs','major_frame',cs+'_05_identifying_slots',asset).face(q-su*.06,q+su*.06,8,slotheight,.15,.03)
 # The outerterminalface has a wider pale metal/service band distinct fromglass.
 outer_edges=[(Vector(a),Vector(b)) for a,b in zip(r,r[1:]+r[:1]) if abs((Vector(b)-Vector(a)).dot(axis))<1.0 and ((Vector(a)+Vector(b))/2-cen).dot(U*sign)>24]
 for a,b in outer_edges:
  uu=(b-a).normalized();q=a+(b-a)*.40;ww=.9;eh=next(h for lo,hi,h in bands if lo<=q.dot(axis)-origin<=hi)
  P(num+'_outer_end_broad_opaque_silver_service_band','frame',cs+'_06_opaque_service_band',asset).face(q-uu*ww/2,q+uu*ww/2,8,eh-.5,.15,.12)
  for f in range(37):
   zz=8+f*PITCH
   if zz+1.3>eh:break
   P(num+'_outer_end_small_service_openings','vent',cs+'_06_opaque_service_band',asset).face(q-uu*.26,q+uu*.26,zz+.65,zz+1.28,.035,.28)
   for dz in [0,.12,.24,.36,.48]:P(num+'_outer_end_louver_bars','major_frame',cs+'_06_opaque_service_band',asset).face(q-uu*.26,q+uu*.26,zz+.69+dz,zz+.72+dz,.055,.31)
# Original centralconnector body has 32m10F, begins above the8mcommon plinth.
asset='bespoke-lotte-castle-empire-common';r=ring(D['footprints'][2]);P('Empire_central_connector','glass_teal','Empire_common_01_connector',asset).prism(r,8,32)
for i,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 a,b=Vector(a),Vector(b);u=(b-a).normalized();L=(b-a).length
 for j in range(9):P('Empire_connector_floor_frames','frame','Empire_common_01_connector',asset).face(a,b,8+j*3-.055,8+j*3+.055,.12,.06)
 for j in range(max(1,round(L/1.7))+1):
  q=a+(b-a)*j/max(1,round(L/1.7));P('Empire_connector_uprights','frame','Empire_common_01_connector',asset).face(q-u*.05,q+u*.05,8,32,.10,.09)
P('Empire_connector_roof','roof','Empire_common_01_connector',asset).prism(r,32.012,32.045)
r=ring(D['footprints'][3]);P('Empire_source_two_storey_retail_podium','shop_glass','Empire_common_02_retail_plinth',asset).prism(r,0,8)
for i,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 a,b=Vector(a),Vector(b);u=(b-a).normalized();L=(b-a).length;n=Vector((u.y,-u.x))
 for z in (.2,3.55,6.95,7.85):P('Empire_retail_pale_horizontal_fascia','stone','Empire_common_02_retail_plinth',asset).face(a,b,z-.1,z+.1,.28,.12)
 for j in range(max(1,round(L/3.2))+1):
  q=a+(b-a)*j/max(1,round(L/3.2));P('Empire_retail_vertical_frames','frame','Empire_common_02_retail_plinth',asset).face(q-u*.055,q+u*.055,.1,7.8,.13,.18)
 for j in range(max(1,round(L/6.4))):
  q=a+(b-a)*(j+.5)/max(1,round(L/6.4));P('Empire_retail_recessed_entrance_glass','dark_recess','Empire_common_03_lobby_portals',asset).face(q-u*.92,q+u*.92,.05,2.85,.025,.26)
  for side in(-1,1):P('Empire_retail_gold_door_jambs','brass','Empire_common_03_lobby_portals',asset).face(q+u*(side*.90-.035),q+u*(side*.90+.035),0,2.95,.12,.31)
 # Shallow frontage eave, physically observed inSEprimaryphoto; no inventedneighborgeometry.
 if L>15:P('Empire_retail_thin_canopy','stone','Empire_common_02_retail_plinth',asset).face(a,b,3.05,3.20,1.0,.2)
P('Empire_retail_roof_slab','roof','Empire_common_02_retail_plinth',asset).prism(r,8.012,8.045)
objs=[b.finish() for b in B.values() if b.f]
for o in objs:o['evidence']='source-evidence.json';o['height_datum']='joint126mregistry+photoestimatedsteppedroof'
# Identifyingcomplexname, samephysicalsignage notadvertisements; letteringplacement reviewed asapproximate.
# Sharedretaillongsouthwestedgehaslargelettering; exactglyphstylenotasserted.
for idx in [3]:
 a,b=Vector(r[idx]),Vector(r[(idx+1)%len(r)]);u=(b-a).normalized();n=Vector((u.y,-u.x));q=(a+b)/2+n*.45
 cu=bpy.data.curves.new('Empire_name','FONT');cu.body='LOTTE CASTLE EMPIRE';cu.align_x='CENTER';cu.align_y='CENTER';cu.size=.68;cu.space_character=1.12;cu.extrude=.018
 ob=bpy.data.objects.new('Empire_observed_retail_sign',cu);col('Empire_common_04_observed_name').objects.link(ob);ob.location=(q.x,q.y,7.24);ob.rotation_euler=Matrix((Vector((u.x,u.y,0)),Vector((0,0,1)),Vector((n.x,n.y,0)))).transposed().to_euler();cu.materials.append(M['brass']);bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH');ob=bpy.context.object;ob['asset_id']=asset;objs.append(ob)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
validation=[]
for id in ['bespoke-lotte-castle-empire-101','bespoke-lotte-castle-empire-102','bespoke-lotte-castle-empire-common']:
 selected=[o for o in objs if o['asset_id']==id];bpy.ops.object.select_all(action='DESELECT')
 for o in selected:o.select_set(True)
 glb=OUT/(id+'.glb');bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_yup=True,export_apply=True)
 coords=[o.matrix_world@v.co for o in selected for v in o.data.vertices];bounds=[[min(v[i] for v in coords) for i in range(3)],[max(v[i] for v in coords) for i in range(3)]]
 rec={'id':id,'boundsBlender':bounds,'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in selected),'meshCount':len(selected),'sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'bytes':glb.stat().st_size,'finiteNormals':all(math.isfinite(v) for o in selected for p in o.data.polygons for v in p.normal)};assert rec['finiteNormals'] and abs(bounds[0][2])<.001;validation.append(rec)
(OUT/'geometry-validation.json').write_text(json.dumps(validation,indent=2)+'\n');(OUT/'recipe.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n')
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=20;world=scene.world or bpy.data.worlds.new('Empire_review_world');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.80,.87,.93,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65
ld=bpy.data.lights.new('Empire_review_sun','SUN');lo=bpy.data.objects.new('Empire_review_sun',ld);col('90_review_only').objects.link(lo);lo.rotation_euler=(.5,-.45,-.5);ld.energy=2.;ld.angle=.13
cam=bpy.data.cameras.new('Empire_comparison_camera');co=bpy.data.objects.new('Empire_comparison_camera',cam);col('90_review_only').objects.link(co);scene.camera=co;cam.type='ORTHO';cam.ortho_scale=173;co.location=(130,-170,140);co.rotation_euler=(Vector((0,0,62))-co.location).to_track_quat('-Z','Y').to_euler();scene.render.resolution_x=1500;scene.render.resolution_y=1400;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'lotte-castle-empire.blend'));print(json.dumps(validation))
