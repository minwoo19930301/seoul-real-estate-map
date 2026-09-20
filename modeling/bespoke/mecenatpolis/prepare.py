"""Create authored trace/recipe input. No remote services or private databases required."""
import json,math
from pathlib import Path
from shapely.geometry import Polygon,shape
import numpy as np
OUT=Path(__file__).resolve().parent
sources=json.loads((OUT/'residential-source-footprints.json').read_text())
# Hand trace of the actual AURUM typical-floor plan, using the inspection crop
# of source aurum-29.jpg at original resolution, crop origin [900,430].
profile=[[177,34],[241,34],[241,64],[301,64],[414,238],[404,244],[426,272],[390,335],[376,346],[383,366],[337,366],[337,374],[231,374],[231,365],[130,365],[119,355],[90,309],[75,325],[41,271],[55,263],[45,232],[86,208],[106,223],[130,181],[149,192],[168,157],[138,154],[152,130],[173,139],[196,105],[147,101],[147,56],[177,56]]
poly=Polygon(profile);cx,cy=poly.centroid.coords[0]
# Printed graphic scale 50 m / 401 original image pixels. Not fitted to the
# larger OSM shape. Site anchors remain the three individually named footprints.
mpp=50/401;ang=math.radians(-74)
def local(p):
 x=(p[0]-cx)*mpp;y=(p[1]-cy)*mpp
 return [round(x*math.cos(ang)+y*math.sin(ang),5),round(x*math.sin(ang)-y*math.cos(ang),5)]
R={'siteId':'mecenatpolis','siteCenter':[126.9139379,37.5513225], 'drawingTrace':{'source':'https://www.aurum.re.kr/Bits/BuildingDoc.aspx?num=5119&page=1','image':'aurum-29.jpg','originalImagePixels':[2654,1539],'cropOrigin':[900,430],'profilePixels':profile,'scaleMPerPixel':mpp,'orientationDeg':-74,'basis':'Printed50m scale and source long facade direction; hand tracing of visible external wall, not a CAD survey. Same repeated typical-floor form is explicitly drawn for all three towers.'},'towers':[], 'sources':[
 {'url':'https://www.aurum.re.kr/Bits/BuildingDoc.aspx?num=5119&page=1','observations':['Architect-supplied Korean Architecture Award2014 photo/drawing set. Actualcompleted photographs00–24; CG25–27 explicitly excluded from facade basis. Typical floor29, roof28, sections45/46, elevations47–49, siteplan50.','Three broken triangular curtainwall towers have fullheight projecting wingwalls; thin pale horizontal grids and intermittent thick dark ledges; opaque pale ventilated narrow vertical stacks; oblique triangular glazed roof screens around smaller central hexagonal rooftop structure.','Retailbase is rounded multilevel limestone volumes and open canyon walks, with curved glass bridges and central circular canopy.']},
 {'url':'https://www.ancbook.com/contents/anc/2012/11/03.htm','observations':['EAWES/JERDE supplied project data:101/10239F,10329F,office32F. 3residential towers plus separately designed office.']},
 {'url':'https://www.ancbook.com/contents/anc/2012/12/18.htm','observations':['Correction: EAWES overall/masterplan/towers, JERDE lowercommercial design.']},
 {'url':'https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do','observations':['Exact Seogyo490/Yanghwa45 register: apartment sharedrecord10151100207031 39F137.4m617households; no individually measured101/102/103height rows. Office164m is distinct and not used for residential towers.']},
 {'url':'https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do','observations':['A12174601:617households and3residentialbuildings, independentlyKapt617/3.']},
 {'url':'https://www.jerde.com/projects/7849/mecenatpolis','observations':['Actual completed lowercommercial photo references, contrasted with explicitly labelled renderings.']}
 ],'uncertainties':['No per-tower as-built height survey found.137.4m shared apartment register is conservatively used as total101/102model envelope INCLUDINGscreens; heightdatum and exactscreenheights uncertain.103height derived by subtracting10typical3.0667m floors, not labelled a measured103height.','Drawing49m typicalplate is smaller than OSMrough60m outline; authoredactualplan rather than extrudedOSM is used. Coordinates use independently named OSMcentroids; geometricplacement is not a cadastral survey.','Hidden curtainwall pane/crown back details are conservative drawing-based approximations. No invented changing-floor curves; plan shows repeated triangular plates.','Primary drawings do not label101/102 text onsiteplan. Number mapping uses namedsourcepolygons, road/compass alignment and the distinct29F103plan/section.','Photographs/drawings retained forprivate reference only; no source imagery embedded or redistributed in exportedgeometry.'], 'coverage':{'residentialTowers':['101','102','103'],'households':617,'officeTower':'SeAH tower excluded and preserved, IDb028f776-57de-460a-ad6f-4f0919b2d0e7','commercial':'Simplified curved podiums/canyonbridges/circular canopy within residentialside fromAURUMsiteplan; individualshop/interior/B7excluded','cultureHall':'Excluded from ownership and fullmodeling; no adjacentparcelclaim'}, 'recipeFiles':['recipe.json','prepare.py','residential-source-footprints.json','register-rows.json']}
