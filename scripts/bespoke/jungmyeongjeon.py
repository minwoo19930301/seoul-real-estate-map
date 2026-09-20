"""Jungmyeongjeon, individually reconstructed from restoration drawings and current photos.

Run inside the dedicated Blender MCP instance. No photo textures or generic facade template.
The 2009 restored drawings supply nominal dimensions; 2020 photographs govern visible details.
"""
import bpy, bmesh, math, json, hashlib
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/jungmyeongjeon';OUT.mkdir(parents=True,exist_ok=True)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name!='Collection':bpy.data.collections.remove(c)
bpy.data.orphans_purge(do_recursive=True)
GROUPS=['01_Raised_Brick_Plinth','02_Asymmetric_Rear_Core','03_Seven_Bay_Front_Arcade','04_Long_East_Arcade','05_Short_West_Arcade','06_Rear_Returns','07_Projecting_Entrance_Balcony','08_Stone_Balustrades','09_Windows_and_Doors','10_L_Hipped_Slate_Roof','11_Dormers_and_Chimneys','12_Cornices_Drainage','QA']
COL={};BUF={};MAT={}
for name in GROUPS:
    c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);COL[name]=c
PL,CO,FR,EA,WE,RE,EN,BA,WI,RO,CH,TR,QA=GROUPS
def material(name,c,metal=0,rough=.7):
    m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;MAT[name]=m;return name
brick=material('Red_brick_body',(.40,.115,.053))
bricks=[material('Photographic_brick_variation_'+str(i),c) for i,c in enumerate([(.46,.155,.068),(.37,.102,.040),(.43,.132,.060),(.49,.181,.088),(.32,.09,.037)])]
mortar=material('Warm_recessed_mortar',(.29,.24,.18));stone=material('Grey_limestone_and_weathered_balusters',(.43,.42,.34));stonelight=material('Stone_cap_and_sills',(.60,.57,.46));darkstone=material('Grey_header_brick',(.25,.255,.22));wood=material('Dark_brown_wood_frames',(.13,.08,.037));soffit=material('Painted_cream_arcade_soffit',(.68,.64,.53));glass=material('Recessed_window_glass',(.09,.13,.13),.2,.22);roof=material('Grey_slate_roof',(.18,.205,.21));roofjoint=material('Slate_courses',(.11,.13,.135));zinc=material('Dark_grey_zinc_gutters',(.22,.26,.25),.5,.42);floor=material('Corridor_stone_floor',(.42,.40,.34));black=material('Open_flue_shadow',(.035,.025,.02))
# All geometry is first authored in measured building axes, then baked into east/north.
# Positive local X is east along facade; local Y points towards the rear.
ANGLE=math.radians(-2.4)
def geo(name,vs,fs,ma,gr):
    v,f=BUF.setdefault((gr,ma),([],[]));n=len(v);v.extend(vs);f.extend(tuple(n+i for i in q) for q in fs)
def box(name,x,y,z,w,d,h,ma,gr):
    vs=[(x+i*w,y+j*d,z+k*h) for k in (0,1) for j in (0,1) for i in (0,1)]
    geo(name,vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],ma,gr)
def beam(name,a,b,w,ma,gr):
    a,b=Vector(a),Vector(b);u=b-a
    if u.length<1e-6:return
    u.normalize();s=u.cross(Vector((0,0,1)))
    if s.length<.01:s=Vector((1,0,0))
    s.normalize();s*=w/2;t=u.cross(s).normalized()*w/2
    vs=[tuple(p+i*s+j*t) for p in [a,b] for i,j in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    geo(name,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],ma,gr)
def prism(name,poly,z,h,ma,gr):
    from mathutils.geometry import tessellate_polygon
    n=len(poly);vs=[(x,y,zz) for zz in [z,z+h] for x,y in poly];lookup={tuple(vs[i]):i for i in range(n)}
    fs=[]
    for tri in tessellate_polygon([[Vector(vs[i]) for i in range(n)]]):
        ids=[i if isinstance(i,int) else lookup[tuple(i)] for i in tri];fs.extend([tuple(reversed(ids)),tuple(i+n for i in ids)])
    fs.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n));geo(name,vs,fs,ma,gr)
