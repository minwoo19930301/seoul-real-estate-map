"""Individually authored Seoul City Hall ensemble; execute via real Blender MCP.
Photo/architect-plan interpretation, not measured CAD. No source photographs embedded.
"""
import bpy,bmesh,math,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/seoul-city-hall';OUT.mkdir(parents=True,exist_ok=True)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name!='Collection':bpy.data.collections.remove(c)
bpy.data.orphans_purge(do_recursive=True)
COL={};BUF={}
GROUPS=['New_01_Double_Curved_Glass','New_02_Triangulated_Steel','New_03_East_Lens_End','New_04_West_Lens_End','New_05_Suspended_Cultural_Hall','New_06_Rear_Office_and_Roof','New_07_Green_Wall_and_Entry','Old_01_Source_U_Footprint','Old_02_Stone_Facade','Old_03_Central_Portal','Old_04_Clock_Tower','Old_05_Roof_Terraces','QA']
for s in GROUPS:
 c=bpy.data.collections.new(s);bpy.context.scene.collection.children.link(c);COL[s]=c
NG,NS,NE,NW,NC,NR,NI,OB,OF,OP,OT,OR,QA=GROUPS
MAT={}
def mat(name,rgb,metal=0,rough=.65,alpha=1):
 m=bpy.data.materials.new(name);m.diffuse_color=(*rgb,alpha);m.use_nodes=True;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*rgb,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
 if alpha<1:
  p.inputs['Alpha'].default_value=alpha;m.surface_render_method='DITHERED';m.use_transparent_shadow=True
 MAT[name]=m;return name
stone=mat('Observed_warm_grey_granite',(.43,.39,.30));trim=mat('Light_limestone_cornices',(.57,.53,.43));joint=mat('Recessed_stone_courses',(.27,.25,.21));oldglass=mat('Historic_dark_green_windows',(.065,.105,.09),.2,.3);oldframe=mat('Historic_bronze_frames',(.25,.28,.21),.25)
copper=mat('Weathered_blue_green_clock_roof',(.22,.40,.40),.45,.45);steel=mat('Curtainwall_grey_steel',(.46,.53,.50),.45,.38);truss=mat('Dark_structural_space_frame',(.10,.16,.145),.45,.4);edge=mat('Champagne_metal_edge_fascia',(.64,.63,.53),.5,.4)
glasses=[mat('Glass_panel_'+str(i),c,.25,.22,.66) for i,c in enumerate([(.25,.43,.42),(.27,.45,.44),(.24,.42,.41),(.28,.46,.45)])]
sideglass=mat('Side_reflective_glass',(.24,.40,.39),.4,.23);lens=mat('Faceted_silver_lens',(.56,.62,.58),.62,.32);panel=mat('Warm_silver_side_panels',(.69,.67,.59),.45,.45);dark=mat('Recess_and_louvres',(.11,.14,.14));white=mat('Suspended_hall_white_metal',(.73,.74,.69),.3);green=mat('Seven_storey_green_wall',(.10,.22,.095));roof=mat('Roof_silver_ribs',(.54,.59,.56),.45);clockface=mat('Clock_cream_face',(.88,.85,.70));garden=mat('Library_roof_planting',(.20,.31,.13));deck=mat('Roof_garden_deck',(.37,.32,.22))
def geom(name,vs,fs,ma,gr):
 key=(gr,ma);v,f=BUF.setdefault(key,([],[]));n=len(v);v.extend(vs);f.extend([tuple(n+i for i in face) for face in fs])
def box(name,x,y,z,w,d,h,ma,gr):
 v=[(x+a*w,y+b*d,z+c*h) for c in(0,1) for b in(0,1) for a in(0,1)];geom(name,v,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],ma,gr)
def beam(name,a,b,w,ma,gr):
 a,b=Vector(a),Vector(b);u=b-a
 if u.length<1e-5:return
 u.normalize();s=u.cross(Vector((0,0,1)))
 if s.length<.001:s=Vector((1,0,0))
 s.normalize();s*=w/2;t=u.cross(s).normalized()*w/2
 v=[tuple(p+i*s+j*t) for p in[a,b] for i,j in[(-1,-1),(1,-1),(1,1),(-1,1)]];geom(name,v,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],ma,gr)
