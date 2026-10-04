import pathlib,json,math,shutil,hashlib,shapely
from shapely.geometry import Polygon,mapping
P=pathlib.Path('data/model-source/bespoke/songpa-helio-city-416-representative');ar=P/'archive-v1';ar.mkdir(exist_ok=True)
for p in P.iterdir():
 if p.is_file():shutil.copy2(p,ar/p.name)
d=json.loads((P/'source-data.json').read_text());r=d['ring_m'];poly=Polygon(r);body=d['body_height_m'];pitch=body/d['floors'];area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]));ei=0;a,b=r[ei],r[(ei+1)%len(r)];L=math.dist(a,b);tx,ty=(b[0]-a[0])/L,(b[1]-a[1])/L;nx,ny=(ty,-tx) if area>0 else(-ty,tx);cx,cy=(a[0]+b[0])/2,(a[1]+b[1])/2
def cutpoly(a,b,t,w,depth):
 L=math.dist(a,b);tx,ty=(b[0]-a[0])/L,(b[1]-a[1])/L;nx,ny=(ty,-tx) if area>0 else(-ty,tx);cx=a[0]+(b[0]-a[0])*t;cy=a[1]+(b[1]-a[1])*t;return Polygon([(cx+tx*u+nx*v,cy+ty*u+ny*v) for u,v in [(-w/2,.5),(w/2,.5),(w/2,-depth),(-w/2,-depth)]])