def localpoint(s,n,z,start,direction):
    dx,dy=direction;return(start[0]+dx*s-dy*n,start[1]+dy*s+dx*n,z)
def oriented_box(name,s,n,z,w,d,h,start,direction,ma,gr):
    vs=[localpoint(s+i*w,n+j*d,z+k*h,start,direction) for k in (0,1) for j in (0,1) for i in (0,1)]
    geo(name,vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],ma,gr)
def face_bricks(start,direction,L,z0,z1,gr,holes=(),n=0):
    # Small flat masonry faces retain relief in GLB; repeating brick bonds are masonry,
    # not a building-generation template. Colours are limited photo interpretations.
    course=.082;length=.245
    for row in range(math.ceil((z1-z0)/course)):
        z=z0+row*course;h=min(course-.014,z1-z)
        if h<=0:continue
        s=-length/2 if row%2 else 0
        col=0
        while s<L:
            a=max(0,s);b=min(L,s+length-.012)
            if b>a and not any(a<q[1] and b>q[0] and z<q[3] and z+h>q[2] for q in holes):
                vs=[localpoint(a,n,z,start,direction),localpoint(b,n,z,start,direction),localpoint(b,n,z+h,start,direction),localpoint(a,n,z+h,start,direction)]
                geo('Individual_brick_face',vs,[(0,1,2,3)],bricks[(row*7+col*3)%len(bricks)],gr)
            s+=length;col+=1
def rail(a,b,z,gr=BA,omit=False):
    if omit:return
    a,b=Vector((*a,z)),Vector((*b,z));d=b-a;L=d.length
    beam('Stone_balustrade_lower',a,b,.15,stone,gr);beam('Stone_balustrade_handcap',a+Vector((0,0,.90)),b+Vector((0,0,.90)),.16,stonelight,gr)
    count=max(2,round(L/.32))
    profile=[(0,.065),(.08,.075),(.13,.043),(.28,.055),(.43,.091),(.56,.075),(.66,.041),(.74,.065),(.78,.067)]
    for j in range(count):
        c=a+d*((j+.5)/count)+Vector((0,0,.06));vs=[]
        for zz,rr in profile:
            vs.extend((c.x+rr*math.cos(k*math.pi/4),c.y+rr*math.sin(k*math.pi/4),c.z+zz) for k in range(8))
        fs=[tuple(reversed(range(8))),tuple(range((len(profile)-1)*8,len(profile)*8))]
        fs.extend((i*8+k,i*8+(k+1)%8,(i+1)*8+(k+1)%8,(i+1)*8+k) for i in range(len(profile)-1) for k in range(8));geo('Turned_stone_baluster',vs,fs,stone,gr)
def arcade(start,direction,piers,gr,base=1.23,top=5.34,railing=True):
    width=.53;spring=base+2.54;crown=base+3.40;end=top-.13
    for s in piers:
        oriented_box('Brick_arcade_pier',s-width/2,-.30,base,width,.60,spring-base,start,direction,brick,gr)
        face_bricks(localpoint(s-width/2,-.311,0,start,direction)[:2],direction,width,base+.2,spring-.12,gr)
        for zz,w,d,h,ma in [(base-.02,.67,.72,.22,stone),(spring-.06,.70,.74,.105,stonelight),(spring+.05,.61,.65,.095,darkstone)]:oriented_box('Pier_cap_and_foot',s-w/2,-d/2,zz,w,d,h,start,direction,ma,gr)
    for j,(left,right) in enumerate(zip(piers,piers[1:])):
        x0=left+width/2;x1=right-width/2;c=(x0+x1)/2;r=(x1-x0)/2;rise=crown-spring;N=24
        # Spandrel volume above a true curved opening, without a box filling the void.
        for k in range(N):
            t0=k*math.pi/N;t1=(k+1)*math.pi/N
            aa=c-r*math.cos(t0);bb=c-r*math.cos(t1);za=spring+rise*math.sin(t0);zb=spring+rise*math.sin(t1)
            vs=[localpoint(s,n,z,start,direction) for n in [-.30,.30] for s,z in [(aa,za),(bb,zb),(bb,end),(aa,end)]]
            geo('Open_arch_spandrel',vs,[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(3,2,6,7),(0,3,7,4)],brick,gr)
            # Two concentric exposed header courses articulate the shallow segmental arch.
            for band in [0,.11]:
                ra=r+band;rb=r+band+.095;ha=rise+band;hb=rise+band+.095
                vv=[localpoint(c-rr*math.cos(t),-.322, spring+hh*math.sin(t),start,direction) for rr,hh,t in [(ra,ha,t0+.009),(ra,ha,t1-.009),(rb,hb,t1-.009),(rb,hb,t0+.009)]]
                geo('Radial_brick_arch_headers',vv,[(0,1,2,3)],bricks[k%5],gr)
        oriented_box('Arcade_floor_stringcourse',left-.27,-.35,top-.15,right-left+.54,.70,.15,start,direction,darkstone,TR)
        if railing and not (gr==FR and j==3 and base<2):
            a=localpoint(x0,-.07,0,start,direction);b=localpoint(x1,-.07,0,start,direction);rail(a[:2],b[:2],base+.12)

