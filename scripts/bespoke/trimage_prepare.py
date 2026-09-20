"""Author the four Trimage component recipes from source topology and inspected photos.
Run against preserved source-footprints.json; no reference photographs are embedded.
"""
from pathlib import Path
import json,math
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/trimage';OUT.mkdir(parents=True,exist_ok=True)
p=OUT/'source-footprints.json'
if not p.exists():p=ROOT/'modeling/bespoke/trimage/source-footprints.json'
S=json.loads(p.read_text());regpath=OUT/'official-register-source.json'
if not regpath.exists():regpath=ROOT/'modeling/bespoke/trimage/official-register-source.json'
REG={r['building_dong'][:3]:r for r in json.loads(regpath.read_text()) if r['building_dong'] in ['101동','102동','103동','104동']}
sources=[
{'url':'https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do','observations':'Official Seoul building-register title CSV downloaded2026-09-08, SHA256 ba00150bbc9b2343fd2ba2fbaaa0c723df7d5dabbbd820345a405e9aaa5162aa; exact Seongdong/Seongsu1/718-0+Wangsimni-ro16+number match.101157.1m47F143households;102153.6m46F143;103144.35m45F189;104150.45m47F213. All approved2017; raw rows/hash retained.'},
{'url':'https://www.nocktown.com/web-front/trimage/','observations':'Current official resident site for Wangsimni-ro16,688households in public initial state. Supplies completed east/aerial reference image, date unspecified, uploaded2024-03.'},
{'url':'https://d1uew7hepkc3d0.cloudfront.net/lifeknock/upload/2024/03/G2rBj4MEbbbpmKudUTEhrIdaePZITh.png','observations':'Resident-site photograph directly inspected.102east side has a broad pale narrow-window core above a low curved glass wing; rear104has a flat glass facade, pale vertical edges and a crown stepped behind the main face.'},
{'url':'http://www.nowarch.com/works/view?idx=48','observations':'Original architect NOW project48, completed2017 photograph. Page retains an earlier48F design figure; not substituted for current source floor counts.'},
{'url':'http://www.nowarch.com/uploads/media/w_m_tri.jpg','observations':'Completed river/southwest photograph, date unspecified. Four staggered towers: rounded horizontal white ribbons on101/102, flat glass and stone spines on103/104; substantial louver crowns and open refuge bands. Manually inspected.'},
{'url':'https://www.skyedaily.com/news/news_view.html?ID=89974','observations':'First-party Skyedaily photograph credited to the publication, published2019-09-07. Opposite courtyard faces show broad pale punched-window core walls and narrower staggered glass wings. Exact photographer position is not surveyed.'},
{'url':'https://pds.skyedaily.com/news_data/20190906095150_doydecsc.jpg','observations':'Actual completed photograph inspected; individual face-to-source mapping is inferred from the four source footprints and river view, not a surveyed elevation.'},
{'url':'https://www.doosanenerbility.com/heavy_file/management/data/overview_result/report/2017_report_kr.pdf','observations':'Contractor2017 report PDF13, printed20–21, actual completed exterior photo bottom right and green-building certification2017-04-06. Small image supports design, not dimension measurement.'},
{'url':'https://pluspp.co.kr/result/result_highend.asp','observations':'Project participant official performance record identifies688households, B3–47F, Seoul Forest Doosan Trimage.'},
{'url':'https://realty.chosun.com/m/article.amp.html?contid=2024032801176','observations':'2024-03-28 firsthand entrance photo by reporter Kim Seo-gyeong: long shallow grey stone portal, deep opening, sloping outer end. Gate location/dimensions not yet surveyed; separate feature not exported until geographically established.'},
{'url':'https://image.chosun.com/sitedata/image/202403/28/2024032801172_1.jpg','observations':'Entrance photograph directly inspected. No image is distributed with the GLB or editable blend.'},
{'url':'https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do','observations':'Existing Seoul apartment inventory A10026988 identifies688households and4residential buildings. Superseded model apt-a10026988 is a4tower compound.'}]
towers=[]
# Component heights are explicit photo-proportion estimates below source-reported total heights.
for s in S:
 n=s['name'][:3];ring=s['geometry']['coordinates'][0][:-1];lon=(min(a for a,b in ring)+max(a for a,b in ring))/2;lat=(min(b for a,b in ring)+max(b for a,b in ring))/2
 xy=[[(a-lon)*111320*math.cos(math.radians(lat)),(b-lat)*111320] for a,b in ring];cx=sum(a for a,b in xy)/len(xy);cy=sum(b for a,b in xy)/len(xy);c=[cx,cy]
 def part(label,indices,h,style,screen=0,stone=[]):
  points=[xy[k] for k in indices]+[c];return {'name':label,'sourceVertexChain':indices,'polygon':points,'heightM':h,'facade':style,'screenM':screen,'stoneEdges':stone,'internalEdges':[len(points)-2,len(points)-1]}
 if n=='101':
  parts=[part('NW_rectangular_high_spine',list(range(1,10)),157,'flat',9,[0,1]),part('SW_lower_round_wing',list(range(9,21)),94,'mosaic',0,[0,1]),part('SE_tall_ribbon_wing',list(range(20,29)),145,'ribbon',0,[0,7]),part('NE_stone_back_and_round_return',list(range(28,36))+[0,1],130,'mosaic',0,[0,5,6,7])]
 elif n=='102':
  parts=[part('NE_rectangular_high_spine',list(range(1,10)),154,'flat',9,[0,1]),part('NW_medium_round_wing',list(range(9,21)),129,'ribbon',0,[0,1]),part('SW_tall_ribbon_wing',list(range(20,29)),143,'ribbon',0,[0,7]),part('SE_stone_back_and_round_return',list(range(28,36))+[0,1],99,'mosaic',0,[0,5,6,7])]
 elif n=='103':
  parts=[part('NW_high_stone_spine',list(range(0,6)),144,'stone',8,[0,1,2]),part('SW_broad_flat_glass',list(range(5,11)),136,'flat',0,[0,1]),part('E_lower_angular_wing',list(range(10,17))+[0],105,'flat',0,[0,1,3,5])]
 else:
  parts=[part('NW_high_stone_spine',list(range(0,6)),150,'stone',8,[0,1,2]),part('S_broad_flat_glass',list(range(5,11)),129,'flat',0,[0,1]),part('NE_lower_angular_wing',list(range(10,17))+[0],112,'flat',0,[0,1,3,5])]
 parts[0]['heightM']=float(REG[n]['height'])
 towers.append({'number':n,'assetId':'bespoke-trimage-'+n,'nameKo':'서울숲 트리마제 '+n+'동','anchor':{'lon':lon,'lat':lat},'footprintId':s['id'],'sourceRecord':s['source_properties']['sources'][0]['record_id'],'sourceHeightM':float(REG[n]['height']),'osmHeightM':s['height_m'],'registerId':REG[n]['id'],'registerSourceHash':REG[n]['source_hash'],'households':int(REG[n]['households']),'floors':s['num_floors'],'ring':xy,'parts':parts,'refugeZ':([24,56,91] if n=='101' else [23,55,88] if n=='102' else [55] if n=='103' else [58]),'lobbyHeightM':4.4})
