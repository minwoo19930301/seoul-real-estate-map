#!/usr/bin/env python3
"""Partition archived fallback meshes for independently reviewed Banpo towers."""
import argparse
import copy
import json
import math
import sqlite3
import numpy as np
from shapely.geometry import shape, Point, MultiPoint
from shapely.ops import transform, unary_union
from split_caelitus_fallback import ROOT, decode, encode, sha
from publish_bespoke_models import replace_batch

CONFIGS = [
    {'site':'onebailey','source':'apt-a10023043','sha':'b50af817af714ec3027f9fa240a0a17d72fc896987180699ae47a50f9fd393ca','count':19,
     'parts':[
         ('fallback-onebailey-101','래미안원베일리 101동','4348b83d-8074-41db-b6fd-2a0220302d25'),
         ('fallback-onebailey-102','래미안원베일리 102동','18482853-b439-4fbc-a964-bbeb2c81c7cc'),
         ('fallback-onebailey-103','래미안원베일리 103동','b1f87321-a5d0-497d-8863-c7b45dc7422c'),
         ('fallback-onebailey-104','래미안원베일리 104동','ccf8cdd2-6388-489d-924f-b26563a9fe1c'),
         ('fallback-onebailey-105','래미안원베일리 105동','6b129b5e-2708-4c00-8152-0e87487a5466'),
         ('fallback-onebailey-106','래미안원베일리 106동','90d15512-c437-4358-bfe6-28c2b9fab0c8'),
         ('fallback-onebailey-107','래미안원베일리 107동','e3e75971-1068-44f0-9ce7-54aa836baf61'),
         ('fallback-onebailey-108','래미안원베일리 108동','54767758-a6b2-42dc-a87c-6d692a530b8c'),
         ('fallback-onebailey-109','래미안원베일리 109동','de07b28c-23ae-4269-8ec4-b52eeb69f263'),
         ('fallback-onebailey-110','래미안원베일리 110동','2d201360-9fb2-45a6-aaf1-24b716cb2497'),
         ('fallback-onebailey-111','래미안원베일리 111동','a067f8da-623a-49c8-ae6f-630514a4e5e0'),
         ('fallback-onebailey-112','래미안원베일리 112동','2d55f2d2-3aea-4c56-a82f-96e3df9a5630'),
         ('fallback-onebailey-117','래미안원베일리 117동','6425f454-ba84-4f09-8035-81972ca60315'),
         ('fallback-onebailey-118','래미안원베일리 118동','79b1392f-7edf-4cc2-9ec4-07c539094e35'),
         ('fallback-onebailey-119','래미안원베일리 119동','c36de435-fa03-41d5-8590-0ea943645668'),
         ('fallback-onebailey-120','래미안원베일리 120동','3db90e64-b0eb-4e9a-bfef-41ea3cf11c43'),
         ('fallback-onebailey-121','래미안원베일리 121동','37167a22-89d6-41be-9768-691ce24bfc6b'),
         ('fallback-onebailey-122','래미안원베일리 122동','1035924e-30e1-4e29-b8d8-894e48fd550e'),
         ('fallback-onebailey-123','래미안원베일리 123동','9bf33339-8503-4c4d-a4a2-e34b800eb8a7')],
     'limits':['The archived compound contains 19 of 23 official residential buildings. All 19 are partitioned independently; 113–116 are absent from this source and no fallback geometry is invented for them.','Official numbered plan and exact building register identify 101–112 and 117–123. Source fallback geometry/heights remain unchanged; no photo-completion credit.']},
    {'site':'onebailey-113-116','source':'apt-a13780006','sha':'592c23e04732cfb977adb31a28c5c41ca0d59b372f1a17a4f22df1ec35dab34e','count':5,
     'remainingName':'잠원위브아파트 (기존 추정 모형)','removeApartmentCode':True,
     'parts':[
         ('fallback-onebailey-113','래미안원베일리 113동','c4e0e45a-f6c4-4e42-9c78-8411bbc35196'),
         ('fallback-onebailey-114','래미안원베일리 114동','6c880c2b-4050-43e1-9966-d778d6919944'),
         ('fallback-onebailey-115','래미안원베일리 115동','cd7c1e28-21f5-4557-9658-4c70b4f31a9c'),
         ('fallback-onebailey-116','래미안원베일리 116동','88e4562e-a229-441e-abdb-6d071becf986')],
     'limits':['The archived apt-a13780006 compound was labeled Banpo Gyeongnam but contains the exact source footprints of One Bailey 113–116 and the separate Jamwon Weve apartment. These four fallbacks preserve existing geometry from this archive, not the 19-footprint apt-a10023043 archive.','Jamwon Weve source 671b8451-4737-4461-b4c4-725117141fb5 remains as the residual at its unchanged original terrain anchor and contributes no One Bailey residential coverage. The mislabeled apartment code and aggregate household count are not transferred to any partition.','All five original source meshes, heights, attributes and materials are retained exactly once. This operation earns no photo-model completion credit.']},
    {'site':'onepentas','source':'apt-a10022556','sha':'4f301eb1e259da07a9580dc86256b044a0e55fcfe654ad5401ad3eacdf8e00f7','count':7,
     'remainingName':'래미안원펜타스 101–104동 (기존 추정 모형)',
     'parts':[
         ('fallback-onepentas-105','래미안원펜타스 105동','1d28aa9d-3ad6-4b50-a32c-a7bc75f3ebcf'),
         ('fallback-onepentas-106','래미안원펜타스 106동','dad2c16e-28a1-4c1c-b786-91be69693ca6'),
         ('fallback-prestige-126','래미안퍼스티지 126동','b21842a2-9832-4a21-bcc5-1c571f309556')],
     'limits':['OfficialOnePentas641apartments/6buildings excludes theneighbor126. The126source23F65m matches officialregister10231100193383 atBanpodong18-1/Banpodaero275,23F65.3m44households:RaemianPrestige. OneBailey126is1Famenityandnotthisbuilding.','The sixOnePentassourcefallbackheights are estimated andnotcorrectedbythispartition; newphoto modelsreplaceindependently. No photomodelingcredit is claimed.']},
    {'site':'acro-riverpark','source':'apt-a10027205','sha':'e02dd03abb3fd65981303758bf47d491d3ff41df0c593ce87b9fb94d7ca38401','count':17,
     'remainingName':'아크로리버파크 나머지13동과 이웃2개 도형 (기존 추정 모형)',
     'parts':[
         ('fallback-acro-riverpark-100','아크로리버파크 100동','60227661-442c-454d-bb39-c5d658cf9e76'),
         ('fallback-acro-riverpark-109','아크로리버파크 109동','aecd9e1e-1d74-4198-90bb-e3a40edeebeb')],
     'limits':['The archived17-footprint compound includes15 numbered Acro buildings and2 neighboring or unidentified footprints. Only100 and109 are isolated here; all15 other footprints remain unchanged.','OSM source heights and meshes are preserved, not corrected or given photo completion credit. Banpo Parkville and the unnamed neighbor remain outside the15-tower residential coverage.']}
]

