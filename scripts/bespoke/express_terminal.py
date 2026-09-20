"""Individual Seoul Gyeongbu/Yeongdong terminal study, executed through Blender MCP.

Source geometry: c313b964-022c-4f5a-9599-d69d0155d010 (OSM w309352819).
References and uncertainty: docs/model-audit/express-terminal-reference.md.
All facade dimensions below are manual photo interpretations, not measured CAD.
Blender uses east X, north Y, up Z; glTF exporter changes to east X, up Y, south Z.
"""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/model-source/bespoke/express-terminal'
OUT.mkdir(parents=True, exist_ok=True)
bpy.context.preferences.filepaths.save_version=0
for old_backup in OUT.glob('express-terminal.blend[1-9]'): old_backup.unlink()
LON, LAT = 127.0055703, 37.5042468
ANGLE = math.radians(20.9)
C, S = math.cos(ANGLE), math.sin(ANGLE)
SOURCE_ID = 'c313b964-022c-4f5a-9599-d69d0155d010'

# Only this dedicated artist instance is cleared; no shared/public assets are touched.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for col in list(bpy.data.collections):
    if col.name != 'Collection': bpy.data.collections.remove(col)
bpy.data.orphans_purge(do_recursive=True)
collections = {}
for name in ['01_Main_Triangular_Section', '02_Recessed_Facade',
             '03_Rooftop_Sign_Terrace', '04_Low_Yeongdong_Wing',
             '05_Bus_Gates_Canopy', '06_End_Walls_Stairs', 'QA_Cameras_Lights']:
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    collections[name] = col

