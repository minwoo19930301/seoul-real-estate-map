"""Culture Station Seoul284, individually photo-authored using its geographic outline.
Execute in the dedicated Blender MCP artist instance. Dimensions are interpretations
unless explicitly labelled source geometry; see the accompanying reference brief.
"""
import bpy, bmesh, math, json, hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/culture-station-seoul284';OUT.mkdir(parents=True,exist_ok=True)
bpy.context.preferences.filepaths.save_version=0
LON,LAT=126.97158,37.555877
IDS=['d8469ff5-7c6b-4514-8e0d-da239407bbda','36356163-6139-3732-A335-333337356337']
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for col in list(bpy.data.collections):
    if col.name!='Collection':bpy.data.collections.remove(col)
bpy.data.orphans_purge(do_recursive=True)
COL={}
for name in ['01_Source_Footprint','02_Central_Arched_Entrance','03_Copper_Dome_Lantern','04_South_Main_Wing','05_North_Main_Wing','06_South_VIP_Annex','07_North_RTO_Annex','08_Rear_Elevation','QA_Cameras_Lights']:
    c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);COL[name]=c
BASE,CENT,DOME,SOUTH,NORTH,VIP,RTO,REAR,QA=list(COL)
def mat(name,rgb,metal=0,rough=.7):
    m=bpy.data.materials.new(name);m.diffuse_color=(*rgb,1);m.use_nodes=True
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value=(*rgb,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    return m
brick=mat('Observed_warm_red_brick',(.39,.155,.09));stone=mat('Observed_pale_granite_and_artificial_stone',(.68,.66,.57))
trim=mat('Light_carved_stone_edges',(.82,.80,.70));roof=mat('Grey_wing_roof_tiles',(.16,.18,.18));copper=mat('Observed_aged_copper_green',(.16,.36,.25),.36,.52)
ribmat=mat('Copper_seam_highlights',(.28,.44,.32),.4,.47);glass=mat('Dark_green_window_glass',(.045,.105,.089),.25,.27)
frame=mat('Observed_green_window_frames',(.14,.25,.17));black=mat('Entrance_and_clock_dark_metal',(.07,.065,.05),.2);cream=mat('Clock_ivory_face',(.87,.83,.67));mortar=mat('Recessed_masonry_courses',(.46,.34,.25))
def mesh(name,verts,faces,material,group):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
    ob=bpy.data.objects.new(name,me);COL[group].objects.link(ob);me.materials.append(material);return ob

def box(name,x,y,z,w,d,h,material,group):
    v=[(x+a*w,y+b*d,z+c*h) for c in (0,1) for b in (0,1) for a in (0,1)]
    return mesh(name,v,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],material,group)
def prism(name,poly,z,h,material,group):
    n=len(poly);v=[(x,y,zz) for zz in [z,z+h] for x,y in poly]
    return mesh(name,v,[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],material,group)
def beam(name,a,b,r,material,group):
    a,b=Vector(a),Vector(b);u=b-a;u.normalize();s=u.cross(Vector((0,0,1)))
    if s.length<.001:s=Vector((1,0,0))
    s.normalize();s*=r/2;t=u.cross(s).normalized()*r/2
    v=[tuple(p+i*s+j*t) for p in [a,b] for i,j in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    return mesh(name,v,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],material,group)
def arch_panel(name,x,y,z,width,height,material,group):
    r=width/2;spring=z+height-r
    points=[(y-r,z),(y+r,z)]+[(y+r*math.cos(a),spring+r*math.sin(a)) for a in [i*math.pi/24 for i in range(25)]]
    return mesh(name,[(x,yy,zz) for yy,zz in points],[tuple(range(len(points)))],material,group)
