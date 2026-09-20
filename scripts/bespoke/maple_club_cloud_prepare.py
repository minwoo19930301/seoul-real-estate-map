"""Freeze this pair's individual observed elevation assignments and retained anchors."""
import json,math
from pathlib import Path
from shapely.geometry import Polygon,LineString
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-club-cloud';OUT.mkdir(parents=True,exist_ok=True)
old=json.loads((ROOT/'docs/MAPLE_XI_MODEL_RECIPE.json').read_text());pair=[]
# Every list is an authored face assignment, not an all-complex apartment rule.
faces={210:[{'kind':'blank-slits','slits':[.77]}, {'kind':'paired','bounds':[0,.18,.34,.51,.72,1],'zones':['white','warm','white','graphite','white'],'openings':[[.2,.44,.6,.83],[.13,.36,.50,.89],[.2,.40,.68,.86],[.08,.38,.53,.93],[.12,.36,.60,.90]]}, {'kind':'blank-slits','slits':[.18,.84]}, {'kind':'paired','bounds':[0,.16,.36,.53,.69,.85,1],'zones':['white','graphite','white','warm','graphite','white'],'openings':[[.16,.37,.65,.86],[.09,.42,.59,.93],[.24,.39,.62,.78],[.15,.36,.51,.88],[.1,.38,.53,.90],[.16,.4,.62,.9]]}],
211:[{'kind':'blank-slits','slits':[.79]}, {'kind':'paired','bounds':[0,.23,.48,.74,1],'zones':['white','warm','graphite','white'],'openings':[[.12,.32,.59,.86],[.2,.4,.6,.87],[.15,.42,.58,.89],[.1,.35,.62,.87]]}, {'kind':'paired','bounds':[0,.27,.54,.80,1],'zones':['white','graphite','white','warm'],'openings':[[.18,.37,.6,.82],[.1,.4,.54,.91],[.22,.39,.6,.79],[.15,.42,.61,.9]]}, {'kind':'blank-slits','slits':[.19]}, {'kind':'glazed','bounds':[0,.18,.39,.61,.82,1]}, {'kind':'paired','bounds':[0,.18,.33,.49,.60,.79,1],'zones':['white','graphite','warm','white','graphite','white'],'openings':[[.12,.33,.56,.87],[.09,.40,.55,.93],[.18,.36,.63,.85],[.21,.39,.63,.8],[.09,.38,.55,.92],[.12,.39,.58,.9]]}]}
# Source2 foreground tower is211 by east-side aerial + numbered bridge endpoints.
# Its broad highway facade isplan edge4, not a fully glazed curtain wall.
faces[211][4]={'kind':'observed-211-e4','source':'photo2 foreground + full-resolution official aerial','photoMapping':'numbered plan edge4 [874,263] to [842,304]; left-to-right in east-side photo','paleFraction':.28,'bands':[[0,.28,'white'],[.28,.37,'warm'],[.37,.47,'warm'],[.47,.60,'warm'],[.60,.67,'warm'],[.67,1,'graphite']],'frames':[.28,.37,.47,.60,.67],'openings':[[.038,.065,.85,1.88,1],[.108,.134,.85,1.88,1],[.155,.178,.85,1.88,1],[.217,.258,.45,2.43,2],[.303,.346,.45,2.43,1],[.400,.444,.45,2.43,2],[.493,.573,.45,2.43,2],[.619,.652,.45,2.43,1],[.699,.748,.45,2.43,1],[.827,.868,.45,2.43,1],[.907,.979,.45,2.43,2]],'darkVentStrip':[.775,.795]}
# In the east-side photograph, image left-to-right traverses edge4 backwards.
p=faces[211][4]
p['bands']=[[1-b,1-a,c] for a,b,c in p['bands']]
p['frames']=[1-f for f in p['frames']]
p['openings']=[[1-b,1-a,z0,z1,m] for a,b,z0,z1,m in p['openings']]
p['darkVentStrip']=[1-p['darkVentStrip'][1],1-p['darkVentStrip'][0]]
p['photoParameterDirection']='image left-to-right = vertex5 to vertex4, reverse canonical edge4'
faces[210][1]={'kind':'observed-210-e1','source':'official aerial background bar long facade','photoMapping':'plan edge1 [726,286] to [767,318]; oblique visible behind211','columns':[[.055,.17],[.215,.33],[.375,.49],[.535,.65],[.695,.81],[.855,.97]]}
faces[210][1]['source']='Oblique return seen in aerial; window count remains provisional'
faces[210][1]['photoMapping']='plan edge1 [726,286] to [767,318], northeast return'
faces[210][2]={'kind':'observed-210-e2','source':'photo2 rear tower front + official original-resolution aerial','photoMapping':'plan edge2 [767,318] to [751,338], southeast end; image left-to-right follows vertex3 to vertex2','columns':[[.055,.17],[.215,.33],[.375,.49],[.535,.65],[.695,.81],[.855,.97]]}
for a in old['assets']:
 if a['id'] not in ['maple-xi-210','maple-xi-211']:continue
 d=a['recipe']['dong'];lon,lat=a['coordinate'].values()
 ring=[[(x-lon)*111320*math.cos(math.radians(lat)),(y-lat)*111320] for x,y in a['groundFootprint']['coordinates'][0][:-1]];poly=Polygon(ring)
 # Gentle rounded lounge/canopy corners observed in completed low-angle photograph.
 lounge=poly.buffer(-1.5,join_style=1,resolution=8).buffer(1.98,join_style=1,resolution=8);cap=poly.buffer(-1.5,join_style=1,resolution=8).buffer(2.5,join_style=1,resolution=8)
 plantcenters=([[-18,-3]] if d==210 else [[-13,2],[12,10]])
 pair.append({'dong':d,'id':'bespoke-maple-xi-'+str(d),'oldId':a['id'],'coordinate':a['coordinate'],'ring':ring,'loungeRing':list(lounge.exterior.coords)[:-1],'canopyRing':list(cap.exterior.coords)[:-1],'faces':faces[d],'roofPlantCenters':plantcenters,'roofPlants':([{'width':9.4,'depth':4.3,'height':3.6,'angleDeg':-37,'steppedAnnex':True}] if d==210 else [{'width':9.1,'depth':4.0,'height':3.25,'angleDeg':-37},{'width':8.0,'depth':3.8,'height':3.6,'angleDeg':54}]),'top':90.16,'heightStatus':'29F Club Cloud verified;90.16m roof retained estimate; rooftop dimensions photo proportion','faceMappingStatus':'Numbered-plan and east-side aerial inference; no facade survey.211e4 observed correction;210e2 observed front,210e1 return provisional; unpictured faces simplified estimates.','roofEdgeMode':'continuous projecting canopy with metal parapet, no repeated perimeter crown louvers'})