def prism(name,p,z,h,ma,gr):
 if p[0]==p[-1]:p=p[:-1]
 n=len(p);v=[(x,y,zz) for zz in[z,z+h] for x,y in p];tr=tessellate_polygon([[Vector((x,y,0)) for x,y in p]]);idx={(round(x,8),round(y,8)):i for i,(x,y) in enumerate(p)};fs=[]
 for t in tr:
  ii=[a if isinstance(a,int) else idx[(round(a.x,8),round(a.y,8))] for a in t];fs.extend([tuple(reversed(ii)),tuple(i+n for i in ii)])
 fs.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n));geom(name,v,fs,ma,gr)
def disk(name,center,r,ma,gr,plane='front'):
 x,y,z=center;v=[(x+r*math.cos(a),y,z+r*math.sin(a)) if plane=='front' else(x,y+r*math.cos(a),z+r*math.sin(a)) for a in[2*math.pi*i/64 for i in range(64)]];geom(name,v,[tuple(range(64))],ma,gr)
# Source anchoring is common across the two independent assets: east X, north Y, up Z.
src=json.loads((OUT/'source-footprints.json').read_text());byid={x['id']:x for x in src['buildings']}
oldid='93725b2d-b39e-490f-bc2e-77536fc0d0c4';newid='c1e08f26-ebe0-4a95-827d-c617ca8b3d5f'
def poly(id):return byid[id]['geometry']['coordinates'][0]
p=poly(oldid);prism('Historic_U_outline',p,0,18,stone,OB)
# U plan remains open: no lawn/site ground plane and no invented rectangular infill.
for a,b in zip(p,p[1:]):
 L=math.dist(a,b);dx=(b[0]-a[0])/L;dy=(b[1]-a[1])/L
 # Polygon is counter-clockwise in source; outward is right of each segment.
 nx,ny=dy,-dx
 for z,thick in[(1.2,.22),(4.2,.25),(17.2,.35),(18.1,.4),(19.05,.45)]:beam('Continuous_U_stone_stringcourse',(a[0]+nx*.10,a[1]+ny*.10,z),(b[0]+nx*.10,b[1]+ny*.10,z),thick,trim,OF)
 beam('Roof_parapet',(a[0],a[1],18.65),(b[0],b[1],18.65),.95,stone,OR)
 if L<3:continue
 count=max(1,round(L/3.2))
 for j in range(count):
  t=(j+.5)/count;x=a[0]+t*(b[0]-a[0]);y=a[1]+t*(b[1]-a[1]);w=min(1.20,L/count*.44)
  # Central portal is separately built, avoiding windows behind its stone entrance.
  if y<-34 and -20<x<0:continue
  for z,h in[(1.35,2.05),(5.0,3.2),(9.05,3.2),(13.1,3.1)]:
   q=[(x-dx*w/2+nx*.08,y-dy*w/2+ny*.08,z),(x+dx*w/2+nx*.08,y+dy*w/2+ny*.08,z),(x+dx*w/2+nx*.08,y+dy*w/2+ny*.08,z+h),(x-dx*w/2+nx*.08,y-dy*w/2+ny*.08,z+h)];geom('Tall_historic_window',q,[(0,1,2,3)],oldglass,OF)
   for u in[-w/2,w/2,0]:beam('Window_stone_jamb',(x+dx*u+nx*.13,y+dy*u+ny*.13,z),(x+dx*u+nx*.13,y+dy*u+ny*.13,z+h),.10 if u==0 else.14,oldframe if u==0 else trim,OF)
   for zz in[z-.1,z+h*.5,z+h]:beam('Window_transom',(x-dx*(w/2+.1)+nx*.15,y-dy*(w/2+.1)+ny*.15,zz),(x+dx*(w/2+.1)+nx*.15,y+dy*(w/2+.1)+ny*.15,zz),.10,oldframe,OF)
  for zz in[.6,1.2,1.8,2.4,3,3.6]:beam('Rusticated_ground_course',(x-dx*1.45+nx*.02,y-dy*1.45+ny*.02,zz),(x+dx*1.45+nx*.02,y+dy*1.45+ny*.02,zz),.035,joint,OF)
  # Upper pilasters tie three storeys into the long vertical rhythm seen in photographs.
  beam('Upper_stone_pilaster',(x+dx*(w/2+.35)+nx*.16,y+dy*(w/2+.35)+ny*.16,4.6),(x+dx*(w/2+.35)+nx*.16,y+dy*(w/2+.35)+ny*.16,16.6),.20,trim,OF)