def arch_ring(name,x,y,spring,r,t,depth,material,group,segments=32):
    # Actual thick voussoir ring, not a drawn arch on a solid rectangular block.
    v=[]
    for xx in [x-depth,x]:
        for rr in [r,r+t]:
            for i in range(segments+1):
                a=math.pi*i/segments;v.append((xx,y+rr*math.cos(a),spring+rr*math.sin(a)))
    n=segments+1;f=[]
    for i in range(segments):
        f += [(i,i+1,n+i+1,n+i),(2*n+i,3*n+i,3*n+i+1,2*n+i+1),(i,2*n+i,2*n+i+1,i+1),(n+i,n+i+1,3*n+i+1,3*n+i)]
    f += [(0,n,3*n,2*n),(n-1,3*n-1,4*n-1,2*n-1)]
    return mesh(name,v,f,material,group)
def lathe(name,x,y,profile,material,group,segments=64):
    v=[(x+r*math.cos(2*math.pi*i/segments),y+r*math.sin(2*math.pi*i/segments),z) for r,z in profile for i in range(segments)]
    f=[(k*segments+i,k*segments+(i+1)%segments,(k+1)*segments+(i+1)%segments,(k+1)*segments+i) for k in range(len(profile)-1) for i in range(segments)]
    f.extend([tuple(reversed(range(segments))),tuple(range((len(profile)-1)*segments,len(profile)*segments))])
    ob=mesh(name,v,f,material,group)
    for p in ob.data.polygons:p.use_smooth=True
    return ob

def window(name,x,y,z,w,h,group,arched=False):
    if arched:
        arch_panel(name+'_glass',x,y,z,w,h,glass,group);arch_ring(name+'_stone_arch',x+.13,y,z+h-w/2,w/2,.22,.25,stone,group,16)
    else:box(name+'_glass',x-.10,y-w/2,z,.13,w,h,glass,group)
    for yy in [y-w/2-.15,y+w/2]:box(name+'_jamb',x-.02,yy,z,.22,.15,h-(w/2 if arched else 0),trim,group)
    box(name+'_sill',x-.10,y-w/2-.28,z-.15,.4,w+.56,.20,stone,group)
    box(name+'_center_mullion',x+.09,y-.065,z,.10,.13,h,frame,group)
    for k in [1,2,3]:
        zz=z+k*h/4
        if arched and zz>z+h-w/2:
            half=math.sqrt(max(0,(w/2)**2-(zz-(z+h-w/2))**2))
        else:half=w/2
        box(name+'_transom',x+.08,y-half,zz,.11,2*half,.10,frame,group)

def hiproof(name,x0,x1,y0,y1,z,rise,group):
    # Long ridge parallel to the original north-south footprint.
    v=[(x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z),((x0+x1)/2,y0+3,z+rise),((x0+x1)/2,y1-3,z+rise)]
    mesh(name,v,[(0,1,4),(1,2,5,4),(2,3,5),(3,0,4,5),(0,3,2,1)],roof,group)
    beam(name+'_ridge',v[4],v[5],.18,stone,group)
    # Visible roof courses run along the roof; no image textures are embedded.
    for k in range(1,9):
        t=k/9;xx=x1+(x0-x1)*t/2;zz=z+rise*t
        beam(name+'_tile_course', (xx,y0+3*t,zz+.025),(xx,y1-3*t,zz+.025),.045,mortar,group)

