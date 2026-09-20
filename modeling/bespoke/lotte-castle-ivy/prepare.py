from pathlib import Path
import json,math
from shapely.geometry import Polygon,box,LineString
from shapely.affinity import scale
OUT=Path(__file__).resolve().parent
S=json.loads((OUT/'source-footprints.json').read_text());T=[]
for i,src in enumerate(S[:2]):
 pts=src['planUV']; ring=[]
 # Numbered street photographs support flat outer ends. Connector-facing V recesses are the explicitly provisional multi-view interpretation.
 outer=-1 if i==0 else 1
 crease=-outer
 for j,a in enumerate(pts):
  ring.append(a)
  b=pts[(j+1)%len(pts)]
  if abs(a[0]-b[0])<1 and abs(a[1]-b[1])>14 and (a[0]*crease)>20:
   for f in [.25,.5,.75]:
    ring.append([a[0]+(b[0]-a[0])*f-crease*(3.5 if f!=.5 else 0),a[1]+(b[1]-a[1])*f])
 poly=Polygon(ring)
 if not poly.exterior.is_ccw:ring=list(reversed(ring));poly=Polygon(ring)
 heights=[86.2,94.5,103.2,112.25,103.2,94.5,86.2] if i==0 else [87.1,95.1,103.7,112.25,103.7,95.1,87.1]
 cuts=[-30,-16.5,-12.2,-7.5,7.5,12.2,16.5,30];parts=[]
 for k,(v0,v1) in enumerate(zip(cuts,cuts[1:])):
  q=poly.intersection(box(-100,v0,100,v1));rr=list(q.exterior.coords)[:-1]
  if not q.exterior.is_ccw:rr=list(reversed(rr))
  roofq=scale(scale(q,xfact=1,yfact=100,origin=(0,0)).buffer(-.85,join_style=2),xfact=1,yfact=.01,origin=(0,0));roofrr=list(roofq.exterior.coords)[:-1]
  if not roofq.exterior.is_ccw:roofrr.reverse()
  lines=[]
  for uu in [z*2.6 for z in range(-11,12)]:
   line=roofq.intersection(LineString([(uu,-40),(uu,40)]))
   if line.geom_type=='LineString' and line.length>.1:lines.append(list(line.coords))
  for frac in [.32,.66]:
   vv=roofq.bounds[1]+(roofq.bounds[3]-roofq.bounds[1])*frac;line=roofq.intersection(LineString([(-40,vv),(40,vv)]))
   if line.geom_type=='LineString' and line.length>.1:lines.append(list(line.coords))
  parts.append({'roofPolygon':roofrr,'roofInsetM':.85,'roofGlazingLines':lines,'name':['SW low terrace','SW middle terrace','SW upper terrace','central high body','NE upper terrace','NE middle terrace','NE low terrace'][k],'polygon':rr,'vRange':[v0,v1],'heightM':heights[k],'slopeRiseM':0 if k==3 else heights[k+1 if k<3 else k-1]-heights[k],'index':k})
 T.append({'number':str(101+i),'id':f'bespoke-lotte-castle-ivy-{101+i}','anchor':dict(zip(['lon','lat'],src['anchor'])),'footprintId':src['id'],'outerSign':outer,'creaseSign':crease,'originalRing':pts,'ring':ring,'parts':parts,'highRoofM':112.25,'crownRiseM':5.3 if i==0 else 5.0,'floorIntervalM':(112.25-8)/33,'heightBasis':'112.25m is the single compound register datum, not independently measured per tower. Applying it to both main high roofs is a conservative shared-envelope interpretation; stepped wings and additional pitched crown are estimated from photographs.'})