def material(name, color, roughness=.7, metallic=0):
    m = bpy.data.materials.new(name); m.diffuse_color = (*color,1)
    m.use_nodes = True
    p = next(node for node in m.node_tree.nodes if node.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value = (*color,1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metallic
    return m

ivory = material('Observed_warm_grey_concrete', (.61,.60,.55))
light = material('Observed_off_white_slab_edges', (.82,.82,.76))
dark = material('Deep_recesses_not_solid_black', (.055,.070,.073))
glass = material('Observed_blue_grey_windows', (.16,.27,.30), .23, .35)
glass2 = material('Muted_window_alternate', (.20,.30,.32), .3, .25)
metal = material('Silver_window_mullions', (.48,.51,.51), .38, .45)
blue = material('Observed_blue_terminal_letters', (.025,.15,.36), .48)
roof = material('Grey_flat_roof_surface', (.29,.31,.29))
green = material('Restrained_terrace_planting', (.17,.25,.11))
yellow = material('Platform_safety_marking', (.7,.50,.08))
warm = material('Observed_warm_rooftop_service_block', (.42,.33,.27))

def world(v):
    x,y,z = v; return (x*C-y*S,x*S+y*C,z)

def mesh(name, verts, faces, mat, group):
    me = bpy.data.meshes.new(name)
    me.from_pydata([world(v) for v in verts], [], faces); me.update()
    ob = bpy.data.objects.new(name, me); collections[group].objects.link(ob)
    ob.data.materials.append(mat)
    # Recalculate after explicit construction to make winding independent of polygon orientation.
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
    ob.select_set(False)
    return ob

def box(name, x,y,z, w,d,h, mat, group):
    vs=[(x+dx*w,y+dy*d,z+dz*h) for dz in (0,1) for dy in (0,1) for dx in (0,1)]
    return mesh(name,vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],mat,group)

def prism(name, polygon, bottom, top, mat, group):
    n=len(polygon); vs=[(x,y,z) for z in [bottom,top] for x,y in polygon]
    return mesh(name,vs,[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],mat,group)

def beam(name, p1,p2,width,mat,group):
    a,b=Vector(p1),Vector(p2); axis=(b-a).normalized()
    side=axis.cross(Vector((0,0,1)))
    if side.length<.01: side=Vector((1,0,0))
    side.normalize(); side*=width/2; up=axis.cross(side).normalized()*width/2
    vs=[tuple(p+sx*side+sy*up) for p in [a,b] for sx,sy in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    return mesh(name,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat,group)

def text_face(name, body, origin, right, up, size, mat, group, target_width=None):
    cu=bpy.data.curves.new(name,'FONT');cu.body=body;cu.size=size
    cu.align_x='CENTER';cu.align_y='CENTER';cu.extrude=.035;cu.resolution_u=4
    fontpath='/System/Library/Fonts/Supplemental/AppleGothic.ttf'
    cu.font=bpy.data.fonts.load(fontpath)
    ob=bpy.data.objects.new(name,cu);collections[group].objects.link(ob)
    r,u=Vector(world(right)),Vector(world(up));n=r.cross(u)
    ob.matrix_world=Matrix(((r.x,u.x,n.x,0),(r.y,u.y,n.y,0),(r.z,u.z,n.z,0),(0,0,0,1)))
    ob.location=world(origin);cu.materials.append(mat)
    bpy.context.view_layer.objects.active=ob;ob.select_set(True)
    bpy.ops.object.convert(target='MESH');ob.select_set(False)
    if target_width:
        span=max(v.co.x for v in ob.data.vertices)-min(v.co.x for v in ob.data.vertices)
        for v in ob.data.vertices: v.co.x*=target_width/span
    return ob

MAIN='01_Main_Triangular_Section';FACADE='02_Recessed_Facade';TOP='03_Rooftop_Sign_Terrace'
LOW='04_Low_Yeongdong_Wing';GATES='05_Bus_Gates_Canopy';ENDS='06_End_Walls_Stairs'

# The actual south end is non-rectangular. This plinth retains its source outline.
main_outline=[(1.343,157.518),(0,0),(32.348,-4.607),(46.465,-4.719),
              (76.497,2.211),(76.633,129.708),(76.509,134.856),(76.52,157.57)]
prism('Main_source_outline_base',main_outline,0,.55,ivory,MAIN)

# Photo-led section: western high back, eastern retreating occupied floors.
# The values are deliberately explicit site authoring, not a floor-count facade generator.
section=[(0,75.7),(6.4,75.7),(11.0,70.6),(15.6,65.5),(20.2,60.4),
         (24.8,55.3),(29.4,50.2),(34.0,45.1),(38.6,40.0),(43.2,34.9)]
for i,((z0,w0),(z1,w1)) in enumerate(zip(section,section[1:])):
    # Continuous back/side solid, deeply recessed courtyard-side glazing.
    profile=[(1.8,1.1,z0),(w0-1.0,1.1,z0),(w1-1.0,1.1,z1),(1.8,1.1,z1),
             (1.8,155.8,z0),(w0-1.0,155.8,z0),(w1-1.0,155.8,z1),(1.8,155.8,z1)]
    if i==0:
        # Keep the ground enclosure behind the actual open entrance colonnade.
        profile=[(min(x,67.0),y,z) for x,y,z in profile]
    mesh('Main_level_%02d_recessed_body'%i,profile,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)],dark,MAIN)
    slabw=w1+1.0 if i else 76.2
    box('Level_%02d_projecting_slab'%i,1.0,.7,z1-.55,slabw-1.0,155.3,.55,light,MAIN)
    if i==0:
        # Terminal entrance is taller and open; don't make this another small office floor.
        for j in range(17):
            y=4+j*9.1
            box('Ground_gate_column_%02d'%j,73.5,y,0,1.15,1.05,6.1,ivory,GATES)
            box('Ground_entry_glass_%02d'%j,73.0,y+1.15,.55,.12,7.75,4.65,glass,FACADE)
        continue
    # Glazed panels follow this floor's actual inclined plane, with real depth to the eaves.
    for j in range(24):
        y=3.0+j*6.28; ya,yb=y,y+5.8
        za,zb=z0+.62,z1-.75
        xa=w0-1.0+(w1-w0)*(za-z0)/(z1-z0)+.08
        xb=w0-1.0+(w1-w0)*(zb-z0)/(z1-z0)+.08
        mesh('East_floor_%02d_window_%02d'%(i,j),[(xa,ya,za),(xa,yb,za),(xb,yb,zb),(xb,ya,zb)],[(0,1,2,3)],glass if j%3 else glass2,FACADE)
        for dy in [0,2.9,5.8]:
            beam('Mullion_%02d_%02d_%s'%(i,j,dy),(xa+.07,y+dy,za),(xb+.07,y+dy,zb),.13,metal,FACADE)
    # Closed triangular end panels are a defining part of the observed silhouette.
    for y in [1.05,155.83]:
        mesh('Triangular_end_level_%02d_%s'%(i,y),[(1.8,y,z0),(w0-.8,y,z0),(w1-.8,y,z1),(1.8,y,z1)],[(0,1,2,3)],light,ENDS)
    # Western street elevation has regular horizontal slot windows, different from the sloping east.
    box('Western_floor_%02d_wall'%i,1.55,1.1,z0+.15,.28,154.7,z1-z0-.55,ivory,FACADE)
    for j in range(24):
        box('Western_slot_%02d_%02d'%(i,j),1.35,3+j*6.28,z0+1.15,.08,5.45,2.05,glass,FACADE)