# Broad projecting historic center, clock at cornice level, smaller rooftop lantern behind.
box('Central_portal_stone',-19.9,-36.15,0,19.2,2.0,21.6,stone,OP)
for x in[-17.2,-12.0,-6.8]:
 box('Three_recessed_doors',x,-36.30,.35,2.6,.16,4.25,oldglass,OP)
 for k in[0,1,2]:box('Door_stile',x+k*1.25,-36.45,.35,.10,.14,4.25,oldframe,OP)
 box('Door_transom',x,-36.47,3.4,2.6,.15,.14,trim,OP)
for x in[-19.9,-15.5,-10.4,-5.25,-1.0]:box('Portal_vertical_stone_pier',x,-36.7,0,.55,.7,5.6,trim,OP)
for z in[5.2,5.8,16.4,18.9,21.6]:box('Center_entablature',-20.15,-36.7,z,19.7,.7,.34,trim,OP)
# Upper center glazing retained without reproducing temporary advertising banners.
for x in[-17,-13.2,-9.4,-5.6]:
 for z in[7.1,11.7]:box('Central_original_window',x,-36.28,z,1.65,.14,3.2,oldglass,OP)
cp=poly('64653532-3632-3162-A430-656635303463');prism('Central_source_22m_volume',cp,18,4,stone,OT)
tp=poly('61663761-3634-3437-B130-396663306134');prism('Clock_lantern_source_plan',tp,18,9,stone,OT)
for z,w,d,h in[(21.4,11.2,11.6,.45),(22.0,10.7,11.1,.38),(25.9,10.4,10.8,.22)]:box('Stepped_clock_stone_base',-10.324-w/2,-24.685-d/2,z,w,d,h,trim,OT)
# Pyramidal patinated cap respects the source 30m roof envelope.
tx,ty=-10.324,-24.685;x0,x1=-15.4,-5.25;y0,y1=-29.85,-19.50
geom('Clock_hipped_copper_roof',[(x0,y0,27),(x1,y0,27),(x1,y1,27),(x0,y1,27),(tx,ty,30)],[(0,1,4),(1,2,4),(2,3,4),(3,0,4),(3,2,1,0)],copper,OT)
for xx in[-14.1,-12.0,-9.9,-7.8]:box('Lantern_front_slit',xx,-29.87,23.0,.95,.10,2.5,oldglass,OT)
for yy in[-28.4,-26.3,-24.2,-22.1]:box('Lantern_side_slit',-15.42,yy,23,.12,.95,2.5,oldglass,OT)
box('Lantern_cap_cornice',-15.7,-30.1,26.55,10.8,11,.45,trim,OT)
box('Clock_stone_tablet',-12.6,-36.85,18.2,4.65,.35,4.1,trim,OT)
disk('Clock_face',(tx,-37.05,20.35),1.38,clockface,OT)
for i in range(12):
 a=2*math.pi*i/12;beam('Clock_hour_index',(tx+1.06*math.sin(a),-37.10,20.35+1.06*math.cos(a)),(tx+1.25*math.sin(a),-37.10,20.35+1.25*math.cos(a)),.07,dark,OT)
