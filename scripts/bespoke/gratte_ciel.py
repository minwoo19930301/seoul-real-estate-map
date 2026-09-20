"""Four Gratte-ciel towers; geometry authored from this site's plans and photos.

Run in an isolated Blender through the MCP client. Measurements not present in
the primary references stay estimates in the frozen recipe and asset records.
"""
import bpy, json, math, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/model-source/bespoke/gratte-ciel'
OUT.mkdir(parents=True, exist_ok=True)
rp = OUT / 'authored-input.json'
if not rp.exists():
    rp = ROOT / 'modeling/bespoke/gratte-ciel/authored-input.json'
recipe = json.loads(rp.read_text())
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if not c.objects and not c.children:
        bpy.data.collections.remove(c)

def material(name, color, metal=0, rough=.55):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Metallic'].default_value = metal
    bs.inputs['Roughness'].default_value = rough
    return m

MAT = [material('warm charcoal mineral facade', (.065,.059,.051)),
       material('projecting ivory white woven frame', (.83,.83,.79),.10,.43),
       material('blue grey recessed apartment glazing', (.020,.060,.095),.45,.24),
       material('window inset and mechanical shadow', (.025,.035,.041)),
       material('narrow aluminium mullion', (.38,.43,.44),.5,.35),
       material('muted salmon balcony front', (.55,.24,.20)),
       material('muted ochre balcony front', (.60,.45,.21)),
       material('roof membrane', (.28,.30,.29)),
       material('terracotta retail cladding', (.39,.18,.105)),
       material('lobby and retail glazing', (.115,.23,.25),.36,.23),
       material('review ground', (.47,.49,.47)),
       material('photo matched pale grey beige roof core', (.53,.51,.46))]

class Mesh:
    def __init__(self,name): self.name=name; self.v=[]; self.f=[]; self.m=[]
    def face(self,p,mi):
        i=len(self.v); self.v.extend(p); self.f.append(tuple(range(i,i+len(p)))); self.m.append(mi)
    def prism(self,p,z0,z1,mi):
        p=[tuple(v) for v in p]
        if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))<0: p.reverse()
        for a,b in zip(p,p[1:]+p[:1]):
            self.face([(a[0],a[1],z0),(b[0],b[1],z0),(b[0],b[1],z1),(a[0],a[1],z1)],mi)
        vs=[Vector((x,y,0)) for x,y in p]
        for tri in tessellate_polygon([vs]):
            pts=[vs[v] if isinstance(v,int) else v for v in tri]
            self.face([(v.x,v.y,z1) for v in pts],mi)
            self.face([(v.x,v.y,z0) for v in reversed(pts)],mi)
    def panel(self,a,b,z0,z1,n,depth,mi):
        self.face([(a[0]+n[0]*depth,a[1]+n[1]*depth,z0),
                   (b[0]+n[0]*depth,b[1]+n[1]*depth,z0),
                   (b[0]+n[0]*depth,b[1]+n[1]*depth,z1),
                   (a[0]+n[0]*depth,a[1]+n[1]*depth,z1)],mi)
    def rail(self,a,b,z0,z1,n,depth,width,mi):
        p=[(a[0]+n[0]*depth,a[1]+n[1]*depth),(b[0]+n[0]*depth,b[1]+n[1]*depth),
           (b[0]+n[0]*(depth+width),b[1]+n[1]*(depth+width)),(a[0]+n[0]*(depth+width),a[1]+n[1]*(depth+width))]
        self.prism(p,z0,z1,mi)
    def box(self,c,s,mi):
        x,y,z=c; w,d,h=s
        self.prism([(x-w/2,y-d/2),(x+w/2,y-d/2),(x+w/2,y+d/2),(x-w/2,y+d/2)],z-h/2,z+h/2,mi)
    def obj(self,col):
        me=bpy.data.meshes.new(self.name); me.from_pydata(self.v,[],self.f); me.update()
        for m in MAT: me.materials.append(m)
        for p,mi in zip(me.polygons,self.m): p.material_index=mi
        ob=bpy.data.objects.new(self.name,me); col.objects.link(ob); return ob

def col(name):
    c=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); return c
def mix(a,b,t): return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
def edges(p):
    sign=1 if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))>0 else -1
    for i,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        L=math.dist(a,b); yield i,a,b,L,(sign*(b[1]-a[1])/L,-sign*(b[0]-a[0])/L)
def pier(m,p,tangent,n,z0,z1,w,depth,mi):
    a=(p[0]-tangent[0]*w/2,p[1]-tangent[1]*w/2)
    b=(p[0]+tangent[0]*w/2,p[1]+tangent[1]*w/2)
    m.rail(a,b,z0,z1,n,.035,depth,mi)

