"""Galleria Palace: individually mapped A/B/C lobes and photo-visible façade assemblies.
Inputs contain actual retained rings; no generated apartment template or source photo textures.
Use isolated Blender MCP port9876. Roof cuts are documented photo/plan approximations.
"""
from pathlib import Path
import bpy,bmesh,json,math,hashlib
from mathutils import Vector,Matrix
from mathutils.geometry import tessellate_polygon
OUT=Path(__file__).resolve().parent;D=json.loads((OUT/'authored-input.json').read_text());A=D['coordinate'];LON=A['lon'];LAT=A['lat']
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
 if c.name!='Collection':bpy.data.collections.remove(c)
for pool in (bpy.data.meshes,bpy.data.curves,bpy.data.materials,bpy.data.cameras,bpy.data.lights):
 for block in list(pool):
  if block.users==0:pool.remove(block)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.preferences.filepaths.save_version=0
palette={'glass':(.085,.18,.255,1),'glass_sky':(.16,.29,.39,1),'glass_dark':(.11,.22,.29,1),'stone':(.56,.49,.38,1),'stone_light':(.68,.60,.47,1),'joint':(.36,.35,.30,1),'frame':(.40,.48,.50,1),'opening':(.065,.10,.12,1),'roof':(.30,.32,.31,1),'vent':(.21,.25,.25,1)}
M={}
for n,c in palette.items():
 m=bpy.data.materials.new('Galleria_'+n);m.diffuse_color=c;m.use_nodes=True;bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=c;bs.inputs['Roughness'].default_value=.30 if 'glass' in n else .67;bs.inputs['Metallic'].default_value=.12 if 'glass' in n or n=='frame' else .025;M[n]=m
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

def exterior_segments(poly):
 r=poly['ring']
 if poly.get('holes'):raise ValueError('holes require explicit triangulation')
 if sum(r[i][0]*r[(i+1)%len(r)][1]-r[(i+1)%len(r)][0]*r[i][1] for i in range(len(r)))<0:r=list(reversed(r))
 return r

def face_assembly(tag,asset,collection,a,b,h,style='residential',zbase=0):
 a,b=Vector(a),Vector(b);u=(b-a).normalized();L=(b-a).length
 if L<.15:return
 if style=='center_strip':
  half=L*.19;mid=(a+b)/2
  face_assembly(tag+'_left_stone_bank',asset,collection,a,mid-u*half,h,'stone_windows',zbase)
  face_assembly(tag+'_central_blue_bank',asset,collection,mid-u*half,mid+u*half,h,'curtain',zbase)
  face_assembly(tag+'_right_stone_bank',asset,collection,mid+u*half,b,h,'stone_windows',zbase)
  return
 glass=P(tag+'_blue_inset_glazing','glass',collection,asset);stone=P(tag+'_warm_stone_piers','stone',collection,asset);light=P(tag+'_pale_edge_frames','stone_light',collection,asset);frame=P(tag+'_silver_window_mullions','frame',collection,asset);dark=P(tag+'_opening_shadow','opening',collection,asset)
 bounds=[zbase]+[z for z in [5,10]+[10+(f-2)*2.95+(3 if f>=16 else 0) for f in range(3,50)] if zbase+.2<z<h-.2]+[h]
 if L<2.0:
  light.face(a,b,zbase,h,.12,.06);return
 glass.face(a,b,zbase,h,.05,.025)
 if style=='curtain':
  bays=max(1,round(L/1.85))
  for k in range(bays+1):
   q=a+(b-a)*k/bays;frame.face(q-u*.035,q+u*.035,zbase,h,.07,.11)
  for zz in bounds:frame.face(a,b,max(zbase,zz-.045),min(h,zz+.045),.065,.11)
  for q in(a,b):light.face(q-u*.26,q+u*.26,zbase,h,.28,.18)
  return
 # Photo-authored asymmetric bank: a continuous darkblue glazing strip on one
 # edge, a distinctly broader stone-framed window field on the rest of this face.
 # It is not a uniform full-width curtainwall. Source photographs show 2-3 small
 # casement panes inside broad horizontal windows and paired stone columns.
 strip=0 if style=='stone_windows' else min(5.4,max(2.1,L*.28));split=a+u*strip
 glass.face(a,split,zbase,h,.065,.09)
 n=max(1,round(strip/1.7))
 for j in range(n+1):
  q=a+u*(strip*j/n);frame.face(q-u*.035,q+u*.035,zbase,h,.07,.16)
 for lo,hi in zip(bounds,bounds[1:]):
  frame.face(a,split,lo+.08,min(hi,lo+.15),.07,.17)
  if hi-lo>2 and n>=2:
   q=a+u*(strip*.68);dark.face(q,q+u*.48,lo+.34,min(hi-.14,lo+1.10),.018,.20)
   frame.face(q,q+u*.48,lo+.31,lo+.36,.04,.23)
 for q in(a,split):light.face(q-u*.40,q+u*.40,zbase,h,.33,.18)
 rest=L-strip
 if rest>.25:
  bays=max(1,round(rest/4.4))
  for j in range(bays):
   aa=split+u*(rest*j/bays);bb=split+u*(rest*(j+1)/bays)
   # wider warm masonry piers separate these banks from blue vertical strips
   for q in(aa,bb):stone.face(q-u*.29,q+u*.29,zbase,h,.32,.18)
   for lo,hi in zip(bounds,bounds[1:]):
    if hi-lo<.20:continue
    stone.face(aa,bb,lo,min(hi,lo+.91),.23,.14)
    # split-pane hierarchy: one broad fixed light with narrower two-part opener
    for t in(.62,.83):
     q=aa+(bb-aa)*t;frame.face(q-u*.026,q+u*.026,lo+.91,hi-.10,.05,.20)
    frame.face(aa+u*.29,bb-u*.29,hi-.13,hi-.07,.05,.20)
    q=aa+(bb-aa)*.83;frame.face(q,bb-u*.29,lo+1.58,min(hi-.1,lo+1.63),.045,.22)
    P(tag+'_stone_bed_joints','joint',collection,asset).face(aa,bb,lo+.865,lo+.885,.01,.38)
 light.face(a,b,h-.52,h,.28,.20)