# Long diagonal concrete frame ribs on the visible east slope, interrupted at terrace slabs.
for j in [0,4,8,12,16,20,24]:
    y=2.5+j*6.26
    for i in range(1,len(section)-1):
        z0,w0=section[i];z1,w1=section[i+1]
        beam('East_inclined_frame_%02d_%02d'%(j,i),(w0-.40,y,z0+.1),(w1-.40,y,z1-.5),.48,light,FACADE)

# The published photos show a service block and two billboard frames above the terrace,
# rather than an additional full-height occupied floor. Keep everything under source51m.
box('Roof_walk_surface',2,1.1,43.2,32.9,154.7,.22,roof,TOP)
box('Roof_rear_upstand',1.55,1.1,43.2,.35,154.7,1.0,light,TOP)
box('Roof_terrace_outer_parapet',34.45,1.1,43.2,.3,154.7,.75,light,TOP)
for j in range(38):
    box('Roof_railing_post_%02d'%j,34.55,2.5+j*4,43.9,.08,.08,.65,metal,TOP)
beam('Roof_railing_top',(34.6,1.1,44.55),(34.6,155.8,44.55),.08,metal,TOP)
box('Warm_central_rooftop_service_block',3.0,43.0,43.42,19.0,65.0,7.28,warm,TOP)
box('Service_block_cap',2.8,42.8,50.7,19.4,65.4,.3,ivory,TOP)
for j in range(14):
    y=45+j*4.45
    box('Service_block_vertical_slit_%02d'%j,22.03,y,44.2,.08,1.35,5.8,dark,TOP)
    box('Service_slit_edge_%02d'%j,22.11,y-.16,44.05,.12,.16,6.1,ivory,TOP)
    for z in [45.5,47.0,48.5]:
        box('Service_slit_louvre_%02d_%s'%(j,z),22.12,y,z,.1,1.35,.12,metal,TOP)
for y in [7,134]:
    # Blank physical boards and support frames: no historical/current advertisements copied.
    box('Billboard_blank_panel_%s'%y,25.8,y,44.0,.42,17.0,6.65,light,TOP)
    for dy in [0,16.65]:
        box('Billboard_vertical_frame_%s_%s'%(y,dy),26.22,y+dy,43.45,.18,.35,7.35,metal,TOP)
    for z in [44.0,50.45]:
        box('Billboard_horizontal_frame_%s_%s'%(y,z),26.22,y,z,.18,17.0,.35,metal,TOP)
    for dy in [2,14]:
        beam('Billboard_rear_brace_%s_%s'%(y,dy),(19.0,y+dy,43.42),(25.5,y+dy,49.8),.24,metal,TOP)
    box('Roof_planter_%s'%y,29,y,43.42,2.5,8.0,.55,ivory,TOP)
    box('Roof_planter_foliage_%s'%y,29.3,y+.3,43.97,1.9,7.4,.35,green,TOP)
