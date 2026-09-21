import bpy, json, math
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
P=Path(__file__).parent
DATA=json.loads((P/'selected-input.json').read_text())['sites']
REC=json.loads((P/'design-recipes.json').read_text())
OUT=P/'outputs';OUT.mkdir(exist_ok=True)
exec((P/'export-compact.py').read_text(),globals())
for ob in list(bpy.data.objects):bpy.data.objects.remove(ob,do_unlink=True)
for c in list(bpy.data.collections):
 if not c.objects and not c.children:bpy.data.collections.remove(c)
def collection(name):
 c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c
def material(name,rgb,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*rgb,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*rgb,1);bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=.3 if metal else .72
 return m
class Mesh:
 def __init__(self,name,mats):self.name=name;self.v=[];self.f=[];self.mi=[];self.mats=mats
 def face(self,p,m):
  k=len(self.v);self.v.extend(p);self.f.append(tuple(range(k,k+len(p))));self.mi.append(m)
 def prism(self,pts,z0,z1,m):
  if z1<=z0:return
  pts=list(pts)
  if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts,pts[1:]+pts[:1]))<0:pts.reverse()
  for a,b in zip(pts,pts[1:]+pts[:1]):self.face([(*a,z0),(*b,z0),(*b,z1),(*a,z1)],m)
  vec=[Vector((*p,0)) for p in pts]
  for tri in tessellate_polygon([vec]):
   tri=[vec[v] if isinstance(v,int) else v for v in tri]
   self.face([(v.x,v.y,z1) for v in tri],m);self.face([(v.x,v.y,z0) for v in reversed(tri)],m)
 def edge(self,a,b,z0,z1,m,depth=.12,off=.02):
  L=math.dist(a,b)
  if L<.01:return
  nx=(b[1]-a[1])/L;ny=(a[0]-b[0])/L
  if m==3 or depth<=.35:
   self.face([(a[0]+nx*(off+depth),a[1]+ny*(off+depth),z0),(b[0]+nx*(off+depth),b[1]+ny*(off+depth),z0),(b[0]+nx*(off+depth),b[1]+ny*(off+depth),z1),(a[0]+nx*(off+depth),a[1]+ny*(off+depth),z1)],m);return
  self.prism([(a[0]+nx*off,a[1]+ny*off),(b[0]+nx*off,b[1]+ny*off),(b[0]+nx*(off+depth),b[1]+ny*(off+depth)),(a[0]+nx*(off+depth),a[1]+ny*(off+depth))],z0,z1,m)
 def finish(self,c):
  me=bpy.data.meshes.new(self.name);me.from_pydata(self.v,[],self.f);me.update()
  for m in self.mats:me.materials.append(m)
  for p,m in zip(me.polygons,self.mi):p.material_index=m
  ob=bpy.data.objects.new(self.name,me);c.objects.link(ob);return ob
def lerp(a,b,t):return tuple(a[i]+(b[i]-a[i])*t for i in range(2))
def shrink(r,s):
 x=sum(p[0] for p in r)/len(r);y=sum(p[1] for p in r)/len(r)
 return [(x+(p[0]-x)*s,y+(p[1]-y)*s) for p in r]
