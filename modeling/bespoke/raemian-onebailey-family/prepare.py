import json,math
from pathlib import Path
P=Path(__file__).resolve().parent
rows=json.loads((P/'numbered-source-mapping.json').read_text());ang=math.radians(28.2);c,s=math.cos(ang),math.sin(ang);towers=[]
for no in [101,102,121,122,123]:
 t=next(x for x in rows if x['number']==no);lon,lat=t['coordinate'];q=[]
 for x,y in t['geometry']['coordinates'][0][:-1]:
  e=(x-lon)*111320*math.cos(math.radians(lat));n=(y-lat)*111320;q.append([e*c+n*s,-e*s+n*c])
 a=dict(t);a['localProfileUV']=q;a['id']=f'bespoke-raemian-onebailey-{no}';a['angleDeg']=28.2;a['parts']=[]
 if no==101:
  a['parts']=[{'kind':'skyTower','bounds':[-9.62,-24.85,21.13,9.25],'height':109.7,'void':[50.7,56.8],'name':'ONE BAILEY'},{'kind':'lowWing','bounds':[-31.29,14.05,-1.28,27.07],'height':42.1,'floors':13,'whiteSide':'east'},{'kind':'lowWing','bounds':[-9.54,9.20,-1.28,14.1],'height':42.1,'floors':13,'whiteSide':'east'}]
 elif no==121:a['parts']=[{'kind':'skyTower','bounds':[-15.91,-16.84,15.91,16.84],'height':109.35,'void':[50.35,56.45],'name':'RAEMIAN'}]
 elif no==102:a['parts']=[{'kind':'lowWing','bounds':[-11.78,-33.2,-.8,18.95],'height':44.7,'floors':14,'whiteSide':'west'},{'kind':'lowWing','bounds':[-.8,7.95,23.3,18.95],'height':38.6,'floors':12,'whiteSide':'east'}]
 elif no==122:a['parts']=[{'kind':'lowWing','bounds':[1.27,-31.7,11.5,21.15],'height':56.9,'floors':18,'whiteSide':'east'},{'kind':'lowWing','bounds':[-27,10.95,1.27,21.10],'height':44.7,'floors':14,'whiteSide':'west'}]
 elif no==123:a['parts']=[{'kind':'lowWing','bounds':[-11.9,-30.8,2.65,20.5],'height':56.9,'floors':18,'whiteSide':'west'},{'kind':'lowWing','bounds':[2.65,9.3,24.4,20.5],'height':47.75,'floors':15,'whiteSide':'east'}]
 towers.append(a)
for a,peer,floor in [(towers[0],towers[1],9),(towers[4],towers[3],11)]:
 lon,lat=a['coordinate'];x,y=peer['coordinate'];e=(x-lon)*111320*math.cos(math.radians(lat));n=(y-lat)*111320;du=e*c+n*s;dv=-e*s+n*c
 if a['number']==101:bounds=[du+14.0,20.5,-20,27.8]
 else:bounds=[14.0,13.8,du-17,21.35]
 a['bridge']={'peer':peer['number'],'bounds':bounds,'floor':floor,'bottom':3.5+(floor-1)*3.05,'height':6.1,'basis':'Official1019F/12311F; registerskycommunityheight6.1m. Elevationaboveground estimatedfromfloorheight, notsurveyed.'}