# The official terrace photo confirms actual wording, while proportions remain interpreted.
mesh('Large_sloping_terminal_sign_fascia',[(40.1,10,38.7),(40.1,147,38.7),(30.4,147,47.6),(30.4,10,47.6)],[(0,1,2,3)],light,TOP)
text_face('Blue_Seoul_Express_Korean','서울고속버스터미널',(34.65,78.5,44.2),(0,1,0),(-.737,0,.675),6.3,blue,TOP,75.0)
text_face('Blue_Seoul_Express_English','SEOUL EXPRESS BUS TERMINAL',(38.18,78.5,41.0),(0,1,0),(-.737,0,.675),1.65,blue,TOP,58.0)

# Low Yeongdong wing shares the source perimeter, never the main building's 51m height.
low_outline=[(76.52,157.57),(318.316,157.723),(318.248,127.268),
             (200.452,127.29),(148.404,127.54),(98.969,127.328),
             (98.611,134.411),(76.509,134.856)]
prism('Low_wing_source_plinth',low_outline,0,.35,ivory,LOW)
prism('Low_wing_roof',low_outline,8.45,9.1,light,LOW)
box('Low_wing_street_wall',77,155.6,.35,240.5,1.2,7.95,ivory,LOW)
for j in range(36):
    x=80+j*6.48
    box('Low_street_glazing_%02d'%j,x,156.86,1.35,5.55,.1,4.55,glass,LOW)
    box('Low_street_mullion_%02d'%j,x+2.7,156.99,1.35,.15,.1,4.55,metal,LOW)
box('Low_wing_street_fascia',77,156.8,6.5,240.5,.6,1.25,light,LOW)
box('Low_wing_roof_inner_parapet',99,127.3,9.1,218,.3,.6,ivory,LOW)
box('Low_wing_roof_outer_parapet',77,157.2,9.1,240.5,.3,.6,ivory,LOW)
box('Low_roof_surface',99,128,9.1,217,28.5,.08,roof,LOW)

# Courtyard-facing sheltered bus gates; spans are estimates informed by the operator plan.
for j in range(22):
    x=101+j*9.65
    box('Low_gate_pier_%02d'%j,x,128.2,.35,1.05,1.15,8.1,light,GATES)
    beam('Gate_haunch_%02d'%j,(x+.5,128.75,6.7),(x+2.3,128.75,8.3),.50,light,GATES)
    box('Gate_inner_shopfront_%02d'%j,x+1.05,144,1.0,8.6,.18,5.0,glass,GATES)
    box('Gate_overhead_band_%02d'%j,x+1.05,128.35,6.1,8.6,.3,1.5,ivory,GATES)
    if j<20:
        text_face('Yeongdong_gate_number_%02d'%(17+j),str(17+j),(x+5.1,128.10,6.85),(1,0,0),(0,0,1),.85,blue,GATES)
    box('Yellow_gate_edge_%02d'%j,x+1.4,127.58,.35,6.7,.12,.035,yellow,GATES)

# One curved glazed street entry is visible in the operator photo. Its dimensions and
# position are explicitly an interpretation, not an independently located source part.
cx=190; radius=8.2; spring=8.5; segments=16
for i in range(segments):
    a=math.pi*i/segments;b=math.pi*(i+1)/segments
    xa,za=cx+radius*math.cos(a),spring+4.8*math.sin(a)
    xb,zb=cx+radius*math.cos(b),spring+4.8*math.sin(b)
    mesh('Entrance_barrel_glazing_%02d'%i,[(xa,136,za),(xa,157.0,za),(xb,157.0,zb),(xb,136,zb)],[(0,1,2,3)],glass,LOW)