outline=[[0.08,82.01],[-11.81,81.76],[-11.81,37.2],[-10.38,-52.49],[-10.45,-56.8],[3.41,-56.86],[3.48,-52.38],[4.91,-51.35],[11.06,-51.49],[11.23,-44.63],[3.49,-44.83],[3.48,-36.07],[8.37,-36.33],[8.37,-26.82],[4.5,-26.55],[4.56,-12.82],[6.06,-12.0],[6.75,-10.1],[12.59,-9.95],[12.52,-11.21],[16.26,-11.17],[16.53,10.84],[12.52,11.01],[12.45,10.1],[7.08,10.3],[6.13,12.33],[4.6,13.25],[4.91,26.27],[8.41,26.34],[10.55,28.18],[10.28,37.28],[2.12,37.28],[1.99,57.54],[3.89,57.54],[3.89,69.36],[0.35,69.5],[0.08,82.01]]
prism('Exact_source_geographic_outline',outline,0,.30,stone,BASE)
# Main hall solid behind its projecting entrance. The front arch remains visibly open/recessed.
box('Central_hall_rear_volume',-10.8,-11.0,.3,20.6,22.0,19.4,brick,CENT)
box('Central_hall_top_cornice',-11,-11.3,19.5,21.1,22.6,.65,trim,CENT)
# Front portico piers leave three real door bays and a large arched fanlight.
for y in [-10.35,-5.3,4.55,9.45]:
    box('Entrance_granite_pier',12.1,y,.3,4.3,.9,10.3,stone,CENT)
    for z in [1.2,2.4,3.6,4.8,6.0,7.2,8.4,9.6]:box('Pier_rustication',16.41,y-.02,z,.055,.94,.055,mortar,CENT)
for y in [-7.65,0,7.65]:
    box('Recessed_entrance_door',12.8,y-1.65,.55,.15,3.3,5.3,glass,CENT)
    for dy in [-1.7,0,1.6]:box('Entrance_door_frame',13,y+dy,.55,.12,.12,5.3,black,CENT)
    box('Door_transom',13,y-1.7,4.6,.15,3.4,.16,black,CENT)
box('Entry_stone_entablature',12,-10.8,6.5,4.6,21.6,.8,stone,CENT)
arch_panel('Main_semicircular_fanlight',15.65,0,8.3,18.2,12.1,glass,CENT)
arch_ring('Main_carved_arch',16.6,0,11.3,9.1,1.35,2.8,stone,CENT)
arch_ring('Main_projecting_arch_drip_edge',16.8,0,11.3,10.4,.25,3.2,trim,CENT)
for a in range(0,181,10):
    theta=math.radians(a)
    beam('Main_arch_radial_stone_joint',(16.83,9.16*math.cos(theta),11.3+9.16*math.sin(theta)),(16.83,10.36*math.cos(theta),11.3+10.36*math.sin(theta)),.045,mortar,CENT)
for y in [-8,-6,-4,-2,0,2,4,6,8]:
    top=11.3+math.sqrt(9.1**2-y*y)
    box('Great_window_vertical_frame',15.79,y-.055,8.3,.11,.11,top-8.3,frame,CENT)
for z in [10.2,12.1,14.0,15.9,17.8]:
    half=9.1 if z<=11.3 else math.sqrt(9.1**2-(z-11.3)**2)
    box('Great_window_transom',15.8,-half,z,.12,2*half,.12,frame,CENT)
# Clock pedestal interrupts the great window exactly as seen in the official front photograph.
box('Clock_stone_pedestal',16.8,-1.7,7.2,.85,3.4,4.2,stone,CENT)
mesh('Clock_broken_pediment',[(17.75,-2.0,11.3),(17.75,0,12.5),(17.75,2.0,11.3)],[(0,1,2)],trim,CENT)
def front_disc(name,x,y,z,r,material,group):
    return mesh(name,[(x,y+r*math.cos(a),z+r*math.sin(a)) for a in [2*math.pi*i/64 for i in range(64)]],[tuple(range(64))],material,group)
front_disc('Clock_dark_bezel',17.68,0,9.85,1.17,black,CENT);front_disc('Clock_ivory_dial',17.70,0,9.85,1.02,cream,CENT)
for i in range(12):
    a=2*math.pi*i/12
    beam('Clock_hour_mark',(17.73,.78*math.sin(a),9.85+.78*math.cos(a)),(17.73,.95*math.sin(a),9.85+.95*math.cos(a)),.08,black,CENT)
