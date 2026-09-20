"""Manually authored Maple Xi model study from the developer's plan and as-built photographs.

Writes only ignored data/model-source/maple-xi-current. No active catalog mutation.
Georeferencing and unseen elevations are interpretive, not surveyed CAD.
"""
from pathlib import Path
import json, math, hashlib
import numpy as np
from shapely.geometry import Polygon, LineString, box
from shapely.ops import transform, unary_union
from shapely.geometry.polygon import orient
from build_district_landmarks import Mesh, projected, unprojected

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/model-source/maple-xi-current'
REF='https://beyondapartment.kr/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja'
PLAN='https://www.xi.co.kr/Files/cmsPage/20240205_132346_189001.jpg'
NOTICE='https://www.xi.co.kr/Files/cmsPage/20240126_101604_789001.pdf'
CLOUD='https://www.xi.co.kr/maple/view?cmsMenuSeq=19690'
PHOTO='https://www.xi.co.kr/Files/aptProcRateImg/20250403_170535_099001.JPG'
CONTROLS=[{'pixel':[110,386],'coordinate':[127.0096393,37.5120376],'osmNode':436816900,'intersection':'신반포로33길 / 잠원로4길'}, {'pixel':[669,84],'coordinate':[127.0133484,37.5138164],'osmNode':436816903,'intersection':'나루터로4길 / 잠원로4길'}, {'pixel':[377,985],'coordinate':[127.0113552,37.5088814],'osmNode':571450682,'intersection':'나루터로4길 / 신반포로33길'}]
GEO=np.linalg.solve(np.array([[*c['pixel'],1] for c in CONTROLS]),np.array([c['coordinate'] for c in CONTROLS]))
# Each outline is traced separately from the numbered 1100 px-wide official site plan.
# Roof edges in an illustrative plan are not a cadastral footprint survey.
TRACES={
101:[[555,226],[575,201],[595,219],[620,187],[641,204],[600,255]],
102:[[545,317],[562,296],[586,318],[612,297],[632,315],[589,350]],
103:[[420,329],[440,306],[467,330],[493,287],[515,306],[471,365]],
104:[[300,411],[316,390],[365,428],[383,402],[398,418],[369,455]],
105:[[418,411],[439,386],[476,416],[511,390],[529,411],[489,463]],
106:[[542,412],[561,390],[615,433],[641,411],[661,428],[617,459]],
107:[[561,533],[580,510],[620,543],[646,521],[666,540],[623,570]],
108:[[443,513],[462,490],[513,531],[536,507],[555,525],[516,564]],
109:[[331,509],[350,488],[398,527],[416,509],[436,528],[404,564]],
110:[[199,504],[219,482],[274,527],[305,489],[324,505],[278,562]],
111:[[258,590],[273,571],[343,627],[329,650]],
112:[[355,625],[384,591],[402,607],[374,646]],
113:[[422,618],[439,599],[482,634],[490,623],[508,639],[482,671]],
114:[[530,617],[547,595],[614,649],[600,674]],
201:[[588,807],[609,782],[641,808],[680,761],[700,778],[644,846]],
202:[[709,787],[727,765],[758,790],[804,735],[825,752],[768,820]],
203:[[844,739],[862,718],[896,746],[930,706],[951,724],[904,781]],
204:[[829,635],[848,612],[882,640],[910,603],[927,620],[890,672]],
205:[[677,669],[696,647],[741,683],[789,621],[809,638],[748,713]],
206:[[715,550],[734,527],[771,558],[806,512],[827,528],[778,583]],
207:[[844,535],[871,501],[893,518],[901,508],[921,525],[883,568]],
208:[[826,415],[853,383],[884,409],[856,443]],
209:[[714,418],[731,396],[768,426],[791,397],[811,413],[776,456]],
210:[[708,308],[726,286],[767,318],[751,338]],
211:[[792,276],[811,251],[839,274],[854,246],[874,263],[842,304]],
212:[[787,176],[807,154],[823,168],[853,132],[871,149],[832,204]],
213:[[700,195],[716,176],[735,193],[758,161],[780,177],[746,219]],
214:[[698,92],[717,73],[738,91],[760,50],[779,64],[756,113],[745,131]],
215:[[790,78],[809,56],[824,68],[852,27],[872,43],[831,100]],
}
# Storey counts other than Club Cloud's 29F are provisional silhouette estimates.
FLOORS={101:35,102:35,103:35,104:35,105:35,106:35,107:35,108:35,109:35,110:35,111:29,112:29,113:35,114:35,201:35,202:35,203:29,204:29,205:35,206:35,207:29,208:29,209:35,210:29,211:29,212:29,213:35,214:29,215:29}
HIGHWAY={203,204,207,208,211,212,215}
IVORY=[.68,.67,.63]; WARM=[.50,.48,.44]; NEUTRAL=[.43,.46,.46]; GLASS=[.18,.31,.34]; FRAME=[.73,.72,.67]; STONE=[.37,.38,.36]; ROOF=[.33,.35,.34]; DARK=[.12,.16,.17]