# Source rings and explicit individual region heights, never a common box silhouette.
for tower,rec in D['towerMap'].items():
 asset='bespoke-galleria-palace-'+tower.lower();base=ring(rec['row']);cc='Galleria_'+tower
 P(tower+'_ground_storey','glass_dark',cc+'_01_base',asset).prism(base,0,10)
 for i,(aa,bb) in enumerate(zip(base,base[1:]+base[:1])):
  face_assembly(tower+'_base_edge'+str(i),asset,cc+'_01_base',aa,bb,10,'curtain')
 for region in D['regions'][tower]:
  h=region['height'];name=region['name']
  for pi,poly in enumerate(region['polygons']):
   r=exterior_segments(poly);P(name+'_actual_outline','glass',cc+'_02_individual_roof_levels',asset).prism(r,10,h)
   P(name+'_terrace','roof',cc+'_03_terraces',asset).prism(r,h+.015,h+.08)
   for ei,(aa,bb) in enumerate(zip(r,r[1:]+r[:1])):
    # Region-internal boundary needs glazing only on the exposed upper difference.
    mid=(Vector(aa)+Vector(bb))/2;external=False
    for sa,sb in zip(base,base[1:]+base[:1]):
     sa,sb=Vector(sa),Vector(sb);v=sb-sa;t=max(0,min(1,(mid-sa).dot(v)/v.length_squared))
     if (mid-(sa+v*t)).length<.02:external=True;break
    zbase=10 if external else min(h,131.0)
    upper_end=False
    if h-zbase>.1:
     # Explicit northern narrow cap faces and southeast chamfers retain glass.
     L=(Vector(bb)-Vector(aa)).length;style='curtain' if (4<L<9 and abs((Vector(bb)-Vector(aa)).y)<L*.45) else 'residential'
     # Identified HeeRim21 courtyard neck: centred glazing with stone windows on both sides.
     if tower=='A' and name=='A_neck42_lines5to6' and mid.y<33:style='center_strip'
     # Identified HeeRim23 C-west projecting end: about six upperlevels continuously
     # glazed including the crown. Do not cover it with thick residentialspandrels.
     upper_end=False
     if tower=='C' and name.startswith('C_W'):
      ea,eb=Vector(base[18]),Vector(base[19]);ev=eb-ea;et=max(0,min(1,(mid-ea).dot(ev)/ev.length_squared))
      upper_end=(mid-(ea+ev*et)).length<.025
     if upper_end:
      face_assembly(name+'_e'+str(ei),asset,cc+'_04_stone_and_glass_banks',aa,bb,131.0,style,zbase)
      # The seatedcontinuouscrown owns thisupperface, avoiding doubled insetframes.
     else:face_assembly(name+'_e'+str(ei),asset,cc+'_04_stone_and_glass_banks',aa,bb,h,style,zbase)
    if not (tower=='C' and name.startswith('C_W') and upper_end):
     P(tower+'_terrace_pale_coping','stone_light',cc+'_03_terraces',asset).face(aa,bb,h-.08,h+.20,.16,.025)
 # Vertical glass/stone crown assemblies, independently placed at photo/plan lobes.
 crown_specs={
  'A':[{'center':(-60.3,44.0),'size':(10.6,7.1),'angle':.15,'floor':142.8,'top':149.4,'slats':True},{'center':(-13.7,41.8),'size':(8.3,5.1),'angle':-.08,'floor':131.0,'top':135.7,'slats':False}],
  'B':[{'center':(32.4,46.9),'size':(9.5,6.2),'angle':.02,'floor':142.8,'top':149.4,'slats':True}],
  'C':[{'center':(-9.3,-31.0),'size':(7.7,7.5),'angle':-.71,'floor':142.8,'top':149.4,'slats':True},{'center':(39.5,-39.0),'size':(7.1,7.8),'angle':.73,'floor':142.8,'top':149.4,'slats':True}]
 }
 for k,cs in enumerate(crown_specs[tower]):
  x,y=cs['center'];w,d=cs['size'];ang=cs['angle'];u=Vector((math.cos(ang),math.sin(ang)));v=Vector((-u.y,u.x));ce=Vector((x,y));r=[tuple(ce+u*xx+v*yy) for xx,yy in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]];lo,hi=cs['floor'],cs['top'];name=tower+'_crown'+str(k)
  if tower=='C' and k==0:
   # HeeRim23 frontSW highend is sourceedge18->19. The earlier NW
   # protrusion hypothesis was rejected by explicitcamera vertexprojection.
   ea,eb=Vector(base[18]),Vector(base[19]);u=(eb-ea).normalized();v=Vector((-u.y,u.x));w=(eb-ea).length;d=6.5;ce=(ea+eb)/2+v*d/2;ang=math.atan2(u.y,u.x)
   r=[tuple(ea),tuple(eb),tuple(eb+v*d),tuple(ea+v*d)];lo=131.0;hi=149.4

  # Tall glazed cap seated on roof; a smaller open side canopy keeps daylight gaps.
  P(name+'_glazed_roof_cap','glass',cc+'_05_photo_crown',asset).prism(r,lo,hi-.45)
  for aa,bb in zip(r,r[1:]+r[:1]):
   face_assembly(name+'_cap',asset,cc+'_05_photo_crown',aa,bb,hi-.45,'curtain',lo)
   P(name+'_stone_top_border','stone_light',cc+'_05_photo_crown',asset).face(aa,bb,hi-.60,hi,.30,.10)
  if cs['slats']:
   # Sparse parallel beams, actual voids, not a dark solid roof decal.
   canopy=ce-v*(d/2+2.2);cw,cd=w,4.4
   if tower=='C' and k==0:canopy=ce+u*(w/2+2.2)+v*1.4;cw,cd=4.4,d
   canopy_hi=hi-(4.4 if tower=='C' and k==0 else 0) # HeeRim23: canopy1–2storeysbelowglasscaptop
   for xx in ((-cw/2,) if tower=='C' else (-cw/2,cw/2)):
    for yy in(-cd/2,cd/2):
     q=canopy+u*xx+v*yy;P(name+'_canopy_stone_supports','stone',cc+'_06_open_roof_canopies',asset).box(q.x,q.y,(lo+canopy_hi-.25)/2,.42,.42,canopy_hi-.25-lo,ang)
   for j in range(12):
    q=canopy+v*(-cd/2+cd*j/11);aa=q-u*cw/2;bb=q+u*cw/2
    P(name+'_open_louver_beams','frame',cc+'_06_open_roof_canopies',asset).beam((aa.x,aa.y,canopy_hi-.35),(bb.x,bb.y,canopy_hi-.35),.16)
   for xx in(-cw/2,cw/2):
    aa=canopy+u*xx-v*cd/2;bb=canopy+u*xx+v*cd/2;P(name+'_canopy_boundary','stone_light',cc+'_06_open_roof_canopies',asset).beam((aa.x,aa.y,canopy_hi-.35),(bb.x,bb.y,canopy_hi-.35),.38)