records=[];groups=[]
for S in DATA:
 if (P.parents[2]/'STOP').exists() or (P/'STOP').exists():raise RuntimeError('Local STOP file')
 code=S['code'];r=REC.get(code)
 if not r or r.get('skip'):records.append({'code':code,'status':'blocked','reason':(r or {}).get('reason','No validated visual reference')});continue
 C=collection(code+' '+S['name']);objects=[];built=[]
 mats=[material(code+' '+n,r[n],.35 if n=='glass' else 0) for n in ['wall','trim','accent','glass','base','roof']]
 mats.append(material(code+' red crown trim',(.43,.09,.065)))
 for ti,T in enumerate(S['towers']):
  pts=[tuple(p) for p in T['ringEastNorthM']]
  if pts[0]==pts[-1]:pts=pts[:-1]
  if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts,pts[1:]+pts[:1]))<0:pts.reverse()
  h=T.get('height_m');floors=T.get('num_floors')
  if not h and floors and r.get('allow_height_estimate'):h=floors*3.0
  if not h or h<6:continue
  floors=floors or max(2,round(h/3));zbase=min(4.0,h*.10);fh=(h-zbase)/floors
  body=Mesh(f'{ti+1:02}_retained_footprint_shell',mats);fac=Mesh(f'{ti+1:02}_representative_facade',mats);roof=Mesh(f'{ti+1:02}_roof_profile',mats);base=Mesh(f'{ti+1:02}_entrance_piers',mats)
  body.prism(pts,zbase,h,0);body.prism(pts,0,zbase,4)
  edges=list(zip(pts,pts[1:]+pts[:1]));longest=max(math.dist(a,b) for a,b in edges)
  for ei,(a,b) in enumerate(edges):
   L=math.dist(a,b)
   if L<2:continue
   bays=max(1,round(L/r.get('bay',3.1)));endwall=L<min(16,longest*r.get('blank_ratio',.55))
   if endwall:
    fac.edge(lerp(a,b,.08),lerp(a,b,.92),zbase,h-1,(2 if ti%2 else 5) if code=='A10024831' else 0,.08)
    if r.get('red_endframe'):
     fac.edge(lerp(a,b,.03),lerp(a,b,.12),zbase,h+1.4,6,.25)
     roof.edge(a,b,h+1.25,h+1.7,6,.6)
     if code=='A10024925':
      for fl in range(floors):fac.edge(a,b,zbase+fl*fh,zbase+fl*fh+.10,1,.025,.13)
    if r.get('end_accent'):fac.edge(a,b,zbase,h-.2,2,.10)
    if r.get('end_stripe'):fac.edge(lerp(a,b,.62),lerp(a,b,.75),zbase,h-.2,2,.12)
    if r.get('end_patch'):fac.edge(lerp(a,b,.63),lerp(a,b,.96),zbase,h*.65,2,.12)
    for f in range(floors) if r.get('blank_windows') and ei%3==0 else []:
     z=zbase+f*fh;fac.edge(lerp(a,b,.44),lerp(a,b,.57),z+fh*.3,z+fh*.82,3,.04,.3)
   else:
    if r.get('whole_accent_face') and ei%3==1 and not r.get('red_endframe'):fac.edge(a,b,zbase,h-.2,2,.10)
    if r['style'] in ['corridor','mido'] and ei%2==0:
     for f in range(floors):
      z=zbase+f*fh;fac.edge(a,b,z+fh*.43,z+fh*.88,3,.04,.14);fac.edge(a,b,z+fh*.08,z+fh*.43,1,.03,.21)
     for t in [.18,.5,.82]:fac.edge(lerp(a,b,t-.02),lerp(a,b,t+.02),zbase,h,2 if code=='A15884703' else 0,.05,.22)
     bays=0
    for k in range(bays):
     u=(k+r.get('window_margin',.18))/bays;v=(k+1-r.get('window_margin',.18))/bays
     if r.get('stone_base_floors'):fac.edge(lerp(a,b,k/bays),lerp(a,b,(k+1)/bays),zbase,zbase+r['stone_base_floors']*fh,4,.10)
     if r.get('accent_stacks') and k%3==1:fac.edge(lerp(a,b,k/bays),lerp(a,b,(k+1)/bays),zbase,h-.2,2,.12)
     # Broad representative apartment window stacks, with physical mullions/reveals.
     if r['style']=='vertical':fac.edge(lerp(a,b,u-.035/bays),lerp(a,b,v+.035/bays),zbase,h-.2,1,.22)
     for f in range(floors):
      z=zbase+f*fh
      fac.edge(lerp(a,b,u),lerp(a,b,v),z+fh*.24,min(h-.15,z+fh*.86),3,.10,.25)
      fac.edge(lerp(a,b,(u+v)/2-.025/max(1,bays)),lerp(a,b,(u+v)/2+.025/max(1,bays)),z+fh*.24,min(h-.15,z+fh*.86),1,.04,.36)
      if r.get('balconies') and k%3==1 and ei%2==0:
       fac.edge(lerp(a,b,u-.06/bays),lerp(a,b,v+.06/bays),z+.12,z+.32,1,r.get('balcony_depth',.95))
       fac.edge(lerp(a,b,u-.06/bays),lerp(a,b,v+.06/bays),z+.32,z+1.15,3,.04,r.get('balcony_depth',.95)-.05)
      if r['style']=='bands':fac.edge(lerp(a,b,k/bays),lerp(a,b,(k+1)/bays),z,z+.24,1,.28)
      if r['style']=='frames' and f%4==0:fac.edge(lerp(a,b,k/bays),lerp(a,b,(k+1)/bays),z,z+.48,1,.32)
     if r['style'] in ['frames','piers'] and k%2==0:fac.edge(lerp(a,b,k/bays),lerp(a,b,min(1,k/bays+.035)),zbase,h,1 if r['style']=='frames' else 2,.35)
    for f in range(1,floors):
     if r['style']=='grid':fac.edge(a,b,zbase+f*fh,zbase+f*fh+.11,1,.15)
   for t in []:
    q=lerp(a,b,t);base.prism([(q[0]-.4,q[1]-.4),(q[0]+.4,q[1]-.4),(q[0]+.4,q[1]+.4),(q[0]-.4,q[1]+.4)],0,zbase,4)
   roof.edge(a,b,h,h+.35,5 if code in ['A13778202','A13170401'] else 1,.20)
   if r['crown']=='louver' and L>=longest*.99:
    for band in range(6):roof.edge(a,b,h+.3+band*.28,h+.4+band*.28,5,.22)
   if r['crown']=='frame' and endwall and L>7:
    roof.edge(a,b,h+2.5,h+3.15,1,.48)
    for t in [.04,.96]:roof.edge(lerp(a,b,max(0,t-.025)),lerp(a,b,min(1,t+.025)),h,h+3.0,1,.45)
  if r.get('green_roofs') and h<30:roof.prism(shrink(pts,.92),h+.05,h+.18,6)
  # Compact rooftop plant enclosure aligned to the dominant facade, not a scaled copy of the footprint.
  aa,bb=max(edges,key=lambda e:math.dist(*e));ux=(bb[0]-aa[0])/longest;uy=(bb[1]-aa[1])/longest
  cx=sum(x for x,y in pts)/len(pts);cy=sum(y for x,y in pts)/len(pts)
  rr=[(cx+ux*u-uy*v,cy+uy*u+ux*v) for u,v in [(-3,-2.4),(3,-2.4),(3,2.4),(-3,2.4)]]
  roof.prism(rr,h,h+r.get('roof_height',2),0 if code=='A13588402' else 5)
  if code=='A13588402':roof.prism(shrink(pts,.98),h+.02,h+.08,5)
  if r['crown']=='pitched':
   for a,b in edges:
    L=math.dist(a,b)
    if L<5:continue
    nx=-(b[1]-a[1])/L;ny=(b[0]-a[0])/L
    depth=min(7.0,L*.3)
    roof.face([(*a,h+.1),(*b,h+.1),(b[0]+nx*depth,b[1]+ny*depth,h+1.65),(a[0]+nx*depth,a[1]+ny*depth,h+1.65)],5)
  if r['crown']=='stepped':roof.prism(shrink(rr,.72),h+r.get('roof_height',2),h+r.get('roof_height',2)+.8,1)
  if r['crown']=='wave':
   for j in range(12):
    u=-4+j*8/12;v=-4+(j+1)*8/12
    def cp(t,d):return (cx+ux*t-uy*d,cy+uy*t+ux*d,h+3.6+.55*math.sin(t*math.pi/4))
    roof.face([cp(u,-2.7),cp(v,-2.7),cp(v,2.7),cp(u,2.7)],5)
   for t in [-3,3]:roof.prism([(cx+ux*t-.15,cy+uy*t-.15),(cx+ux*t+.15,cy+uy*t-.15),(cx+ux*t+.15,cy+uy*t+.15),(cx+ux*t-.15,cy+uy*t+.15)],h+2,h+3.5,5)
  if code=='A13987304':
   for k in range(3):
    xx=cx+k*.7;roof.prism([(xx-.05,cy-.05),(xx+.05,cy-.05),(xx+.05,cy+.05),(xx-.05,cy+.05)],h+1,h+2.5+k*.3,5)
  for m in [body,fac,roof,base]:
   ob=m.finish(C);ob['source_building_id']=T['id'];ob['source_height_m']=h;ob['representative_profile']=r['style'];objects.append(ob)
  built.append({'sourceId':T['id'],'sourceHeightM':T.get('height_m'),'modeledHeightM':h,'heightBasis':'source' if T.get('height_m') else '3m-per-source-floor estimate','floors':floors,'floorBasis':'source' if T.get('num_floors') else 'height-estimate','objects':4})
 if not built:bpy.data.collections.remove(C);records.append({'code':code,'status':'blocked','reason':'Missing usable source heights'});continue
 for ob in bpy.context.selected_objects:ob.select_set(False)
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
 objects[0]['wgs84_anchor']=json.dumps(S['anchor']);objects[0]['reference_evidence']=json.dumps(r['references'],ensure_ascii=False);objects[0]['status']='provisional representative reconstruction'
 export_compact(S,objects,OUT)
 labeldata=bpy.data.curves.new(code+' review label','FONT');labeldata.body=code;labeldata.size=7;labeldata.extrude=0
 label=bpy.data.objects.new(code+' REVIEW ONLY label',labeldata);C.objects.link(label);label.location=(-60,-135,.1);objects.append(label)
 groups.append((S,C,objects));records.append({'code':code,'name':S['name'],'status':'excluded_source_identity' if r.get('excluded') else 'provisional','anchor':S['anchor'],'design':r,'towers':built,'towerCount':len(built),'glb':str(OUT/(code+'.glb'))})
