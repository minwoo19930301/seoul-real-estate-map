import pathlib,json,shutil,math,shapely
from shapely.geometry import Polygon
P=pathlib.Path('data/model-source/bespoke/jamsil-els-family')
code='''
# Clip decorative boxes only against actual neighbor polygon below shared height.
# Full parent mass is built by mass()/mesh(), so source walls/grade/deck stay exact.
mask_stats={'decorative_boxes_examined':0,'decorative_boxes_changed':0,'fully_hidden_boxes_removed':0,'clipped_prisms_generated':0,'cutoff_m':D['shared_wall_mask']['height_m'],'neighbor':D['shared_wall_mask']['neighbor_tower']}
mask_materials={}
def signed_area(q):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(q,q[1:]+q[:1]))/2
cutters=D['shared_wall_mask']['neighbor_triangles_m']
cutters=[q if signed_area(q)>0 else list(reversed(q)) for q in cutters]
def halfclip(q,a,b,inside):
 out=[]
 def dist(p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
 for u,v in zip(q,q[1:]+q[:1]):
  du,dv=dist(u),dist(v);iu=du>=0 if inside else du<=0;iv=dv>=0 if inside else dv<=0
  if iu:out.append(u)
  if iu!=iv:
   f=du/(du-dv);out.append((u[0]+(v[0]-u[0])*f,u[1]+(v[1]-u[1])*f))
 clean=[]
 for p in out:
  if not clean or math.dist(p,clean[-1])>1e-8:clean.append(p)
 if len(clean)>1 and math.dist(clean[0],clean[-1])<1e-8:clean.pop()
 return clean if len(clean)>=3 and abs(signed_area(clean))>1e-10 else []
def subtract_triangle(q,tr):
 remain=q;outside=[]
 for a,b in zip(tr,tr[1:]+tr[:1]):
  if not remain:break
  piece=halfclip(remain,a,b,False)
  if piece:outside.append(piece)
  remain=halfclip(remain,a,b,True)
 return outside
original_box=box
def prism(q,z0,z1,m):
 if z1-z0<1e-8:return
 if signed_area(q)<0:q=list(reversed(q))
 n=len(q);vv=[(x,y,z) for z in [z0,z1] for x,y in q];ff=[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 ff += [(0,i+1,i) for i in range(1,n-1)]+[(n,n+i,n+i+1) for i in range(1,n-1)]
 mesh(vv,ff,m);mask_stats['clipped_prisms_generated']+=1
def box(c,d,m,ang=0):
 z0,z1=c[2]-d[2]/2,c[2]+d[2]/2;limit=D['shared_wall_mask']['height_m']
 if z0>=limit:return original_box(c,d,m,ang)
 mask_stats['decorative_boxes_examined']+=1
 co,si=math.cos(ang),math.sin(ang);w,h=d[0]/2,d[1]/2;q=[(c[0]+u*co-v*si,c[1]+u*si+v*co) for u,v in [(-w,-h),(w,-h),(w,h),(-w,h)]];parts=[q]
 for tr in cutters:
  nextparts=[]
  for piece in parts:
   if max(p[0] for p in piece)<min(p[0] for p in tr) or min(p[0] for p in piece)>max(p[0] for p in tr) or max(p[1] for p in piece)<min(p[1] for p in tr) or min(p[1] for p in piece)>max(p[1] for p in tr):nextparts.append(piece)
   else:nextparts.extend(subtract_triangle(piece,tr))
  parts=nextparts
 before=abs(signed_area(q));after=sum(abs(signed_area(v)) for v in parts)
 if before-after<1e-9:return original_box(c,d,m,ang)
 mask_stats['decorative_boxes_changed']+=1
 if not parts:mask_stats['fully_hidden_boxes_removed']+=1
 if m not in mask_materials:
  cm=m.copy();cm.name='Shared-wall clipped surface '+str(len(mask_materials));mask_materials[m]=cm
 cm=mask_materials[m]
 for qpart in parts:prism(qpart,z0,min(z1,limit),cm)
 if z1>limit:prism(q,limit,z1,cm)
'''
for t,n in [(138,139),(139,138),(153,158),(158,153)]:
 p=P/str(t);d=json.loads((p/'source-data.json').read_text());nd=json.loads((P/str(n)/'source-data.json').read_text());lon,lat=d['anchor_lonlat'];rings=[[[ (x-lon)*111320*math.cos(math.radians(lat)),(y-lat)*111320] for x,y in ring[:-1]] for ring in nd['geometry']['coordinates']];poly=Polygon(rings[0],rings[1:]);mask={'neighbor_tower':n,'neighbor_source_id':nd['id'],'neighbor_geometry':nd['geometry'],'height_m':min(d['register_height_m'],nd['register_height_m']),'neighbor_triangles_m':[list(q.exterior.coords)[:3] for q in shapely.constrained_delaunay_triangles(poly).geoms],'basis':'Exact source adjacency; only decorative box volume inside neighbor polygon below shared minimum register height is removed. Source parent mass/grade/roof remain unchanged; exposed upper facade preserved.'}
 if (p/'standalone-validation.json').exists():
  ar=p/'archive-before-shared-wall-mask';ar.mkdir(exist_ok=True)
  for f in p.iterdir():
   if f.is_file():shutil.copy2(f,ar/f.name)
 d['shared_wall_mask']=mask;(p/'source-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));s=(p/'build.py').read_text();pos=s.index("H=D['register_height_m']");s=s[:pos]+code+'\n'+s[pos:];s=s.replace('batches={}',"s['shared_wall_mask']=json.dumps(D['shared_wall_mask'])\nbatches={}");s=s.replace('objs=[]',"(P/'shared-wall-mask-proof.json').write_text(json.dumps(mask_stats,indent=2))\nobjs=[]");(p/'build.py').write_text(s)
(P/'revise-shared-138-139.py').write_text("import pathlib\nP=pathlib.Path(__file__).parent\nfor t in [138,139]:\n for name in ['build.py','check-standalone.py']:\n  p=P/str(t)/name;exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})\n")
(P/'prepare-shared-wall-mask.py').write_bytes(pathlib.Path(__file__).read_bytes());print('masked source preparations',[138,139,153,158])