W=20.635;D=21.470;X=-W/2;Y=-D/2;XF=W/2;YB=D/2
outline=[(X,Y),(XF,Y),(XF,YB),(X+5.29,YB),(X+5.29,YB-5.22),(X,YB-5.22)]
prism('Source_aligned_measured_L_base',outline,0,1.20,mortar,PL)
for a,b in zip(outline,outline[1:]+outline[:1]):
    dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);direction=(dx/L,dy/L)
    face_bricks(a,direction,L,.06,1.10,PL,n=-.012)
    beam('Limestone_base_coping',(*a,1.17),(*b,1.17),.18,stone,PL)
# Distinct main rooms and projecting northern service block, leaving actual deep corridors.
core=[(X+2.195,Y+3.040),(XF-2.175,Y+3.040),(XF-2.175,YB),(X+5.29,YB),(X+5.29,YB-7.97),(X+2.195,YB-7.97)]
prism('Recessed_brick_rooms_L_outline',core,1.2,7.90,mortar,CO)
# Corridor floors above and below are independently visible from the open arches.
prism('Lower_stone_corridor_slab',outline,1.20,.13,floor,CO)
prism('Upper_corridor_floor',outline,5.19,.15,floor,CO)
prism('Upper_arcade_ceiling',outline,8.97,.16,soffit,CO)
front=[X,X+8.740/3,X+2*8.740/3,X+8.740,X+11.790,X+11.790+8.845/3,X+11.790+2*8.845/3,XF]
east=[i*D/8 for i in range(9)]
west=[i*(D-5.22)/6 for i in range(7)]
def foundation_details(start,direction,piers,gr):
    for s in piers:
        for row in range(4):
            oriented_box('Foundation_stone_pier_strip',s-.30,-.321,.02+row*.283,.60,.13,.268,start,direction,stone,PL)
    for j,(a,b) in enumerate(zip(piers,piers[1:])):
        if gr==FR and j==3:continue
        if gr!=FR and j%2:continue
        s=(a+b)/2
        oriented_box('Basement_vent_stone_surround',s-.28,-.322,.29,.56,.10,.46,start,direction,stone,PL)
        oriented_box('Dark_rectangular_basement_vent',s-.20,-.382,.35,.40,.045,.32,start,direction,black,PL)
        for k in range(4):oriented_box('Basement_vent_iron_bar',s-.16+k*.105,-.413,.35,.015,.018,.32,start,direction,zinc,PL)
foundation_details((0,Y),(1,0),front,FR)
foundation_details((XF,Y),(0,1),east,EA)
foundation_details((X,YB-5.22),(0,-1),west,WE)
for z,t in [(1.23,5.34),(5.34,9.14)]:
    arcade((0,Y),(1,0),front,FR,z,t)
    arcade((XF,Y),(0,1),east,EA,z,t)
    arcade((X,YB-5.22),(0,-1),west,WE,z,t)
    # Rear east end is a single open return. Rear west return includes blind brick arches.
    arcade((XF,YB),(-1,0),[0,2.175],RE,z,t)
    arcade((X,YB-5.22),(1,0),[0,2.195,5.29],RE,z,t,railing=False)
    rail((X+.30,YB-5.22),(X+1.94,YB-5.22),z+.12)
