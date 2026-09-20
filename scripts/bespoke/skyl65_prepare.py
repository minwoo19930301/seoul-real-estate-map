"""SKY-L65 only: hand-traced official plan, independently anchored A/B/C/D.

Run with repo .venv Python. Reference photographs stay outside published assets.
This is an illustrative reconstruction, not a measured as-built survey.
"""
import json, math
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon, shape, mapping
from shapely.ops import unary_union
from shapely import affinity

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/model-source/bespoke/skyl65'
OUT.mkdir(parents=True, exist_ok=True)
source_path=OUT/'claimed-source-buildings.json'
if not source_path.exists():source_path=ROOT/'modeling/bespoke/skyl65/claimed-source-buildings.json'
sources = json.loads(source_path.read_text())
if not (OUT/'claimed-source-buildings.json').exists():
 (OUT/'claimed-source-buildings.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
ORIGIN = [127.0453, 37.579]
SX = 111319.49079327358 * math.cos(math.radians(ORIGIN[1]))
SY = 111319.49079327358
def en(pt): return [(pt[0]-ORIGIN[0])*SX, (pt[1]-ORIGIN[1])*SY]
def geographic(pt): return [ORIGIN[0]+pt[0]/SX, ORIGIN[1]+pt[1]/SY]

# Pixel coordinates refer to the official 1100x832 site plan, downloaded
# 2026-09-20 from 202206170824559250.jpg. Six coloured dwelling wings and
# the central circulation core are traced separately, never nearest-building clones.
# Crop coordinates are retained so each manual vertex can be reviewed visually.
TRACES = {
 'A': {'crop':[540,390,6], 'core':[(400,307),(485,287),(624,369),(632,447),(537,604),(450,655),(287,566),(334,452)], 'wings':[
 [(643,240),(760,270),(813,233),(848,282),(829,303),(866,355),(709,443),(677,461),(647,444),(620,373),(633,355),(617,341)],
 [(633,450),(701,445),(747,532),(777,523),(801,602),(735,626),(710,678),(547,601),(599,484)],
 [(433,611),(480,625),(513,642),(492,676),(524,702),(495,741),(514,754),(447,837),(369,797),(381,766),(341,747),(397,662),(418,675)],
 [(178,523),(205,537),(233,491),(269,466),(317,490),(308,522),(342,544),(314,589),(284,573),(257,623),(398,700),(369,746),(219,674),(213,699),(142,658),(179,603),(146,585)],
 [(193,244),(248,239),(258,259),(371,246),(370,295),(398,320),(315,460),(265,437),(151,351),(188,301)],
 [(387,77),(456,78),(455,57),(515,57),(515,95),(501,114),(585,179),(495,268),(474,252),(440,283),(374,295)]
 ]},
 'B': {'crop':[423,260,5], 'core':[(296,303),(360,294),(477,368),(500,416),(403,543),(328,563),(224,453)], 'wings':[
 [(545,191),(566,194),(564,214),(632,239),(598,382),(569,376),(552,418),(524,421),(498,382),(493,349),(477,344)],
 [(505,420),(551,422),(588,508),(615,498),(638,555),(580,575),(556,617),(410,545)],
 [(325,550),(351,566),(370,552),(411,576),(399,598),(430,622),(414,651),(432,673),(391,711),(368,699),(335,751),(274,716),(289,691),(259,674),(302,604),(320,612)],
 [(164,454),(196,473),(210,465),(250,487),(241,508),(274,521),(245,559),(218,547),(207,570),(306,628),(280,679),(139,626),(130,644),(86,607),(117,552),(92,542),(134,481),(146,489)],
 [(130,253),(184,248),(190,265),(275,259),(293,294),(287,322),(229,433),(191,406),(111,337),(143,301)],
 [(295,206),(396,103),(446,144),(459,128),(484,156),(460,205),(396,278),(372,265),(359,284),(338,270),(323,284),(311,271),(281,279),(307,230)]
 ]},
 'C': {'crop':[256,231,5], 'core':[(273,321),(328,302),(445,371),(448,423),(367,552),(286,603),(182,519),(210,430)], 'wings':[
 [(480,261),(558,285),(598,258),(623,288),(608,311),(642,351),(522,423),(485,443),(470,425),(452,376),(464,354),(450,343)],
 [(485,443),(521,423),(547,500),(571,491),(591,559),(541,579),(521,624),(373,560)],
 [(281,567),(308,582),(330,563),(368,584),(353,607),(381,631),(365,654),(389,677),(348,720),(330,706),(299,754),(248,722),(262,697),(228,678),(266,613),(284,624)],
 [(126,461),(151,474),(172,466),(211,490),(199,512),(229,529),(207,565),(183,551),(169,574),(269,629),(244,677),(113,629),(104,645),(49,615),(83,563),(58,548),(98,488),(110,495)],
 [(80,256),(132,249),(144,278),(240,267),(239,301),(261,322),(250,342),(226,345),(231,368),(209,375),(202,348),(188,351),(204,415),(160,423),(153,387),(97,398)],
 [(249,124),(308,126),(310,108),(358,109),(355,137),(345,153),(420,207),(343,289),(324,276),(303,295),(243,306)]
 ]},
 'D': {'crop':[106,319,5], 'core':[(291,277),(339,264),(468,343),(477,388),(410,511),(294,569),(217,495),(231,397)], 'wings':[
 [(501,219),(589,244),(627,215),(651,252),(631,270),(672,318),(550,383),(516,402),(500,386),(476,334),(489,312),(473,304)],
 [(514,401),(549,384),(578,466),(605,457),(628,522),(567,544),(549,583),(409,511)],
 [(324,530),(347,543),(369,528),(405,550),(391,575),(416,591),(400,622),(419,642),(378,692),(356,677),(332,722),(271,761),(227,716),(247,677),(202,654),(270,573),(296,586)],
 [(184,424),(226,443),(216,472),(247,493),(219,529),(192,517),(177,540),(284,600),(254,654),(146,601),(114,638),(55,600),(85,552),(60,540),(97,480),(118,493),(155,441),(168,451)],
 [(119,218),(164,213),(174,233),(268,220),(267,261),(290,284),(225,390),(181,368),(95,303),(125,267)],
 [(282,69),(339,70),(340,56),(390,57),(384,93),(376,107),(436,169),(367,242),(349,230),(327,253),(271,265)]
 ]}
}

control_px={'A':[618,474],'B':[491,350],'C':[318,324],'D':[175,400]}
source_by_name={r['name'][0]:r for r in sources if r['name'] in ['A동','B동','C동','D동']}
anchors={n:en(shape(source_by_name[n]['geometry']).centroid.coords[0]) for n in 'ABCD'}
mat=np.linalg.lstsq(np.array([control_px[n]+[1] for n in 'ABCD']),np.array([anchors[n] for n in 'ABCD']),rcond=None)[0]
result={'site':'청량리역 롯데캐슬 SKY-L65','authoring':'hand-traced official plan and completed July 2023 photographs; site-specific Blender MCP construction',
 'replacesReferenceId':'reference-flight-cheongnyangni-skyl65', 'origin':ORIGIN,'planUrl':'https://www.lottecastle.co.kr/files/etc/2022/6/202206170824559250.jpg',
 'floorChartUrl':'https://www.lottecastle.co.kr/files/etc/2022/6/202206170824566590.jpg',
 'photoUrls':['https://www.lottecastle.co.kr/files/etc/2023/7/202307270158028590.jpg','https://www.lottecastle.co.kr/files/etc/2023/7/202307270158028592.jpg','https://www.lottecastle.co.kr/files/etc/2023/7/202307270158028591.jpg'],
 'georeference':{'method':'four corresponding official-plan core points and named OSM source polygon centroids, affine fit; each final tower separately recentred on its source centroid','pixelToEN':mat.tolist(),'controls':[{'tower':n,'pixel':control_px[n],'sourceCentroid':geographic(anchors[n]),'affineResidualM':float(np.linalg.norm(np.array(control_px[n]+[1])@mat-np.array(anchors[n])))} for n in 'ABCD'],'limitations':'OSM polygons are not survey control; plan perspective/diagram and source geometry differ. Local dimensions and offsets remain unsurveyed.'},'buildings':[]}
for n in 'ABCD':
 t=TRACES[n]; ox,oy,s=t['crop']
 def trace(points):
  return Polygon([np.array([ox+x/s,oy+y/s,1])@mat for x,y in points]).buffer(0)
 wings=[trace(w) for w in t['wings']]; core=trace(t['core'])
 # Thin white separating strokes on the brochure are not outdoor voids.
 # Bridge only these central circulation seams; never convex-hull the six arms.
 core_seam=0
 for seam in [0,.35,.7,1.1,1.5,2,2.5,3]:
  candidate=core.buffer(seam,join_style=2)
  hull=unary_union([candidate]+wings).buffer(.12).buffer(-.12)
  if hull.geom_type=='Polygon':core=candidate;core_seam=seam;break
 if hull.geom_type!='Polygon':raise ValueError(f'{n}: disconnected manual trace needs review')
 centre=hull.centroid
 def local(poly):return mapping(affinity.translate(poly,xoff=-centre.x,yoff=-centre.y))
 src=source_by_name[n]; source_polygon=Polygon([en(p) for p in src['geometry']['coordinates'][0]])
 shifted=affinity.translate(hull,xoff=anchors[n][0]-centre.x,yoff=anchors[n][1]-centre.y)
 floor={'A':64,'B':65,'C':63,'D':65}[n]
 result['buildings'].append({'id':'bespoke-skyl65-'+n.lower(),'nameKo':'청량리역 롯데캐슬 SKY-L65 '+n+'동','tower':n,
  'coordinate':dict(zip(['lon','lat'],geographic(anchors[n]))),'siteEN':anchors[n], 'footprintIds':[src['id']], 'floors':floor,'refugeFloors':[23,44] if n=='A' else [24,45],
  'heightM':{'A':196,'B':199,'C':193,'D':199}[n], 'heightBasis':'B/D use OSM 199m recorded height; A/C reduced by estimated 3m per differing official storey. Height includes illustrative crown. No measured as-built heights.',
  'sourceHeightM':src['height_m'],'sourceFloors':src['num_floors'],'floorsBasis':'official dated 2022-06-17 dong/unit chart, source OSM all65 superseded',
  'footprint':local(hull),'core':local(core),'wings':[local(w) for w in wings],
  'sourceFootprintOverlapIoU':shifted.intersection(source_polygon).area/shifted.union(source_polygon).area,
  'tracedPlanPixels':t, 'centralSeamClosureM':core_seam, 'floorplanAccuracy':'Manual diagram trace; OSM-centroid anchored, not cadastral or architectural measurement.'})
(OUT/'recipe-input.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'towers':[{k:b[k] for k in ['tower','coordinate','floors','sourceFootprintOverlapIoU']} for b in result['buildings']],'controlResidualsM':[c['affineResidualM'] for c in result['georeference']['controls']]},ensure_ascii=False,indent=2))