beam('Clock_hand',(tx,-37.13,20.35),(tx+.8,-37.13,20.85),.10,dark,OT);beam('Clock_hand',(tx,-37.14,20.35),(tx-.4,-37.14,21.18),.085,dark,OT)
for z,w,h in[(30,1.5,.35),(30.35,.9,1.25),(31.6,1.15,.22),(31.82,.65,1.0),(32.82,.8,.18),(33,.26,1.6)]:box('Clock_finial_source_levels',tx-w/2,ty-w/2,z,w,w,h,copper,OT)
beam('Clock_finial_tip',(tx,ty,34.4),(tx,ty,35),.10,copper,OT)
# Modest roof-garden strips stay on the historic U wings.
for x,y,w,d in[(-46,-19,6,18),(-38,-31,16,7),(1,-30,10,6),(15,-23,5,5)]:
 box('Library_roof_deck',x,y,18.1,w,d,.16,deck,OR);box('Roof_planter',x+.5,y+.5,18.25,w-1,1.3,.6,stone,OR);box('Roof_planting',x+.6,y+.6,18.85,w-1.2,1.1,.30,garden,OR)
# NEW HALL: station-specific lofted S section, not an extrusion or curved opaque box.
# Section interpreted from architect's published cross-section; 47.4m retained author
# height is an estimate, not an official survey. XY comes from geographic source.
W=105.2;X0=-15.3
profile=[(8,0),(8.5,4),(10,8),(12.5,12),(15,16),(17,20),(18,23),(17.5,26),(14.5,29),(9.5,32),(3.5,35),(-1.0,38),(-3.0,40.5),(-3.2,42.7),(-2.2,44.4),(0,45.8),(4,46.7),(10,47.15),(18,47.4),(28,47.4),(37,47.2),(45,46.9)]
def fp(i,j):
 u=i/48;yy,zz=profile[j]; bulge=2.2*math.sin(math.pi*u)**2;return(X0+W*u,yy+bulge*(1-zz/48),zz+.65*math.sin(math.pi*u)*math.sin(math.pi*j/(len(profile)-1)))
for i in range(48):
 for j in range(len(profile)-1):
  v=[fp(i,j),fp(i+1,j),fp(i+1,j+1),fp(i,j+1)];geom('Individual_curved_glass_pane',v,[(0,1,2,3)],glasses[(i*7+j*3)%4],NG)
  beam('Curtain_vertical_mullion',v[0],v[3],.075,steel,NS);beam('Curtain_horizontal_mullion',v[0],v[1],.075,steel,NS)
  if j<16:
   ai,bi=(0,2) if (i+j)%2==0 else (1,3)
   beam('Alternating_inner_diagonal',tuple(Vector(v[ai])+Vector((0,.12,0))),tuple(Vector(v[bi])+Vector((0,.12,0))),.16,truss,NS)
   if i%4==0 and j%3==0:beam('Secondary_cross_brace',tuple(Vector(v[1-ai])+Vector((0,.15,0))),tuple(Vector(v[3-ai])+Vector((0,.15,0))),.12,truss,NS)
for j in range(len(profile)-1):beam('East_edge_fascia',fp(48,j),fp(48,j+1),.42,edge,NE);beam('West_edge_fascia',fp(0,j),fp(0,j+1),.42,edge,NW)
# Larger internal triangulated ribs carry the suspended cultural hall inside the glass.
for i in range(0,49,4):
 for j in range(0,16):
  a=Vector(fp(i,j))+Vector((0,1.25,0));b=Vector(fp(i,j+1))+Vector((0,1.25,0));beam('Inner_structural_rib',a,b,.25,truss,NS)
  if j%2==0:beam('Space_frame_depth_strut',fp(i,j),a,.13,truss,NS)
