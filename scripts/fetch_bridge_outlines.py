import concurrent.futures,json,sqlite3,urllib.request,xml.etree.ElementTree as ET, math
from pathlib import Path
from shapely.geometry import Polygon,LineString,mapping,shape
from shapely.ops import unary_union,polygonize,transform,linemerge
ROOT=Path(__file__).resolve().parents[1]; CACHE=ROOT/'data/model-source/bridges'; CACHE.mkdir(parents=True,exist_ok=True)
names=['한강대교','한강철교','월드컵대교','행주대교','당산철교','잠실철교','성수대교','청담대교','올림픽대교','광진교','반포대교','잠수교','잠실대교','영동대교','동작대교','한남대교','양화대교','마포대교','천호대교','서강대교','원효대교','가양대교','성산대교','동호대교','강동대교','방화대교']
c=sqlite3.connect(ROOT/'data/places.sqlite'); c.row_factory=sqlite3.Row
rows=[]
for n in names:
 r=c.execute('select id,name,source_url from places where kind="bridge" and name=? limit 1',(n,)).fetchone()
 if r: rows.append(dict(r))
def get(url,path):
 if not path.exists():
  q=urllib.request.Request(url,headers={'User-Agent':'seoul-elevation-local/1.0'})
  with urllib.request.urlopen(q,timeout=20) as h:path.write_bytes(h.read())
 return path
def parse(root):
 ns={x.attrib['id']:(float(x.attrib['lon']),float(x.attrib['lat'])) for x in root.findall('node')}; out=[]
 for w in root.findall('way'):
  p=[ns[x.attrib['ref']] for x in w.findall('nd') if x.attrib['ref'] in ns]
  if len(p)>=4 and p[0]==p[-1]: out.append((w.attrib['id'],Polygon(p),{x.attrib['k']:x.attrib['v'] for x in w.findall('tag')}))
 return out
def parse_lines(root):
 ns={x.attrib['id']:(float(x.attrib['lon']),float(x.attrib['lat'])) for x in root.findall('node')}; out=[]
 for w in root.findall('way'):
  p=[ns[x.attrib['ref']] for x in w.findall('nd') if x.attrib['ref'] in ns]
  if len(p)>=2: out.append((w.attrib['id'],LineString(p),{x.attrib['k']:x.attrib['v'] for x in w.findall('tag')}))
 return out
def one(r):
 typ,i=r['id'].split(':',1)[1].split('/'); path=CACHE/f'{typ}-{i}.osm'; rec={'nameKo':r['name'],'sourceId':r['id'],'sourceUrl':r['source_url'],'status':'failed'}
 try:
  root=ET.fromstring(get(f'https://api.openstreetmap.org/api/0.6/{typ}/{i}/full',path).read_bytes()); polys=parse(root); lines=parse_lines(root)
  if typ=='relation':
   rel=next((x for x in root.findall('relation') if x.attrib.get('id')==i),None); outer={x.attrib['ref'] for x in rel.findall('member') if x.attrib.get('type')=='way' and x.attrib.get('role')=='outer'} if rel is not None else set(); polys=[p for p in polys if p[0] in outer]
   if not polys:
    seg=[p[1] for p in lines if p[0] in outer]; polys=[('polygonized-outer',g,{}) for g in polygonize(unary_union(seg))]
  if not polys and typ=='way':
   seg=[p for p in lines if p[0]==i]
   if seg:
    tags=seg[0][2]; ws=tags.get('width','').split(); width=float(ws[0]) if ws and ws[0].replace('.','',1).isdigit() else 0; lanes=float(tags.get('lanes','0') or 0); meters=width or (lanes*3.25+2 if lanes else 0)
    if meters: polys=[('buffered-centerline',transform(lambda x,y,z=None:(x/(111320*math.cos(math.radians(seg[0][1].centroid.y))),y/111320), transform(lambda x,y,z=None:(x*111320*math.cos(math.radians(seg[0][1].centroid.y)),y*111320),seg[0][1]).buffer(meters/2,cap_style=2)),tags)]; rec['widthBasis']='OSM width tag' if width else 'lanes*3.25m plus 2m margin'
  if not polys: rec['failure']='no closed deck outline'; return rec
  g=unary_union([p[1] for p in polys])
  if g.is_empty or g.geom_type not in ('Polygon','MultiPolygon'): rec['failure']='not polygon'; return rec
  rec.update(status='ok',geometry=mapping(g),wayIds=[p[0] for p in polys],osmTags=[p[2] for p in polys],geometrySource=('buffered OSM centerline; width estimated' if polys[0][0]=='buffered-centerline' else ('polygonized OSM outer segments from /full' if polys[0][0]=='polygonized-outer' else 'closed OSM way outline(s) from /full')))
 except Exception as e: rec['failure']=str(e)
 return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex: results=list(ex.map(one,rows))
features=[]; seen=[]
for r in results:
 if r['status']!='ok': continue
 g=shape(r['geometry'])
 if any(g.equals(x) for x in seen): continue
 seen.append(g); features.append({'type':'Feature','properties':{k:r[k] for k in ('nameKo','sourceId','sourceUrl','wayIds','osmTags','geometrySource') } | ({'widthBasis': r['widthBasis']} if 'widthBasis' in r else {}),'geometry':r['geometry']})
(ROOT/'public/bridge-outlines.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,indent=2)+'\n')
(ROOT/'docs/bridge-outline-audit.json').write_text(json.dumps({'requested':len(names),'placeRows':len(rows),'ok':len(features),'results':results},ensure_ascii=False,indent=2)+'\n')
print({'requested':len(names),'placeRows':len(rows),'ok':len(features),'failed':sum(x['status']!='ok' for x in results)})
