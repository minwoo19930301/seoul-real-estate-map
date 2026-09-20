#!/usr/bin/env python3
"""Separate Hyperion II's four apartment towers from its two officetel towers."""
import copy
import json
import math
from pathlib import Path
import sqlite3
import numpy as np
from shapely.geometry import shape, Point, MultiPoint
from shapely.ops import transform, unary_union
from split_caelitus_fallback import ROOT, decode, encode, sha
from publish_bespoke_models import replace_batch

SOURCE = 'apt-a15805111'
TARGETS = {'e75bec98-4829-45f0-ac3e-a2b73a4d8999', '13e9a720-1daf-4c3d-89a0-5d3d53b70139'}
EXPECTED = 'f92d9da98ba1324d2296e9a47cc012b9db34d48cdf8c06cc16c4898c1d8c564f'
def main():
    folder=ROOT/'public/models';base=json.loads((folder/'manifest.json').read_text());matches=json.loads((folder/'footprint-matches.json').read_text());asset=next(a for a in base['assets'] if a['id']==SOURCE)
    original=(folder/asset['model']).read_bytes();assert sha(original)==EXPECTED==asset['sha256']
    g,parts=decode(original);assert len(g['nodes'])==1 and set(g['nodes'][0])=={'mesh','name'} and len(parts)==3
    ids=matches[SOURCE];assert len(ids)==6 and TARGETS.issubset(ids)
    anchor=asset['coordinate'];scale=6378137*math.cos(math.radians(anchor['lat']));lat0=math.log(math.tan(math.pi/4+math.radians(anchor['lat'])/2))
    def project(x,y,z=None):return scale*math.radians(x-anchor['lon']),-scale*(math.log(math.tan(math.pi/4+math.radians(y)/2))-lat0)
    db=sqlite3.connect(f'file:{ROOT}/data/buildings.sqlite?mode=ro',uri=True);polys=[];sources=[]
    for id in ids:
        name,height,geo=db.execute('SELECT name,height_m,geometry FROM buildings WHERE id=?',(id,)).fetchone();local=transform(project,shape(json.loads(geo)));polys.append(local)
        sources.append({'id':id,'sourceName':name,'sourceHeightM':height,'localFootprint':local.__geo_interface__})
    db.close();polys=[unary_union([poly for fid,poly in zip(ids,polys) if fid not in TARGETS]),unary_union([poly for fid,poly in zip(ids,polys) if fid in TARGETS])];groups=['apartments','officetels'];assignments=[];counts={i:0 for i in groups};components={}; max_distance=0
    # Vertex-connected components must stay within the apartment or officetel ownership group.
    owners=[];vertices={};parent=[]
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for p,attrs,indices in parts:
        result=[]
        for tri in attrs['POSITION'][indices]:
            outline=MultiPoint(tri[:,[0,2]]); candidates=[i for i,poly in enumerate(polys) if poly.buffer(.15).covers(outline)]
            assert len(candidates)==1,('ambiguous/unowned triangle',candidates,tri.tolist())
            owner=candidates[0];result.append(owner);counts[groups[owner]]+=1
            max_distance=max(max_distance,max(polys[owner].distance(Point(float(v[0]),float(v[2]))) for v in tri))
            index=len(parent);parent.append(index);owners.append(owner)
            for v in tri:
                key=v.tobytes()
                if key in vertices:parent[find(index)]=find(vertices[key])
                else:vertices[key]=index
        assignments.append(np.array(result))
    for i,owner in enumerate(owners):components.setdefault(find(i),set()).add(owner)
    assert all(len(v)==1 for v in components.values()),'Connected component crosses group ownership'
    outputs=[];documents={};target_index=1
    for id,subset,name in [(SOURCE,[i for i in ids if i not in TARGETS],'목동현대하이페리온2차 아파트 201–204동 (기존 추정 모형)'),('fallback-hyperion-ii-officetels',[i for i in ids if i in TARGETS],'목동현대하이페리온2차 오피스텔 205·206동 (기존 추정 모형)')]:
        masks=[a!=target_index if id==SOURCE else a==target_index for a in assignments]
        data,stats=encode(g,parts,masks,id); model=f'generic-corrections/{id}.glb';documents[folder/model]=data
        new=copy.deepcopy(asset);new.update(stats,id=id,model=model,name=name,nameKo=name,buildingCount=len(subset),footprintIds=subset,searchable=id==SOURCE)
        low,high=stats['bounds']['min'],stats['bounds']['max']
        def longitude(x):return anchor['lon']+math.degrees(x/scale)
        def latitude(z):return math.degrees(2*math.atan(math.exp(lat0-z/scale))-math.pi/2)
        new['geoBounds']=[longitude(low[0]),latitude(high[2]),longitude(high[0]),latitude(low[2])]
        new['measuredGlbDimensions']=stats['dimensions'];new['genericCorrection']={'sourceId':SOURCE,'sourceSha256':EXPECTED,'operation':'Exact triangle partition; unchanged vertex attributes, materials and original terrain anchor.'}
        if id!=SOURCE:
            for k in ['householdCount','apartmentCode']:new.pop(k,None)
            new['category']='officetel'
            new['residentialCompletionCredit']=False
        outputs.append(new)
    assert sum(x['triangles'] for x in outputs)==asset['triangles']
    correction=json.loads((folder/'generic-corrections.json').read_text())
    correction['corrections']=[c for c in correction['corrections'] if c['sourceId']!=SOURCE]+[{'sourceId':SOURCE,'sourceSha256':EXPECTED,'sourceFootprintIds':ids,'assets':outputs}]
    proof={'version':1,'sourceId':SOURCE,'sourceSha256':EXPECTED,'sourceTriangles':asset['triangles'],'sourceCoordinate':anchor,'sourceFootprints':sources,'triangleCountsByGroup':counts,'groupFootprints':{'apartments':[i for i in ids if i not in TARGETS],'officetels':[i for i in ids if i in TARGETS]},'vertexConnectedComponents':len(components),'crossGroupComponents':0,'ownershipToleranceM':.15,'maximumVertexDistanceOutsideSourceFootprintM':max_distance,'outputs':[{k:a[k] for k in ['id','model','sha256','bytes','triangles','bounds','footprintIds']} for a in outputs],'limits':['No new photo modeling or completion credit. Official building-register records distinguish apartments 201–204 (140+156+124+156=576 households) from officetels 205–206 (zero apartment households). Preserved original geometry is still an estimated fallback, not a photo-derived model.','Both partitions deliberately retain the original anchor and vertex positions, preserving world geometry and original shared terrain datum.']}
    documents[folder/'generic-corrections.json']=(json.dumps(correction,ensure_ascii=False,indent=2)+'\n').encode()
    documents[ROOT/'docs/model-audit/hyperion-ii-generic-split.json']=(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode()
    deployment_path=ROOT/'public/data/deployment-assets.json'
    deployment=json.loads(deployment_path.read_text())
    for path,data in documents.items():
        if path.is_relative_to(folder): deployment['files'][str(path.relative_to(ROOT))]=sha(data)
    documents[deployment_path]=(json.dumps(deployment,ensure_ascii=False,indent=2)+'\n').encode()
    replace_batch([],documents)
    print(json.dumps({k:v for k,v in proof.items() if k not in ['sourceFootprints','outputs']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