# Review scene: each site collection retains local coordinates and its WGS84 anchor.
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.65,.65,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
review=collection('REVIEW_CAMERA_LIGHTS')
ld=bpy.data.lights.new('Large softbox','AREA');lo=bpy.data.objects.new('Large softbox',ld);review.objects.link(lo);lo.location=(100,-150,400);ld.energy=2100;ld.shape='DISK';ld.size=250
sun=bpy.data.lights.new('Sun','SUN');sun.energy=3;so=bpy.data.objects.new('Sun',sun);review.objects.link(so);so.rotation_euler=(.4,-.5,-.4)
cam=bpy.data.cameras.new('Review camera');co=bpy.data.objects.new('Review camera',cam);review.objects.link(co);scene.camera=co;cam.type='ORTHO';cam.lens=45

def aim(cx,cy,z,span):
 co.location=(cx+span*.9,cy-span*1.1,z+span*.85);co.rotation_euler=(Vector((cx,cy,z))-co.location).to_track_quat('-Z','Y').to_euler();cam.ortho_scale=span*1.4;cam.clip_end=20000
for S,C,obs in groups:
 for _,cc,_ in groups:cc.hide_render=cc!=C
 allp=[v.co for ob in obs if ob.type=='MESH' for v in ob.data.vertices];xmin=min(v.x for v in allp);xmax=max(v.x for v in allp);ymin=min(v.y for v in allp);ymax=max(v.y for v in allp);h=max(v.z for v in allp)
 aim((xmin+xmax)/2,(ymin+ymax)/2,h*.35,max(xmax-xmin,ymax-ymin,h)*1.1)
 scene.render.filepath=str(OUT/(S['code']+'-overview.png'));bpy.ops.render.render(write_still=True)
 cx=(xmin+xmax)/2;cy=(ymin+ymax)/2;span=max(xmax-xmin,ymax-ymin,h)*1.1;co.location=(cx-span,cy+span,h*.45+span*.55);co.rotation_euler=(Vector((cx,cy,h*.40))-co.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/(S['code']+'-reverse.png'));bpy.ops.render.render(write_still=True)
