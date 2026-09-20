import json, math, hashlib
from pathlib import Path
import numpy as np
from shapely.geometry import shape, Polygon
from shapely.ops import unary_union
OUT=Path(__file__).resolve().parent
rows=json.loads((OUT/'source-buildings.json').read_text());byid={r['id']:r for r in rows}
controls=[('western-a','웨스턴 A',49,185.7,164.2,[224,232],'b560f468-8338-4129-8897-594d06024307'),('western-b','웨스턴 B',42,162.8,143,[221,429],'eb763d30-2a31-4b0a-b77c-2bb753b9d5d4'),('eastern-a','이스턴 A',48,182.5,161,[569,232],'f48046f3-fc57-44db-9f1d-a228ab5c688f'),('eastern-b','이스턴 B',41,159.6,139.8,[568,429],'9bed6662-0c52-4337-abdd-cd0e22788406')]
center=[126.87095,37.5260];mx=111320*math.cos(math.radians(center[1]));my=111320
anchors=[list(shape(json.loads(byid[r[-1]]['geometry'])).centroid.coords[0]) for r in controls]
X=np.array([[*r[5],1] for r in controls]);Y=np.array([[(a[0]-center[0])*mx,(a[1]-center[1])*my] for a in anchors]);coef=np.linalg.lstsq(X,Y,rcond=None)[0]
def off(p,c):return (np.array([p[0]-c[0],p[1]-c[1]])@coef[:2]).tolist()
def site(p):return (np.array([*p,1])@coef).tolist()
# Manually traced visible roof/body outline, rather than the coarse OSM square.
profile=[[-24,-74],[23,-74],[23,-47],[73,3],[3,74],[-78,-3],[-24,-53]]
# Each footprint is recorded independently; repeated matching forms are explicit
# in the numbered 4-tower plan and SIAPLAN completed photos, not a city template.
towers=[]
for r,a in zip(controls,anchors):
 key,label,f,h,occ,pc,fid=r
 pts=[off([pc[0]+x,pc[1]+y],pc) for x,y in profile]
 # Terrace stages correspond to the southpoint helipad and stepped wings.
 stages=[{'pixels':[[-47,-5],[0,-52],[48,-5],[0,43]],'bottom':h-20.7,'top':h-11.6}, {'pixels':[[-38,42],[2,3],[43,43],[2,82]],'bottom':h-20.7,'top':h-1.4}]
 towers.append({'id':'bespoke-mokdong-trapalace-'+key,'label':label,'floors':f,'heightM':h,'occupiedM':occ,'footprintId':fid,'coordinate':{'lon':a[0],'lat':a[1]},'planCenter':pc,'profile':pts,'profilePixels':profile,'stages':[{'profile':[off([pc[0]+x,pc[1]+y],pc) for x,y in st['pixels']],'bottom':st['bottom'],'top':st['top']} for st in stages],'ringCenter':off([pc[0]+2,pc[1]+47],pc),'ringRadiusM':11.2,'bodyTopM':h-20.7,'bodyBottomM':28.7,'planTransform':coef[:2].tolist()})
sources=[{'url':'http://www.siaplan.com/m11_view.php?idx=172&cate=3&sort=st1','observations':['Designer primary completed photographs: asymmetrical stepped penthouses, circular/annular helipad outer edge with radial understructure, broad pale piers, bluegreen glazing, dark framed 34F bridge, terracotta parking podium; completed2009.']},{'url':'https://www.raemian.co.kr/sales/mokdongpalace','observations':['Contractor official522 totalhouseholds,2009.01occupancy. No usable exterior image at current source.']},{'url':'https://openapt.seoul.go.kr/openApt/index.do?aptCode=A15870101','observations':['Combined officialmanagement A15870101,522households,4buildings,299Omok-ro.']},{'url':'http://www.mokdong.com/apt/m1apt/trapalace/trapalace.htm','observations':['Secondary localarchive numberedsiteplan K2004014_E: westernA49/B42,easternA48/B41; primary issuer of plan not independently established. Contemporary completedphotos are supporting viewpoint references, separatelyclassified from4-tuCG.']},{'url':'https://eleng.co.kr/bbs/board.php?bo_table=at01_gallery&wr_id=71','observations':['Safety inspection participant2019site photograph published2020; confirms builtfrontfacade/podium/bridges.']},{'url':'https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do','observations':['Preserved publicregister exactparcel962:264households/49F/174.17m;962-1:258/48F/170.99m. Eachsingle record covers twotowers; heightdatum notconfirmedasarchitecturalhelipad.'] }]
for k,i,h,occ in [('a',2204,185.7,164.2),('b',2205,162.8,143),('c',2206,182.5,161),('d',2207,159.6,139.8)]:sources.append({'url':f'https://www.skyscrapercenter.com/building/mokdong-trapalace-tower-{k}/{i}','observations':[f'ProfessionalCTBUH/CVU buildingrecord architectural+helipadheight{h}m,occupied{occ}m; floorcountcrossmatchwithnumberedplan establishes WA/WB/EA/EB. Notourmeasurement.']})
unc=['Plan is a secondary-hosted architectural drawing with unverified original issue date; as-builtphotoschecked but notconstructionCAD.','Plan georeference uses four independentlynamedOSM towercentres, notsurveyedcontrolpoints; individualanchors retained exactly, local tracedshapes affinefit.','CTBUH architectural/helipad heights adopted; register174.17/170.99m are differentunknownlegalheightdatum, not discarded or claimed identical. Interiorfloor/roofstage elevations except publishedtop/occupied are inferred fromphotos.','Fine rearfacade,terrace equipment,door locations and individualwindow dimensions partlyinferred; no interior modeling.','Podium and commercialstreetfronts simplified; publiccentralwalkway must remain open; onlyexplicitactualsourceIDs claimed.']
podium=[]
for side,shift,fid in [('western',0,'c097c940-ce51-4c9f-bd7f-58cd6c23dcef'),('eastern',344,'f56285fc-1765-405a-82a8-c9fa8c5aa491')]:
 # The photographed reddish residentialparkingpodium forms peripheral wings,
 # kept offcentralpedestrianstreet and southernstandaloneretail8F frontage.
 loops=[[[122+shift,145],[177+shift,145],[177+shift,488],[122+shift,488]],[[282+shift,143],[318+shift,143],[318+shift,475],[282+shift,475]],[[122+shift,470],[318+shift,470],[318+shift,510],[122+shift,510]]]
 podium.append({'side':side,'loops':[[site(q) for q in list(unary_union([Polygon(loop) for loop in loops]).exterior.coords)[:-1]]],'retailFootprintId':fid,'retailGeometry':json.loads(byid[fid]['geometry'])})
R={'siteId':'mokdong-trapalace','siteCenter':center,'code':'A15870101','households':522,'towers':towers,'podiums':podium,'sources':sources,'uncertainties':unc,'georef':{'matrix':coef.tolist(),'controlResidualsM':np.linalg.norm(X@coef-Y,axis=1).tolist(),'method':'fourOSMnamedtowercentroids to numberedplan approximatebodycentres'},'coverage':{'residentialTowers':['western-a','western-b','eastern-a','eastern-b'],'bridges':['western34F','eastern34F'],'commercial':'simplifiedseparate8Ffrontretail+residentialparkingpodium','excluded':'neighborHyperionII,school,broadcastingbuilding,publicstreet'}}
(OUT/'recipe.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(R['georef']))