# Recessed opening placements follow the restored elevation, not facade-wide repetition.
def window(start,direction,s,z,w=1.05,h=1.95,door=False):
    n=-.035
    oriented_box('Dark_recessed_sash',s-w/2,n,z,w,.10,h,start,direction,glass,WI)
    for ss in [s-w/2-.05,s+w/2-.04,s-.025]:oriented_box('Window_vertical_wood',ss,n-.065,z,.085,.12,h,start,direction,wood,WI)
    for zz in [z,z+h*.34,z+h*.68,z+h-.06]:oriented_box('Window_horizontal_wood',s-w/2-.05,n-.075,zz,w+.1,.13,.065,start,direction,wood,WI)
    oriented_box('Projecting_stone_sill',s-w/2-.13,n-.12,z-.13,w+.26,.27,.13,start,direction,stonelight,WI)
    # Segmental header relief in grey masonry, distinct from arcade's larger red arch.
    for k in range(13):
        a=math.pi*k/13;b=math.pi*(k+1)/13
        vv=[localpoint(s-r*math.cos(t),n-.075,z+h+.03+hh*math.sin(t),start,direction) for r,hh,t in [(w/2+.06,.075,a),(w/2+.06,.075,b),(w/2+.20,.185,b),(w/2+.20,.185,a)]]
        geo('Shallow_brick_segmental_window_header',vv,[(0,1,2,3)],bricks[1] if k%3 else darkstone,WI)
    if door:
        oriented_box('Door_lower_panel',s-w/2+.10,n-.09,z+.12,w-.20,.10,.61,start,direction,wood,WI)
        oriented_box('Door_handle',s+.15,n-.19,z+1.0,.035,.1,.27,start,direction,zinc,WI)
# Core faces; explicit window placements produce separate front/side/rear arrangements.
wall_specs=[((X+2.195,Y+3.040),(1,0),W-4.37,[1.10,4.02,8.14,12.08,15.10],CO),((XF-2.175,Y+3.040),(0,1),D-3.04,[1.18,3.65,6.32,9.0,11.68,14.36,17.12],CO),((X+2.195,YB-7.97),(0,-1),10.46,[1.3,4.0,6.7,9.30],CO),((X+5.29,YB),(-1,0),0,[],CO),((XF-2.175,YB),(-1,0),W-7.465,[2.1,6.1,10.1],RE),((X+5.29,YB),(0,-1),7.97,[1.40,4.25,6.70],RE),((X+5.29,YB-7.97),(-1,0),3.095,[1.45],RE)]
for start,direction,L,positions,gr in wall_specs:
    if L<=0:continue
    holes=[]
    for level in [1.23,5.34]:
        for i,s in enumerate(positions):
            isdoor=(start==(X+2.195,Y+3.040) and i==2 and level<2)
            w=1.4 if isdoor else 1.05;z=level+.05 if isdoor else level+.78;h=2.65 if isdoor else 1.95
            # Back elevation has fewer upper openings than its lower storey.
            if gr==RE and level>2 and i==1 and L>10:continue
            holes.append((s-w/2-.22,s+w/2+.22,z-.14,z+h+.35));window(start,direction,s,z,w,h,isdoor)
    face_bricks(start,direction,L,1.27,9.0,gr,holes,n=-.055)
# Main entry projects beyond the front arcade, with open flanks and balcony above.
px=X+8.740;pw=3.050;py=Y-1.530
for a in [px,px+pw]:
    box('Portal_stone_foot',a-.39,py-.36,0,.78,.78,1.30,stone,EN)
arcade((0,py),(1,0),[px,px+pw],EN,1.23,5.34,railing=False)
for a,sgn in [(px,1),(px+pw,-1)]:arcade((a,py),(0,1),[0,1.53],EN,1.23,5.34,railing=False)
box('Balcony_slab',px-.38,py-.42,5.18,pw+.76,2.1,.21,stone,EN)
for x in [px,px+pw]:
    box('Balcony_brick_capped_pier',x-.39,py-.35,5.34,.78,.74,1.22,darkstone,EN);box('Balcony_pier_stone_cap',x-.44,py-.40,6.53,.88,.84,.12,stonelight,EN)
