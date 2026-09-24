import pathlib,json,math,shapely
from shapely.geometry import Polygon,mapping
P=pathlib.Path(__file__).parent;d=json.loads((P/'source-data.json').read_text());r=d['ring_m'];poly=Polygon(r,d['rings_m'][1:]);a,b=r[9],r[10];dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy);sgn=1 if poly.exterior.is_ccw else -1;nx,ny=sgn*dy/L,-sgn*dx/L
# Inward notch: own-edge local station .34 to .66, original outer face atdepth0.
def pt(t,dep):return (a[0]+dx*t+nx*dep,a[1]+dy*t+ny*dep)
notch=Polygon([pt(.34,.01),pt(.66,.01),pt(.66,-1.5),pt(.34,-1.5)]);inside=notch.intersection(poly);shell=poly.difference(notch);assert shell.geom_type=='Polygon' and shell.is_valid and abs(inside.area-L*.32*1.5)<.001
m={'edge':9,'left_station':.34,'right_station':.66,'inward_depth_m':1.5,'edge_length_m':L,'outward_normal':[nx,ny],'notch_geometry':mapping(inside),'shell_rings':[list(shell.exterior.coords)[:-1]]+[list(x.coords)[:-1] for x in shell.interiors],'shell_triangles':[list(q.exterior.coords)[:3] for q in shapely.constrained_delaunay_triangles(shell).geoms],'basis':'104 numbered photo observed deep central service zone; geometric dimensions/orientation inferred; recess subtracts inward from own source, boxes bridge back to original face only','base_full_footprint_height_m':1.0,'upper_full_footprint_closure_z':112.55}
d['central_recess']=m;(P/'source-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));(P/'facade-regions.json').write_text(json.dumps(m,indent=2));print('recess removed area',inside.area,'sourcearea',poly.area,'ccw',poly.exterior.is_ccw)
