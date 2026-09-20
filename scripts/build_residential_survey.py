"""Build individual official-footprint models and publish a lazy regional catalog."""
from __future__ import annotations
import argparse, collections, concurrent.futures, hashlib, json, math, os, shutil, sqlite3
from pathlib import Path
from shapely.geometry import shape
from shapely.ops import transform
from build_district_landmarks import Mesh, projected, unprojected
from residential_facade import residential_geometry
from select_residential_survey import ROOT, WORK, sha

CACHE=WORK/'glb-cache'
OUTPUT=ROOT/'public/models/residential-survey'
REFERENCE='https://urban.seoul.go.kr/view/map/main.html'


def build_one(job):
    row,key=job
    candidate=dict(row);ident=candidate['id'];cache=CACHE/(ident+'.glb');record=CACHE/(ident+'.json')
    if cache.exists() and record.exists():
        saved=json.loads(record.read_text())
        if saved['buildKey']==key and sha(cache)==saved['asset']['sha256']:return saved
    poly=shape(json.loads(candidate['geometry']));anchor=poly.representative_point();origin=(anchor.x,anchor.y)
    local=transform(lambda x,y,z=None:projected(x,y,origin),poly)
    facade=candidate['kind']
    if facade=='multifamily':facade='villa' if candidate['floors']<=4 else 'apartment'
    mesh=Mesh();seed=int(hashlib.sha256(ident.encode()).hexdigest()[:8],16)
    polygons=list(local.geoms) if local.geom_type=='MultiPolygon' else [local]
    for part in polygons:
        if not residential_geometry(mesh,part,candidate['height'],candidate['floors'],facade,seed):raise ValueError('Failed source geometry '+ident)
    temp=cache.with_suffix('.tmp.glb');stats,offset=mesh.save(temp)
    if abs(stats['dimensions'][1]-candidate['height'])>.01:raise ValueError('Height envelope changed '+ident)
    os.replace(temp,cache)
    lon,lat=unprojected(offset[0],offset[2],origin)
    evidence=json.loads(candidate['evidence']);basis=evidence['heightBasis']
    asset={'id':ident,'nameKo':candidate['name'],'model':f"residential-survey/glb/{candidate['tile']}/{ident}.glb",'coordinate':{'lon':lon,'lat':lat},'dimensions':stats['dimensions'],'yawDegFromEast':0,'heightDatum':'local ground at individual model anchor','units':'metres','district':candidate['district'],'category':'residential-'+candidate['kind'],'minZoom':16.5,'referenceUrl':REFERENCE,'footprintIds':json.loads(candidate['footprints']),'buildingCount':1,'heightEstimated':('estimated' in basis or 'fallback' in basis),'sha256':stats['sha256'],'bytes':stats['bytes'],'triangles':stats['triangles'],'drawCalls':stats['drawCalls'],'sourceRecord':{'provider':'Seoul UPIS public building layer 86','objectId':evidence['officialObjectId'],'buildingManagerId':evidence['buildingManagerId'],'parcelId':evidence['parcelId'],'mainUse':evidence['mainUse'],'otherUse':evidence['otherUse'],'roadAddress':evidence['roadAddress'],'classificationBasis':evidence['classificationBasis'],'sourceFloors':evidence['sourceFloors'],'sourceApprovalYear':evidence['sourceApprovalYear'],'heightBasis':basis,'register':evidence['register'],'registerLinkBasis':evidence['registerLinkBasis'],'overtureMatches':evidence['overtureMatches']},'modelingEstimates':{'facade':'Procedural source-outline facade, not photographic reconstruction','sourceVintage':'UPIS publication/vintage not specified; acquired 2026-09-20','details':'docs/RESIDENTIAL_SURVEY.md'}}
    result={'buildKey':key,'tile':candidate['tile'],'bounds':list(poly.bounds),'asset':asset}
    tmp=record.with_suffix('.tmp.json');tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n');os.replace(tmp,record)
    return result


