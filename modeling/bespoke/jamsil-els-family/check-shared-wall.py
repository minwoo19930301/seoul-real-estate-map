from pathlib import Path
import json,importlib.util,numpy as np,shapely
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
R=Path.cwd();P=R/'data/model-source/bespoke/jamsil-els-family'
spec=importlib.util.spec_from_file_location('height',R/'scripts/bespoke/validate_height_regions.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sources={s['number']:s for s in json.loads((R/'docs/model-audit/jamsil-els-source-identity.json').read_text())['towers']}
project=Transformer.from_crs(4326,5179,always_xy=True).transform
polys={n:transform(project,shape(sources[n]['geometry'])) for n in [138,139]}
shared=polys[138].boundary.intersection(polys[139].boundary);assert polys[138].intersection(polys[139]).area<1e-6
report={'sharedBoundaryLengthM':shared.length,'footprintAreaOverlapM2':polys[138].intersection(polys[139]).area,'models':[]}
for n,other in [(138,139),(139,138)]:
 d=json.loads((P/str(n)/'source-data.json').read_text());bundle=json.loads((P/'bundle-132-141.json').read_text());a=next(a for a in bundle if int(a['tower'])==n)
 tri=m.read_triangles(P/a['glbPath']);v=tri.reshape(-1,3);lon,lat=d['anchor_lonlat']
 points=shapely.points(np.column_stack(project(lon+v[:,0]/(111320*np.cos(np.radians(lat))),lat-v[:,2]/111320)))
 exterior=shapely.distance(points,polys[n])>.001
 insideNeighbor=shapely.contains(polys[other].buffer(-.001),points)
 lower=v[:,1]<min(float(sources[n]['register']['height']),float(sources[other]['register']['height']))-.001
 mask=exterior&insideNeighbor&lower
 report['models'].append({'tower':n,'neighbor':other,'vertexOccurrencesInsideNeighborBelowSharedHeight':int(np.sum(mask)),'affectedTriangleCount':int(np.sum(np.any(mask.reshape(-1,3),axis=1))),'maxPenetrationInsideNeighborM':float(np.max(shapely.distance(points[mask],polys[other].boundary))) if np.any(mask) else 0})
(P/'author-shared-wall-review.json').write_text(json.dumps(report,indent=2)+'\n');assert all(x['affectedTriangleCount']==0 for x in report['models']);print(json.dumps(report))
