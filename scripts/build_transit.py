#!/usr/bin/env python3
"""Build transit labels from the project-local OSM places snapshot."""
import json, re, sqlite3
from math import hypot
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
db = sqlite3.connect(f'file:{ROOT / "data/places.sqlite"}?mode=ro', uri=True)
rows = db.execute("select id,name,lon,lat,source_url,location_method from places where kind='station' and name is not null and trim(name)<>''").fetchall()
features=[]
for ident,name,lon,lat,url,method in rows:
    features.append({'type':'Feature','id':ident,'geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{'nameKo':name,'kind':'rail_station','sourceUrl':url,'locationMethod':method}})
raw=json.loads((ROOT/'data/sources/osm-roads-2026-09-08/overpass.json').read_text())
rail_points=[(f['geometry']['coordinates'][0],f['geometry']['coordinates'][1]) for f in features]
for e in raw.get('elements',[]):
    t=e.get('tags',{})
    if t.get('highway')!='bus_stop' or not t.get('name'): continue
    lon=e.get('lon'); lat=e.get('lat')
    if lon is None or lat is None: continue
    # Keep actual bus-stop nodes at a bounded station-transfer distance.
    if not any(hypot((lon-x)*0.8, lat-y) < 0.002 for x,y in rail_points): continue
    features.append({'type':'Feature','id':f"bus-{e['id']}",'geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{'nameKo':t['name'],'kind':'bus_stop','ref':t.get('ref'),'sourceUrl':f"https://www.openstreetmap.org/node/{e['id']}",'locationMethod':'osm_node'}})
out={'type':'FeatureCollection','metadata':{'source':'data/places.sqlite and local Overpass OSM snapshot','attribution':'© OpenStreetMap contributors'},'features':features}
(ROOT/'public/transit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(f'wrote {len(features)} transit records')