beam('Clock_hour_hand',(17.77,0,9.85),(17.77,-.52,10.15),.10,black,CENT)
beam('Clock_minute_hand',(17.79,0,9.85),(17.79,.10,10.64),.07,black,CENT)
# A green balustrade strip below the fanlight: repeated openings, not an opaque billboard.
for side in [-1,1]:
    y0=2.0 if side==1 else -9.1
    box('Balustrade_lower_rail',16.3,y0,7.4,.30,7.1,.24,trim,CENT)
    box('Balustrade_top_rail',16.3,y0,8.65,.30,7.1,.25,trim,CENT)
    for k in range(12):
        y=y0+.3+k*.58
        beam('Balustrade_diagonal',(16.45,y,7.65),(16.45,y+.45,8.65),.10,frame,CENT)
        beam('Balustrade_diagonal',(16.46,y+.45,7.65),(16.46,y,8.65),.10,frame,CENT)
# Dome on its actual central hall, with an east-facing thermal window and metal seams.
lathe('Dome_stone_drum',0,0,[(8.8,19.8),(8.8,22.8),(9.1,23.15),(9.1,23.5)],stone,DOME)
profile=[(9.2*math.cos(t),23.35+7.35*math.sin(t)) for t in [i*math.pi/2/24 for i in range(25)]]
lathe('Broad_aged_copper_ellipsoid',0,0,profile,copper,DOME,96)
for j in range(24):
    a=2*math.pi*j/24
    for k in range(len(profile)-1):
        r,z=profile[k];rr,zz=profile[k+1]
        if rr>.8:beam('Dome_copper_seam',(r*math.cos(a),r*math.sin(a),z+.035),(rr*math.cos(a),rr*math.sin(a),zz+.035),.09,ribmat,DOME)
arch_panel('Dome_front_half_round_glazing',9.03,0,23.25,10.9,5.65,glass,DOME)
arch_ring('Dome_thermal_window_carved_stone',9.25,0,23.45,5.45,.72,.5,stone,DOME)
for a in range(0,181,20):
    t=math.radians(a);beam('Dome_fanlight_radial',(9.30,0,23.45),(9.30,5.42*math.cos(t),23.45+5.42*math.sin(t)),.08,frame,DOME)
for y in [-3.5,-1.75,0,1.75,3.5]:
    top=23.45+math.sqrt(5.45**2-y*y)
    box('Dome_window_vertical',9.32,y-.045,23.45,.10,.09,top-23.45,frame,DOME)
lathe('Dome_lantern_base',0,0,[(1.25,30.2),(1.25,30.65),(1.0,30.8)],copper,DOME,32)
lathe('Lantern_dark_open_center',0,0,[(.77,30.7),(.77,32.05)],glass,DOME,24)
for j in range(8):
    a=math.pi*j/4
    beam('Lantern_open_column',(.95*math.cos(a),.95*math.sin(a),30.7),(.95*math.cos(a),.95*math.sin(a),32.05),.16,copper,DOME)
lathe('Lantern_copper_cap',0,0,[(1.3,32.0),(1.35,32.2),(.9,32.45),(.4,32.6),(0,32.75)],copper,DOME,32)
beam('Lantern_finial',(0,0,32.7),(0,0,34.25),.09,black,DOME)
# Official frontal-photo proportion review: copper dome is approximately0.60-0.65
# of the great stone arch span, not the nearly0.9 ratio of the first study.
# Keep the hall center and drum base; narrow the complete ensemble consistently.
for ob in list(COL[DOME].objects):
    if ob.type=='MESH':
        for v in ob.data.vertices:
            v.co.x*=.74;v.co.y*=.74
            if v.co.z>23.35:v.co.z=23.35+(v.co.z-23.35)*.82
# Two slender roof turrets are individual elements framing the central dome.
for y in [-10.6,10.6]:
    box('Central_flanking_turret',3.5,y-1.05,16.2,3.0,2.1,8.8,stone,DOME)
    window('Turret_arched_slit',6.55,y,19.0,.75,4.9,DOME,True)
    for z in [17.1,22.0,24.5]:box('Turret_stone_stringcourse',3.3,y-1.25,z,3.4,2.5,.26,trim,DOME)
    lathe('Turret_green_cap',5.0,y,[(1.60,24.8),(1.58,25.1),(1.0,25.8),(.25,26.4),(0,26.65)],copper,DOME,32)
    beam('Turret_cap_spike',(5,y,26.4),(5,y,27.35),.07,black,DOME)