# Side elevations combine reflective S-shaped glazing, oval lens and folded triangular
# cladding behind it. Both ends have a lens, as shown in the two opposing site photos.
for xx,sgn,gr in[(X0,-1,NW),(X0+W,1,NE)]:
 sidepoly=[(yy,zz) for yy,zz in profile]+[(45,0)]
 geom('Side_glass_outline',[(xx,yy,zz) for yy,zz in sidepoly],[tuple(range(len(sidepoly)))],sideglass,gr)
 # Panel seams follow photograph's roughly 2m grid, clipped against sampled profile.
 for j in range(0,13):
  z=j*3.6;nearest=min(profile,key=lambda p:abs(p[1]-z));beam('Side_horizontal_seam',(xx+sgn*.04,nearest[0],z),(xx+sgn*.04,45,z),.055,steel,gr)
 # Distinct faceted almond/oval, raised as an actual shallow bulging surface.
 cy,cz=16.0,35.0;ry,rz=14.0,7.9;ang=-.20
 def clip_axis(pp,axis,bound,greater):
  out=[]
  for a,b in zip(pp,pp[1:]+pp[:1]):
   ia=a[axis]>=bound if greater else a[axis]<=bound;ib=b[axis]>=bound if greater else b[axis]<=bound
   if ia:out.append(a)
   if ia!=ib:
    t=(bound-a[axis])/(b[axis]-a[axis]);out.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
  return out
 def lenspoint(u,v):
  dy=ry*u;dz=rz*v;return(xx+sgn*(.30+2.1*max(0,1-u*u-v*v)),cy+dy*math.cos(ang)-dz*math.sin(ang),cz+dy*math.sin(ang)+dz*math.cos(ang))
 circle=[(math.cos(2*math.pi*k/64),math.sin(2*math.pi*k/64)) for k in range(64)]
 for iu in range(8):
  for iv in range(6):
   pp=circle[:]
   for axis,bound,greater in[(0,-1+iu/4,True),(0,-1+(iu+1)/4,False),(1,-1+iv/3,True),(1,-1+(iv+1)/3,False)]:
    if pp:pp=clip_axis(pp,axis,bound,greater)
   if len(pp)<3:continue
   vv=[lenspoint(u,v) for u,v in pp];geom('Lens_irregular_glazed_facets',vv,[tuple(range(len(vv)))],lens,gr)
   for a,b in zip(vv,vv[1:]+vv[:1]):beam('Lens_panel_metal_seam',a,b,.10,edge,gr)
   if len(vv)==4:beam('Lens_panel_diagonal',vv[0],vv[2],.13,edge,gr)
 for k in range(64):beam('Lens_raised_perimeter',lenspoint(*circle[k]),lenspoint(*circle[(k+1)%64]),.40,edge,gr)
 # Actual back-side mosaic and diagonal structure, deliberately not a random template.
 nodes=[(24,0),(45,0),(45,16),(29,12),(26,28),(45,32),(45,46.8),(29,45.8)]
 tris=[(0,1,3),(1,2,3),(2,4,3),(2,5,4),(4,5,7),(5,6,7)]
 for k,t in enumerate(tris):geom('Rear_side_folded_triangle',[(xx+sgn*.15,nodes[n][0],nodes[n][1]) for n in t],[(0,1,2)],panel if k%2==0 else sideglass,gr)
 for a,b in[(0,3),(3,4),(4,7),(1,3),(3,5),(5,7),(2,4),(4,6)]:beam('Large_diagonal_side_ribbon',(xx+sgn*.22,*nodes[a]),(xx+sgn*.22,*nodes[b]),.48,edge,gr)
 for yy,zz in[(38,7),(37,22),(38,39)]:
  geom('Mechanical_louvre_inset',[(xx+sgn*.27,yy,zz),(xx+sgn*.27,yy+5,zz),(xx+sgn*.27,yy+5,zz+4),(xx+sgn*.27,yy,zz+4)],[(0,1,2,3)],dark,gr)
  for k in range(12):beam('Louvre_blade',(xx+sgn*.35,yy,zz+k*.33),(xx+sgn*.35,yy+5,zz+k*.33),.08,edge,gr)
# Back office mass and its source-plan roof fingers remain distinct behind the atrium.
box('Rear_office_backbone',X0+1,29,0,W-2,15.8,43.4,dark,NR)
for k in range(13):
 z=.3+k*3.35;box('Rear_office_floor_edge',X0+.7,28.8,z,W-1.4,16.1,.24,panel,NR)
 for i in range(33):box('Rear_office_window',X0+1+i*3.12,44.85,z+.32,2.7,.10,2.5,sideglass,NR)