rail((px+.43,py),(px+pw-.43,py),5.44);rail((px,py+.35),(px,Y),5.44);rail((px+pw,py+.35),(px+pw,Y),5.44)
# Seven low stair risers follow post-2017 ground treatment in the current photo.
for i in range(7):box('Current_front_entrance_stair',px-.1,py-2.10+i*.30,0,pw+.2,2.12-i*.30,(i+1)*1.23/7,stonelight,EN)
# Rear-side return's one infilled former arch is deliberately closed, as photographed.
box('Rear_blind_arch_infill',X+2.47,YB-5.22-.12,5.34,2.53,.20,3.45,brick,RE)
box('Rear_lower_window_infill',X+2.47,YB-5.22-.12,1.23,2.53,.20,3.40,brick,RE)
window((X+2.47,YB-5.22+.03),(-1,0),-1.20,2.0)
# Masonry belt with dentils runs around the actual L, not across its notch.
for a,b in zip(outline,outline[1:]+outline[:1]):
    dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);u=(dx/L,dy/L)
    for zz,w,ma in [(1.17,.18,stone),(5.06,.16,darkstone),(5.19,.20,stonelight),(8.95,.17,darkstone),(9.12,.25,wood)]:beam('Continuous_L_masonry_band',(*a,zz),(*b,zz),w,ma,TR)
    for i in range(round(L/.22)):
        s=(i+.5)*L/round(L/.22);oriented_box('Interstorey_dentil',s-.05,-.38,4.91,.10,.13,.15,a,u,darkstone,TR)
    # Pipe and brackets at documented corners, outside arcade opening faces.
for x,y in [(X-.30,Y-.3),(XF+.30,Y-.3),(XF+.30,YB+.22),(X+5.29-.22,YB+.22)]:
    beam('Corner_downpipe',(x,y,.10),(x,y,9.25),.11,zinc,TR)
    for z in [1.4,4.0,6.3,8.5]:box('Drainpipe_bracket',x-.09,y-.08,z,.18,.17,.06,zinc,TR)
# L-shaped hipped roof: two ridges and a genuine re-entrant valley.
A=(X-.60,Y-.60,9.28);B=(XF+.60,Y-.60,9.28);C=(XF+.60,YB+.60,9.28);DD=(X+5.29-.60,YB+.60,9.28);E=(X+5.29-.60,YB-5.22+.60,9.28);F=(X-.60,YB-5.22+.60,9.28)
R1=(-2.20,-2.60,13.14);R2=(2.65,-2.60,13.14);R3=(2.65,3.05,13.14)
surfaces=[[A,B,R2,R1],[B,C,R3,R2],[C,DD,R3],[DD,E,R2,R3],[E,F,R1,R2],[F,A,R1]]
for face in surfaces:
    geo('Individually_resolved_L_roof_facet',face,[tuple(range(len(face)))],roof,RO)
    # Slate courses are clipped to the actual roof facets; no rectangular floating grid.
    for k in range(1,24):
        z=9.28+k*(13.14-9.28)/24;hits=[]
        for a,b in zip(face,face[1:]+face[:1]):
            if (a[2]<=z<b[2]) or (b[2]<=z<a[2]):
                t=(z-a[2])/(b[2]-a[2]);hits.append((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,z+.007))
        if len(hits)==2:beam('Slate_course_reveal',hits[0],hits[1],.016,roofjoint,RO)
for a,b in [(A,R1),(B,R2),(C,R3),(DD,R3),(E,R2),(F,R1),(R1,R2),(R2,R3)]:beam('Hipped_roof_ridge_valley',a,b,.07,zinc,RO)
for a,b in [(A,B),(B,C),(C,DD),(DD,E),(E,F),(F,A)]:
    beam('Deep_wood_eave_fascia',a,b,.20,wood,RO);beam('Perimeter_eaves_gutter',tuple(Vector(a)+Vector((0,0,.07))),tuple(Vector(b)+Vector((0,0,.07))),.14,zinc,TR)