R={'siteId':'raemian-onebailey-north-first5','siteCenter':[126.9974,37.50818],'angleDeg':28.2,'towers':towers,'coverage':{'modeledNumbers':[101,102,121,122,123],'modeledResidentialCount':5,'officialResidentialCount':23,'officialHouseholds':2990,'notYetModeled':[i for i in range(101,124) if i not in [101,102,121,122,123]],'bridges':[[101,102],[123,122]],'note':'Firstnorthwaterfront5of23 only; notwholecomplexcomplete.'},'sources':[{'url':'https://ratiodesign.com/project/raemian-one-bailey/','observations':'Completedphotos: northdualskytowers101/121 darkreflectivewrappedfacade, setbackcrownandlargeintermediaterecess; lowLwingsdifferentnavy/whitefacades; enclosedskyloungeswiththickmetalbandsanddiagonalinternalbracing.'},{'url':'https://raemian.co.kr/community/times/raemianHomeStyling/view.do?pg=1&searchStr=&searchType=&seq=98','observations':'Officialcompletedtour2023-09-26:23buildings2990households; skycommunity1019F/12311F. Photosactualbuilt, notCG.'},{'url':'https://www.raemian.co.kr/sales/sub/s/onebailey?menuSeq=9573','observations':'Officialnumberedplan corroboratesall23sourceidentitiesandtwoindependentbridgepairs.'},{'url':'https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do','observations':'ExactparcelBanpodong1/0 andBanpodaero333, all23registerrows withheights/floors/householdssum2990. Statutoryroofdatumunspecified.'}], 'uncertainties':['Individualwingheights andbigskyTowerintermediatevoidlevels are completedphoto-proportioninterpretations; onlyper-buildingmaxheight/floors fromofficialregister.','OSMfootprints anchor buildings; officialnumberedplan andphotosguidesteppedindividualparts. SubmetreCADaccuracy notclaimed.','Opaque/reflectiveglasssimplified withauthoredgeometry, nooriginalphotos embedded; invisiblebackfacades conservativereconstruction.','Bridge flooridentities official; abovegroundmetrelevel inferredusing3.05m typicalstoreyand3.5m grounddatum.','Sourcephotoscopyrightreferenceonly; notredistributedtextures.']}
(P/'recipe.json').write_text(json.dumps(R,ensure_ascii=False,indent=2))
# Partition the verified source outline into authored height wings without filling its notches.
from shapely.geometry import Polygon,box
from shapely.geometry.polygon import orient
for t in R['towers']:
 p=Polygon(t['localProfileUV'])
 if t['number']==101:
  high=p.intersection(box(-9.62,-100,100,9.28));low=p.difference(high)
  t['parts']=[dict(t['parts'][0],profile=list(orient(high,1).exterior.coords)[:-1]),dict(t['parts'][1],profile=list(orient(low,1).exterior.coords)[:-1],bounds=list(low.bounds))]
 elif t['number']==121:t['parts'][0]['profile']=list(orient(p,1).exterior.coords)[:-1]
 else:
  if t['number']==102:high=p.intersection(box(-100,-100,-.45,100))
  elif t['number']==122:high=p.difference(box(-100,10.92,1.27,100))
  else:high=p.intersection(box(-100,-100,2.60,100))
  low=p.difference(high)
  if low.geom_type=='MultiPolygon':low=max(low.geoms,key=lambda g:g.area);high=p.difference(low)
  for part,q in zip(t['parts'],[high,low]):part['profile']=list(orient(q,1).exterior.coords)[:-1];part['bounds']=list(q.bounds)
R['uncertainties'].append('Only the first five waterfront residential buildings are reconstructed. Eighteen other buildings, overall landscaping, later phase roof-glass boxes and whole-site ancillary coverage are not completed by this bundle.')
(P/'recipe.json').write_text(json.dumps(R,ensure_ascii=False,indent=2))
R['sources'][0]['observations']='Architect completed photographs: distinct forward grey tower spine, unequal lower side-wing roofs, mixed-width windows and small service-window column; three middle-gallery openings and lower vertical recess. Riverfront photo identifies ONEBAILEY on101 and RAEMIAN on121.'
R['sources'].append({'url':'https://www.raemian.co.kr/upload/editor/image/images/000265/kinetic_field__0452.jpg','observations':'Official completed photograph explicitly shows 101 and102 numbers, glazed lounge supports and a separate low open connecting passage. Central inner roof admits daylight.'})
R['sources'].append({'url':'https://www.raemian.co.kr/upload/editor/image/images/000265/_C6A3965.jpg','observations':'Official completed photograph explicitly shows123 on Luminary Hill side, its skybridge support and the low open connector. Paired official _C6A3839.jpg shows the opposite support.'})
R['uncertainties'].append('Low open connecting passages are verified in both numbered official photographs; modeled deck elevation6.6m, span depth2.7m and height2.6m are proportion estimates, not surveyed levels. RATIO unnamed inner-lounge photograph is not alone used for exact building identity.')
R['uncertainties'].append('High tower roofs are unequal side wings and a forward main spine, as seen in the completed riverfront crop. Reverse roof depths and small equipment details remain unverified; not a measured CAD reconstruction.')
(P/'recipe.json').write_text(json.dumps(R,ensure_ascii=False,indent=2))