# The northern source parent includes a lower officetel band, not another149m slab.
for idx,pod in enumerate(D['podiums']):
 asset='bespoke-galleria-palace-common';cc='Galleria_common';h=pod['height']
 for pi,poly in enumerate(pod['polygons']):
  r=exterior_segments(poly);name=pod['name']+str(pi)
  P(name+'_lower_envelope','glass',cc+'_01_lower_wings',asset).prism(r,0,h)
  P(name+'_roof','roof',cc+'_02_low_roof',asset).prism(r,h+.01,h+.08)
  for ei,(aa,bb) in enumerate(zip(r,r[1:]+r[:1])):
   face_assembly(name+'_e'+str(ei),asset,cc+'_03_projecting_stone_frames',aa,bb,h,'residential')
   P(name+'_thick_frame_coping','stone_light',cc+'_03_projecting_stone_frames',asset).face(aa,bb,max(0,h-1.65),h,.48,.13)
   aa,bb=Vector(aa),Vector(bb);u=(bb-aa).normalized()
   if (bb-aa).length>12:
    for q in(aa,bb):P(name+'_broad_podium_stone_jambs','stone_light',cc+'_03_projecting_stone_frames',asset).face(q-u*.68,q+u*.68,0,h,.48,.13)
 # No ornamentalgroundplane orneighborstructures added.
