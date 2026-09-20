from pathlib import Path
import json,math
from shapely.geometry import shape,Polygon
from shapely.ops import unary_union
OUT=Path(__file__).resolve().parent
bs=json.loads((OUT/'source-buildings.json').read_text());rs=json.loads((OUT/'source-register.json').read_text())
center=[126.87035,37.52417];tw=[]
for num,h,f in [(201,122.8,37),(202,134.55,41),(203,109.65,33),(204,134.55,41)]:
 b=next(x for x in bs if x['name']==str(num));g=shape(json.loads(b['geometry']));lon,lat=g.centroid.coords[0]
 pts=[[(x-lon)*111320*math.cos(math.radians(lat)),(y-lat)*111320] for x,y in g.exterior.coords[:-1]]
 if sum(a[0]*c[1]-c[0]*a[1] for a,c in zip(pts,pts[1:]+pts[:1]))<0:pts.reverse()
 # Explicit face roles from actual Y outline: narrow spur ends stone, broad
 # south living fronts and north re-entrant faces have different glazing.
 faces=[]
 for i,(a,c) in enumerate(zip(pts,pts[1:]+pts[:1])):
  L=math.dist(a,c);mid=[(a[k]+c[k])/2 for k in range(2)]
  role='living_side'
  if L<5:role='stone_return'
  elif 7<L<12 and mid[1]>1:role='stone_spur_end'
  elif L>17 and mid[1]<-7:role='broad_south_front'
  elif mid[1]>1:role='courtyard_bay'
  faces.append({'edge':i,'role':role,'length':L})
 tw.append({'number':num,'id':f'bespoke-mokdong-hyperion-2-{num}','coordinate':{'lon':lon,'lat':lat},'profile':pts,'faceRoles':faces,'footprintId':b['id'],'heightM':h,'floors':f,'households':{201:140,202:156,203:124,204:156}[num], 'angleDeg':{201:17.8,202:20.5,203:18.7,204:17.1}[num]})
R={'siteCenter':center,'towers':tw,'sources':[{'url':'https://www.aurum.re.kr/Bits/BuildingDoc.aspx?num=341&page=1&tb=A','observations':'2007 architectural award: NeoPlan/Hyundai project at Mokdong961. Actual photographs: pale stone short wing ends, inset green glazing, floor spandrels, roof blade screens. Photo4 camera/building identification inferred from surrounding arrangement.'},{'url':'https://www.sfacade.net/dongtan-hyperion-1','observations':'Facade consultant completed photos, courtyard and close rooftop skyline. Raised central stone roofvolume with paired sloped blades and horizontal crossbars; outer wings remain lower. Page49storey/Gyeonggi text conflicts with register and is not used.'},{'url':'https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do','observations':'Exact parcel Mokdong961 / Omokro300: 201 37F122.8m140homes;20241F134.55m156;20333F109.65m124;20441F134.55m156. Building heights statutory datum unspecified.'},{'url':'https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do','observations':'A15805111 official576households4residentialbuildings, distinguished from separate business205/206.'},{'url':'http://www.mokdong.com/apt/m1apt/hyperion2/hyperion2.htm','observations':'Secondary contemporaneous siteplan host, used only to corroborate six-building arrangement. CG explicitly excluded from completed facade evidence.'}], 'uncertainties':['Legal register height datum does not explicitly identify highest decorative blade; modeled entire envelope conservatively fits published legal height, not asserted survey roof-tip height.','Primary completed photos support facade composition but face-to-number assignment and exact hidden roof service geometry are interpretations.','OSM traced source plates are not architect as-built CAD; small edge inaccuracies retained and source IDs preserved.','Sloped crown blade positions/counts and glazing mullions reconstructed from visible photographs; rear servicefaces conservative.','Entrances simplified within each residential footprint; separate commercial/officetel205/206 remain outside this model.'], 'coverage':{'residentialTowerCount':4,'households':576,'managementCode':'A15805111','included':['201','202','203','204'],'excluded':['205 business/officetel','206 business/officetel','unowned sitewide retail/landscape'], 'roofAndFacade':'Individually traced Y plates; pale stone piers, green livingbays, floorbands, narrow servicewindows and raised central crown with angled blades.'}}
# Union equal-elevation parapet solids to remove coincident cap polygons.
for t in tw:
 pp=t['profile'];low=[];high=[]
 for desc,(a,b) in zip(t['faceRoles'],zip(pp,pp[1:]+pp[:1])):
  dx=b[0]-a[0];dy=b[1]-a[1];L=math.hypot(dx,dy);nx=dy/L;ny=-dx/L
  def rect(lo,hi):return Polygon([(a[0]+nx*lo,a[1]+ny*lo),(b[0]+nx*lo,b[1]+ny*lo),(b[0]+nx*hi,b[1]+ny*hi),(a[0]+nx*hi,a[1]+ny*hi)])
  low.append(rect(-.2,.4))
  if desc['role']=='stone_spur_end':high.append(rect(-.9,.45))
 for key,polys in [('lowParapets',low),('highParapets',high)]:
  u=unary_union(polys);parts=[u] if u.geom_type=='Polygon' else list(u.geoms)
  # Holes can appear in the low continuousring. Split into nonoverlapping
  # triangles, filtering by actualcoveredarea, so no accidental solidroofcap.
  from shapely.ops import triangulate
  t[key]=[]
  for q in parts:
   if q.interiors:
    for tr in triangulate(q):
     z=tr.intersection(q)
     if z.geom_type=='Polygon' and z.area>.0001:t[key].append(list(z.exterior.coords)[:-1])
   else:t[key].append(list(q.exterior.coords)[:-1])
(OUT/'recipe.json').write_text(json.dumps(R,ensure_ascii=False,indent=2))