R={'siteId':'lotte-castle-ivy','managementCode':'A15088915','residentialHouseholds':445,'residentialTowerCount':2,'siteCenter':[126.9317762,37.52018955],'planAxes':{'uEastNorth':[.626,-.780],'vEastNorth':[.780,.626],'meaning':'u=101 northwest to102 southeast; v=NE international finance road, -v=SW Yeouidaebang69-gil','basis':'Architect north arrow/35m roads/12m road paired with original OSM footprints; photo appraisal labels101/102 on SW street. No claim of surveyed architectural plan georeference.'},'towers':T,'connector':{'id':'bespoke-lotte-castle-ivy-connector','anchor':dict(zip(['lon','lat'],S[2]['anchor'])),'ring':S[2]['planUV'],'podiumRing':S[3]['planUV'],'footprintIds':[S[2]['id'],S[3]['id']],'heightM':30,'podiumHeightM':8,'heightBasis':'OSM source-reported30m/min_height8m, roughly8storey connector supported visually; not independently measured register height.'},'sources':[{'url':'https://choeshincm.com/residential/?bmode=view&idx=167044842','observations':['Design site plan andCG, not completed photographs. Used only orientation and component arrangement.']},{'url':'https://kbland.kr/se/otd/1238381','observations':['Photographer2024 completed facade shows V creases, vertical louvers and stepped glazed crown. Exact tower/face identity unresolved; inner-end assignment is a multi-view interpretation rather than photo-confirmed orientation.']},{'url':'https://www.redauction.co.kr/gam/000212/2014/000212_20140130000564.pdf','observations':['Original appraiser-authored report onthird-party mirror, p16photos label101 foreground102 rear; SW longface broad glazing/stepped roof. Household typo not used.']},{'url':'https://realty.chosun.com/site/data/html_dir/2026/09/07/2026090702660.html','observations':['Completed frontal photograph of central connector and glass retail podium; publication2026, capturedateunknown.']},{'url':'https://www.seantecs.co.kr/en/project/project.aspx?CODE=pm','observations':['Operator-labeled image is excluded as identity evidence: Empire/Ivy labeling conflicts with photographed signs.']},{'url':'https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do','observations':['Exact parcel43-4 register102017214:445households,35F/B6,112.25m compound, approved2005-12-30.']},{'url':'https://openapt.seoul.go.kr/commonPortal/programLink.do?aptCode=A15088915&codParams=&jspNm=%2FopenApt%2FdMenu%2FdangiInfo%2FdangiInfo.open&tr_code=sweb','observations':['Official445apartmenthouseholds/two residentialtowers; office units not summed.']}],'uncertainties':['No measured individual tower roof elevation;112.25m shared compound datum applied to mainbody only, crown+5.0–5.3m photo estimate.','Wing step elevations, slope angles, .85m end-face roof setback, facade dimensions and occluded reverse surfaces manually estimated.', '101 NW end is flat in numbered appraiser/KB2023 street photographs. KB2024 V face cannot yet be securely assigned to a tower; assigning it to the inner connector-facing ends remains an explicitly provisional interpretation, not photograph-confirmed orientation.','Unseen roofequipment and CG-only antenna not added.','Podium simplified to original8mfootprint; storefront tenants/signage and undergroundlevel interiors omitted.','No claim that every2026alteration is reflected; actual source photos2014/2024 and unknown capture2026publication.'],'coverage':{'managementCode':'A15088915','households':445,'expectedResidentialBuildings':['101','102'],'residentialAssets':[x['id'] for x in T],'nonResidentialComponents':['low central connector','8mcommonretailpodium'],'sourceFootprintCount':4,'legacyFootprintCount':3,'note':'Existing three legacyfootprints aretwo towers plusconnector, notthree residentialtowers; new exactraw8mpodium footprint separatelyclaimed. Completeonlyresidentialexterior scope afterindependentreview.'}}
pd=Polygon(R['connector']['podiumRing']);notched=pd.difference(box(-5.2,20.5,5.2,40));R['connector']['recessedGroundRing']=list(notched.exterior.coords)[:-1]
(OUT/'recipe.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n')
