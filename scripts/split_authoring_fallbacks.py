#!/usr/bin/env python3
"""Partition byte-exact authoring emissions when touching source polygons are ambiguous.

Every triangle must still agree with its source geometry and callers must compare
per-source attribute/material signatures before publishing any output.
"""
import copy
import json
import math
import sqlite3
import numpy as np
from shapely.geometry import shape, Point, MultiPoint
from shapely.ops import transform, unary_union
from split_caelitus_fallback import ROOT, decode, encode, sha

def partition(cfg, folder, base, matches, source_owners, authoring_proof):
    source=cfg['source'];asset=next(a for a in base['assets'] if a['id']==source)
    original=(folder/asset['model']).read_bytes();assert sha(original)==cfg['sha']==asset['sha256']
    assert authoring_proof['byteExact'] and authoring_proof['sha256']==sha(original), 'Exact authoring replay is required'
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
    hull_triangles=0; spatial_ambiguities=[]
    group_for_source={fid:i for i,(_,_,subset) in enumerate(groups) for fid in subset}
    assert set(group_for_source)==set(ids)
    assignments=[];counts={pid:0 for pid,_,_ in groups};owners=[];vertices={};parent=[];maximum=0
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for primitive,attrs,indices in parts:
        result=[]; emitted=source_owners[primitive['material']]
        assert len(emitted)==len(indices)
        for triangle_index,tri in enumerate(attrs['POSITION'][indices]):
            outline=MultiPoint(tri[:,[0,2]]);candidates=[i for i,poly in enumerate(buffered) if poly.covers(outline)]
            if not candidates:
                candidates=[i for i,hull in enumerate(hulls) if hull.covers(outline)];hull_triangles+=1
            source_fid=emitted[triangle_index]; owner=group_for_source[source_fid]
            assert owner in candidates, ('Replay owner is not supported by source geometry',source,source_fid,candidates)
            if len(candidates)>1: spatial_ambiguities.append({'material':primitive['material'],'triangleIndex':triangle_index,'sourceFootprintId':source_fid,'assignedGroup':groups[owner][0],'geometricCandidateGroups':[groups[c][0] for c in candidates]})
            result.append(owner);counts[groups[owner][0]]+=1
            maximum=max(maximum,max(polys[owner].distance(Point(float(v[0]),float(v[2]))) for v in tri))
            index=len(parent);parent.append(index);owners.append(owner)
            for v in tri:
                key=v.tobytes()
                if key in vertices:parent[find(index)]=find(vertices[key])
                else:vertices[key]=index
        assignments.append(np.array(result))
    components={}
    for i,owner in enumerate(owners):components.setdefault(find(i),set()).add(owner)
    cross_group_components=sum(len(v)>1 for v in components.values())
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
    proof={'version':1,'sourceId':source,'sourceSha256':cfg['sha'],'sourceTriangles':asset['triangles'],'sourceCoordinate':anchor,'sourceFootprints':sources,'triangleCountsByGroup':counts,'groupFootprints':{pid:subset for pid,_,subset in groups},'vertexConnectedComponents':len(components),'crossGroupComponents':cross_group_components,'authoringResolvedSpatialAmbiguities':spatial_ambiguities,'ownershipToleranceM':.15,'ownershipMethod':'Byte-exact authoring emission assigns each triangle to its original source feature. Every emission also lies in its source polygon or inherited convex-hull tolerance. Coincident vertices/shared boundaries may connect separate source features; they do not override exact original source ownership. Original geometry is preserved, not repaired.','trianglesAssignedWithinSourceConvexHull':hull_triangles,'sourceAuthoringReplay':authoring_proof,'maximumVertexDistanceOutsideSourceFootprintM':maximum,'outputs':[{k:a[k] for k in ['id','model','sha256','bytes','triangles','bounds','footprintIds']} for a in outputs],'limits':cfg['limits']}
    documents[ROOT/f"docs/model-audit/{cfg['site']}-generic-split.json"]=(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode()
    return {'sourceId':source,'sourceSha256':cfg['sha'],'sourceFootprintIds':ids,'assets':outputs},documents,proof