for y in [136,139,142,145,148,151,154,157]:
    for i in range(segments):
        a=math.pi*i/segments;b=math.pi*(i+1)/segments
        beam('Barrel_roof_rib_%s_%02d'%(y,i),(cx+radius*math.cos(a),y,spring+4.8*math.sin(a)),(cx+radius*math.cos(b),y,spring+4.8*math.sin(b)),.16,metal,LOW)

# South-end stair/entrance details belong to the main source footprint, without a ground plane.
for y in [12,141]:
    box('West_stair_core_%s'%y,1.1,y,.55,4.0,7.0,42.65,light,ENDS)
    for z in [9,14,19,24,29,34,39]:
        box('Stair_core_recess_%s_%s'%(y,z),.98,y+2,z,.08,2.3,1.65,glass,ENDS)
# Large end frame relief is visible in the archival exterior view, with no extra ornament.
for y in [.5,156.25]:
    box('End_vertical_structural_edge_%s'%y,2.0,y,.55,2.15,.55,42.65,light,ENDS)
    for i in range(1,len(section)-1):
        z0,w0=section[i];z1,w1=section[i+1]
        beam('End_inclined_structural_edge_%s_%s'%(y,i),(w0-2,y,z0),(w1-2,y,z1),1.05,light,ENDS)

# Join details by named architectural collection/material for compact scene and GLB.
for cname,col in collections.items():
    if cname.startswith('QA'): continue
    for mat in list(bpy.data.materials):
        objs=[o for o in list(col.objects) if o.type=='MESH' and len(o.data.materials)==1 and o.data.materials[0]==mat]
        if not objs:continue
        bpy.ops.object.select_all(action='DESELECT')
        for ob in objs:ob.select_set(True)
        bpy.context.view_layer.objects.active=objs[0]
        if len(objs)>1:bpy.ops.object.join()
        ob=bpy.context.object;ob.name=cname+'__'+mat.name
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        ob.select_set(False)

scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=1500;scene.render.resolution_y=1050;scene.render.resolution_percentage=100
scene.world.color=(.4,.4,.4)
scene.world.use_nodes=True
background=next(node for node in scene.world.node_tree.nodes if node.type=='BACKGROUND')
background.inputs[0].default_value=(.72,.78,.86,1)
background.inputs[1].default_value=.6
scene.view_settings.view_transform='AgX'

def camera(name,position,target,scale):
    dat=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,dat);collections['QA_Cameras_Lights'].objects.link(ob)
    ob.location=world(position);direction=Vector(world(target))-ob.location
    ob.rotation_euler=direction.to_track_quat('-Z','Y').to_euler();dat.type='ORTHO';dat.ortho_scale=scale
    return ob
camera('View_Courtyard', (400,-310,270),(150,82,16),400)
camera('View_Main_South_End',(200,-230,140),(40,75,25),228)
camera('View_Street', (370,440,230),(145,95,18),405)
camera('View_Main_East',(305,75,103),(39,79,27),195)
dat=bpy.data.lights.new('QA_Sun','SUN');ob=bpy.data.objects.new('QA_Sun',dat);collections['QA_Cameras_Lights'].objects.link(ob)
dat.energy=2.5;dat.angle=.12;ob.rotation_euler=(math.radians(25),math.radians(-20),math.radians(-30))
scene.camera=bpy.data.objects['View_Courtyard']
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA'
        area.spaces.active.overlay.show_overlays=False
        area.spaces.active.shading.type='MATERIAL'