def ll(p):return (np.array([*p,1])@GEO).tolist()
def local(p,anchor):return projected(*ll(p),anchor)
def polygons(g):return [g] if g.geom_type=='Polygon' else list(g.geoms) if g.geom_type=='MultiPolygon' else []
def solid(mesh,p,b,t,col=IVORY,roof=ROOF):
 if p.is_empty or t<=b:return
 for q in polygons(p):
  if q.area>.001:mesh.solid(q,b,t,col,roof)
def strip(mesh,a,b,width,bottom,top,color):
 solid(mesh,LineString([a,b]).buffer(width/2,cap_style=2),bottom,top,color,color)
def wall_quad(mesh,a,b,lo,hi,col,mat=1,offset=.09):
 dx,dz=b[0]-a[0],b[1]-a[1];le=math.hypot(dx,dz)
 if le<.001:return
 nx,nz=dz/le,-dx/le;a=(a[0]+nx*offset,a[1]+nz*offset);b=(b[0]+nx*offset,b[1]+nz*offset)
 mesh.quad(mat,(a[0],lo,a[1]),(a[0],hi,a[1]),(b[0],hi,b[1]),(b[0],lo,b[1]),col)

def facade(mesh,poly,top,floors,dong):
 ring=list(orient(poly,sign=1).exterior.coords)
 for edge,(a,b) in enumerate(zip(ring,ring[1:])):
  length=math.dist(a,b)
  if length<2:continue
  ux,uz=(b[0]-a[0])/length,(b[1]-a[1])/length
  pos=lambda s:(a[0]+ux*s,a[1]+uz*s)
  east_face=uz>.25
  glass_face=dong in HIGHWAY and east_face and length>9
  blank=length<18.5 and dong not in [112,208]
  if blank:
   # Completed107/108/215 side walls: broad pale wall, fine vertical grooves,
   # and a distinct gray stone lower zone; do not add a window grid here.
   wall_quad(mesh,pos(0),pos(length),7,min(20,top-1),STONE,0,.12)
   for s in np.arange(.6,length-.3,1.25):
    # Keep the visible face32cm beyond the wall for MapLibre depth precision.
    strip(mesh,pos(s),pos(min(length-.3,s+.09)),.64,20,top-1.2,FRAME)
   continue
  if glass_face:
   # Seven highway-facing façades: continuous blue-gray glazing and white
   # perimeter frames; mullions remain finer than the main frame rhythm.
   wall_quad(mesh,pos(.35),pos(length-.35),7,top-.3,GLASS,1,.13)
   bays=max(2,round(length/4.4));span=length/bays
   for bay in range(bays):
    start=bay*span+.27;end=(bay+1)*span-.27
    strip(mesh,pos(bay*span+.02),pos(bay*span+.22),.36,7,top,FRAME)
    wall_quad(mesh,pos((start+end)/2-.045),pos((start+end)/2+.045),7,top-.4,NEUTRAL,0,.21)
    for level in range(2,floors):
     lo=7+(level-2)*(top-7)/(floors-2)
     wall_quad(mesh,pos(start),pos(end),lo,lo+.43,NEUTRAL,0,.20)
     wall_quad(mesh,pos(start),pos(end),lo+.95,lo+1.03,FRAME,0,.22)
   for s in [.38,length-.8]:strip(mesh,pos(s),pos(s+.42),.55,7,top,FRAME)
   wall_quad(mesh,pos(0),pos(length),top-1.0,top,FRAME,0,.27)
  else:
   # Completed bridge-front and215 photographs show paired unequal windows
   # within broad gray stacks, separated by substantial white frame piers.
   # Geometry/orientation selects a coherent elevation, never random windows.
   margin=2.4 if east_face else 1.5
   usable=length-2*margin;groups=max(2,round(usable/(7.6 if east_face else 6.8)));span=usable/groups
   for group in range(groups):
    start=margin+group*span+.30;end=margin+(group+1)*span-.30
    middle=(group in ({1,groups-2} if groups>=5 else {groups//2})) and groups>=3
    panel=[.30,.32,.32] if middle and east_face else [.43,.44,.43] if middle else IVORY
    wall_quad(mesh,pos(start),pos(end),7,top-.65,panel,0,.14)
    # White perimeter frames span the whole elevation and remain legible
    # from the map camera, unlike the old repeating single-window grid.
    pier=margin+group*span-.36
    strip(mesh,pos(pier),pos(pier+1.02),.65,7,top,FRAME)
    width=end-start
    if middle:
     openings=[(.12,.31),(.47,.88)]
    elif east_face:
     openings=[(.10,.31),(.65,.88)]
    else:
     openings=[(.12,.33),(.65,.88)]
    for level in range(2,floors):
     lo=7+(level-2)*(top-7)/(floors-2)+.43;hi=min(top-.70,lo+2.00)
     if hi<=lo:continue
     for wi,(u,v) in enumerate(openings):
      x0=start+width*u;x1=start+width*v
      wall_quad(mesh,pos(x0),pos(x1),lo,hi,GLASS,1,.22)
      if x1-x0>1.65:
       mid=(x0+x1)/2
       wall_quad(mesh,pos(mid-.035),pos(mid+.035),lo,hi,NEUTRAL,0,.26)
      strip(mesh,pos(x0-.06),pos(x1+.06),.18,lo-.12,lo+.02,FRAME)
     # Light floor spandrels define a large framed bay, retaining the paired
     # window asymmetry rather than a uniform cell lattice.
     if not middle:wall_quad(mesh,pos(start),pos(end),lo-.43,lo-.15,IVORY,0,.23)
   strip(mesh,pos(length-margin-.32),pos(length-margin+.36),.55,7,top,FRAME)
   wall_quad(mesh,pos(0),pos(length),top-.85,top,FRAME,0,.30)
   # Lower gray stone-clad sleeve observed in the completed courtyard photo.
   for s0,s1 in [(0,margin),(length-margin,length)]:
    wall_quad(mesh,pos(s0),pos(s1),7,min(20,top-.9),STONE,0,.24)
  for s in [length*.17,length*.79]:solid(mesh,PointBox(pos(s),.68,.68),0,7,STONE,STONE)
  if length>15:
   mid=length*.51;strip(mesh,pos(mid-2.6),pos(mid+2.6),1.25,5.2,5.55,FRAME)


def PointBox(p,w,d):return box(p[0]-w/2,p[1]-d/2,p[0]+w/2,p[1]+d/2)

def crown(mesh,poly,top,dong):
 # As-built upper screens follow the actual bent plan rather than a generic pitched roof.
 inner=poly.buffer(-.35,join_style=2)
 if inner.is_empty:inner=poly
 solid(mesh,inner.buffer(.27,join_style=1).difference(inner.buffer(-.28,join_style=1)),top-.18,top+.28,FRAME,FRAME)
 ring=list(orient(inner,sign=1).exterior.coords)
 if dong in HIGHWAY or dong in [111,112,210]:
  for a,b in zip(ring,ring[1:]):
   le=math.dist(a,b)
   if le<3:continue
   for t in np.arange(.45,le,.85):
    p=(a[0]+(b[0]-a[0])*t/le,a[1]+(b[1]-a[1])*t/le)
    solid(mesh,PointBox(p,.13,.33),top,top+(1.0 if dong in [210,211] else 1.95),FRAME,FRAME)
  solid(mesh,inner.buffer(.3).difference(inner.buffer(-.3)),top+(.95 if dong in [210,211] else 1.90),top+(1.15 if dong in [210,211] else 2.15),FRAME,FRAME)
 else:
  solid(mesh,inner.buffer(.2).difference(inner.buffer(-.18)),top,top+.9,FRAME,FRAME)
 core=poly.buffer(-3.1)
 if not core.is_empty:
  # Two small rooftop service enclosures on long L/I wings, not an invented extra residential floor.
  for q in polygons(core):
   c=q.representative_point();plant=PointBox((c.x,c.y),4.8,4.2).intersection(q)
   solid(mesh,plant,top,top+4.4,IVORY,FRAME)


def roof_lounge(mesh,poly,top):
 lounge=poly.buffer(-.18,join_style=1)
 solid(mesh,lounge,top-4.4,top-.2,GLASS,ROOF)
 solid(mesh,lounge.buffer(.6,join_style=1),top-.2,top+.18,FRAME,FRAME)
 ring=list(orient(lounge,sign=1).exterior.coords)
 for a,b in zip(ring,ring[1:]):
  le=math.dist(a,b)
  for t in np.arange(0,le,1.55):
   p=(a[0]+(b[0]-a[0])*t/le,a[1]+(b[1]-a[1])*t/le)
   solid(mesh,PointBox(p,.09,.12),top-4.4,top-.2,NEUTRAL,NEUTRAL)

def build_tower(dong):
 coords=[ll(p) for p in TRACES[dong]];geo=Polygon(coords);anchor=(geo.centroid.x,geo.centroid.y)
 poly=Polygon([local(p,anchor) for p in TRACES[dong]])
 assert poly.is_valid and poly.area>30,(dong,poly.area)
 if dong in HIGHWAY:poly=poly.buffer(-.65,join_style=1).buffer(.65,join_style=1,resolution=3)
 mesh=Mesh();floors=FLOORS[dong];top=7+(floors-2)*3.08
 # Pilotis space is open around a recessed lobby and structural columns.
 lobby=poly.buffer(-2.5,join_style=2);solid(mesh,lobby,0,7,STONE,STONE)
 bodytop=top-4.4 if dong in [210,211] else top
 solid(mesh,poly,7,bodytop,IVORY,ROOF)
 facade(mesh,poly,bodytop,floors-1 if dong in [210,211] else floors,dong)
 crown(mesh,poly,top,dong)
 features=['individually traced numbered plan','7m pilotis portal','recessed stone lobby','broad gray paired-window stacks and projecting white perimeter frames','unequal center/corner window widths by elevation','gray stone lower sleeve','raised window mullions','plan-shaped crown','rooftop service enclosure']
 if dong in HIGHWAY:features+=['documented highway-facing curtain-wall-look elevation','projecting vertical fins','louver crown screen']
 if dong in [210,211]:
  roof_lounge(mesh,poly,top)
  features+=['29F CLUB CLOUD glazed roof lounge']
 if dong==210:
  # Connecting bridge is attached to 210 so its true above-ground y survives GLB placement.
  a=local([748,310],anchor);b=local([813,279],anchor)
  deck=LineString([a,b]).buffer(1.65,cap_style=2)
  solid(mesh,deck,top-4.5,top-4.05,FRAME,FRAME)
  solid(mesh,deck,top-4.05,top-.25,GLASS,GLASS)
  solid(mesh,deck.buffer(.28),top-.25,top+.13,FRAME,FRAME)
  vx,vz=b[0]-a[0],b[1]-a[1];length=math.hypot(vx,vz);nx,nz=vz/length,-vx/length
  for sign in [-1,1]:
   for t in np.arange(.65,length,1.35):
    p=(a[0]+vx*t/length+nx*1.7*sign,a[1]+vz*t/length+nz*1.7*sign)
    solid(mesh,PointBox(p,.08,.12),top-4.05,top-.25,NEUTRAL,NEUTRAL)
  features+=['diagonal glazed skybridge connecting210–211 at29F']
 return mesh,anchor,geo,{'dong':dong,'floorsEstimate':floors,'floorCountVerified':dong in [210,211],'floorBasis': 'Official CLUB CLOUD 29F page and 2025 completed photo' if dong in [210,211] else 'Unverified individual floor count; approximate aerial silhouette constrained by official35F complex maximum','storeyHeightEstimateM':3.08,'mainRoofHeightEstimateM':top,'groundFootprintPixelTrace':TRACES[dong],'features':features}

def asset(mesh,anchor,geo,ident,name,category,recipe):
 path=OUT/(ident+'.glb');stats,offset=mesh.save(path);lon,lat=unprojected(offset[0],offset[2],anchor)
 return {'id':ident,'nameKo':name,'model':path.name,'coordinate':{'lon':lon,'lat':lat},'dimensions':stats['dimensions'],'yawDegFromEast':0,'heightDatum':'local ground at individual model anchor','category':category,'district':'서초구','minZoom':15,'referenceQuality':'photo-authored','referenceUrl':REF,'referenceUrls':[REF,PLAN,NOTICE,CLOUD,PHOTO],'heightEstimated':True,'geometryEstimated':True,'footprintIds':[],'geoBounds':list(geo.bounds),'groundFootprint':geo.__geo_interface__,'recipe':recipe,**stats}

def build_kindergarten():
 trace=[[494,673],[518,647],[581,698],[560,725]]
 coords=[ll(p) for p in trace];geo=Polygon(coords);anchor=(geo.centroid.x,geo.centroid.y);poly=Polygon([local(p,anchor) for p in trace]);mesh=Mesh()
 solid(mesh,poly,0,17.2,[.62,.60,.55],ROOF);facade(mesh,poly,17.2,5,900)
 return asset(mesh,anchor,geo,'maple-xi-kindergarten','메이플자이 남측 유치원·종교시설 예정부지','kindergarten',{'residential':False,'floorsEstimate':5,'floorCountVerified':False,'basis':'2024 official plan labels separate kindergarten/religious planned facility1–5F; completed dimensions not independently confirmed','pixelTrace':trace})

def build_pedestrian_bridge():
 trace=[[434,482],[522,487],[602,479],[682,483],[755,494],[820,505],[868,499]]
 coords=[ll(p) for p in trace];geo=LineString(coords).buffer(.000035)
 anchor=coords[3];localpoints=[local(p,anchor) for p in trace];line=LineString(localpoints)
 deck=line.buffer(4.2,cap_style=2,join_style=1);mesh=Mesh()
 # Slender piers and an elevator core reach local ground and make the deck a separate grounded asset.
 for p in localpoints[1:-1]:solid(mesh,PointBox(p,.95,1.5),0,5.9,STONE,STONE)
 solid(mesh,deck,5.9,6.5,IVORY,IVORY)
 park=deck.buffer(-.65);solid(mesh,park,6.5,6.75,[.30,.40,.22],[.30,.40,.22])
 path=line.buffer(1.1,cap_style=2);solid(mesh,path,6.75,6.79,[.59,.55,.46],[.59,.55,.46])
 edge=deck.boundary
 for p in localpoints[1:-1]:solid(mesh,PointBox((p[0]+2.8,p[1]),.32,.32),6.8,9.3,[.25,.23,.17],[.25,.23,.17])
 for q in polygons(deck.buffer(.10).difference(deck.buffer(-.12))):solid(mesh,q,6.5,7.65,[.44,.60,.57],[.44,.60,.57])
 solid(mesh,PointBox(localpoints[2],2.5,3.3),0,10.2,GLASS,FRAME)
 return asset(mesh,anchor,geo,'maple-xi-maple-road','메이플자이 메이플로드 보행브리지','pedestrian-bridge',{'residential':False,'basis':'Official plan route and completed2025 photos; deck height/width, pier spacing are visual estimates','pixelCenterline':trace,'distinguishedFromSkybridge':True})

def main():
 OUT.mkdir(parents=True,exist_ok=True);assets=[]
 for dong in sorted(TRACES):
  mesh,anchor,geo,recipe=build_tower(dong);assets.append(asset(mesh,anchor,geo,f'maple-xi-{dong}',f'메이플자이 {dong}동','residential-apartment',recipe))
 assets+=[build_kindergarten(),build_pedestrian_bridge()]
 # Site suppression masks follow the official red parcel lines, leaving the middle public road open.
 site_traces=[[[171,482],[200,451],[272,462],[337,373],[547,203],[643,175],[664,469],[667,541],[561,738],[473,699],[397,643],[369,666],[348,687],[246,706],[201,593]],[[702,42],[875,17],[895,490],[972,798],[628,914],[568,809],[682,584],[695,484]]]
 sites=[Polygon([ll(p) for p in tr]) for tr in site_traces]
 for i in range(2):
  own=[Polygon([ll(p) for p in TRACES[d]]) for d in TRACES if (d<200)==(i==0)]
  sites[i]=unary_union([sites[i],*own])
 assert all(g.is_valid for g in sites)
 out={'name':'메이플자이','generator':'scripts/build_maple_xi.py','acquiredAt':'2026-09-20','sources':[{'url':PLAN,'kind':'developer illustrative numbered plan','date':'2024-02-05 filename; pre-completion'},{'url':NOTICE,'kind':'official sales notice','date':'2024-01-26'},{'url':PHOTO,'kind':'developer actual aerial construction photo','date':'2025-03 photo label; uploaded2025-04-03'},{'url':REF,'kind':'developer magazine completed-building photographs','date':'2025-11-26 publication; capture dates unspecified'},{'url':'https://www.xi.co.kr/maple/aptconst?aptSeq=2527&type=9','kind':'developer construction page','moveInYearMonth':'2025-06'},{'url':'https://overpass.kumi.systems/api/interpreter','kind':'OpenStreetMap public road geometries','osmBaseTimestamp':'2026-06-01T08:52:28Z','license':'ODbL; ©OpenStreetMap contributors'}],'imagesRedistributed':False,'residentialBuildingCount':29,'ancillaryBuildingCount':2,'skybridgeAttachedTo':'maple-xi-210','individualFloorCountsVerified':[210,211],'georeference':{'controls':CONTROLS,'pixelToLonLatAffine':GEO.tolist(),'method':'3 road intersection centers; visual cross-check against all nearby road polylines','accuracy':'illustrative-plan trace, not surveying; control selection/changed road width and plan roof overhang introduce error'},'siteMaskGeoJSON':{'type':'MultiPolygon','coordinates':[g.__geo_interface__['coordinates'] for g in sites]},'siteMaskPixelTraces':site_traces,'assets':assets,'totals':{'glbs':len(assets),'bytes':sum(a['bytes'] for a in assets),'triangles':sum(a['triangles'] for a in assets)},'limitations':['Individual floors except210/211 need as-built register confirmation; other heights are aerial silhouette estimates, not certified metrics.','Plan is2024 sales illustration, cross-checked against actual2025 photographs; exterior details on unseen faces are inferred.','Site mask is digitized and must be overlap-reviewed before suppressing surrounding original buildings.','Only the seven documented highway-facing towers use curtain-wall-look elevations; podiums and louver spacing are photo-led approximations.']}
 (OUT/'modeling-recipe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(out['totals']),flush=True)

if __name__=='__main__':main()