# Main wings retain their footprint-specific lengths and projecting end pavilions.
for group,y0,y1,xf,end0,end1,endx in [(SOUTH,-26.55,-12.8,4.55,-36.2,-26.55,8.3),(NORTH,13.25,26.3,4.8,26.3,37.2,10.25)]:
    box('Long_red_brick_wing',-10.8,y0,5.1,xf+10.8,y1-y0,9.1,brick,group)
    box('Projecting_end_pavilion',-10.8,end0,5.1,endx+10.8,end1-end0,9.55,brick,group)
    for a,b,xfront in [(y0,y1,xf),(end0,end1,endx)]:
        box('Rusticated_granite_ground_storey',-10.85,a,.3,xfront+10.91,b-a,4.8,stone,group)
        for z,h in [(5.0,.38),(7.65,.30),(11.6,.20),(13.75,.38),(14.2,.30)]:
            box('Pale_horizontal_stone_belt',-11.0,a-.14,z,xfront+11.2,b-a+.28,h,trim,group)
        for yy in [a+.2,b-.8]:
            for z in [5.55,6.3,7.05,8.35,9.1,9.85,10.6,12.0,12.75,13.45]:
                box('Alternating_stone_corner_quoin',xfront+.025,yy,z,.17,.6 if int(z*10)%2 else .85,.35,trim,group)
    for j in range(4):
        yy=y0+1.8+j*(y1-y0-3.6)/3
        window('Upper_wing_paired_window',xf+.08,yy,8.65,1.65,3.7,group)
        window('Ground_wing_arch_window',xf+.08,yy,1.15,1.8,4.5,group,True)
        arch_panel('Intermediate_arch_lunette',xf+.10,yy,6.0,1.7,1.4,glass,group)
        arch_ring('Intermediate_lunette_stone',xf+.22,yy,6.55,.85,.18,.18,stone,group,12)
    yc=(end0+end1)/2
    for zz in [1.0,8.55]:window('End_pavilion_paired_tall_window',endx+.08,yc,zz,2.9,3.9,group)
    # Curved gable silhouette built as an extruded shape, over a real pitched roof.
    hiproof('Long_wing_hip_roof',-11.15,xf+.4,y0-.3,y1+.3,14.5,3.3,group)
    hiproof('End_pavilion_roof',-11.15,endx+.4,end0-.3,end1+.3,14.6,3.8,group)
    gp=[(yc-5.1,14.5),(yc-5.1,15.0),(yc-3.9,15.4),(yc-3.1,17.0),(yc-1.0,18.0),(yc,18.4),(yc+1.0,18.0),(yc+3.1,17.0),(yc+3.9,15.4),(yc+5.1,15.0),(yc+5.1,14.5)]
    n=len(gp);v=[(xx,yy,zz) for xx in [endx-.15,endx+.25] for yy,zz in gp]
    mesh('Curved_renaissance_end_gable',v,[tuple(reversed(range(n))),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],stone,group)
    for k in range(len(gp)-1):beam('Gable_carved_edge',(endx+.42,*gp[k]),(endx+.42,*gp[k+1]),.20,trim,group)
    window('Gable_arched_attic_window',endx+.49,yc,14.65,3.1,3.0,group,True)
    # Small eyebrow dormers are visible over the wings between the central and end gables.
    for yy in [y0+3,y1-3]:
        arch_panel('Roof_eyebrow_dormer_glass',xf-1.3,yy,15.45,1.5,1.1,glass,group)
        arch_ring('Roof_eyebrow_stone',xf-1.18,yy,15.8,.75,.22,.4,stone,group,12)
    # Actual rear elevation is less documented; simple tall windows with no invented sculpture.
    for yy in [a+1.8 for a in [y0,y0+4,y0+8]]:
        for zz in [1.1,8.55]:
            box('Rear_window',-10.93,yy,zz,.12,1.6,3.5,glass,REAR)
            box('Rear_window_sill',-11.1,yy-.15,zz-.18,.3,1.9,.18,stone,REAR)