def partition(cfg, folder, base, matches):
    source=cfg['source'];asset=next(a for a in base['assets'] if a['id']==source)
    original=(folder/asset['model']).read_bytes();assert sha(original)==cfg['sha']==asset['sha256']
    g,parts=decode(original);assert len(g['nodes'])==1 and set(g['nodes'][0])=={'mesh','name'}
    ids=matches[source];assert len(ids)==len(set(ids))==cfg['count']
    selected={p[2] for p in cfg['parts']};assert len(selected)==len(cfg['parts']) and selected.issubset(ids)
    assert len({p[0] for p in cfg['parts']})==len(cfg['parts']) and source not in {p[0] for p in cfg['parts']}
    remaining=[fid for fid in ids if fid not in selected]
    # A fully partitioned compound has no residual asset and must never encode an empty GLB.
    groups=([(source,cfg['remainingName'],remaining)] if remaining else [])+[(pid,name+' (기존 추정 모형)',[fid]) for pid,name,fid in cfg['parts']]
    anchor=asset['coordinate'];scale=6378137*math.cos(math.radians(anchor['lat']));lat0=math.log(math.tan(math.pi/4+math.radians(anchor['lat'])/2))
    def project(x,y,z=None):return scale*math.radians(x-anchor['lon']),-scale*(math.log(math.tan(math.pi/4+math.radians(y)/2))-lat0)
    db=sqlite3.connect(f'file:{ROOT}/data/buildings.sqlite?mode=ro',uri=True);shapes={};sources=[]
    for fid in ids:
        name,height,geo=db.execute('SELECT name,height_m,geometry FROM buildings WHERE id=?',(fid,)).fetchone();local=transform(project,shape(json.loads(geo)));shapes[fid]=local
        sources.append({'id':fid,'sourceName':name,'sourceHeightM':height,'localFootprint':local.__geo_interface__})
    db.close();polys=[unary_union([shapes[fid] for fid in subset]) for _,_,subset in groups];buffered=[p.buffer(.15) for p in polys]
    hulls=[unary_union([shapes[fid].convex_hull for fid in subset]).buffer(.15) for _,_,subset in groups]
    hull_triangles=0
    assignments=[];counts={pid:0 for pid,_,_ in groups};owners=[];vertices={};parent=[];maximum=0
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for primitive,attrs,indices in parts:
        result=[]
        for tri in attrs['POSITION'][indices]:
            outline=MultiPoint(tri[:,[0,2]]);candidates=[i for i,poly in enumerate(buffered) if poly.covers(outline)]
            if not candidates:
                candidates=[i for i,hull in enumerate(hulls) if hull.covers(outline)];hull_triangles+=1
            assert len(candidates)==1,('ambiguous/unowned triangle',source,candidates,tri.tolist())
            owner=candidates[0];result.append(owner);counts[groups[owner][0]]+=1
            maximum=max(maximum,max(polys[owner].distance(Point(float(v[0]),float(v[2]))) for v in tri))
            index=len(parent);parent.append(index);owners.append(owner)
            for v in tri:
                key=v.tobytes()
                if key in vertices:parent[find(index)]=find(vertices[key])
                else:vertices[key]=index
        assignments.append(np.array(result))
    components={}
    for i,owner in enumerate(owners):components.setdefault(find(i),set()).add(owner)
    assert all(len(v)==1 for v in components.values()),'Component crosses ownership'
    documents={};outputs=[]
    for i,(pid,name,subset) in enumerate(groups):
        data,stats=encode(g,parts,[a==i for a in assignments],pid);model=f'generic-corrections/{pid}.glb';documents[folder/model]=data
        new=copy.deepcopy(asset);new.update(stats,id=pid,model=model,name=name,nameKo=name,buildingCount=len(subset),footprintIds=subset,searchable=pid==source,residentialCompletionCredit=False)
        new.pop('householdCount',None)
        if pid=='fallback-prestige-126' or cfg.get('removeApartmentCode'):new.pop('apartmentCode',None)
        lo,hi=stats['bounds']['min'],stats['bounds']['max']
        def lon(x):return anchor['lon']+math.degrees(x/scale)
        def lat(z):return math.degrees(2*math.atan(math.exp(lat0-z/scale))-math.pi/2)
        new['geoBounds']=[lon(lo[0]),lat(hi[2]),lon(hi[0]),lat(lo[2])];new['measuredGlbDimensions']=stats['dimensions']
        new['genericCorrection']={'sourceId':source,'sourceSha256':cfg['sha'],'operation':'Exact triangle partition; unchanged vertex attributes, materials and original terrain anchor.'};outputs.append(new)
    assert sum(a['triangles'] for a in outputs)==asset['triangles']
    proof={'version':1,'sourceId':source,'sourceSha256':cfg['sha'],'sourceTriangles':asset['triangles'],'sourceCoordinate':anchor,'sourceFootprints':sources,'triangleCountsByGroup':counts,'groupFootprints':{pid:subset for pid,_,subset in groups},'vertexConnectedComponents':len(components),'crossGroupComponents':0,'ownershipToleranceM':.15,'ownershipMethod':'Full source polygon first; otherwise a uniquely covering union of individual source convex hulls. Legacy roofplant shrinking about an interior point can leave concave footprint bounds; original geometry is preserved, not repaired. Vertex-connected components cannot cross groups.','trianglesAssignedWithinUniqueSourceConvexHull':hull_triangles,'maximumVertexDistanceOutsideSourceFootprintM':maximum,'outputs':[{k:a[k] for k in ['id','model','sha256','bytes','triangles','bounds','footprintIds']} for a in outputs],'limits':cfg['limits']}
    documents[ROOT/f"docs/model-audit/{cfg['site']}-generic-split.json"]=(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode()
    return {'sourceId':source,'sourceSha256':cfg['sha'],'sourceFootprintIds':ids,'assets':outputs},documents,proof

def main(sites=None):
    folder=ROOT/'public/models';base=json.loads((folder/'manifest.json').read_text());matches=json.loads((folder/'footprint-matches.json').read_text());corrections=json.loads((folder/'generic-corrections.json').read_text());documents={}
    for cfg in CONFIGS:
        if sites and cfg['site'] not in sites:continue
        correction,files,proof=partition(cfg,folder,base,matches);documents.update(files)
        corrections['corrections']=[c for c in corrections['corrections'] if c['sourceId']!=cfg['source']]+[correction]
        print(json.dumps({k:v for k,v in proof.items() if k not in ['sourceFootprints','outputs']},ensure_ascii=False))
    documents[folder/'generic-corrections.json']=(json.dumps(corrections,ensure_ascii=False,indent=2)+'\n').encode()
    path=ROOT/'public/data/deployment-assets.json';deployment=json.loads(path.read_text())
    for file,data in documents.items():
        if file.is_relative_to(folder):deployment['files'][str(file.relative_to(ROOT))]=sha(data)
    documents[path]=(json.dumps(deployment,ensure_ascii=False,indent=2)+'\n').encode();replace_batch([],documents)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',action='append',choices=[cfg['site'] for cfg in CONFIGS],help='Publish only this site; repeat for several sites. Default: all configured sites.')
    main(parser.parse_args().site)
