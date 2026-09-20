"""Four Maple elevations authored from identified opposite-side Xi photographs."""
import json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-next-towers';OUT.mkdir(parents=True,exist_ok=True)
OLD=json.loads((ROOT/'docs/MAPLE_XI_MODEL_RECIPE.json').read_text());AS={a.get('recipe',{}).get('dong'):a for a in OLD['assets']}
URLS={3: 'https://beyondapartment.kr/media/pages/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja/16eb139021-1773801981/27.webp', 8: 'https://beyondapartment.kr/media/pages/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja/8a1bb14d60-1773801981/pokeoseu-15.webp', 15: 'https://beyondapartment.kr/media/pages/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja/56592f7013-1773801981/pokeoseu26.webp'}
# Each edge lists all openings independently in canonical v_i -> v_i+1 order.
# [fraction start,end,height fraction]; no random/shared apartment facade classifier.
def face(kind,cols,bands=(),basis='oblique photo interpretation; dimensions estimated'):
 return {'kind':kind,'windows':[[a,b,h] for a,b,h in cols],'bands':list(bands),'basis':basis}
F={
208:[face('pale',[(.13,.22,.70),(.29,.40,.70),(.53,.64,.70),(.75,.86,.70)],basis='February opposite aerial, northwest return partly seen'),
 face('pale',[(.045,.16,.71),(.205,.32,.71),(.375,.49,.71),(.54,.66,.71),(.71,.82,.71),(.87,.965,.71)],basis='March aerial northeast white grid, independently traced six columns'),
 face('curtain-look',[(.035,.095,.63),(.13,.265,.70),(.31,.435,.70),(.49,.615,.70),(.67,.80,.70),(.855,.95,.70)],[(0,1,'graphite')],basis='March aerial southeast dark framed window field;2024official notice names208 curtain-wall-look, not uninterrupted glass'),
 face('pale',[(.065,.19,.70),(.24,.36,.70),(.43,.50,.68),(.56,.63,.68),(.70,.82,.70),(.87,.97,.70)],[(.40,.67,'warm')],basis='February aerial southwest white-grid return; entry nearby but precise doorway axis provisional')],
209:[face('blank',[(.72,.758,.34)],basis='February northwest end: large blank pale wall and narrow core slot'),
 face('pale',[(.065,.21,.71),(.28,.43,.71),(.50,.65,.71),(.74,.91,.71)],basis='February inside return grid; partly occluded'),
 face('pale',[(.045,.20,.70),(.27,.43,.70),(.51,.67,.70),(.76,.94,.70)],[(.25,.46,'warm')],basis='March inner return above lower arm, partial evidence'),
 face('pale',[(.055,.21,.70),(.27,.43,.70),(.52,.605,.70),(.67,.76,.70),(.82,.94,.70)],basis='March northeast short end, broad and narrow columns'),
 face('pale',[(.05,.195,.72),(.25,.40,.72),(.46,.525,.70),(.57,.635,.70),(.69,.84,.72),(.885,.96,.70)],[(.43,.66,'warm')],basis='March southeast high arm front; broad outer windows, narrow central groups'),
 face('pale',[(.035,.16,.70),(.20,.325,.70),(.37,.43,.66),(.48,.54,.66),(.59,.72,.70),(.77,.90,.70),(.935,.978,.58)],[(.34,.565,'warm')],basis='February southwest lower arm broad window stacks;209 number oncompletedcollage confirmswallpatch only')],
212:[face('blank',[(.73,.774,.38)],basis='February northwest end: pale wall/slit; obscured details simplified'),
 face('pale',[(.075,.24,.71),(.32,.485,.71),(.56,.72,.71),(.80,.95,.71)],basis='February inner southwest-arm return, white grid'),
 face('pale',[(.055,.195,.70),(.25,.39,.70),(.465,.605,.70),(.69,.835,.70),(.89,.96,.65)],[(.42,.64,'warm')],basis='Opposite aerial inner northeast-arm return'),
 face('pale',[(.07,.215,.71),(.285,.43,.71),(.51,.59,.69),(.66,.745,.69),(.815,.955,.71)],basis='March northeast end: white grid with two narrow central slots'),
 face('curtain-look',[(.035,.105,.62),(.15,.30,.72),(.345,.50,.72),(.55,.68,.71),(.735,.865,.71),(.91,.967,.62)],[(0,1,'graphite')],basis='March southeast highway front: dark window field and broad mullion piers; official notice lists212'),
 face('pale',[(.04,.15,.71),(.19,.305,.71),(.35,.42,.66),(.465,.54,.66),(.585,.695,.71),(.74,.85,.71),(.89,.975,.70)],[(.325,.56,'warm')],basis='March southwest long face, unequal columns; lower stone field visibly taller than208')],
213:[face('blank',[(.73,.766,.33)],basis='Opposite aerial northwest high-arm end; large pale wall'),
 face('pale',[(.04,.20,.72),(.265,.425,.72),(.49,.65,.72),(.73,.92,.72)],basis='February high-arm inside return, partial lower-floor occlusion'),
 face('pale',[(.05,.18,.71),(.25,.38,.71),(.45,.52,.63),(.60,.73,.71),(.80,.95,.71)],[(.42,.57,'warm')],basis='February lower-arm inside return'),
 face('blank',[(.16,.20,.37),(.71,.745,.37)],basis='March northeast lower-arm end, broad white wall and slitgroups'),
 face('painted-dark',[(.05,.185,.73),(.24,.37,.73),(.425,.56,.73),(.61,.745,.73),(.80,.94,.73)],[(0,1,'graphite')],basis='March southeast lower wing, dark inset rows;213 is not in official curtain-wall-look list'),
 face('pale',[(.045,.175,.72),(.23,.36,.72),(.425,.49,.67),(.55,.62,.67),(.68,.81,.72),(.865,.965,.72)],[(.395,.65,'warm')],basis='March southwest higher arm white grid, two narrower central stacks')]
}
ROOFS={208:{'heights':[90.16],'screenEdges':[0,1,3],'screenHeight':2.55,'darkHeaderEdge':2,'plants':[{'center':[-2,2],'size':[7.1,4.4,3.6],'angle':-37}], 'panels':[{'center':[-4,-5],'size':[13.2,4.0],'angle':-37,'tilt':10}], 'description':'Rectangular roof court with three fin-screen edges and dark southeast fascia; one broadplant and lowpanelstrip'},
209:{'heights':[99.40,108.64],'screenEdges':[],'plants':[{'wing':0,'along':.82,'size':[7.2,3.8,4.4]},{'wing':1,'along':.82,'size':[7.7,4.3,6.0]}],'panels':[{'wing':0,'along':.34,'size':[19.5,7.0]},{'wing':1,'along':.34,'size':[17.0,6.0]}], 'description':'Lower southwest wing and high northeast wing, separate broad tilted panelcanopies and tall equipment cores; step estimated3storeys'},
212:{'heights':[90.16,90.16],'screenEdges':[0,1,2,3,5],'screenHeight':2.9,'darkHeaderEdge':4,'plants':[{'wing':0,'along':.79,'size':[7.2,4.6,4.4]},{'wing':1,'along':.83,'size':[6.8,4.0,3.0]}],'panels':[{'wing':0,'along':.31,'size':[11.0,5.5]},{'wing':1,'along':.34,'size':[20.0,5.8]}], 'description':'Lcourt, tallfins oninside/white edges, southeastdark fascia, twoequipmentvolumes, two panelstrips'},
213:{'heights':[108.64,96.32],'screenEdges':[],'plants':[{'wing':0,'along':.82,'size':[6.1,4.4,5.6]},{'wing':1,'along':.83,'size':[6.4,3.9,5.1]}],'panels':[{'wing':0,'along':.32,'size':[12.0,5.8]},{'wing':1,'along':.34,'size':[17.0,5.8]}], 'description':'High southwest whitegrid wing, lower northeast dark wing, tall offsetservicecores and separatepanelcanopies; step estimated4storeys'}}
# Corrected with same-height208/210/211 roofprojection: Marchcamera is eastside,
# image-right is north. The darkreturns are NE, not broad SE whitefacades.
F[208][1],F[208][2]=F[208][2],F[208][1]
F[208][1]['basis']='March east aerial NE e1 dark return, completed highway panorama; official208 curtain-wall-look'
F[208][2]['basis']='March east aerial SE e2 broad white six-column face'
ROOFS[208]['screenEdges']=[0,2,3];ROOFS[208]['darkHeaderEdge']=1
ROOFS[208]['description']='Rectangular roof court with three fin-screen edges and dark northeast fascia; one broadplant and lowpanelstrip'
F[212][3]=face('curtain-look',[(.045,.175,.69),(.23,.36,.71),(.425,.56,.72),(.625,.76,.71),(.825,.955,.69)],[(0,1,'graphite')],basis='March NE e3 dark short return, confirmed opposed geometry and official212 curtain-wall-look')
F[212][4]=face('pale',[(.045,.155,.72),(.20,.315,.72),(.365,.435,.68),(.48,.55,.68),(.595,.715,.72),(.76,.88,.72),(.925,.98,.65)],[(.34,.575,'warm')],basis='March SE e4 broad whitegrid; narrower middle columns, not full-heightdark curtainfield')
ROOFS[212]['screenEdges']=[0,1,2,4,5];ROOFS[212]['darkHeaderEdge']=3
ROOFS[212]['description']='Lcourt, tallfins onwhite edges, northeastdark fascia, twoequipmentvolumes, two panelstrips'
F[213][3]=face('painted-dark',[(.055,.20,.73),(.27,.42,.73),(.485,.62,.73),(.69,.84,.73),(.90,.96,.65)],[(0,1,'graphite')],basis='March NE e3 lowerarm dark return, painted/insetwindow interpretation; not listed curtain-wall-look')
F[213][4]=face('pale',[(.045,.18,.72),(.23,.365,.72),(.425,.49,.69),(.545,.61,.69),(.675,.81,.72),(.865,.965,.72)],[(.395,.645,'warm')],basis='March SE e4 lowerarm whitegrid with two narrow middle slots; matching east camera')
# Per-room visible openings and capprofiles; offsets in that room's own u/v axes.
# side = +v/-v longwall or +u/-u endwall; [side,offset,width,bottom,height].
ROOFS[208]['plants'][0].update({'apertures':[['+v',-1.7,.55,2.1,.80],['+v',1.3,.48,2.1,.80],['-v',-.8,2.9,.60,1.55],['+u',.2,.43,.8,1.70]],'capStep':.20,'capSide':'+v','openingBasis':'208 roofroom smallupper squareopenings inMarch; broadoppositevent inFebruary; positioning anddepthestimated'})
ROOFS[209]['plants'][0].update({'apertures':[['+v',-.4,.45,1.8,1.55],['-v',.8,2.8,.8,1.4],['+u',0,.52,2.2,.75]],'capStep':.30,'capSide':'-v','openingBasis':'209lowerroof room smallsideopening andwidevent; proportionestimated'})
ROOFS[209]['plants'][1].update({'apertures':[['+v',.65,.52,2.05,1.60],['+u',-.7,.40,1.4,2.50],['-v',0,3.0,.85,1.60]],'capStep':.45,'capSide':'+v','openingBasis':'209 tallcore slenderverticalslot below top, separatelargervent andraisededgecap; two-storey-lookingheightestimated6.0m'})
ROOFS[212]['plants'][0].update({'apertures':[['+v',.9,.65,2.5,.80],['-v',-.5,2.75,.9,1.65],['+u',0,.45,1.0,1.80]],'capStep':.28,'capSide':'+v','openingBasis':'212 tallcourtroom upperdarkrectangle/slot andoppositevent'})
ROOFS[212]['plants'][1].update({'apertures':[['+v',-1.2,.65,1.55,.70],['+v',1.3,.48,1.45,.85],['-v',0,2.5,.6,1.40]],'capStep':.15,'capSide':'-v','openingBasis':'212 lowservicebox twooffsetsmallopenings, broadbackvent'})
ROOFS[213]['plants'][0].update({'apertures':[['+v',0,.50,2.3,1.65],['+u',-.4,.42,1.8,2.20],['-v',0,2.4,.9,1.45]],'capStep':.40,'capSide':'+v','openingBasis':'213 higharm tallcore upperverticalslot andseparatevent; height5.6m estimate'})
ROOFS[213]['plants'][1].update({'apertures':[['+v',-1.0,.60,2.9,.80],['+v',.9,.42,1.6,2.0],['-v',0,2.7,.8,1.55]],'capStep':.25,'capSide':'-v','openingBasis':'213 lowarm tallservicecore offsetapertures andcapledge; height5.1m estimate'})
assets=[]
for d in [208,209,212,213]:
 a=AS[d];lon,lat=a['coordinate']['lon'],a['coordinate']['lat'];ring=[[(x-lon)*111320*math.cos(math.radians(lat)),(y-lat)*111320] for x,y in a['groundFootprint']['coordinates'][0][:-1]]
 assets.append({'dong':d,'id':f'bespoke-maple-xi-{d}','oldId':a['id'],'coordinate':a['coordinate'],'ring':ring,'pixelRing':a['recipe']['groundFootprintPixelTrace'],'faces':F[d],'roof':ROOFS[d],'baseHeight':6.6 if d!=212 else 7.1,'stoneTop':12.9 if d!=212 else 17.0,'originalSha256':a['sha256'],'heightStatus':'mainroof heights retained from previous estimates; wingstep metric proportions inferred from opposite photos, actualfloorcounts notverified','entry':{'edge':3,'fraction':.56,'width':6.8,'height':5.2,'basis':'208 number visible oncompletedentrancephoto; exactwest-facing orientation inferred frominterior circulation not surveyed'} if d==208 else None})
