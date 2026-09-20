"""Tower Palace only. Named OSM geometry + manually interpreted SAMOO/SWA forms.

Use the repository .venv Python. No network request or automatic city template.
Committed modelling inputs are preferred when the ignored stage is absent.
"""
from pathlib import Path
import json, math
import numpy as np
from shapely.geometry import Polygon, mapping
from shapely import affinity

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/tower-palace';OUT.mkdir(parents=True,exist_ok=True)
def input_json(name):
 p=OUT/name
 if not p.exists():p=ROOT/'modeling/bespoke/tower-palace'/name
 return json.loads(p.read_text())
sources=input_json('claimed-source-buildings.json')
ORIGIN=[127.0540,37.48845]
SX=111319.49079327358*math.cos(math.radians(ORIGIN[1]));SY=111319.49079327358
def en(p):return [(p[0]-ORIGIN[0])*SX,(p[1]-ORIGIN[1])*SY]
def planar(poly):return Polygon([en(p) for p in poly['coordinates'][0]])
def coords(poly):return [[round(x,5),round(y,5)] for x,y in poly.exterior.coords[:-1]]

# Label centres read directly from the original 445x311 SWA embedded plan.
# Fit is topology verification, NOT a replacement for the independent anchors.
PX={'A':[334,178],'B':[263,215],'C':[198,254],'D':[154,177],
    'E':[271,65],'F':[376,66],'G':[57,231]}
