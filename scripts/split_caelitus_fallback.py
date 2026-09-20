#!/usr/bin/env python3
"""Partition an erroneously matched generic compound; never rebuild its geometry."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import struct
import numpy as np
from shapely.geometry import shape, Point, MultiPoint
from shapely.ops import transform
from publish_bespoke_models import replace_batch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'apt-a14003002'
TARGET = '805bb192-2c3d-473f-b645-1eca99731876'
EXPECTED = '5494b70faff113da6d2decc3e11ba1eaae690d41204b11ee109e48dd86f6472a'
DTYPES = {5121: np.dtype('u1'), 5123: np.dtype('<u2'), 5125: np.dtype('<u4'), 5126: np.dtype('<f4')}
WIDTHS = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4}
def sha(b): return hashlib.sha256(b).hexdigest()
def decode(data):
    size, = struct.unpack_from('<I', data, 12)
    g = json.loads(data[20:20+size]); binary = data[28+size:]
    def array(i):
        a = g['accessors'][i]; v = g['bufferViews'][a['bufferView']]
        assert 'byteStride' not in v and 'sparse' not in a
        return np.frombuffer(binary, DTYPES[a['componentType']], a['count']*WIDTHS[a['type']], v.get('byteOffset', 0)+a.get('byteOffset', 0)).reshape(a['count'], WIDTHS[a['type']]).copy()
    return g, [(p, {k:array(i) for k,i in p['attributes'].items()}, array(p['indices']).ravel().reshape(-1,3)) for p in g['meshes'][0]['primitives']]
def encode(g, parts, selectors, name):
    out = copy.deepcopy(g); out['accessors']=[];out['bufferViews']=[];out['meshes'][0]['primitives']=[];out['nodes'][0]['name']=name
    binary=bytearray(); positions=[]; count=0
    def add(a, template, target):
        while len(binary)%4: binary.append(0)
        view=len(out['bufferViews']);out['bufferViews'].append({'buffer':0,'byteOffset':len(binary),'byteLength':a.nbytes,'target':target});binary.extend(a.tobytes())
        accessor={k:v for k,v in template.items() if k not in ['bufferView','byteOffset','min','max','count']};accessor.update(bufferView=view,count=len(a))
        if accessor['type']=='VEC3': accessor.update(min=a.min(axis=0).tolist(),max=a.max(axis=0).tolist())
        i=len(out['accessors']);out['accessors'].append(accessor);return i
    for (p,attrs,indices), mask in zip(parts,selectors):
        selected=indices[mask];assert len(selected)
        used,inverse=np.unique(selected.ravel(),return_inverse=True)
        new={'attributes':{},'material':p['material'],'mode':4}
        for k, a in attrs.items(): new['attributes'][k]=add(a[used],g['accessors'][p['attributes'][k]],34962)
        new['indices']=add(inverse.astype(DTYPES[g['accessors'][p['indices']]['componentType']]).reshape(-1,1),g['accessors'][p['indices']],34963)
        out['meshes'][0]['primitives'].append(new);positions.append(attrs['POSITION'][used]);count+=len(selected)
    while len(binary)%4: binary.append(0)
    out['buffers']=[{'byteLength':len(binary)}]
    js=json.dumps(out,separators=(',',':')).encode();js+=b' '*((-len(js))%4)
    data=struct.pack('<III',0x46546c67,2,28+len(js)+len(binary))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(binary),0x004e4942)+binary
    pos=np.concatenate(positions); low=pos.min(axis=0);high=pos.max(axis=0)
    return data,dict(bounds={'min':low.tolist(),'max':high.tolist()},dimensions=(high-low).tolist(),triangles=count,drawCalls=len(parts),bytes=len(data),sha256=sha(data))
def main():
    folder=ROOT/'public/models';base=json.loads((folder/'manifest.json').read_text());matches=json.loads((folder/'footprint-matches.json').read_text());asset=next(a for a in base['assets'] if a['id']==SOURCE)
    original=(folder/asset['model']).read_bytes();assert sha(original)==EXPECTED==asset['sha256']
    g,parts=decode(original);assert len(g['nodes'])==1 and set(g['nodes'][0])=={'mesh','name'} and len(parts)==3
    ids=matches[SOURCE];assert len(ids)==7 and TARGET in ids
    anchor=asset['coordinate'];scale=6378137*math.cos(math.radians(anchor['lat']));lat0=math.log(math.tan(math.pi/4+math.radians(anchor['lat'])/2))
    def project(x,y,z=None):return scale*math.radians(x-anchor['lon']),-scale*(math.log(math.tan(math.pi/4+math.radians(y)/2))-lat0)
    db=sqlite3.connect(f'file:{ROOT}/data/buildings.sqlite?mode=ro',uri=True);polys=[];sources=[]
    for id in ids:
        name,height,geo=db.execute('SELECT name,height_m,geometry FROM buildings WHERE id=?',(id,)).fetchone();local=transform(project,shape(json.loads(geo)));polys.append(local)
        sources.append({'id':id,'sourceName':name,'sourceHeightM':height,'localFootprint':local.__geo_interface__})
    db.close();assignments=[];counts={i:0 for i in ids};components={}; max_distance=0
    # Vertex-connected components are independently checked against source footprints.
    owners=[];vertices={};parent=[]
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for p,attrs,indices in parts:
        result=[]
        for tri in attrs['POSITION'][indices]:
            outline=MultiPoint(tri[:,[0,2]]); candidates=[i for i,poly in enumerate(polys) if poly.buffer(.65).covers(outline)]
            assert len(candidates)==1,('ambiguous/unowned triangle',candidates,tri.tolist())
            owner=candidates[0];result.append(owner);counts[ids[owner]]+=1
            max_distance=max(max_distance,max(polys[owner].distance(Point(float(v[0]),float(v[2]))) for v in tri))
            index=len(parent);parent.append(index);owners.append(owner)
            for v in tri:
                key=v.tobytes()
                if key in vertices:parent[find(index)]=find(vertices[key])
                else:vertices[key]=index
        assignments.append(np.array(result))
    for i,owner in enumerate(owners):components.setdefault(find(i),set()).add(owner)
    assert all(len(v)==1 for v in components.values()),'Connected component crosses building ownership'
    outputs=[];documents={};target_index=ids.index(TARGET)
    for id,subset,name in [(SOURCE,[i for i in ids if i!=TARGET],'이촌왕궁 및 인접 점보아파트 (기존 6동)'),('fallback-caelitus-101',[TARGET],'래미안 첼리투스 101동 (기존 추정 모형)')]:
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
        outputs.append(new)
    assert sum(x['triangles'] for x in outputs)==asset['triangles']
    correction={'version':1,'corrections':[{'sourceId':SOURCE,'sourceSha256':EXPECTED,'sourceFootprintIds':ids,'assets':outputs}]}
    proof={'version':1,'sourceId':SOURCE,'sourceSha256':EXPECTED,'sourceTriangles':asset['triangles'],'sourceCoordinate':anchor,'sourceFootprints':sources,'triangleCountsByFootprint':counts,'vertexConnectedComponents':len(components),'crossBuildingComponents':0,'maximumVertexDistanceOutsideSourceFootprintM':max_distance,'outputs':[{k:a[k] for k in ['id','model','sha256','bytes','triangles','bounds','footprintIds']} for a in outputs],'limits':['No new photo modeling or completion credit. Six retained neighbors include a separately named Jumbo apartment; original management-compound identity was not re-certified.','Both partitions deliberately retain the original anchor and vertex positions, preserving world geometry and original shared terrain datum.']}
    documents[folder/'generic-corrections.json']=(json.dumps(correction,ensure_ascii=False,indent=2)+'\n').encode()
    documents[ROOT/'docs/model-audit/caelitus-generic-split.json']=(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode()
    deployment_path=ROOT/'public/data/deployment-assets.json'
    deployment=json.loads(deployment_path.read_text())
    for path,data in documents.items():
        if path.is_relative_to(folder): deployment['files'][str(path.relative_to(ROOT))]=sha(data)
    documents[deployment_path]=(json.dumps(deployment,ensure_ascii=False,indent=2)+'\n').encode()
    replace_batch([],documents)
    print(json.dumps({k:v for k,v in proof.items() if k not in ['sourceFootprints','outputs']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