def dormer(start,direction,z,w=1.25):
    # Rectangular timber opening with a broad shallow metal cap, from current photographs.
    oriented_box('Dormer_roof_join_and_cheek',-w/2,0,z-.65,w,1.50,1.89,start,direction,zinc,CH)
    oriented_box('Dormer_dark_glass',-w/2+.12,-.025,z+.08,w-.24,.06,.99,start,direction,glass,CH)
    for s in [-w/2+.08,0,w/2-.15]:oriented_box('Dormer_wood_mullion',s,-.08,z+.04,.075,.10,1.10,start,direction,wood,CH)
    for zz in [z+.05,z+.55,z+1.11]:oriented_box('Dormer_wood_transom',-w/2+.05,-.085,zz,w-.1,.10,.065,start,direction,wood,CH)
    oriented_box('Dormer_overhanging_cap',-w/2-.25,-.26,z+1.22,w+.5,1.30,.12,start,direction,zinc,CH)
dormer((.00,-6.30),(1,0),11.28)
dormer((XF-3.0,.5),(0,1),10.95)
dormer((X+2.8,-.6),(0,-1),10.95)
for x,y,z,h in [(X-.62,-2.5,0,13.45),(-1.55,YB-2.2,10.0,3.62)]:
    box('Documented_brick_chimney',x-.33,y-.40,z,.66,.80,h,brick,CH)
    for zz in [z+h-.58,z+h-.15]:box('Chimney_projecting_brick_cap',x-.42,y-.49,zz,.84,.98,.15,bricks[1],CH)
    box('Chimney_dark_open_flue',x-.26,y-.33,z+h+.012,.52,.66,.02,black,CH)
    for xx in [x-.21,x+.07]:
        box('Chimney_small_side_flue_opening',xx,y-.412,z+h-.39,.14,.022,.17,black,CH)
        box('Chimney_rear_flue_opening',xx,y+.399,z+h-.39,.14,.022,.17,black,CH)
    for yy in [y-.24,y+.09]:
        box('Chimney_return_flue_opening',x-.342,yy,z+h-.39,.022,.15,.17,black,CH)
    for i in range(int(h/.11)):box('Chimney_mortar_course',x-.338,y-.41,z+i*.11,.68,.82,.012,mortar,CH)
# Bake geographic orientation into vertices. No hidden root scale or geographic recentering.
for (gr,ma),(vs,fs) in BUF.items():
    world=[(x*math.cos(ANGLE)-y*math.sin(ANGLE),x*math.sin(ANGLE)+y*math.cos(ANGLE),max(0,z)) for x,y,z in vs]
    me=bpy.data.meshes.new(gr+'_'+ma);me.from_pydata(world,[],fs);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
    ob=bpy.data.objects.new(gr+'_'+ma,me);COL[gr].objects.link(ob);me.materials.append(MAT[ma])
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.world.use_nodes=True;bg=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs['Color'].default_value=(.72,.79,.87,1);bg.inputs['Strength'].default_value=.65
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.0
scene.render.resolution_x=1500;scene.render.resolution_y=1150;scene.render.resolution_percentage=100
sun=bpy.data.lights.new('Warm_afternoon_sun','SUN');sun.energy=2.3;sun.angle=.13;ob=bpy.data.objects.new(sun.name,sun);COL[QA].objects.link(ob);ob.rotation_euler=(.5,-.6,-.4)
for name,loc,target,scale in [('Front_Southwest',(-34,-48,17),(0,0,5.7),35),('Front_Southeast',(37,-43,16),(0,0,5.8),36),('Rear_Northwest',(-36,42,20),(0,1,5.5),35),('Measured_Roof',(30,-38,52),(0,0,4.5),39),('Front_Elevation',(0,-60,8),(0,0,7),28)]:
    d=bpy.data.cameras.new(name);d.type='ORTHO';d.ortho_scale=scale;o=bpy.data.objects.new(name,d);COL[QA].objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
