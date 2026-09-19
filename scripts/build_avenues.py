"""Major road surfaces follow retained OSM centerlines; missing widths are labeled estimates."""
from pathlib import Path
import json,sqlite3,zlib,math,collections,re
from shapely.geometry import shape,mapping
from shapely.ops import transform
ROOT=Path(__file__).resolve().parents[1];LAT=37.56;X=111319.49*math.cos(math.radians(LAT));Y=111319.49

def main():
 db=sqlite3.connect((ROOT/'data/roads.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 surfaces=[];lines=[];names=set();counts=collections.Counter()
 for r in db.execute("SELECT * FROM roads WHERE category='roadway' AND highway IN ('motorway','trunk','primary','secondary') AND name IS NOT NULL"):
  tags=json.loads(zlib.decompress(r['tags']))
  if tags.get('bridge') not in (None,'no') or tags.get('tunnel') not in (None,'no'):continue
  one=tags.get('oneway') in ('yes','1','-1')
  try:lanes=int(tags.get('lanes','0').split(';')[0])
  except ValueError:lanes=0
  try:width=float(re.sub(r'\s*m$','',tags.get('width','0')))
  except ValueError:width=0
  basis='OSM width tag' if width else 'OSM lanes × 3.25m plus margins' if lanes else 'estimated width from road class and one-way tag'
  if not width:width=lanes*3.25+1.0 if lanes else (11 if one else 18 if r['highway'] in ('primary','trunk','motorway') else 14)
  width=max(5,min(45,width));geo=shape(json.loads(r['geometry']));projected=transform(lambda x,y,z=None:(x*X,y*Y),geo)
  poly=transform(lambda x,y,z=None:(x/X,y/Y),projected.buffer(width/2,cap_style=2,join_style=2))
  props={'id':r['id'],'name':r['name'],'widthM':width,'widthBasis':basis,'sourceLanes':lanes or None,'oneway':one,'sourceUrl':'https://www.openstreetmap.org/way/'+r['id'].split(':')[-1]}
  surfaces.append({'type':'Feature','id':r['id'],'properties':props,'geometry':mapping(poly)})
  lines.append({'type':'Feature','id':r['id'],'properties':props,'geometry':mapping(geo)})
  names.add(r['name']);counts[basis]+=1
 for fn,features in [('avenue-surfaces.geojson',surfaces),('avenue-centerlines.geojson',lines)]:
  (ROOT/'public'/fn).write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':')))
 (ROOT/'docs/AVENUE_COVERAGE.json').write_text(json.dumps({'segments':len(surfaces),'namedRoads':len(names),'widthEvidence':counts,'names':sorted(names),'scope':'Named motorway/trunk/primary/secondary source ways; bridge and tunnel ways excluded. Road edges from buffered centerlines are not surveyed curb polygons.'},ensure_ascii=False,indent=2)+'\n')
 print(len(surfaces),'segments',len(names),'names',dict(counts))
if __name__=='__main__':main()