objs=[b.finish() for b in B.values() if b.f]
for o in objs:o['asset_id']=o['asset_id'];o['evidence']='authored-input.json';o['height_datum']='joint149.4m; photoestimatedroofandmechlevels'
bpy.ops.object.select_all(action='DESELECT')
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
validation=[]
for id in ['bespoke-galleria-palace-a','bespoke-galleria-palace-b','bespoke-galleria-palace-c','bespoke-galleria-palace-common']:
 selected=[o for o in objs if o['asset_id']==id];bpy.ops.object.select_all(action='DESELECT')
 # Export-only batching preserves every authored triangle/material while the
 # editable scene keeps named site/component collections. No map drawcall explosion.
 verts=[];faces=[];face_mats=[];used=[]
 for o in selected:
  offset=len(verts);verts += [tuple(o.matrix_world@v.co) for v in o.data.vertices]
  mat=o.data.materials[0]
  if mat not in used:used.append(mat)
  mi=used.index(mat)
  for f in o.data.polygons:faces.append(tuple(offset+i for i in f.vertices));face_mats.append(mi)
 me=bpy.data.meshes.new(id+'_export_batch');me.from_pydata(verts,[],faces);me.update()
 for mat in used:me.materials.append(mat)
 for f,mi in zip(me.polygons,face_mats):f.material_index=mi
 export_ob=bpy.data.objects.new(id+'_export_batch',me);scene_collection=bpy.context.scene.collection;scene_collection.objects.link(export_ob);export_ob.select_set(True);bpy.context.view_layer.objects.active=export_ob
 glb=OUT/(id+'.glb');bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_yup=True,export_apply=True)
 bpy.data.objects.remove(export_ob,do_unlink=True);bpy.data.meshes.remove(me)
 coords=[o.matrix_world@v.co for o in selected for v in o.data.vertices];bounds=[[min(v[i] for v in coords) for i in range(3)],[max(v[i] for v in coords) for i in range(3)]]
 rec={'id':id,'boundsBlender':bounds,'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in selected),'editableMeshCount':len(selected),'exportMeshCount':1,'materialCount':len(used),'sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'bytes':glb.stat().st_size,'finiteNormals':all(math.isfinite(v) for o in selected for p in o.data.polygons for v in p.normal)};assert rec['finiteNormals'] and abs(bounds[0][2])<.001;validation.append(rec)
(OUT/'geometry-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
(OUT/'recipe.json').write_text(json.dumps({'siteId':D['siteId'],'coordinate':A,'status':'v9_photo_review_corrections_complete_pending_freeze','regions':D['regions'],'heightDatum':D['heightDatum'],'uncertainties':['Exact roofcap/slatdimensions estimated fromphotos.','Republishedroofplanheightlabels rejected wherecontradictingcompletedphoto/CODIL.','B/C letters inferred fromuniqueplan/towercount; exactmarkedsiteplan notfound.','Apartment/officetel flooruses unverified.','Hiddenroofservices and courtyardlandscape omitted.'],'photoSpecificFacadeCorrections':{'A_south_neck':'Sourceedge11–12: centredblueglassbank+stonewindowsbothsides','C_SW_upper_end':'Sourceedge18–19: continuousupperglazing131–149.4m. EarlierNWprojectionhypothesiswithdrawn aftercamera-vertexinspection.','C_canopy':'C_SWcantilever beamcentre144.65m,topapproximately144.84m below149.4mglazecap; sourcephotoapproximately1–2floorslower. Exactdimensionsestimated.'},'sourceFiles':['authored-input.json','build.py']},ensure_ascii=False,indent=2)+'\n')
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=20;world=scene.world or bpy.data.worlds.new('Galleria_review_world');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.78,.86,.95,1);world.node_tree.nodes['Background'].inputs[1].default_value=.6
ld=bpy.data.lights.new('Galleria_review_sun','SUN');lo=bpy.data.objects.new('Galleria_review_sun',ld);col('90_review_only').objects.link(lo);lo.rotation_euler=(.50,-.50,-.50);ld.energy=2.;ld.angle=.12
cam=bpy.data.cameras.new('Galleria_comparison_camera');co=bpy.data.objects.new('Galleria_comparison_camera',cam);col('90_review_only').objects.link(co);scene.camera=co;cam.type='PERSP';cam.lens=45;co.location=(-210,-220,18);co.rotation_euler=(Vector((-3,-7,74))-co.location).to_track_quat('-Z','Y').to_euler();scene.render.resolution_x=1500;scene.render.resolution_y=1600;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'galleria-palace.blend'));print(json.dumps(validation))