d['entry'].update({'edge':ei,'center_m':[cx,cy],'outward_normal':[nx,ny],'unit_tangent':[tx,ty]});d['label']={'text':'416','edge':ei,'basis':'Actual photo number verified; mesh text on inferred photo-facing shortwall, compass orientation not surveyed'};d['colored_frame_dimensions']={'section_width_m':.34,'section_depth_m':.34,'recess_depth_m':.38,'shelf_max_projection_m':.46,'basis':'Unmeasured inferred dimensions; revised after direct photo comparison'};entrycut=cutpoly(a,b,.5,3,.85);cuts=[]
for edge,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 L=math.dist(a,b)
 if L<16:continue
 count=max(4,round(L/3.7));bw=L/count
 for ji,fs,fe in [(1,2,4),(count-2,8,10),(count//2+1,4,6)]:
  t=(ji+.5)/count;w=bw*.96-.34;cuts.append({'edge':edge,'bay':ji,'floors':[fs,fe],'z0':fs*pitch+.17,'z1':fe*pitch-.17,'cut':cutpoly(a,b,t,w,.38)})
def data(q):return {'rings':[list(q.exterior.coords)[:-1]]+[list(v.coords)[:-1] for v in q.interiors],'triangles':[list(t.exterior.coords)[:3] for t in shapely.constrained_delaunay_triangles(q).geoms]}
levels=sorted(set([0,.18,d['entry']['top_m'],2*pitch,body]+[z for q in cuts for z in [q['z0'],q['z1']]]));bands=[]
for z0,z1 in zip(levels,levels[1:]):
 mid=(z0+z1)/2;q=poly
 if .18<mid<d['entry']['top_m']:q=q.difference(entrycut)
 for c in cuts:
  if c['z0']<mid<c['z1']:q=q.difference(c['cut'])
 assert q.is_valid and q.geom_type=='Polygon';bands.append({'z0':z0,'z1':z1,'material':'base' if mid<2*pitch else 'white','shape':data(q)})
(P/'body-bands.json').write_text(json.dumps(bands,indent=2));(P/'entry-shape.json').write_text(json.dumps({'full':data(poly),'notched':data(poly.difference(entrycut)),'cut_geometry':mapping(entrycut),'source_footprint_area_m2':poly.area,'entry_removed_area_m2':poly.intersection(entrycut).area},indent=2));d['reference_scope']+=' V2:416 mesh label and entry share the photo-facing shortwall; exact compass chosen by inference. Colored frame section0.34m and0.38m inset group cavities are unmeasured visual dimensions.';(P/'source-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));s=(P/'build.py').read_text().replace('from mathutils import Vector','from mathutils import Vector,Matrix');s=s.replace("s['entry_recess']=json.dumps(entry);", "s['number_label']=json.dumps(D['label']);s['colored_frame_dimensions']=json.dumps(D['colored_frame_dimensions']);s['entry_recess']=json.dumps(entry);")
s=s.replace("mass(shapes['full'],0,.18,base);mass(shapes['notched'],.18,entry['top_m'],base);mass(shapes['full'],entry['top_m'],pitch*2,base);mass(shapes['full'],pitch*2,body,white);mass(shapes['full'],body,D['roof_deck_height_m'],roof)","for band in json.loads((P/'body-bands.json').read_text()):mass(band['shape'],band['z0'],band['z1'],base if band['material']=='base' else white)\nmass(shapes['full'],body,D['roof_deck_height_m'],roof)")
s=s.replace("orange=mat('orange narrow accent',(.90,.29,.045),.12,.48)","orange=mat('orange narrow accent',(.90,.29,.045),.12,.48);recess=mat('deep shaded frame recess',(.035,.045,.060))")
s=s.replace("z=(f+.55)*pitch;hh=.72*pitch;face(t,z,ww,hh,.035,frame if service else glass,depth=.055)","z=(f+.55)*pitch;hh=.72*pitch;off=-.34 if any(j==jj and ff<=f<ee for jj,ff,ee in [(1,2,4),(count-2,8,10),(count//2+1,4,6)]) else 0;face(t,z,ww,hh,.035+off,frame if service else glass,depth=.055)")
s=s.replace('ww,.026,.08,metal','ww,.026,.08+off,metal').replace('hh,.082,frame','hh,.082+off,frame').replace('hh,.09,white','hh,.09+off,white').replace("face(t,(f+.08)*pitch,bw-.03,.30,.11,base if f<2 else white)","face(t,(f+.08)*pitch,bw-.03 if off==0 else bw*.96-.34,.30,.11+off,base if f<2 else white)")
s=s.replace('z1=fe*pitch;th=.22','z1=fe*pitch;th=.34\n   face(t,(z0+z1)/2,w-.34,z1-z0-.34,-.355,recess,depth=.03)');s=s.replace('th,z1-z0+.22,.22,cm,depth=.42','th,z1-z0+.34,.17,cm,depth=.34').replace('w+.22,th,.22,cm,depth=.42','w+.34,th,.17,cm,depth=.34').replace('face(t,z0+.10,w,.14,.24,cm,depth=.44)','face(t,z0+.15,w-.12,.30,.03,cm,depth=.86)')
pos=s.index("(P/'optimization-proof.json').write_text")
label="""# Verified building number as editable mesh text, on same chosen shortwall as entry.
cx,cy=D['entry']['center_m'];nx,ny=D['entry']['outward_normal'];cu=bpy.data.curves.new('Photo verified416 number','FONT');cu.body='416';cu.align_x='CENTER';cu.align_y='CENTER';cu.size=1.25;cu.extrude=.022;cu.resolution_u=4;ob=bpy.data.objects.new('416 verified number mesh',cu);s.collection.objects.link(ob);ob.location=(cx+nx*.10,cy+ny*.10,body*.68);ob.rotation_euler=Matrix(((-ny,0,nx),(nx,0,ny),(0,1,0))).to_euler();cu.materials.append(frame)
for q in bpy.context.selected_objects:q.select_set(False)
ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH');objs.append(bpy.context.view_layer.objects.active)
"""
s=s[:pos]+label+s[pos:];(P/'build.py').write_text(s);(P/'revise-v2.py').write_bytes(pathlib.Path(__file__).read_bytes());print('v2 prepared',len(bands),'bands',len(cuts),'frame cavities; shortwall entryedge',ei)
