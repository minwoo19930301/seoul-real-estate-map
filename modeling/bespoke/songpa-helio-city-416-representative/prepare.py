import pathlib,json,math,hashlib,sqlite3,shapely
from shapely.geometry import Polygon,box,mapping
R=pathlib.Path.cwd();B=R/'data/model-source/bespoke';P=B/'songpa-helio-city-416-representative';P.mkdir(exist_ok=True);O=B/'jamsil-els-120-representative';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();src=B/'songpa-hellio-city-research/root-reviewed-source-84.json';assert sha(src)=='227fbfd6ceb76dd3850c9746b4211f7ed9cd3fbeec2400c95537acde8e7e90bb';photo=B/'songpa-hellio-city-research/images/kb-hellio-02-1920.jpg';assert sha(photo)=='097df37dcc9409d91b1367dadde7eabeaf2d26dd9928d7b0e8018a549cfaeeb6';A=json.loads(src.read_text());e=next(x for x in A['entries'] if x['tower']=='416동');b=e['osm_building'];db=sqlite3.connect(R/'data/model-source/residential-survey/register.sqlite');db.row_factory=sqlite3.Row;reg=dict(db.execute('select * from reg where id=?',(e['register']['id'],)).fetchone());assert reg==e['register'];g=json.loads(b['geometry']);outer=g['coordinates'][0][:-1];lon=sum(x for x,y in outer)/len(outer);lat=sum(y for x,y in outer)/len(outer);rings=[[[ (x-lon)*111320*math.cos(math.radians(lat)),(y-lat)*111320] for x,y in ring[:-1]] for ring in g['coordinates']];r=rings[0];poly=Polygon(r,rings[1:]);ei=max(range(len(r)),key=lambda i:math.dist(r[i],r[(i+1)%len(r)]));a,z=r[ei],r[(ei+1)%len(r)];theta=math.atan2(z[1]-a[1],z[0]-a[0]);L=math.dist(a,z);dx,dy=(z[0]-a[0])/L,(z[1]-a[1])/L;area=sum(x[0]*y[1]-y[0]*x[1] for x,y in zip(r,r[1:]+r[:1]));nx,ny=(dy,-dx) if area>0 else(-dy,dx);cx,cy=(a[0]+z[0])/2,(a[1]+z[1])/2;cut=Polygon([(cx+dx*u+nx*v,cy+dy*u+ny*v) for u,v in [(-1.5,.5),(1.5,.5),(1.5,-.85),(-1.5,-.85)]]);notched=poly.difference(cut);assert notched.is_valid and notched.geom_type=='Polygon';H=float(reg['height']);F=int(reg['floors']);body=H-1.2;pitch=body/F;roofdeck=H-1.05;entrytop=pitch*1.6;M=json.loads((B/'songpa-helio-city-fallback-review/published-model-binding-map.json').read_text());binding=next(x for x in M['bindings'] if x['number']==416);assert binding['sourceFootprintId']==b['id'];d={'tower':'416','approved_entry':e,'id':b['id'],'geometry':g,'ring_m':r,'rings_m':rings,'anchor_lonlat':[lon,lat],'register_row':reg,'register_height_m':H,'floors':F,'osm_height_m':b['height_m'],'facade_axis_rad_inferred':theta,'body_height_m':body,'roof_deck_height_m':roofdeck,'model_upper_envelope_m':H,'entry':{'edge':ei,'center_m':[cx,cy],'outward_normal':[nx,ny],'unit_tangent':[dx,dy],'width_m':3,'depth_m':.85,'bottom_m':.18,'top_m':entrytop},'roof_rail_ring':list(poly.buffer(-.22).exterior.coords)[:-1],'reference_scope':'Numbered416 facade photo KB32148 primary photoList[2] directly viewed. White grid/dark glazing, gray service grilles, blank panel wall/orange slit accents, yellow frames and low roof railing are photo-derived. Exact orientation/frame stations/window spacing/hidden faces and colored projecting balcony details are unmeasured complex-photo-inference.','height_assumption':'No child parts: uniform own footprint envelope34.6m12F. Entrance recess is facade detail only; full own ground and roof caps preserved. Legal roof datum unmeasured; railing included inside34.6m.','source_sha256':sha(src),'photo_sha256':sha(photo),'photo_list_index':2,'inferredFromAssetIds':[],'ancestor_glb_sha256':None,'supersedesAssetIds':binding['supersedes'],'binding_status':'root verified existing singleton residential asset; exact fallback bytes preserved','current_owner_asset_ids':binding['supersedes'],'complex_household_discrepancy':'Official/KAPT parcel479 versus register913 unresolved; exact road Songpa-daero345,84numbered residential rows and9510HH match. Own41646HH retained.','scope_exclusions':['42 support/unnamed source buildings outside84 residential scope']};(P/'source-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
def shape_data(q):return {'rings':[list(q.exterior.coords)[:-1]]+[list(v.coords)[:-1] for v in q.interiors],'triangles':[list(x.exterior.coords)[:3] for x in shapely.constrained_delaunay_triangles(q).geoms]}
full=shape_data(poly);notch=shape_data(notched);(P/'regions.json').write_text(json.dumps([{'id':'uniform-parent-assumption','geometry':mapping(poly),'height_m':H,'body_height_m':body,'roof_deck_height_m':roofdeck,'floors':F,'basis':d['height_assumption'],**full}],indent=2));(P/'entry-shape.json').write_text(json.dumps({'full':full,'notched':notch,'cut_geometry':mapping(cut),'source_footprint_area_m2':poly.area,'entry_removed_area_m2':poly.area-notched.area},indent=2));(P/'binding-map-frozen.json').write_text(json.dumps(binding,indent=2));fallback=R/'public/models'/binding['fallbackModel'];assert sha(fallback)==binding['fallbackSha256'];(P/'prior-hashes.json').write_text(json.dumps({str(p):sha(p) for folder in [O,B/'songpa-hellio-city-research'] for p in folder.rglob('*') if p.is_file()}|{str(fallback):sha(fallback)},indent=2))
s=(O/'build.py').read_text().replace('Jamsil Els120','Songpa Helio416').replace('Els120','Helio416').replace('jamsil-els-120','songpa-helio-city-416').replace("s['photo_list_index']=0","s['photo_list_index']=2");start=s.index('white=mat(');end=s.index('def mesh(',start);s=s[:start]+"white=mat('white slab frames',(.84,.85,.82));metal=mat('blankwall grey panels',(.65,.67,.66));glass=mat('dark blue grey glazing',(.065,.14,.20),.38,.25);frame=mat('grey service grille',(.24,.27,.29),.25,.48);roof=mat('low roof deck',(.40,.43,.43));base=mat('dark grey twofloor base',(.22,.23,.24));yellow=mat('yellow projecting rectangular frame',(.94,.65,.025),.12,.48);orange=mat('orange narrow accent',(.90,.29,.045),.12,.48)\n"+s[end:];start=s.index("H=D['register_height_m']");end=s.index('objs=[]',start)
s=s[:start]+'''H=D['register_height_m'];body=D['body_height_m'];FLOORS=D['floors'];pitch=body/FLOORS;r=D['ring_m'];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta);entry=D['entry'];shapes=json.loads((P/'entry-shape.json').read_text())
s['entry_recess']=json.dumps(entry);s['parcel_discrepancy']=D['complex_household_discrepancy']
def mass(shape,z0,z1,m):
 for ring in shape['rings']:
  n=len(ring);mesh([(x,y,z) for z in [z0,z1] for x,y in ring],[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
 for tr in shape['triangles']:
  mesh([(x,y,z0) for x,y in reversed(tr)],[(0,1,2)],m);mesh([(x,y,z1) for x,y in tr],[(0,1,2)],m)
mass(shapes['full'],0,.18,base);mass(shapes['notched'],.18,entry['top_m'],base);mass(shapes['full'],entry['top_m'],pitch*2,base);mass(shapes['full'],pitch*2,body,white);mass(shapes['full'],body,D['roof_deck_height_m'],roof)
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]));roles=[];colorframes=[]
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else(-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.10):
  # Keep the real inward entrance volume unobstructed by foreground facade boxes.
  if ei==entry['edge'] and z-h/2<entry['top_m'] and z+h/2>.18 and abs((t-.5)*L)<(w+3)/2:return
  box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 blank=L<16;roles.append({'edge':ei,'length_m':L,'role':'blank panel endwall with short vertical orange accents' if blank else 'white slab grid, blue-grey glazing, narrow grilles and selective colored frames','basis':'Own edge length and numbered416 photo; orientation and stations unmeasured'})
 if blank:
  if L>5:
   for f in range(2,FLOORS):face(.5,f*pitch,L-.08,.023,.045,frame,depth=.012)
   for t in [.25,.50,.75]:face(t,(body+pitch*2)/2,.016,body-pitch*2,.04,metal,depth=.015)
   for j,(t,f) in enumerate([(.30,3),(.64,4),(.45,6),(.30,8),(.64,9)]):face(t,(f+.45)*pitch,.18,pitch*.72,.060,orange,depth=.025)
 else:
  count=max(4,round(L/3.7));bw=L/count
  for j in range(count):
   t=(j+.5)/count;service=j==count//2;ww=bw*(.38 if service else .82)
   for f in range(FLOORS):
    z=(f+.55)*pitch;hh=.72*pitch;face(t,z,ww,hh,.035,frame if service else glass,depth=.055)
    if service:
     for k in range(9):face(t,z-hh/2+(k+.5)*hh/9,ww,.026,.08,metal,depth=.028)
    else:
     face(t,z,.050,hh,.082,frame,depth=.035)
     for q in [-.5,.5]:face(t+q*ww/L,z,.055,hh,.09,white,depth=.06)
    face(t,(f+.08)*pitch,bw-.03,.30,.11,base if f<2 else white)
  for j in range(count+1):
   t=max(.12/L,min(1-.12/L,j/count));face(t,body/2,.28,body,.10,white)
  # Large colored open frames surround selected groups; stations are visual inference.
  for ji,fs,fe,cm in [(1,2,4,yellow),(count-2,8,10,yellow),(count//2+1,4,6,orange)]:
   if ji>=count:continue
   t=(ji+.5)/count;w=bw*.96;z0=fs*pitch;z1=fe*pitch;th=.22
   for q in [-.5,.5]:face(t+q*w/L,(z0+z1)/2,th,z1-z0+.22,.22,cm,depth=.42)
   for z in [z0,z1]:face(t,z,w+.22,th,.22,cm,depth=.42)
   # Supported colored lower shelf creates a shallow boxlike balcony edge.
   face(t,z0+.10,w,.14,.24,cm,depth=.44);colorframes.append({'edge':ei,'bay':ji,'floors':[fs,fe],'projection_m':.46,'basis':'unmeasured numbered/complex photo frame inference'})
 face(.5,body-.12,L,.24,.10,white)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2));(P/'colored-frame-proof.json').write_text(json.dumps(colorframes,indent=2))
# Actual inset entrance: glazing on the back wall at0.82m inward, supported by floor.
a=r[entry['edge']];b=r[(entry['edge']+1)%len(r)];ang=math.atan2(b[1]-a[1],b[0]-a[0]);cx,cy=entry['center_m'];nx,ny=entry['outward_normal'];top=entry['top_m'];box((cx-nx*.82,cy-ny*.82,(top+.18)/2),(2.65,.04,top-.18-.10),glass,ang);box((cx-nx*.78,cy-ny*.78,(top+.18)/2),(.06,.08,top-.18-.10),frame,ang)
# Thin actual roof railing inside own inset contour, upper surface exactlyH.
roofrail=D['roof_rail_ring'];postcount=0
for a,b in zip(roofrail,roofrail[1:]+roofrail[:1]):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx)
 for z in [H-.04,H-.58]:box(((a[0]+b[0])/2,(a[1]+b[1])/2,z),(L,.035,.08 if z==H-.04 else .035),frame,ang)
 count=max(1,math.ceil(L/.42))
 for j in range(count+1):
  t=j/count;box((a[0]+dx*t,a[1]+dy*t,(D['roof_deck_height_m']+H-.08)/2),(.027,.027,H-.08-D['roof_deck_height_m']),frame,ang);postcount+=1
''' +s[end:]
start=s.index("ob=next(o for o in s.objects");end=s.index('for o in bpy.context.selected_objects',start);s=s[:start]+"(P/'optimization-proof.json').write_text(json.dumps({'mesh_count':len(objs),'material_batching':True,'decimation':False,'roof_railing_posts':postcount,'no_embedded_photo':True},indent=2))\n"+s[end:];(P/'build.py').write_text(s)
for n in ['check-standalone.py','validate.py']:
 s=(O/n).read_text().replace('jamsil-els-120','songpa-helio-city-416').replace("P.parent/'jamsil-els-research/root-reviewed-source-101-172.json'","P.parent/'songpa-hellio-city-research/root-reviewed-source-84.json'").replace("=='120동'","=='416동'");(P/n).write_text(s)
(P/'run.py').write_text("import pathlib\nP=pathlib.Path(__file__).parent\nfor name in ['build.py','check-standalone.py']:\n p=P/name;exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})\n");(P/'prepare.py').write_bytes(pathlib.Path(__file__).read_bytes());print(H,F,'entryedge',ei,'ownlengths',[round(math.dist(a,b),2) for a,b in zip(r,r[1:]+r[:1])])