# Spatial comparison contact render; restores local authoring coordinates afterward.
cols=math.ceil(math.sqrt(len(groups))) if groups else 1
for i,(S,C,obs) in enumerate(groups):
 C.hide_render=False
 for ob in obs:ob.location.x+=(i%cols)*350;ob.location.y-=(i//cols)*350
if groups:
 rows=math.ceil(len(groups)/cols);aim((cols-1)*175,-(rows-1)*175,25,max(cols,rows)*400 if len(groups)>1 else 390);scene.render.resolution_y=700;scene.render.filepath=str(OUT/'all-sites-contact.png');bpy.ops.render.render(write_still=True)
for i,(S,C,obs) in enumerate(groups):
 for ob in obs:ob.location.x-=(i%cols)*350;ob.location.y+=(i//cols)*350
 C.hide_render=i!=0;C.hide_viewport=i!=0
if groups:
 first=groups[0][2];pp=[v.co for ob in first if ob.type=='MESH' for v in ob.data.vertices];xx=[v.x for v in pp];yy=[v.y for v in pp];hh=max(v.z for v in pp);aim((min(xx)+max(xx))/2,(min(yy)+max(yy))/2,hh*.35,max(max(xx)-min(xx),max(yy)-min(yy),hh)*1.1)
scene['README']='Benchmark only. Site collections use individual local east/north metre coordinates with WGS84 anchors in each GLB and manifest. Toggle one site collection at a time. Representative facade details are provisional, not surveyed or exact window matches.'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'representative-batch14.blend'))
for record in records:
 (OUT/(record['code']+'-review.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
(OUT/'manifest.json').write_text(json.dumps({'sites':records,'modeledSites':len(groups),'modeledTowers':sum(x.get('towerCount',0) for x in records),'status':'photo-informed representative assets; geometry and geographic metadata verified separately; appearance approximation'},ensure_ascii=False,indent=2))
print(json.dumps({'modeledSites':len(groups),'modeledTowers':sum(x.get('towerCount',0) for x in records),'output':str(OUT)}))