# Existing bridge centerline tied to the same official plan and affine transform.
import numpy as np
G=np.array(old['georeference']['pixelToLonLatAffine']);anchor=pair[0]['coordinate'];points=[]
for p in [[748,310],[813,279]]:
 lon,lat=np.array([*p,1])@G;points.append([(lon-anchor['lon'])*111320*math.cos(math.radians(anchor['lat'])),(lat-anchor['lat'])*111320])
bridge=list(LineString(points).buffer(1.80,cap_style=2).exterior.coords)[:-1]
out={'siteId':'maple-club-cloud','assets':pair,'bridgeOwner':'bespoke-maple-xi-210','bridgeCenterline':points,'bridgeRing':bridge,'sources':[{'url':'https://www.xi.co.kr/Files/cmsPage/20240205_132346_189001.jpg','observations':'Retain existing numbered 210bar/211L plan trace and anchor relationship.'},{'url':'https://beyondapartment.kr/media/pages/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja/800715b5a5-1773801981/pokeoseu-3.webp','observations':'Completed lounge+connector, differentiated wall colors/openings, multiple rooftop enclosures and perimeter rail.'},{'url':'https://beyondapartment.kr/media/pages/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja/f5d9b99e4f-1773801981/pokeoseu-12.webp','observations':'Rounded glazed lounge corner returns, deep projecting canopy and horizontal mullion at connector.'}],'uncertainties':['Per-face window dimensions and obscured rear faces are photo-derived interpretations, not measured shop drawings.','Existing illustrative-plan trace and anchors retained; no new survey placement claim.','Absolute roof height90.16m and plant enclosure dimensions remain estimates.','Identity of distant roof equipment in aerial photos cannot be fully resolved; enclosure count/form approximates visible pair rather than exact equipment specification.']}
(OUT/'authored-input.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(OUT/'authored-input.json')