assets=[]
for tower in recipe['assets']:
    no=tower['tower']; ring=tower['ring']; top=tower['mainTopM']; base=tower['podiumTopM']
    floors=tower['floors']; fh=(top-base)/(floors-3)
    c=col('GRATTE_CIEL_'+no)
    mass=Mesh(no+'_individual_stepped_plan')
    windows=Mesh(no+'_recessed_windows_and_mullions')
    frame=Mesh(no+'_projecting_woven_white_frames')
    balconies=Mesh(no+'_lower_coloured_projecting_balconies')
    refuge=Mesh(no+'_29F_refuge_louvers')
    roof=Mesh(no+'_open_lattice_crowns_and_roof_core')
    podium=Mesh(no+'_simplified_retail_and_lobby')
    mass.prism(ring,0,top,0)
    roof.prism(ring,top,top+.20,7)
    # The roof is an inhabited/service core with a setback, not a solid cap
    # drawn across the open white lattice visible in completed photographs.
    roof.prism(tower['roofCoreRing'],top+.20,top+3.1,11)
    roof.prism(tower['roofCoreRing'],top+3.1,top+3.28,0)
    roof.box((0,0,top+3.35),(10,8,.14),7)
    for ei,a,b,L,n in edges(ring):
        face=tower['facades'][ei]; count=face['windowColumns']; kind=face['treatment']
        t=((b[0]-a[0])/L,(b[1]-a[1])/L)
        podium.panel(a,b,.45,base-.45,n,.08,9)
        podium.rail(a,b,0,.55,n,.01,.28,8)
        podium.rail(a,b,base-.6,base,n,.01,.48,8)
        for z in [3.65,7.25]: podium.rail(a,b,z,z+.32,n,.06,.25,8)
        for k in range(max(1,round(L/3))+1):
            pier(podium,mix(a,b,k/max(1,round(L/3))),t,n,.5,base-.5,.13,.25,4)
        if not count: continue
        for field in face['fields']:
            aa=mix(a,b,field['start']); bb=mix(a,b,field['end'])
            cols=field['columns']; treatment=field['treatment']; white=treatment in ['woven','return']
            for f in range(4,floors+1):
                z=base+(f-4)*fh
                for k in range(cols):
                    inset=.12 if white else .26
                    wa=mix(aa,bb,(k+inset)/cols);wb=mix(aa,bb,(k+1-inset)/cols)
                    if f==29 and not white:
                        refuge.panel(wa,wb,z+.9,z+1.4,n,.055,3)
                        continue
                    bottom=.39 if white else .72
                    windows.panel(wa,wb,z+bottom,z+fh-.40,n,.028,3)
                    windows.panel(mix(wa,wb,.04),mix(wa,wb,.96),z+bottom+.06,z+fh-.46,n,.04,2)
                    pier(windows,mix(wa,wb,.5),t,n,z+bottom+.06,z+fh-.46,.055,.05,4)
                if white:
                    for k in range(cols):
                        fa=mix(aa,bb,k/cols);fb=mix(aa,bb,(k+1)/cols)
                        depth=.50 if (f+k)%2==0 else .26
                        frame.rail(fa,fb,z+.035,z+.23,n,.045,depth,1)
            if white:
                for k in range(cols+1):
                    pier(frame,mix(aa,bb,k/cols),t,n,base,top,.28,.57 if k%2==0 else .34,1)
        if ei in tower['balconyEdges']:
            # Schedule explicitly locates projecting balconies on floors4–20;
            # the visible salmon/ochre fronts are kept in these lower fields.
            for f in range(4,21,2):
                z=base+(f-4)*fh
                aa=mix(a,b,.43);bb=mix(a,b,.59)
                balconies.rail(aa,bb,z+.04,z+.24,n,.02,1.1,1)
                balconies.rail(aa,bb,z+.24,z+.92,n,.94,.16,5 if f%4==0 else 6)
                balconies.panel(aa,bb,z+.92,z+1.4,n,1.06,2)
                balconies.rail(aa,bb,z+1.40,z+1.46,n,1.0,.12,4)
        if no!='104' and ei==6:
            # Two foreground columns are visible in the June2023 completed
            # photograph. Keep them off the broad brown service-wall strips.
            for centre,phase in [(.307,0),(.585,2)]:
                for f in range(4+phase,21,2):
                    z=base+(f-4)*fh;aa=mix(a,b,centre-.031);bb=mix(a,b,centre+.031)
                    balconies.rail(aa,bb,z+.05,z+.23,n,.015,1.1,1)
                    balconies.rail(aa,bb,z+.23,z+.87,n,.96,.14,5 if (f+phase)%4==0 else 6)
                    balconies.panel(aa,bb,z+.87,z+1.38,n,1.08,2)
                    balconies.rail(aa,bb,z+1.38,z+1.44,n,1.02,.12,4)
        if ei in tower['crownEdges']:
            # Lattice projects only over selected wing ends, leaving the roof
            # open. Unequal extensions match the characteristic split skyline.
            h=7.2 if ei in ([1,11] if no!='104' else [0,15]) else 4.8
            spans=[(.03,.97)] if L<20 else [(.01,.17),(.74,.99)]
            for start,end in spans:
                ca,cb=mix(a,b,start),mix(a,b,end); intervals=max(2,round(math.dist(ca,cb)/2.8))
                backa=(ca[0]-n[0]*3.2,ca[1]-n[1]*3.2);backb=(cb[0]-n[0]*3.2,cb[1]-n[1]*3.2)
                for fa,fb in [(ca,cb),(backa,backb)]:
                    for k in range(intervals+1):
                        pier(roof,mix(fa,fb,k/intervals),t,n,top,top+h,.29,.42,1)
                    for dz in [2.4,4.8,h]:
                        if dz<=h:roof.rail(fa,fb,top+dz-.24,top+dz,n,.05,.40,1)
                for k in range(intervals+1):
                    front=mix(ca,cb,k/intervals);back=mix(backa,backb,k/intervals)
                    roof.rail(front,back,top+h-.22,top+h,t,0,.22,1)
    # Only simplified commercial geometry is added outside the residential
    # plans. An approximate site-wide mall would incorrectly claim neighbours.
    objects=[m.obj(c) for m in [mass,windows,frame,balconies,refuge,roof,podium] if m.v]
    for ob in objects: ob['tower']=no; ob['sourceFootprintId']=tower['sourceFootprintId']
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects: ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    filename=tower['id']+'.glb'
    bpy.ops.export_scene.gltf(filepath=str(OUT/filename),export_format='GLB',use_selection=True,export_apply=True,export_yup=True)
    assets.append({'id':tower['id'],'nameKo':'청량리역 한양수자인 그라시엘 '+no+'동',
        'file':filename,'blendSource':'gratte-ciel-authored.blend','coordinate':dict(zip(['lon','lat'],tower['anchor'])),
        'category':'apartment','district':'동대문구','minZoom':15,'footprintIds':[tower['sourceFootprintId']],
        'supersedes':['apt-a10023188'],'referenceUrl':recipe['sources'][1]['url'],
        'components':[ob.name for ob in objects],'floors':floors,'floorsBasis':'Developer official numbered floor schedule',
        'heightM':tower['heightM'],'heightBasis':tower['heightBasis'],'uncertainties':recipe['limits'],
        'blendSceneOffsetEN':tower['siteEN']})
    for ob in objects: ob.location.x+=tower['siteEN'][0]; ob.location.y+=tower['siteEN'][1]