R={'siteId':'trimage','sources':sources,'towers':towers,'households':688,'residentialTowerCount':4,'heightBasis':'Official Seoul OA-22424 individual building-register heights157.1/153.6/144.35/150.45m and floors47/46/45/47 are adopted. These are legal registry heights: exact inclusion of decorative roof screen is unconfirmed, so the authored overall mesh is capped at the register height without inventing extra metres. CTBUH2017completed report200/182m and NOW older48F record conflict; the address-and-number-matched individual official rows take precedence. Wing heights/refuge levels remain photo-proportion estimates, not measured floor schedules.','uncertainties':['Wing height, refuge levels, crown details and facade orientation inferred by completed photographs; no surveyed CAD/elevation available.','Fine glazing/spandrel variation is an authored repeating abstraction of visible white-panel patches, not a window-by-window survey.','Unseen reverse faces and roof equipment simplified. No inference of private interior or occupancy.','Ground lobby profiles are photo-proportion estimates. Separate gate and low ancillary buildings are not claimed by the4tower ownership.'],'coverage':{'included':['101–104 four residential towers, each source-traced','staggered wings;101/102 curved glass ribbons;103/104 flat curtain walls','individual stone cores, open refuge bands, louver crowns, ground lobby/pilotis'], 'excluded':['underground parking/interior','separate unlocated gate and ancillary buildings','landscaping and public roads'], 'status':'four residential towers; gate georeference pending, not whole-complex ancillary completion'}}
(OUT/'authored-input.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n')
print('Authored4tower component recipes; all heights separately qualified.')
