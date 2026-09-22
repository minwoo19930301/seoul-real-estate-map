import pathlib,json,math,hashlib,sqlite3,shapely
from shapely.geometry import Polygon,box,mapping
from shapely.ops import transform,polylabel
R=pathlib.Path.cwd();B=R/'data/model-source/bespoke';P=B/'jamsil-els-120-representative';P.mkdir(exist_ok=True);O=B/'jamsil-ricenz-family/201';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();src=B/'jamsil-els-research/root-reviewed-source-101-172.json';assert sha(src)=='e8f2a54420654efcd85cb945797623d85384efa60529f88393acee96645f26e0';photo=B/'jamsil-els-research/images/kb-15617-photo-1920.jpg';assert sha(photo)=='93ef9a4d3b8d702e1343c70a27f347667fbec50c5855a269172728b4545aa8c4';A=json.loads(src.read_text());e=next(x for x in A['entries'] if x['tower']=='120동');b=e['osm_building'];db=sqlite3.connect(R/'data/model-source/residential-survey/register.sqlite');db.row_factory=sqlite3.Row;reg=dict(db.execute('select * from reg where id=?',(e['register']['id'],)).fetchone());assert reg==e['register'];g=json.loads(b['geometry']);outer=g['coordinates'][0][:-1];lon=sum(x for x,y in outer)/len(outer);lat=sum(y for x,y in outer)/len(outer);rings=[[[ (x-lon)*111320*math.cos(math.radians(lat)),(y-lat)*111320] for x,y in ring[:-1]] for ring in g['coordinates']];r=rings[0];poly=Polygon(r,rings[1:]);a,z=max(zip(r,r[1:]+r[:1]),key=lambda q:math.dist(*q));theta=math.atan2(z[1]-a[1],z[0]-a[0]);co,si=math.cos(theta),math.sin(theta);uv=transform(lambda x,y:(x*co+y*si,-x*si+y*co),poly);c=polylabel(uv,tolerance=.01);w,h=14.,5.
while not uv.buffer(-.4).covers(box(c.x-w/2-.2,c.y-h/2-.2,c.x+w/2+.2,c.y+h/2+.2)):w*=.95;h*=.95
M=json.loads((B/'jamsil-els-fallback-review/published-model-binding-map.json').read_text());binding=next(x for x in M['bindings'] if x['number']==120);assert binding['sourceFootprintId']==b['id'];H=float(reg['height']);F=int(reg['floors']);d={'tower':'120','approved_entry':e,'id':b['id'],'geometry':g,'ring_m':r,'rings_m':rings,'anchor_lonlat':[lon,lat],'register_row':reg,'register_height_m':H,'floors':F,'osm_height_m':b['height_m'],'facade_axis_rad_inferred':theta,'roof_cap_uv':[c.x,c.y,w,h],'body_height_m':H-2.5,'roof_deck_height_m':H-2.25,'model_upper_envelope_m':H,'reference_scope':'KB15617 primary data.photoList[0]:120 visible on central background blankwall. Foreground balcony proportions and brown lower two storeys are complex-photo-inference, not confirmed120 facade. Orientation/hidden faces/spacing unmeasured.','height_assumption':'No child parts; uniform own full source polygon envelope73.8m. Roof grille and raised pale ends photo-derived but dimensions and legal roof datum unmeasured.','source_sha256':sha(src),'photo_sha256':sha(photo),'photo_list_index':0,'photo_attribution':json.loads((B/'jamsil-els-research/root-kb-attribution-parsed.json').read_text()),'inferredFromAssetIds':[],'ancestor_glb_sha256':None,'supersedesAssetIds':binding['supersedes'],'binding_status':'root verified staged split binding; public application pending','current_owner_asset_ids':[],'complex_household_discrepancy':'KB complex5678HH; own register100HH retained','scope_exclusions':[]};(P/'source-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));(P/'regions.json').write_text(json.dumps([{'id':'uniform-parent-assumption','geometry':mapping(poly),'height_m':H,'body_height_m':H-2.5,'roof_deck_height_m':H-2.25,'floors':F,'basis':d['height_assumption'],'triangles':[list(q.exterior.coords)[:3] for q in shapely.constrained_delaunay_triangles(poly).geoms]}],indent=2));(P/'binding-map-frozen.json').write_text(json.dumps(binding,indent=2));
s=(O/'build.py').read_text().replace('Jamsil Ricenz201','Jamsil Els120').replace('Ricenz201','Els120').replace('jamsil-ricenz-201','jamsil-els-120').replace("s['photo_list_index']=1","s['photo_list_index']=0").replace("s['ancestor_glb_sha256']=D['ancestor_glb_sha256']","s['ancestor_glb_sha256']=D['ancestor_glb_sha256'] or ''")
s=s.replace("(.82,.83,.81)","(.86,.84,.77)").replace("(.60,.63,.64)","(.64,.65,.63)").replace("(.16,.37,.39)","(.17,.42,.43)").replace("(.34,.36,.35)","(.36,.25,.19)")
a=s.index('# Numbered218 photographed vocabulary:');z=s.index('objs=[]',a)
s=s[:a]+'''# Els-specific facade derived from KB15617: wide banks either side of twin service windows.
area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]));roles=[]
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);ang=math.atan2(dy,dx);nx,ny=(dy/L,-dx/L) if area>0 else (-dy/L,dx/L)
 def face(t,z,w,h,dep,m,depth=.10):box((a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep,z),(w,depth,h),m,ang)
 blank=L<18;roles.append({'edge':ei,'length_m':L,'role':'numbered-photo gray blankwall with rectangular panel joints' if blank else 'paired broad balcony banks flanking pale twin service window field','basis':'own long/short edge dimensions; photo120 wall and unnumbered complex balcony inference; compass unmeasured'})
 face(.5,pitch,L,2*pitch,.025,base)
 if blank:
  for k in range(1,FLOORS*2):face(.5,k*body/(FLOORS*2),L-.12,.022,.058,roof,depth=.014)
  for t in [.20,.40,.60,.80]:face(t,body/2,.018,body,.057,roof,depth=.014)
  for t in [.025,.975]:face(t,body/2,.32,body,.12,white)
 else:
  # Solid central wall occupies16%; twin narrow window strips stay distinct.
  face(.5,body/2,L*.16,body,.035,white)
  for t in [.466,.534]:
   for f in range(FLOORS):
    z=(f+.57)*pitch;face(t,z,L*.033,.64*pitch,.075,glass)
    face(t,z,.06,.64*pitch,.135,white)
    face(t,(f+.18)*pitch,L*.034,.10,.14,white)
  for side0,side1 in [(.02,.42),(.58,.98)]:
   count=max(2,round(L*(side1-side0)/5.2));bw=L*(side1-side0)/count
   for j in range(count):
    t=side0+(j+.5)*(side1-side0)/count;ww=bw-.42
    for f in range(FLOORS):
     z=(f+.56)*pitch;hh=.69*pitch;face(t,z,ww,hh,.06,glass)
     for q in [-.5,0,.5]:face(t+q*ww/L,z,.055,hh,.13,white)
     face(t,(f+.105)*pitch,bw-.02,.32,.15,base if f<2 else white)
     railw=ww-.08;bottom=(f+.23)*pitch;top=bottom+.87
     face(t,bottom,railw,.055,.275,white,depth=.045);face(t,top,railw,.055,.275,white,depth=.045)
     num=max(4,round(railw/.19))
     for k in range(num+1):face(t+(k/num-.5)*railw/L,(bottom+top)/2,.022,.87,.275,white,depth=.025)
     for q in [-.5,.5]:face(t+q*railw/L,top,.04,.045,.19,white,depth=.20)
   for j in range(count+1):
    t=side0+j*(side1-side0)/count;face(t,body/2,.38,body,.17,white);face(t,pitch,.38,2*pitch,.19,base)
  # Fine panel joints across central solid field, no continuous dark service curtain.
  for f in range(1,FLOORS):face(.5,f*pitch,L*.16,.018,.093,metal,depth=.012)
 face(.5,body-.20,L,.40,.18,white)
(P/'facade-regions.json').write_text(json.dumps(roles,indent=2))
# Photo-specific roof: supported low dark horizontal grille between raised pale ends.
u,v,w,d=D['roof_cap_uv'];x,y=u*co-v*si,u*si+v*co
box((x,y,H-1.90),(w,d,.70),metal,theta)
for off in [-w/2+.40,w/2-.40]:
 box((x+off*co,y+off*si,H-1.10),(.80,d,2.20),white,theta)
# Dark inset equipment enclosure backs the horizontal slats; all inside source.
box((x,y,H-1.02),(w-1.60,d-.38,1.50),service,theta)
for off in [-d/2,d/2]:
 for z in [H-1.67,H-1.40,H-1.13,H-.86,H-.59]:
  box((x-off*si,y+off*co,z),(w-1.60,.12,.12),roof,theta)
box((x,y,H-.24),(w-1.60,d,.12),roof,theta)
''' + s[z:]
(P/'build.py').write_text(s)
for n in ['check-standalone.py','validate.py']:
 s=(O/n).read_text().replace('jamsil-ricenz-201','jamsil-els-120').replace("P.parent.parent/'jamsil-ricenz-research/root-reviewed-source-63.json'","P.parent/'jamsil-els-research/root-reviewed-source-101-172.json'").replace("=='201동'","=='120동'");(P/n).write_text(s)
(P/'run.py').write_text("import pathlib\nP=pathlib.Path(__file__).parent\nfor name in ['build.py','check-standalone.py']:\n p=P/name;exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})\n")
(P/'prior-hashes.json').write_text(json.dumps({str(p):sha(p) for folder in [B/'jamsil-ricenz-218-representative',B/'jamsil-els-research'] for p in folder.rglob('*') if p.is_file()},indent=2));(P/'prepare.py').write_bytes(pathlib.Path(__file__).read_bytes());print('prepared',H,F,r)