for x,w in[(-11,20),(14,26),(45,24),(74,12)]:
 box('Roof_service_finger',x,21,47.0,w,21.5,1.1,panel,NR)
 for j in range(20):beam('Roof_louvre_rib',(x,21+j,48.15),(x+w,21+j,48.15),.14,roof,NR)
# Ellipsoidal suspended volume: the pale civic hall seen through the front glass.
# Ground-floor/upper-floor drawings locate the auditorium on the western side;
# eastern cultural terraces are separate, avoiding an invented continuous white bar.
for i in range(36):
 for j in range(12):
  def hall(u,v):
   x=-4+36*u;y=17+13*math.cos(math.pi*v);z=39-5*math.sin(math.pi*v);return(x,y,z)
  v=[hall(i/36,j/12),hall((i+1)/36,j/12),hall((i+1)/36,(j+1)/12),hall(i/36,(j+1)/12)];geom('Suspended_hall_curved_shell',v,[(0,1,2,3)],white,NC)
for x in[2,15,28]:beam('Hanging_hall_raking_support',(x,26,26),(x-3,12,35),.70,white,NC)
for z,y in[(32,21),(36,23),(40,25)]:box('East_civic_terrace_floor',35,y,z,49,8,.30,white,NC)
box('Green_wall_seven_floors',-8,28.65,1,92,.30,25,green,NI)
for z in[4,8,12,16,20,24]:box('Greenwall_balcony_ledge',-8,27.9,z,92,1.1,.30,white,NI)
# Main entry is the actual east-front exposed area beside the historic building.
for x in[43,48,53,58]:box('Main_entry_glazing',x,7.6,.15,4.3,.12,4.0,sideglass,NI)
box('Main_entry_canopy',42,5.6,4.15,22,4,.26,white,NI)
for x in[43,53,63]:beam('Entry_canopy_column',(x,6,0),(x,6,4.2),.18,steel,NI)
# Make editable material/component meshes with consistent normals, without image textures.
for (gr,ma),(v,f) in BUF.items():
 me=bpy.data.meshes.new(gr+'_'+ma);me.from_pydata([(x,y,max(0,z)) for x,y,z in v],[],f);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free();ob=bpy.data.objects.new(gr+'_'+ma,me);COL[gr].objects.link(ob);me.materials.append(MAT[ma])
# Neutral inspection stage: no exportable ground/pedestal, roof and site remain separate.
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.world.use_nodes=True;bg=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs['Color'].default_value=(.72,.78,.84,1);bg.inputs['Strength'].default_value=.65;scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.2
scene.render.resolution_x=1700;scene.render.resolution_y=1150;scene.render.resolution_percentage=100
for name,loc,energy,size in [('Key',(-100,-100,160),6500,100),('Fill',(110,-40,110),4500,80)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);COL[QA].objects.link(o);o.location=loc;o.rotation_euler=(Vector((15,5,20))-o.location).to_track_quat('-Z','Y').to_euler()
sun=bpy.data.lights.new('Sun','SUN');sun.energy=2.5;sun.angle=.15;o=bpy.data.objects.new('Sun',sun);COL[QA].objects.link(o);o.rotation_euler=(.45,-.6,-.45)
views=[('Front_South',(30,-205,47),(17,5,23),178),('East_Photo',(170,-155,17),(27,7,24),177),('West_Lens',(-130,-55,31),(0,12,26),125),('Geographic_Roof',(155,-150,170),(17,2,17),192),('Historic_Front',(-10,-150,36),(-10,-20,15),102)]
for name,loc,target,scale in views:
 d=bpy.data.cameras.new(name);d.type='ORTHO';d.ortho_scale=scale;o=bpy.data.objects.new(name,d);COL[QA].objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();scene.camera=o;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