M=np.linalg.lstsq(np.array([PX[b['tower']]+[1] for b in sources]),np.array([en(b['coordinate']) for b in sources]),rcond=None)[0]
records=[]
for s in sources:
 n=s['tower']; centre=en(s['coordinate']);p=affinity.translate(planar(s['geometry']),-centre[0],-centre[1]);H=s['primaryDatabaseHeightM']
 b={'id':'bespoke-tower-palace-'+n.lower(),'tower':n,'phase':s['phase'],'nameKo':'타워팰리스 '+n+'동',
    'coordinate':dict(zip(['lon','lat'],s['coordinate'])),'siteEN':centre,'footprintIds':[s['footprintId']],
    'supersedes':['reference-flight-tower-palace']+s['legacyAssetOwners'],'heightM':H,'floors':s['localSourceFloors'],
    'heightBasis':'CTBUH/CVU named complex table, architectural top. A/C209m and D153m conflict with OSM211/154m; CTBUH preferred, no datum reconciliation claimed.',
    'floorsBasis':'SAMOO phase I59/66/42, phase II55, phase III69; older III73-storey descriptions use unresolved different counting.',
    'sourceFootprint':coords(p),'sourceRecordId':s['sourceRecordId'],
    'referenceUrl':'https://www.samoo.com/home/works/view.do?cntntsSn='+{'I':'59','II':'60','III':'61'}[s['phase']],
    'uncertainties':['Named OSM outline/centroid is not a cadastral or measured as-built survey.','Window mullion sizes, vertical storey interpolation, unseen faces and roof equipment are manual photographic estimates.','Official photographs do not state capture date; buildings completed2002/2003/2004 respectively.']}
 if n in 'ABCD':
  # Four independently named rectangles, preserving measured orientation/size.
  q=list(p.exterior.coords)[:-1];v=np.array(q[1])-q[0]
  yaw=math.degrees(math.atan2(v[1],v[0]))
  # Align the long photo window bank approximately ENE, not whichever OSM
  # polygon happened to start first. Width/depth remain specific to each tower.
  while yaw>75:yaw-=90
  while yaw<-15:yaw+=90
  local=affinity.rotate(p,-yaw,origin=(0,0));x0,y0,x1,y1=local.bounds
  b.update(yawDeg=yaw,widthM=x1-x0,depthM=y1-y0,mainTopM=H-{'A':24,'B':25,'C':24,'D':20}[n],
           penthouseTopM=H-2.0,penthouseWidthRatio={'A':.75,'B':.77,'C':.74,'D':.76}[n],
           penthouseDepthRatio={'A':.74,'B':.72,'C':.74,'D':.77}[n],
           mechanicalBandCentreM={'A':105,'B':119,'C':105,'D':76}[n],
           mechanicalBandHeightM=4.1 if n!='D' else 3.8,
           featureBasis='SAMOO59 seq3/4/5: rectangular banked-window body, interrupted open middle belt with large piers, recessed occupied penthouse and flat cornice. No mast or cone.',
           photoAssignments={'primary':'https://www.samoo.com/home/works/content/download.do?seq=4&cntntsSn=59',
              'roof':'https://www.samoo.com/home/works/content/download.do?seq=5&cntntsSn=59'},
           faceBankDivisions=[6,5,6,5] if n!='D' else [5,6,5,6])
  b['courtyardSlotFace']={'A':'west','B':'west','C':'north','D':'east'}[n]
  b['centralSlotWidthM']={'A':6.8,'B':7.1,'C':6.9,'D':8.0}[n]
  b['centralPierWidthM']={'A':1.20,'B':1.35,'C':1.25,'D':2.10}[n]
  b['courtyardFaceBasis']='SAMOO59 seq3 low-angle courtyard photograph contrasted with seq4 outer faces; SWA labelled central courtyard and named-source positions interpreted as A/B WSW, C NNW, D ENE. Face registration is manual and not independently surveyed.'
  b['uncertainties'].append(b['courtyardFaceBasis'])
  b['uncertainties'].append('Mid-height open-belt datum is photograph-proportion estimated; exact floor number is not asserted from a primary register.')
 elif n in 'EF':
  # Manual angular roof/wing decomposition. E/F share the actual architectural
  # family, but each polygon is fitted into its own independently named outline.
  local=affinity.rotate(p,-29,origin=(0,0));x0,y0,x1,y1=local.bounds
  # The SWA plan and SAMOO completed photos show angular recesses, not rounded
  # bows. These explicit roof-height regions are photographic interpretations.
  raw=[('central_reentrant_spine',[(-9,-24),(9,-24),(9,24),(-9,24)],181.0),
       ('south_east_shoulder',[(0,-40),(21,-20),(21,-1),(9,-1),(9,-21),(-1,-25)],171.0),
       ('south_west_shoulder',[(0,-40),(-21,-20),(-21,-1),(-9,-1),(-9,-21),(1,-25)],151.0),
       ('north_east_shoulder',[(0,40),(21,20),(21,1),(9,1),(9,21),(-1,25)],158.0),
       ('north_west_shoulder',[(0,40),(-21,20),(-21,1),(-9,1),(-9,21),(1,25)],174.0)]
  wings=[]
  for name,points,h in raw:
   # Slight recenter/width changes follow each retained source footprint.
   poly=Polygon([(x*(x1-x0)/45,y*(y1-y0)/85) for x,y in points]).intersection(local.buffer(-.18))
   if poly.geom_type!='Polygon':raise ValueError('Disconnected E/F authored wing')
   wings.append({'name':name,'polygon':coords(poly),'topM':h+(0 if n=='E' else {'central_reentrant_spine':0,'south_east_shoulder':-1.5,'south_west_shoulder':1,'north_east_shoulder':-1,'north_west_shoulder':1.5}[name])})
  b.update(yawDeg=29,wings=wings,coreCrownTopM=191,featureBasis='SAMOO60 seq3/9: broad white horizontal spandrels, angular indented wings, staggered shoulders, triangular open roof frames, two longitudinal arch ribs at tallest roof.',
           photoAssignments={'primary':'https://www.samoo.com/home/works/content/download.do?seq=3&cntntsSn=60','full':'https://www.samoo.com/home/works/content/download.do?seq=9&cntntsSn=60'},
           roofWingHeightsBasis='Photographic relative proportions; geodetic assignment of partly hidden E/F roof faces remains uncertain. Total191m is CTBUH; individual shoulder heights are not measured.')
  b['uncertainties'].append(b['roofWingHeightsBasis'])
  b['crownScreenOpenings']={'basis':'SAMOO60 seq3 and SAMOO59 seq4 show upper-corner dark rectangular opening with blue glazed band below; adjacent narrow return is glazed below. Only these observed breaks are authored.', 'authoredFace':'local west screen toward north end, plus north return; geographic assignment interpreted from plan/photo, not a surveyed elevation', 'reverseFace':'Unobserved reverse retained mostly solid; no replicated openings.'}
 else:
  # Partition the actual serrated Y-shaped OSM ring into three radial wings.
  # Unlike an oval cylinder this preserves each stepped bay and the re-entrant
  # valleys. Top datum per lobe is interpreted from SAMOO61 seq3/4/11.
  sectors=[('southeast_tall_blade',-68,264),('northeast_second_blade',53,253),('west_lower_blade',174,218)]
  wings=[]
  for wi,(name,ang,h) in enumerate(sectors):
   before=sectors[wi-1][1]-(360 if wi==0 else 0)
   after=sectors[(wi+1)%3][1]+(360 if wi==2 else 0)
   a0=math.radians((before+ang)/2);a1=math.radians((ang+after)/2)
   poly=p.intersection(Polygon([(0,0),(200*math.cos(a0),200*math.sin(a0)),(200*math.cos(a1),200*math.sin(a1))]))
   if poly.geom_type!='Polygon':raise ValueError('G wing partition failed')
   wings.append({'name':name,'polygon':coords(poly),'topM':h,'axisDeg':ang})
  b.update(yawDeg=0,wings=wings,featureBasis='SAMOO61 explicit three-bladed Y description and seq3/4/5/11 completed photos; separate unequal blades, white vertical fins, deep louver returns, blue curtain wall; no conical spire.',
           photoAssignments={'upper':'https://www.samoo.com/home/works/content/download.do?seq=3&cntntsSn=61','whole':'https://www.samoo.com/home/works/content/download.do?seq=11&cntntsSn=61','entrance':'https://www.samoo.com/home/works/content/download.do?seq=6&cntntsSn=61'})
  b['uncertainties'].append('G secondary wing tops253/218m and orientation of unseen upper returns are photographic estimates, not official measured per-wing heights. Detailed OSM plan is retained but may include lower-level projections.')
 records.append(b)