def tile_bounds(tile):
    z,x,y=map(int,tile.split('-'));n=2**z
    lat=lambda t:math.degrees(math.atan(math.sinh(math.pi*(1-2*t/n))))
    return [x/n*360-180,lat(y+1),(x+1)/n*360-180,lat(y)]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=3);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    if OUTPUT.exists():raise ValueError('Catalog already published; refusing to overwrite')
    manifest=ROOT/'public/models/manifest.json';original=manifest.read_bytes();baseline=json.loads(original)
    selection=WORK/'selection.sqlite';audit=json.loads((WORK/'selection-audit.json').read_text())
    if sha(manifest)!=audit['baselineManifestSha256']:raise ValueError('Baseline changed since selection')
    db=sqlite3.connect(selection.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    candidates=[dict(r) for r in db.execute('SELECT * FROM candidates ORDER BY id')];db.close()
    if len(candidates)!=audit['counts']['selected']:raise ValueError('Selection count differs')
    for asset in baseline['assets']:
        if sha(ROOT/'public/models'/asset['model'])!=asset['sha256']:raise ValueError('Changed baseline GLB '+asset['id'])
    CACHE.mkdir(parents=True,exist_ok=True)
    selection_hash=sha(selection)
    key=hashlib.sha256((selection_hash+sha(Path(__file__))+sha(ROOT/'scripts/residential_facade.py')+sha(ROOT/'scripts/build_district_landmarks.py')).encode()).hexdigest()
    rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1,min(4,args.workers))) as pool:
        for i,result in enumerate(pool.map(build_one,((c,key) for c in candidates),chunksize=16),1):
            rows.append(result)
            if i%1000==0 or i==len(candidates):print(f'{i}/{len(candidates)} official housing GLBs ready',flush=True)
    if sha(selection)!=selection_hash:raise ValueError('Selection input changed during build')
    if manifest.read_bytes()!=original:raise ValueError('Manifest changed during build')
    if args.prepare_only:return
    staging=WORK/'catalog-publish'
    if staging.exists():shutil.rmtree(staging)
    (staging/'tiles').mkdir(parents=True)
    groups=collections.defaultdict(list)
    for row in rows:groups[row['tile']].append(row)
    tiles=[]
    for tile,group in sorted(groups.items()):
        if len(group)>4096:raise ValueError('Shard exceeds supported catalog cap '+tile)
        folder=staging/'glb'/tile;folder.mkdir(parents=True)
        for row in group:os.link(CACHE/(row['asset']['id']+'.glb'),folder/(row['asset']['id']+'.glb'))
        path=staging/'tiles'/(tile+'.json');path.write_text(json.dumps({'version':1,'assets':[r['asset'] for r in group]},ensure_ascii=False,separators=(',',':'))+'\n')
        if path.stat().st_size>8*1024*1024:raise ValueError('Shard byte limit exceeded '+tile)
        bounds=tile_bounds(tile)
        for row in group:
            b=row['bounds'];p=row['asset']['coordinate'];bounds=[min(bounds[0],b[0],p['lon']),min(bounds[1],b[1],p['lat']),max(bounds[2],b[2],p['lon']),max(bounds[3],b[3],p['lat'])]
        tiles.append({'id':tile,'path':f'residential-survey/tiles/{tile}.json','bounds':bounds,'count':len(group),'sha256':sha(path)})
    index={'version':1,'minZoom':16.5,'assetCount':len(rows),'tiles':tiles}
    (staging/'index.json').write_text(json.dumps(index,ensure_ascii=False,separators=(',',':'))+'\n')
    proof={'generator':'scripts/build_residential_survey.py','selectionSha256':selection_hash,'selectionBaselineManifestSha256':audit['baselineManifestSha256'],'baselineModels':len(baseline['assets']),'newModels':len(rows),'totalModels':len(baseline['assets'])+len(rows),'catalogTiles':len(tiles),'categories':audit['categories'],'newBytes':sum(r['asset']['bytes'] for r in rows),'newTriangles':sum(r['asset']['triangles'] for r in rows),'newCatalogIndexSha256':sha(staging/'index.json'),'maxTileModels':max(len(g) for g in groups.values()),'maxTileBytes':max((staging/'tiles'/(t+'.json')).stat().st_size for t in groups),'allPreviousModelRecordsPreserved':True,'allPreviousFootprintMatchesPreserved':True,'allSourceDispositionsAccounted':audit['sourceIdsExactlyAccounted'],'individualGroundAnchors':True}
    # The baseline asset array remains byte-for-byte intact; only root metadata grows.
    marker=b'  "assets": ['
    if original.count(marker)!=1:raise ValueError('Unexpected manifest layout')
    extra={'catalogIndex':'residential-survey/index.json','residentialSurvey':{'count':len(rows),'tiles':len(tiles),'provenance':'../../docs/RESIDENTIAL_SURVEY_PROVENANCE.json'}}
    insertion=b''.join(('  '+json.dumps(k)+': '+json.dumps(v,ensure_ascii=False,separators=(',',':'))+',\n').encode() for k,v in extra.items())
    updated=original.replace(marker,insertion+marker,1)
    assert json.loads(updated)['assets']==baseline['assets']
    proof_path=ROOT/'docs/RESIDENTIAL_SURVEY_PROVENANCE.json'
    if proof_path.exists():raise ValueError('Provenance already exists')
    os.replace(staging,OUTPUT)
    try:
        proof_path.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
        pending=manifest.with_suffix('.survey.tmp');pending.write_bytes(updated);os.replace(pending,manifest)
    except BaseException:
        # Keep the complete new directory if restoring the manifest fails.
        # Moving assets first could leave readers pointing at missing files.
        restore=manifest.with_suffix('.restore.tmp');restore.write_bytes(original);os.replace(restore,manifest)
        os.replace(OUTPUT,staging)
        if proof_path.exists():proof_path.unlink()
        raise
    print(json.dumps(proof,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