# Export two separately owned models, same geographic origin, preserving exact local XY.
assets=[]
for id,name,prefix,ids,sup in[
 ('bespoke-seoul-city-hall-new','서울특별시청 신청사','New_', [newid,'bb10e1bc-1807-41fc-87c5-3bdac2090c9c'],['reference-flight-seoul-city-hall','landmark-'+newid]),
 ('bespoke-seoul-city-hall-library','서울도서관 · 구 서울시청','Old_', [oldid]+[x for x in byid if x not in[oldid,newid,'bb10e1bc-1807-41fc-87c5-3bdac2090c9c']],['reference-flight-seoul-city-hall','civic-'+oldid])]:
 bpy.ops.object.select_all(action='DESELECT');objects=[o for c in COL.values() if c.name.startswith(prefix) for o in c.objects if o.type=='MESH']
 for ob in objects:ob.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];file=OUT/(id+'.glb');bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_apply=True,export_yup=True)
 pts=[o.matrix_world@v.co for o in objects for v in o.data.vertices];lo=[min(v[k] for v in pts) for k in range(3)];hi=[max(v[k] for v in pts) for k in range(3)];tri=sum(len(p.vertices)-2 for o in objects for p in o.data.polygons)
 assets.append({'id':id,'nameKo':name,'file':str(file),'blendSource':str(OUT/'seoul-city-hall.blend'),'coordinate':{'lon':126.978,'lat':37.5665},'category':'city-hall' if prefix=='New_' else 'heritage','footprintIds':ids,'supersedes':sup,'referenceUrl':'https://www.archdaily.com/457570/seoul-new-city-hall-iarc-architects','components':[c.name for c in COL.values() if c.name.startswith(prefix)],'uncertainties':['Photo-authored architectural approximation, not surveyed CAD.','New hall 47.4m nominal envelope retained from former authored model; no verified official metre height found.'] if prefix=='New_' else ['OSM part heights 18/19.5/22/30/35m are source-reported and unverified.','Temporary banners/advertisements omitted; facade details interpreted from photographs.'],'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'triangles':tri,'meshCount':len(objects),'boundsBlender':{'min':lo,'max':hi},'heightM':hi[2]})
scene.camera=bpy.data.objects['East_Photo'];bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'seoul-city-hall.blend'))
sources=[{'url':'https://www.archdaily.com/457570/seoul-new-city-hall-iarc-architects','observations':['Architect-supplied ground-floor plan, section and Archframe completion photographs.','S-shaped double-skin curtainwall; structural triangular lattice; projecting faceted lenses at both ends; suspended pale cultural hall; folded rear side panels.']},{'url':'https://www.seoul.go.kr/seoul/newoffice.do','observations':['Official current 13 above-ground floor guide; diagram confirms historic front building separated from new hall.']},{'url':'https://culture.seoul.go.kr/night/sub/nightFac/view.do?facId=9','observations':['Official photograph confirms historic stone window rhythm, centered clock tablet, lower roof lantern and flat parapet wings.']}]
bundle={'siteId':'seoul-city-hall','sources':sources,'assets':assets,'places':[{'id':'bespoke-seoul-city-hall','name':'서울시청 신청사·서울도서관','subtitle':'곡면 유리 청사와 구청사 석조 입면','center':[126.97813,37.56648],'zoom':17.65,'source_url':sources[0]['url']}],'recipeFiles':['source-footprints.json','architecture-recipe.json'],'mcpEvidence':[{'file':str(OUT/'mcp-build.json'),'tool':'execute_blender_code','port':9876}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2))
(OUT/'architecture-recipe.json').write_text(json.dumps({'commonGeographicAnchor':[126.978,37.5665],'coordinateSystem':'Blender eastX northY upZ; GLB eastX upY southZ','sourceProfileYZ':profile,'newHeightBasis':'47.4m retained author estimate, not verified official metric height','oldHeightBasis':'OSM geographic child envelopes, source-reported unverified','ownership':'Split nine existing owned source IDs into two new and seven historic IDs. No neighbors or entire plaza claimed.','photographsEmbedded':False,'temporaryAdsModeled':False,'assets':assets},ensure_ascii=False,indent=2))
print(json.dumps({'assets':assets,'blend':str(OUT/'seoul-city-hall.blend')},ensure_ascii=False))