for num in ['101','102','103']:
 s=next(s for s in sources if num in s['name']);geo=s['geometry'];geo=json.loads(geo) if isinstance(geo,str) else geo;g=shape(geo);h=137.4 if num!='103' else 137.4-10*(110.4/36)
 T={'number':num,'id':'bespoke-mecenatpolis-'+num,'anchor':{'lon':g.centroid.x,'lat':g.centroid.y},'footprintId':s['id'],'sourceOSM':s['source_properties'],'floors':39 if num!='103' else 29,'floorIntervalM':110.4/36,'bodyBottomM':14.7,'bodyTopM':h-12.3,'envelopeM':h,'profile':list(reversed([local(p) for p in profile])),'planProfile':profile,'localProjection':{'centerPixel':[cx,cy],'mpp':mpp,'angleDeg':-74},'heightBasis':'Shared137.4m register envelope interpretation; independently confirmed floorcount. 103 subtracts10typicalfloorintervals, not a measurement.'}
 # Roofplan independenthandtrace scaledfrom actual roofplan28 crop; roof center
 # and screen positions align with the three corresponding body facade wings.
 # Coordinates below are in the same typicalfloor pixel frame, transcribed from28.
 T['roofCore']= [local(p) for p in [[218,137],[316,137],[374,246],[316,326],[208,326],[158,244]]]
 T['screens']=[{'a':local([301,64]),'b':local([426,272]),'heightAtA':12.3,'heightAtB':0.8}, {'a':local([383,366]),'b':local([119,365]),'heightAtA':12.3,'heightAtB':0.8}, {'a':local([45,232]),'b':local([177,34]),'heightAtA':12.3,'heightAtB':0.8}]
 T['wingEdges']=[[local([301,64]),local([426,272])],[local([383,366]),local([119,365])],[local([45,232]),local([177,34])]]
 R['towers'].append(T)
# The separate mall approximation is traced in a1800px-wide copy ofAURUM50.
# Three residentialplan centroids are controlpoints; only this lowlevel trace is
# affinegeoreferenced, never scaled to modifytower floorplate geometry.
pix=np.array([[984,592,1],[786,920,1],[580,578,1]],dtype=float)
xy=[]
for T in R['towers']:
 a=T['anchor'];xy.append([(a['lon']-R['siteCenter'][0])*111320*math.cos(math.radians(R['siteCenter'][1])),(a['lat']-R['siteCenter'][1])*111320])
coef=np.linalg.solve(pix,np.array(xy))
def sitept(p):return [round(v,5) for v in (np.array([*p,1])@coef)]
# Closed curves are authored along real residential-side podiumperimeters, not
# the propertyboundary. Omit office/culturehall, streets and centralpedestrian gaps.
loops=[[[429,459],[506,429],[585,440],[649,481],[671,552],[701,581],[705,617],[667,652],[605,697],[541,696],[490,661],[461,610],[430,556]], [[919,469],[959,442],[1007,450],[1054,489],[1108,569],[1124,624],[1090,664],[1031,689],[970,682],[915,675],[883,640],[877,591],[901,550]], [[537,779],[587,747],[649,752],[705,782],[752,808],[814,828],[854,871],[877,930],[861,972],[819,1006],[760,1012],[708,984],[651,993],[590,1004],[543,987],[538,900]]]
R['mall']={'id':'bespoke-mecenatpolis-residential-podium','anchor':{'lon':R['siteCenter'][0],'lat':R['siteCenter'][1]},'footprintIds':[], 'loops':[list(reversed([sitept(v) for v in q])) for q in loops],'canopyCenter':sitept([766,681]),'canopyRadiusM':15.2,'heightM':12.6,'controlPoints':{'pixels':pix.tolist(),'sourceMeters':xy,'affine':coef.tolist()},'heightsBasis':'Sharedmallregister12.6m as simplifiedtop; levelheights and geometryhandtrace estimated. No undergroundinterior.'}
(OUT/'recipe.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n')
print('profilearea',poly.area*mpp*mpp,'dimensionsdrawingM',[(poly.bounds[i+2]-poly.bounds[i])*mpp for i in range(2)])
print([(t['number'],t['anchor'],t['envelopeM']) for t in R['towers']])
