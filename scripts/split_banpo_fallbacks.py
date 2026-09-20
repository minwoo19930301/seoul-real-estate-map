#!/usr/bin/env python3
"""Partition archived fallback meshes for independently reviewed Banpo towers."""
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
     'remainingName':'래미안원베일리 나머지14동 (기존 추정 모형)',
     'parts':[
         ('fallback-onebailey-101','래미안원베일리 101동','4348b83d-8074-41db-b6fd-2a0220302d25'),
         ('fallback-onebailey-102','래미안원베일리 102동','18482853-b439-4fbc-a964-bbeb2c81c7cc'),
         ('fallback-onebailey-121','래미안원베일리 121동','37167a22-89d6-41be-9768-691ce24bfc6b'),
         ('fallback-onebailey-122','래미안원베일리 122동','1035924e-30e1-4e29-b8d8-894e48fd550e'),
         ('fallback-onebailey-123','래미안원베일리 123동','9bf33339-8503-4c4d-a4a2-e34b800eb8a7')],
     'limits':['The archived compound contains19of23officialresidentialbuildings. This operation preservesonlythose19; it does not claim the entirecomplex is modeled.','Officialnumberplan andexactbuildingregister identify101,102,121,122,123. Sourcefallbackgeometry/heights remain unchanged; no photo-completion credit.']},
    {'site':'onepentas','source':'apt-a10022556','sha':'4f301eb1e259da07a9580dc86256b044a0e55fcfe654ad5401ad3eacdf8e00f7','count':7,
     'remainingName':'래미안원펜타스 101–104동 (기존 추정 모형)',
     'parts':[
         ('fallback-onepentas-105','래미안원펜타스 105동','1d28aa9d-3ad6-4b50-a32c-a7bc75f3ebcf'),
         ('fallback-onepentas-106','래미안원펜타스 106동','dad2c16e-28a1-4c1c-b786-91be69693ca6'),
         ('fallback-prestige-126','래미안퍼스티지 126동','b21842a2-9832-4a21-bcc5-1c571f309556')],
     'limits':['OfficialOnePentas641apartments/6buildings excludes theneighbor126. The126source23F65m matches officialregister10231100193383 atBanpodong18-1/Banpodaero275,23F65.3m44households:RaemianPrestige. OneBailey126is1Famenityandnotthisbuilding.','The sixOnePentassourcefallbackheights are estimated andnotcorrectedbythispartition; newphoto modelsreplaceindependently. No photomodelingcredit is claimed.']}
]

def partition(cfg, folder, base, matches):
    source=cfg['source'];asset=next(a for a in base['assets'] if a['id']==source)
    original=(folder/asset['model']).read_bytes();assert sha(original)==cfg['sha']==asset['sha256']
    g,parts=decode(original);assert len(g['nodes'])==1 and set(g['nodes'][0])=={'mesh','name'}
    ids=matches[source];assert len(ids)==cfg['count']
    selected={p[2] for p in cfg['parts']};assert selected.issubset(ids)
    groups=[(source,cfg['remainingName'],[fid for fid in ids if fid not in selected])]+[(pid,name+' (기존 추정 모형)',[fid]) for pid,name,fid in cfg['parts']]
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
        if pid=='fallback-prestige-126':new.pop('apartmentCode',None)
        lo,hi=stats['bounds']['min'],stats['bounds']['max']
        def lon(x):return anchor['lon']+math.degrees(x/scale)
        def lat(z):return math.degrees(2*math.atan(math.exp(lat0-z/scale))-math.pi/2)
        new['geoBounds']=[lon(lo[0]),lat(hi[2]),lon(hi[0]),lat(lo[2])];new['measuredGlbDimensions']=stats['dimensions']
        new['genericCorrection']={'sourceId':source,'sourceSha256':cfg['sha'],'operation':'Exact triangle partition; unchanged vertex attributes, materials and original terrain anchor.'};outputs.append(new)
    assert sum(a['triangles'] for a in outputs)==asset['triangles']
    proof={'version':1,'sourceId':source,'sourceSha256':cfg['sha'],'sourceTriangles':asset['triangles'],'sourceCoordinate':anchor,'sourceFootprints':sources,'triangleCountsByGroup':counts,'groupFootprints':{pid:subset for pid,_,subset in groups},'vertexConnectedComponents':len(components),'crossGroupComponents':0,'ownershipToleranceM':.15,'ownershipMethod':'Full source polygon first; otherwise a uniquely covering union of individual source convex hulls. Legacy roofplant shrinking about an interior point can leave concave footprint bounds; original geometry is preserved, not repaired. Vertex-connected components cannot cross groups.','trianglesAssignedWithinUniqueSourceConvexHull':hull_triangles,'maximumVertexDistanceOutsideSourceFootprintM':maximum,'outputs':[{k:a[k] for k in ['id','model','sha256','bytes','triangles','bounds','footprintIds']} for a in outputs],'limits':cfg['limits']}
    documents[ROOT/f"docs/model-audit/{cfg['site']}-generic-split.json"]=(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode()
    return {'sourceId':source,'sourceSha256':cfg['sha'],'sourceFootprintIds':ids,'assets':outputs},documents,proof

def main():
    folder=ROOT/'public/models';base=json.loads((folder/'manifest.json').read_text());matches=json.loads((folder/'footprint-matches.json').read_text());corrections=json.loads((folder/'generic-corrections.json').read_text());documents={}
    for cfg in CONFIGS:
        correction,files,proof=partition(cfg,folder,base,matches);documents.update(files)
        corrections['corrections']=[c for c in corrections['corrections'] if c['sourceId']!=cfg['source']]+[correction]
        print(json.dumps({k:v for k,v in proof.items() if k not in ['sourceFootprints','outputs']},ensure_ascii=False))
    documents[folder/'generic-corrections.json']=(json.dumps(corrections,ensure_ascii=False,indent=2)+'\n').encode()
    path=ROOT/'public/data/deployment-assets.json';deployment=json.loads(path.read_text())
    for file,data in documents.items():
        if file.is_relative_to(folder):deployment['files'][str(file.relative_to(ROOT))]=sha(data)
    documents[path]=(json.dumps(deployment,ensure_ascii=False,indent=2)+'\n').encode();replace_batch([],documents)
if __name__=='__main__':main()
