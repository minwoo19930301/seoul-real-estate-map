"""Prepare the three named Hyperion locations and the photograph-based L podium.

No architectural plan has been traced: source rectangles locate the towers and
site-specific recess/crown recipes interpret two primary-source photographs.
"""
import json,math
from pathlib import Path
from shapely.geometry import Polygon,LineString,mapping
from shapely.ops import unary_union
from shapely import affinity
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/hyperion';OUT.mkdir(parents=True,exist_ok=True)
srcfile=OUT/'claimed-source-buildings.json'
if not srcfile.exists():srcfile=ROOT/'modeling/bespoke/hyperion/claimed-source-buildings.json'
sources=json.loads(srcfile.read_text())
if not (OUT/'claimed-source-buildings.json').exists():(OUT/'claimed-source-buildings.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
origin=[126.87497,37.52697];sx=111319.490793*math.cos(math.radians(origin[1]));sy=111319.490793
def en(p):return [(p[0]-origin[0])*sx,(p[1]-origin[1])*sy]
def geo(p):return [origin[0]+p[0]/sx,origin[1]+p[1]/sy]
physical={'A':{'heightM':256,'floors':69,'beltFloors':[9,32,50],'crownHeightM':17.0,'crownWidthM':20.0,'spineWidthM':10.4,'cornerCutM':3.8},
 'B':{'heightM':216,'floors':59,'beltFloors':[9,32],'crownHeightM':16.0,'crownWidthM':17.8,'spineWidthM':11.4,'cornerCutM':3.1},
 'C':{'heightM':201.2,'floors':54,'beltFloors':[9,32],'crownHeightM':15.2,'crownWidthM':18.4,'spineWidthM':9.3,'cornerCutM':3.6}}
buildings=[];polys={};centers={}
for n in 'ABC':
 s=next(r for r in sources if r['name']=='목동 하이페리온 '+n);p=Polygon([en(v) for v in s['geometry']['coordinates'][0]]);c=p.centroid;centers[n]=[c.x,c.y];polys[n]=p
 q=list(p.minimum_rotated_rectangle.exterior.coords)[:-1];edges=[(math.dist(a,b),math.atan2(b[1]-a[1],b[0]-a[0])) for a,b in zip(q,q[1:]+q[:1])]
 angle=min([a for l,a in edges],key=lambda a:abs((a+math.pi/2)%math.pi-math.pi/2));angle=(angle+math.pi/2)%math.pi-math.pi/2
 local=affinity.rotate(affinity.translate(p,xoff=-c.x,yoff=-c.y),-math.degrees(angle),origin=(0,0));bounds=local.bounds
 spec=physical[n]
 buildings.append({'id':'bespoke-hyperion-'+n.lower(),'tower':n,'nameKo':'목동 현대하이페리온 '+n+'동','coordinate':dict(zip(['lon','lat'],geo(centers[n]))),'siteEN':centers[n],
  'footprintIds':[s['id']],'sourceFootprint':s['geometry'],'yawDegFromEast':math.degrees(angle),'sourceRectangleM':[bounds[2]-bounds[0],bounds[3]-bounds[1]],
  'widthM':(bounds[2]-bounds[0])*.96,'depthM':(bounds[3]-bounds[1])*.95,'podiumHeightM':30.,**spec,
  'heightBasis':'Hyundai E&C official 2024 article 256m' if n=='A' else 'CTBUH project structural authors Table7 B216m/59F, prioritised over conflicting current database239.3m/63F; decorative top datum unresolved' if n=='B' else 'CTBUH C architectural height201.2m/54F; structural paper200m',
  'floorsBasis':'Summit Facade project listing69/59/54F; Seoul Development Institute2010 table2-7 agrees. B current CTBUH63F conflicts.',
  'uncertainties':['OSM named rectangular footprint supplies centre and orientation, not surveyed architectural perimeter.','Corner recesses, central stone width A10.4/B11.4/C9.3m, crown curves and window spacings are manual photographic estimates. Broad transfer triangles occupy each side wing rather than individual window bays.','Crown split heights and podium30m are estimates; floor levels interpolate between those landmarks.']+(['B216m is the project engineer stated structural height; decorative total height remains unresolved.'] if n=='B' else [])})
podium=unary_union([polys[n] for n in 'ABC']+[LineString([centers['B'],centers['A']]).buffer(17.5,cap_style=2),LineString([centers['B'],centers['C']]).buffer(17.5,cap_style=2)]).buffer(.3,join_style=2)
dept=next(s for s in sources if s['id']=='c7f66902-54ea-4bac-ae09-73a57bdf98b7');deptp=Polygon([en(v) for v in dept['geometry']['coordinates'][0]])
podium=podium.difference(deptp.buffer(.15)).buffer(0)
if podium.geom_type!='Polygon':raise ValueError('Podium needs manual disconnected-geometry review')
pc=podium.centroid
recipe={'siteId':'hyperion','origin':origin,'householdCount':466,'householdBasis':'existing official Seoul apartment source recordA15805114; apartment households only, excludes separate officetel count','buildings':buildings,
 'podium':{'id':'bespoke-hyperion-parking-podium','nameKo':'목동 현대하이페리온 L자 주차 포디움','coordinate':dict(zip(['lon','lat'],geo([pc.x,pc.y]))),'siteEN':[pc.x,pc.y],'heightM':30.,'footprint':mapping(affinity.translate(podium,xoff=-pc.x,yoff=-pc.y)),'footprintIds':[],
 'ownershipBasis':'Only connecting parking structure described by project engineer and visibly photographed by facade contractor. Does not own tower IDs or separate department-store source.','estimate':'L outline between named tower rectangles reconstructed from photo and source positions; shared podium dimensions not surveyed.','departmentStoreIntersectionAreaM2':podium.intersection(deptp).area,'facadeInterpretation':{'solidEndEdge':8,'stairGlassEdge':5,'stairGlassInterval':[0.38,0.70],'stoneEndReturnEdge':7,'stoneEndReturnInterval':[0.72,1.0],'basis':'Consultant photograph shows a stone end panel with recessed rectangle, tall glazed stair interruption and upper continuous glazing. Assignment to east A end and south connector is photo-to-site interpretation, not a surveyed facade elevation.'}},
 'sources':[{'url':'https://www.sfacade.net/dongtan-hyperion','observations':'Participating curtain-wall consultant:69,59,54-storey project; actual low-angle daylight photo shows ivory horizontal floor frames, blue-grey glazing, central stone walls, open parking slots and planted L podium.'},
 {'url':'https://static.wixstatic.com/media/90ddf2_d316ae4e030a46f1b011424d70f6c182~mv2.jpg','observations':'Actual daylight photograph, publication/capture date not specified; reviewed locally, never embedded or redistributed.'},
 {'url':'https://newsroom.hdec.kr/kr/newsroom/news_view.aspx?NewsListType=inter_list&NewsSeq=1120&NewsType=JOURNAL','observations':'2024-08-27 contractor article and completed photograph:256m69F and2003completion; flared white colonnade crown, central piers and white diagonal transfer belts visible. Sunset colour grading not used as exact albedo.'},
 {'url':'https://global.ctbuh.org/resources/papers/1651-Chung_2004_StructuralDesign.pdf','observations':'2004 structural project authors: Table7 A254m69F, B216m59F, C200m54F; outrigger A9/32/50, B/C9/32F; L-shaped9-level podium. Cached text inspected; direct PDF download404 and figures not traced.'},
 {'url':'https://www.si.re.kr/sites/default/files/2010-PR-01_0%20(s).pdf','observations':'2010 Seoul Development Institute table2-7: A69,B59,C54 floors.'},
 {'url':'https://www.skyscrapercenter.com/building/mokdong-hyperion-tower-b/1008','observations':'Current database239.3m63F conflicts with project participant sources. Retained as a conflict, not copied.'},
 {'url':'https://www.skyscrapercenter.com/building/mokdong-hyperion-tower-c/1633','observations':'Architectural height201.2m54F.'}],
 'retainedUntouchedSourceFootprintIds':[dept['id']]}
(OUT/'recipe-input.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'towers':[{k:b[k] for k in ['tower','coordinate','yawDegFromEast','widthM','depthM','floors','heightM']} for b in buildings],'podiumDepartmentStoreIntersectionM2':recipe['podium']['departmentStoreIntersectionAreaM2']},ensure_ascii=False,indent=2))