review=col('REVIEW_ONLY')
g=Mesh('Review ground');g.box((0,0,-.4),(500,500,.5),10);g.obj(review)
scene=bpy.context.scene
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.81,.88,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.75
ld=bpy.data.lights.new('Review sun','SUN');ld.energy=2.5;ld.angle=.18
sun=bpy.data.objects.new('Review sun',ld);review.objects.link(sun);sun.rotation_euler=(.45,-.65,-.4)
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1400;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
views=[('southwest',(-320,-520,285),(0,0,96),285),('northeast',(330,480,285),(0,0,96),285),('plan',(0,0,700),(0,0,0),225),('crown',(150,-280,250),(0,0,172),140)]
for name,eye,target,scale in views:
    cd=bpy.data.cameras.new('review-'+name);cam=bpy.data.objects.new('review-'+name,cd);review.objects.link(cam)
    cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cd.type='ORTHO';cd.ortho_scale=scale
scene.camera=bpy.data.objects['review-southwest']
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.shading.type='MATERIAL';sp.clip_end=4000
            sp.region_3d.view_location=(0,0,95);sp.region_3d.view_distance=360
            sp.region_3d.view_rotation=(Vector((-320,-520,285))-Vector((0,0,96))).to_track_quat('Z','Y')
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'gratte-ciel-authored.blend'))
bundle={'siteId':'gratte-ciel','sources':recipe['sources'],'assets':assets,'recipeFiles':['authored-input.json','source-footprints.json','official-register-source.json'],
        'places':[{'id':'bespoke-gratte-ciel','name':'청량리역 한양수자인 그라시엘','subtitle':'1,152세대 · 101–104동 개별 모델',
                   'center':recipe['siteAnchor'],'zoom':16.4,'source_url':recipe['sources'][0]['url'],'household_count':1152,
                   'supersedesPlaceIds':['model:apt-a10023188','seoul-apartment:A10023188']}],
        'authoredVia':'Blender MCP execute_blender_code isolated GUI port9876','blenderVersion':bpy.app.version_string,
        'scope':'Four residential towers; commercial base simplified; no full landscaping or surveyed hidden surfaces.'}
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'built':[a['id'] for a in assets],'blend':str(OUT/'gratte-ciel-authored.blend')},ensure_ascii=False))