# Southern single-storey VIP annex follows its stepped source perimeter.
vip=[(-10.45,-56.75),(3.4,-56.8),(3.48,-52.38),(4.91,-51.35),(11.06,-51.49),(11.18,-44.66),(3.49,-44.8),(3.48,-36.15),(-10.7,-36.15)]
prism('South_VIP_annex',vip,.3,6.3,brick,VIP)
prism('South_VIP_cornice',vip,6.6,.35,trim,VIP)
prism('South_VIP_flat_roof',vip,6.95,.12,roof,VIP)
for yy in [-53.8,-40.0]:window('VIP_side_arch',3.58,yy,.85,3.5,4.7,VIP,True)
window('VIP_projecting_portal',11.28,-48.0,.4,4.7,5.55,VIP,True)
for yy in [-51.35,-45.1]:
    box('VIP_portal_granite_pier',10.78,yy,.3,.5,.5,6.5,stone,VIP)
# Long low north annex / RTO. This is the exact owned child, not a modern station hall.
northpoly=[(-11.81,37.2),(2.1,37.28),(1.99,57.54),(3.89,57.54),(3.89,69.36),(.35,69.5),(.08,82.01),(-11.81,81.76)]
prism('North_RTO_long_brick_body',northpoly,.3,5.9,brick,RTO)
prism('North_RTO_pale_roof_cornice',northpoly,6.2,.40,stone,RTO)
prism('North_RTO_low_roof',northpoly,6.6,.17,roof,RTO)
for j in range(11):
    yy=39.3+j*3.9;xf=2.08 if yy<57.5 else 3.89 if yy<69.4 else .24
    window('RTO_ground_window',xf+.08,yy,.9,2.3,3.4,RTO)
    box('RTO_brick_pier',xf+.15,yy+1.35,.3,.32,.40,5.7,stone,RTO)
    box('RTO_upper_transom',xf+.08,yy-1.1,4.8,.13,2.2,.75,glass,RTO)

# Compact export: retain architectural collection boundaries and physical material choices.
for cname,col in COL.items():
    if cname==QA:continue
    for material in list(bpy.data.materials):
        obs=[o for o in list(col.objects) if o.type=='MESH' and o.data.materials[0]==material]
        if not obs:continue
        bpy.ops.object.select_all(action='DESELECT')
        for ob in obs:ob.select_set(True)
        bpy.context.view_layer.objects.active=obs[0]
        if len(obs)>1:bpy.ops.object.join()
        ob=bpy.context.object;ob.name=cname+'__'+material.name
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ob.select_set(False)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32
scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world.use_nodes=True;bg=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs[0].default_value=(.69,.76,.85,1);bg.inputs[1].default_value=.6
scene.view_settings.view_transform='AgX'
def camera(name,location,target,scale):
    d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);COL[QA].objects.link(o);o.location=location;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='ORTHO';d.ortho_scale=scale