scene.camera=bpy.data.objects['Front_Southwest']
bpy.ops.object.select_all(action='DESELECT');objects=[o for o in bpy.data.objects if o.type=='MESH']
for ob in objects:ob.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
file=OUT/'bespoke-jungmyeongjeon.glb';bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_apply=True,export_yup=True)
bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'jungmyeongjeon.blend'))
sources=[{'url':'https://dh.aks.ac.kr/hanyang2/image/2021/cha/A/04/%EB%8D%95%EC%88%98%EA%B6%81%20%EC%A4%91%EB%AA%85%EC%A0%84%20%EB%B3%B4%EC%88%98%20%EB%B3%B5%EC%9B%90%20%EB%B3%B4%EA%B3%A0%EC%84%9C_2009.pdf','observations':['2009 restoration report: restored site/plan/roof/elevations/section on printed pages251,257,263,265,267,269,271,273; existing-state drawings not used as restored appearance.']},{'url':'https://mediahub.seoul.go.kr/archives/1504110','observations':['Original municipal-platform photographs dated2020: open front/side arcades, contrasting grey bands and balusters, projecting balcony, rear notch and chimney positions; current exterior takes precedence over2009 site-grade depiction.']}]
asset={'id':'bespoke-jungmyeongjeon','nameKo':'덕수궁 중명전','file':str(file),'blendSource':str(OUT/'jungmyeongjeon.blend'),'coordinate':{'lon':126.9725588920004,'lat':37.56673044964224},'category':'heritage','district':'중구','footprintIds':['4c53ad91-93b0-4472-b7a4-0086e45cbdd2'],'supersedes':['civic-4c53ad91-93b0-4472-b7a4-0086e45cbdd2'],'referenceUrl':sources[0]['url'],'components':GROUPS[:-1],'uncertainties':['Restoration-drawing reconstruction with photo-interpreted masonry colours and simplified fine ornament; not an as-built2026 survey.','Nominal drawing dimensions are smaller than retained OVT outline; source anchor/orientation preserved, width not inflated to cover source error.','Post2017 site grading and stair run interpreted from2020 photograph; no enclosing terrain or neighboring garden geometry.','Roof hip intersections and dormer depths are interpretations; interior partitions and exhibition objects omitted.'],'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
recipe={'site':'Jungmyeongjeon','nominalDimensionsM':{'frontWidth':20.635,'depth':21.470,'firstFloor':1.230,'secondFloor':5.340,'eaveReference':9.140,'ridgeReference':13.140},'dimensionBasis':'2009 restored drawings257/273; roof fascia .14m above reference and chimney caps separately modeled','frontArcadeBays':7,'eastArcadeBays':8,'westArcadeBays':6,'northwestNotchM':[5.29,5.22],'frontPierPositions':front,'orientationDegFromEast':-2.4,'orientationBasis':'retained source south/east edge direction, consistent with north-up site drawing251','anchor':asset['coordinate'],'outlineBuildingAxesM':outline,'coreBuildingAxesM':core,'roofFacetVerticesM':surfaces,'rights':'Photos/plan images not embedded; local evidence is for review only','sources':sources,'omitted':['neighboring embassy/theatre buildings','site retaining walls and gardens','interior displays','hidden structural roof timbers'],'sourceFootprintId':asset['footprintIds'][0]}
(OUT/'recipe-input.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n')
bundle={'siteId':'jungmyeongjeon','sources':sources,'assets':[asset],'places':[{'id':'bespoke-jungmyeongjeon','name':'덕수궁 중명전','subtitle':'실측 복원도와 사진을 바탕으로 재구성한 벽돌 회랑 건축','center':[asset['coordinate']['lon'],asset['coordinate']['lat']],'zoom':18.25,'source_url':sources[1]['url']}],'recipeFiles':['recipe-input.json','source-footprint.json'],'mcpEvidence':[{'file':str(OUT/'mcp-build.json'),'tool':'execute_blender_code','port':9876}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'asset':asset,'blender':bpy.app.version_string,'meshCount':len(objects),'triangles':sum(len(p.vertices)-2 for o in objects for p in o.data.polygons)},ensure_ascii=False))