sources=[{'url':'https://www.xi.co.kr/Files/cmsPage/20240205_132346_189001.jpg','observations':'Numberedbar/L footprint identity and relativeposition; illustrativeplan, notCAD.'},{'url':'https://www.xi.co.kr/Files/aptProcRateImg/20250403_170535_099001.JPG','observations':'March2025east aerial; eastsides, fourindividualroofsilhouettes.'},{'url':'https://www.xi.co.kr/Files/aptProcRateImg/20250403_170447_204001.JPG','observations':'February2025opposite aerial; corroboratesroofpanelcanopies anddifferentwingheights.'},{'url':URLS[15],'observations':'Completedhighwaypanorama; fincrowns, windowcolorfields andverticalframeaccent.'},{'url':URLS[8],'observations':'208numberedstoneentry, thickportal, verticalslats, ceilinglouvers.'},{'url':URLS[3],'observations':'209numberedreturnpatch, completedtop-downsitecollage andbridgecontext.'},{'url':'https://www.xi.co.kr/Files/cmsPage/20240126_101604_789001.pdf','observations':'Officialnotice distinguishes curtain-wall-look208/212 from209/213; common35F maximum doesnotverifyeachfloorcount.'}]
out={'siteId':'maple-next-towers','sources':sources,'assets':assets,'faceMapping':'All canonical edges are v_i to v_i+1 in retainednumberedplanring. Crosschecked road order, ClubCloud connection andopposite aerials; exactphotocamera notsurveyed.','uncertainties':['Overallroof heights, wingstep heights, windowsizes, crownheight, paneltilt andservicevolume dimensions arephoto-proportion estimates.','Individualfloorcounts areunverified; repeatedstoreyrows areestimated.','Occluded rearface/window details simplified andnotreviewed ascomplete.','208entryidentity verified bynumber; exactentrancecompassorientation isprovisional.','Nointerior, landscape, exactequipmentarrangement orbelowgroundgeometry reconstruction.','Unseen209/212/213 groundfloors areconservativeopaqueprovisionalmass, not inventedopenpilotis or verifiedentrylayout.']}
(OUT/'authored-input.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(OUT/'authored-input.json')