camera('View_East_Front',(160,0,39),(0,0,15),99)
camera('View_South_East',(145,-115,97),(-1,6,11),157)
camera('View_North_East',(155,142,120),(-1,12,11),166)
camera('View_Plan',(0,12,200),(0,12,0),240)
d=bpy.data.lights.new('Review_Sun','SUN');o=bpy.data.objects.new('Review_Sun',d);COL[QA].objects.link(o);d.energy=2.5;d.angle=.14;o.rotation_euler=(math.radians(25),math.radians(25),math.radians(-20))
scene.camera=bpy.data.objects['View_South_East']
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.overlay.show_overlays=False;area.spaces.active.shading.type='MATERIAL'
building=[o for c,col in COL.items() if c!=QA for o in col.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in building:o.select_set(True)
bpy.context.view_layer.objects.active=building[0]
glb=OUT/'culture-station-seoul284.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_cameras=False,export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'culture-station-seoul284.blend'))
v=[o.matrix_world@p.co for o in building for p in o.data.vertices];mn=[min(p[i] for p in v) for i in range(3)];mx=[max(p[i] for p in v) for i in range(3)]
tri=0
for o in building:o.data.calc_loop_triangles();tri+=len(o.data.loop_triangles)
uncertainties=['No measured building height supplied by the geospatial source; 32.29m finial height is an explicit photo-derived estimate.',
'Facade dimensions, dome profile, windows and roof pitches are manual interpretations of official photographs, not measured CAD or photogrammetry.',
'Official photographs were published in 2021 but their capture dates are not specified; current facade condition is not independently surveyed.',
'Rear elevation and low RTO roof are less well photographed; these use conservative simplified geometry. RTO floor count2 in source is not treated as evidence of equal two-storey facade height.',
'Clock hands are illustrative; no real time is claimed. Sculpture, temporary installations, advertisements and the modern Seoul Station are omitted.']
report={'id':'bespoke-culture-station-seoul284','nameKo':'문화역서울284(구 서울역사)','coordinate':{'lon':LON,'lat':LAT},'footprintIds':IDS,
'model':glb.name,'sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'bytes':glb.stat().st_size,'triangles':tri,'meshObjects':len(building),'materials':sorted({m.name for o in building for m in o.data.materials}),
'gltfBounds':{'min':[mn[0],mn[2],-mx[1]],'max':[mx[0],mx[2],-mn[1]]},'heightBasis':'photographic estimate; source height unavailable',
'coordinateConvention':'Baked east X / up Y / south Z; no additional yaw. Long axis north-south; main facade east.',
'components':list(COL)[:-1],'uncertainty':uncertainties,'tooling':{'authoring':'Blender4.5.11 through real MCP execute_blender_code','port':9876},
'preservedNeighbor':{'id':'a78efc86-7dae-4e63-8e4b-d672a7eff741','name':'서울역 신역사','source':'https://www.openstreetmap.org/relation/7307085','policy':'Not owned, not modeled, original source remains visible'},
'replacedReference':'reference-flight-seoul-station','replacementBasis':'Old Flight main station runs east-west with an approximately44m principal frontage; source old-station footprint is approximately139m north-south. New model owns only the same old-station parent and RTO child. Legacy GLB bytes are untouched.'}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
sources=[{'url':'https://seoul284.org/cms/content/view/253','observations':['Official exterior photos: central dome, thermal window, great arched entrance and clock, red brick and stone belts, curved end gables, low annexes.']},{'url':'https://seoul284.org/space/menu/256','observations':['Official floor plan: central hall, asymmetrical north/south rooms, north RTO, projecting east entrance.']},{'url':'https://www.openstreetmap.org/way/759569673','observations':['Geographic old-station outline from existing local source record w759569673@5.']},{'url':'https://www.openstreetmap.org/way/1103628080','observations':['Northern RTO child footprint within the old-station parent.']}]
bundle={'siteId':'culture-station-seoul284','sources':sources,'assets':[{'id':report['id'],'nameKo':report['nameKo'],'file':str(glb),'blendSource':str(OUT/'culture-station-seoul284.blend'),'coordinate':report['coordinate'],'category':'cultural-site','footprintIds':IDS,'supersedes':['reference-flight-seoul-station'],'referenceUrl':sources[0]['url'],'components':report['components'],'uncertainties':uncertainties}],
'places':[{'id':'culture-station-seoul284','name':'문화역서울284 · 구 서울역사','subtitle':'중앙 돔과 시계가 있는 붉은 벽돌 구역사','center':[LON,LAT],'zoom':17.8,'source_url':sources[0]['url']}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'exported':str(glb),'triangles':tri,'bounds':report['gltfBounds']}))