obs=input_json('source-observations.json')
recipe={'siteId':'tower-palace','origin':ORIGIN,'buildings':records,'sources':[{'url':s['url'],'observations':s.get('confirmed',s.get('caution',''))} for s in obs['sources']],
 'planVerification':{'url':'https://swacdn.s3.amazonaws.com/1/988ea28b_towerpalace.pdf','embeddedImageSize':[445,311],
 'method':'Seven explicitly lettered tower centres on SWA landscape plan; affine alignment to independent OSM centres verifies phase topology only. No survey accuracy claimed.',
 'pixelToEN':M.tolist(),'controlPoints':[{'tower':s['tower'],'pixel':PX[s['tower']],'coordinate':s['coordinate'],'residualM':float(np.linalg.norm(np.array(PX[s['tower']]+[1])@M-np.array(en(s['coordinate']))))} for s in sources]},
 'retainedUntouchedSourceFootprintIds':[], 'excludeFromOwnership':['Adjacent phaseIII sports centre','Shared phaseI/II streetmall and landscape podium','Public roads between the three blocks'],
 'sourcePhotoRedistribution':'None: externally linked observations only; no photos embedded in blend or GLB.'}
(OUT/'recipe-input.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'siteId':recipe['siteId'],'towers':[{k:b[k] for k in ['tower','heightM','floors']} for b in records], 'planResidualsM':[round(c['residualM'],2) for c in recipe['planVerification']['controlPoints']]},indent=2))
