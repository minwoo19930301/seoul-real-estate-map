from pathlib import Path
import json,math,hashlib,shutil
O=Path(__file__).parent;ROOT=O.parents[3]
assets=json.loads((ROOT/'public/models/reference-manifest.json').read_text())['assets'];rows=json.loads((O.parent/'maple-next-research/register-rows.json').read_text())
inputs=[]
for number in [205,206]:
 a=next(x for x in assets if x['id']==f'maple-xi-{number}');r=next(x for x in rows if x.get('building_dong')==f'{number}동');sr=a['sourceRecord'];p=sr['recipe']['groundFootprintPixelTrace'];m=sr['georeference']['pixelToLonLatAffine'];ll=[[x*m[0][0]+y*m[1][0]+m[2][0],x*m[0][1]+y*m[1][1]+m[2][1]]for x,y in p];co=a['coordinate'];sx=111319.49079327358*math.cos(math.radians(co['lat']));ring=[[(x-co['lon'])*sx,(y-co['lat'])*111319.49079327358]for x,y in ll];area=abs(sum(ring[i][0]*ring[(i+1)%6][1]-ring[(i+1)%6][0]*ring[i][1]for i in range(6)))/2
 d={'id':f'bespoke-maple-xi-{number}','number':number,'originalId':a['id'],'coordinate':co,'groundFootprint':{'type':'Polygon','coordinates':[ll+[ll[0]]]},'ringEN':ring,'planPixelTrace':p,'register':r,'heightM':float(r['height']),'floors':int(r['floors']),'rows':32,'bodyRoofM':107.8 if number==206 else 103.55,'baseM':7.0 if number==206 else 6.75,'modelingBasis':'representative-photo-inference','inferredFromAssetIds':['bespoke-maple-xi-203','bespoke-maple-xi-204','bespoke-maple-xi-207'],'sources':sr['sources'][:5]+[{'url':'https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do','kind':'exact building register'}],'footprintMetricLimit':{'tracedAreaM2':area,'registeredBuildingAreaM2':float(json.loads(r['raw_json'])['건축면적']),'basis':'Existing numbered illustrative plan trace and original anchor retained; area differs from official building area. No arbitrary area scaling or survey accuracy claim.'},'identity':{'basis':'Existing official numbered-plan trace, exact register dong name and unique ID. Photo family inference does not substitute for numbered identity.','registerId':r['id'],'numberedPlanDong':number},'supersedes':[a['id']],'footprintIds':[]}
 if number==206:
  old=json.loads((O.parent/'maple-206/authored-input.json').read_text());d['research206']=old;assert d['coordinate']==old['coordinate'];d['ringEN']=old['ringEN'];d['groundFootprint']=old['groundFootprint'];d['footprintMetricLimit']=old['footprintMetricLimit']
 (O/f'source-anchor-{number}.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n');(O/f'input-{number}.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');inputs.append(d)
(O/'inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2)+'\n')
frozen={}
for name in ['maple-203','maple-204','maple-207','maple-206']:
 for f in (O.parent/name).iterdir():
  if f.is_file():frozen[str(f.relative_to(O.parent))]=hashlib.sha256(f.read_bytes()).hexdigest()
(O/'prior-stage-hashes.json').write_text(json.dumps(frozen,indent=2)+'\n')
print([(d['number'],d['heightM'],d['footprintMetricLimit'])for d in inputs])