building=[o for c,col in collections.items() if not c.startswith('QA') for o in col.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for ob in building:ob.select_set(True)
bpy.context.view_layer.objects.active=building[0]
glb=OUT/'express-terminal.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_cameras=False,export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'express-terminal.blend'))
verts=[ob.matrix_world@v.co for ob in building for v in ob.data.vertices]
mn=[min(v[i] for v in verts) for i in range(3)];mx=[max(v[i] for v in verts) for i in range(3)]
tris=0
for ob in building:ob.data.calc_loop_triangles();tris+=len(ob.data.loop_triangles)
report={'id':'bespoke-seoul-express-terminal','nameKo':'서울고속버스터미널 경부·영동선',
 'coordinate':{'lon':LON,'lat':LAT},'footprintIds':[SOURCE_ID],
 'sourceRecord':'OpenStreetMap w309352819@19','sourceHeightM':51,'heightBasis':'OSM height, not independent measurement',
 'model':glb.name,'sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'bytes':glb.stat().st_size,
 'meshObjects':len(building),'triangles':tris,'materials':sorted({m.name for ob in building for m in ob.data.materials}),
 'blenderBounds':{'min':mn,'max':mx},'gltfBounds':{'min':[mn[0],mn[2],-mx[1]],'max':[mx[0],mx[2],-mn[1]]},
 'coordinateConvention':'GLB east X / up Y / south Z, baked source bearing 20.9deg, no additional yaw',
 'modelParts':{name:len([o for o in col.objects if o.type=='MESH']) for name,col in collections.items() if not name.startswith('QA')},
 'referenceBrief':'docs/model-audit/express-terminal-reference.md',
 'qualityBasis':'Individual Blender mesh authored from operator exterior and rooftop photographs, operator floor and gate guides, existing geospatial footprint; not photogrammetry or measured architectural CAD',
 'uncertainty':['Photo capture dates not published; current facade colors have not been independently surveyed',
 'Main section setbacks, facade module widths and floor heights are photo interpretations',
 'Low-wing 9.1m roof and entrance barrel vault position/size are unmeasured interpretations',
 'OSM9floor versus operator10floor discrepancy unresolved; operator main/annex floor distinction used',
 'Only main L footprint modeled; separate parking decks, southern annex and Honam terminal are not claimed'],
 'tooling':{'authoring':'Blender 4.5.11 via real MCP execute_blender_code','port':9876}}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
bundle={'siteId':'seoul-express-terminal-gyeongbu-yeongdong',
 'sources':[
  {'url':'http://www.exterminal.co.kr/greeting.asp','observations':['Operator exterior photograph: high inclined main building and low adjoining wing; capture date unknown']},
  {'url':'http://www.exterminal.co.kr/floor.asp','observations':['Main building10F and separate annex2F, individual roof terrace photograph']},
  {'url':'http://www.exterminal.co.kr/take.asp','observations':['Orthogonal two-wing gate arrangement, main gates1–16 and annex17–36']},
  {'url':'http://www.exterminal.co.kr/parking.asp','observations':['Gyeongbu western main block and long Yeongdong northern wing, separate southern annex']},
  {'url':'https://www.openstreetmap.org/way/309352819','observations':['Geographic L outline and source-reported51m height, supplied via existing local dataset']}],
 'assets':[{'id':'bespoke-seoul-express-terminal','nameKo':'서울고속버스터미널 경부선·영동선',
  'file':str(glb),'blendSource':str(OUT/'express-terminal.blend'),
  'coordinate':report['coordinate'],'category':'landmark','footprintIds':[SOURCE_ID],'supersedes':[],
  'referenceUrl':'http://www.exterminal.co.kr/greeting.asp',
  'components':['High main terminal with interpreted inclined section','Recessed window bands and projecting concrete slabs',
                'Rooftop sign wall and terrace','Low Yeongdong annex','Open bus-gate colonnade','Curved glazed entry canopy'],
  'uncertainties':report['uncertainty']}],
 'places':[{'id':'seoul-express-terminal-gyeongbu-yeongdong','name':'서울고속버스터미널 경부선·영동선',
  'subtitle':'경부·영동선 터미널 · 센트럴시티 호남선과 별개',
  'center':[127.00620195,37.50541550],'zoom':17.0,'source_url':'http://www.exterminal.co.kr/location.asp'}]}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'exported':str(glb),'triangles':tris,'meshes':len(building),'bounds':report['gltfBounds']},ensure_ascii=False))
