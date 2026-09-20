"""Publish source-authored landmarks with explicit geometric replacement evidence.

The preserved catalog and GLBs remain immutable. Only covered source footprints
and generic models are superseded; no circular landmark exclusion zones are used.
"""
from pathlib import Path
import json, math, hashlib, shutil, sqlite3, struct
import numpy as np
from shapely.geometry import shape, Polygon, box, mapping
from shapely.ops import unary_union, transform

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / 'public/models'
STAGE = ROOT / 'data/model-source'
sha = lambda b: hashlib.sha256(b).hexdigest()

def glb_geometry(path):
    blob = path.read_bytes()
    length = struct.unpack_from('<I', blob, 12)[0]
    doc = json.loads(blob[20:20+length])
    binary = memoryview(blob)[28+length:]
    types = {5121: 'u1',5123:'<u2',5125:'<u4',5126:'<f4'}
    def accessor(index):
        a=doc['accessors'][index]; v=doc['bufferViews'][a['bufferView']]
        n={'VEC3':3,'SCALAR':1}[a['type']]; dtype=np.dtype(types[a['componentType']])
        return np.ndarray((a['count'],n),dtype=dtype,buffer=binary,
            offset=v.get('byteOffset',0)+a.get('byteOffset',0),
            strides=(v.get('byteStride',n*dtype.itemsize),dtype.itemsize)).copy()
    triangles=[]; allpoints=[]
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            p=accessor(primitive['attributes']['POSITION']);allpoints.append(p)
            ids=accessor(primitive['indices']).ravel() if 'indices' in primitive else np.arange(len(p))
            triangles.append(p[ids].reshape(-1,3,3))
    # Both builders bake transforms into vertex positions. Reject unhandled nodes.
    for node in doc.get('nodes',[]):
        if any(k in node for k in ['matrix','translation','rotation','scale']):
            raise ValueError('Unexpected unbaked node transform: '+str(path))
    points=np.vstack(allpoints); tri=np.concatenate(triangles)
    normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    area=np.abs(normal[:,1])*.5
    selected=(tri[:,:,1].min(axis=1)>3)&(area>.08)
    polygons=[Polygon(t[:,[0,2]]) for t in tri[selected]]
    coverage=unary_union(polygons) if polygons else Polygon()
    return points.min(axis=0).tolist(),points.max(axis=0).tolist(),coverage,len(tri),len(doc.get('materials',[]))

def main():
    adapted=STAGE/'flight-adapted'; report=json.loads((adapted/'report.json').read_text())
    original=json.loads((STAGE/'flight-current/report.json').read_text())
    original_by_id={a['id']:a for a in original['assets']}
    placements=json.loads((ROOT/'scripts/reference_placements.json').read_text())
    legacy=json.loads((PUB/'manifest.json').read_text())['assets']
    matches=json.loads((PUB/'footprint-matches.json').read_text())
    building=sqlite3.connect('file:'+str(ROOT/'data/buildings.sqlite')+'?mode=ro',uri=True)
    survey=sqlite3.connect('file:'+str(STAGE/'residential-survey/selection.sqlite')+'?mode=ro',uri=True)
    assets=[]; evidence=[]; coverage_by_id={}; shapes_by_id={}; survey_shapes={}
    def publish(source, model, coordinate, name, model_id, metadata):
        lo,hi,coverage,triangles,materials=glb_geometry(source)
        if abs(lo[1])>.01:raise ValueError('Nonzero GLB floor '+model_id)
        lon,lat=coordinate; sx=111319.49079327358*math.cos(math.radians(lat));sy=111319.49079327358
        geocover=transform(lambda x,z:(lon+np.asarray(x)/sx,lat-np.asarray(z)/sy),coverage)
        bounds=[lon+lo[0]/sx,lat-hi[2]/sy,lon+hi[0]/sx,lat-lo[2]/sy]
        dest=PUB/model;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        asset={'id':model_id,'nameKo':name,'model':model,'coordinate':{'lon':lon,'lat':lat},
            'dimensions':[hi[i]-lo[i] for i in range(3)],'yawDegFromEast':0,'heightDatum':'metres; independent terrain anchor',
            'sha256':sha(dest.read_bytes()),'quality':'reference','minZoom':15,'geoBounds':bounds,
            'footprintIds':[],'supersedes':[],**metadata}
        assets.append(asset);coverage_by_id[model_id]=geocover
        evidence.append({'id':model_id,'triangles':triangles,'materials':materials,'bytes':dest.stat().st_size,
            'coverageMethod':'union of projected actual model triangles above 3m, excluding ground plane',
            'matchedFootprints':[],'supersedes':[]})
        return asset
    for adapted_asset in report['assets']:
        key=adapted_asset['id']; source=original_by_id[key]; override=placements.get(key,{})
        anchor=override.get('coordinate',[source['moduleCoordinate']['lon'],source['moduleCoordinate']['lat']])
        offset=adapted_asset.get('exportOffsetFromSource',source['exportOffsetFromSource'])
        # The adapted report offset is expressed in the final source metre frame.
        lon,lat=anchor; coordinate=[lon+offset[0]/(111319.49079327358*math.cos(math.radians(lat))),lat-offset[2]/111319.49079327358]
        publish(adapted/adapted_asset['model'],'reference-flight/'+key+'.glb',coordinate,source['nameKo'],'reference-flight-'+key,
            {'referenceUrl':source['sourceUrl'],'district':source['district'],
             'category':override.get('category','landmark'),'groundOffsetM':offset[1],
             'sourceRecord':{'provider':'Seoul Flight authored landmark','revision':original['sourceRevision'],
                 'sourceFile':source['sourceFile'],'sourceFileSha256':source['sourceFileSha256'],
                 'coordinateBasis':override.get('basis','source module author coordinate; approximate placement'),
                 'adaptation':adapted_asset.get('adaptationRecipe',{}),
                 'accuracy':'Authored illustrative reconstruction; not a measured architectural survey'},
             'placementReview':override})
    maple=json.loads((STAGE/'maple-xi-current/modeling-recipe.json').read_text())
    maple_site=shape(maple['siteMaskGeoJSON'])
    for src in maple['assets']:
        coord=src['coordinate'];coord=[coord['lon'],coord['lat']] if isinstance(coord,dict) else coord
        publish(STAGE/'maple-xi-current'/src['model'],'maple-xi/'+Path(src['model']).name,coord,('메이플자이 유치원 계획안' if src['id'].endswith('kindergarten') else src['nameKo']),src['id'],
            {'referenceUrl':src['referenceUrl'],'district':'서초구','category':('k12-school' if src['id'].endswith('kindergarten') else 'bridge' if src['id'].endswith('maple-road') else 'apartment'),'minZoom':16,
             'searchable':False,'sourceRecord':{'provider':'GS Xi official plan and completed-building photographs','sources':maple['sources'],'recipe':src['recipe'],'georeference':maple['georeference'],'accuracy':'Plan-traced and photo-referenced; individual heights and fine details are estimates'},
             'groundOffsetM':src.get('groundOffsetM',0)})
    # Only geometric source matches can hide retained solids. One asset owns each.
    claims={}; survey_claims={}
    for asset,ev in zip(assets,evidence):
        model_id=asset['id']; coverage=coverage_by_id[model_id]
        scope=maple_site if asset['model'].startswith('maple-xi/') else coverage
        if scope.is_empty:continue
        w,s,e,n=scope.bounds
        for id,name,geom in building.execute('SELECT b.id,b.name,b.geometry FROM building_index i JOIN buildings b ON b.rowid=i.rowid WHERE i.maxx>=? AND i.minx<=? AND i.maxy>=? AND i.miny<=?',(w,e,s,n)):
            polygon=shape(json.loads(geom));shapes_by_id[id]=polygon
            fraction=scope.intersection(polygon).area/polygon.area if polygon.area else 0
            if fraction<.65:continue
            if scope is maple_site:
                cx,cy=polygon.centroid.coords[0];dist=math.hypot((cx-asset['coordinate']['lon'])*.79,cy-asset['coordinate']['lat']);score=2-dist
            else:score=fraction
            if id not in claims or score>claims[id][0]:claims[id]=(score,model_id,fraction,name)
        for id,geom,footprints in survey.execute('SELECT c.id,c.geometry,c.footprints FROM selected_index i JOIN candidates c ON c.rowid=i.rowid WHERE i.maxx>=? AND i.minx<=? AND i.maxy>=? AND i.miny<=?',(w,e,s,n)):
            polygon=shape(json.loads(geom));survey_shapes[id]=polygon
            fraction=scope.intersection(polygon).area/polygon.area if polygon.area else 0
            if fraction<.65:continue
            if scope is maple_site:
                cx,cy=polygon.centroid.coords[0];score=2-math.hypot((cx-asset['coordinate']['lon'])*.79,cy-asset['coordinate']['lat'])
            else:score=fraction
            if id not in survey_claims or score>survey_claims[id][0]:survey_claims[id]=(score,model_id,fraction,json.loads(footprints))
    by_id={a['id']:a for a in assets};ev_id={a['id']:a for a in evidence}
    for key, placement in placements.items():
        for fid in placement.get('explicitFootprintIds', []):
            row=building.execute('SELECT name,geometry FROM buildings WHERE id=?',(fid,)).fetchone()
            if not row:raise ValueError('Missing explicit source identity '+fid)
            owner='reference-flight-'+key
            shape_bounds=shape(json.loads(row[1])).bounds
            if not box(*by_id[owner]['geoBounds']).buffer(.0007).intersects(box(*shape_bounds)):raise ValueError('Explicit source identity is outside authored site')
            claims[fid]=(1,owner,None,row[0])
            ev_id[owner].setdefault('explicitIdentityMatches',[]).append({'id':fid,'name':row[0],'basis':placement['identityMatchBasis']})
    for fid,(_,owner,fraction,name) in claims.items():
        by_id[owner]['footprintIds'].append(fid);ev_id[owner]['matchedFootprints'].append({'id':fid,'name':name,'coveredFraction':round(fraction,4) if fraction is not None else None})
    for generic in legacy:
        ids=matches.get(generic['id'],[])
        owned=[claims[f][1] for f in ids if f in claims]
        # Never remove an entire retained multi-building model for one covered wing.
        if ids and len(owned)==len(ids):
            owner=max(set(owned),key=owned.count);by_id[owner]['supersedes'].append(generic['id'])
    for sid,(_,owner,fraction,footprints) in survey_claims.items():
        by_id[owner]['supersedes'].append(sid)
        for fid in footprints:
            if fid in claims and claims[fid][1]==owner and fid not in by_id[owner]['footprintIds']:by_id[owner]['footprintIds'].append(fid)
    for asset in assets:
        asset['footprintIds'].sort();asset['supersedes'].sort();ev_id[asset['id']]['supersedes']=asset['supersedes']
    manifest={'version':1,'sourceRevision':original['sourceRevision'],'assets':assets,
        'places':[{'id':'reference:maple-xi','name':'메이플자이','subtitle':'2025년 입주 · 공식 배치도와 실제 외관을 참고한 29개 동',
                   'center':list(maple_site.centroid.coords[0]),'zoom':16.4,'household_count':3307,
                   'supersedesPlaceIds':['seoul-apartment:A13790730','seoul-apartment:A13790708','seoul-apartment:A10020557','osm:way/998065952','osm:way/998065953'],'source_url':maple.get('referenceUrl',assets[-1]['referenceUrl'])}]}
    (PUB/'reference-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    proof={'sourceRevision':original['sourceRevision'],'models':len(assets),'flightModels':len(report['assets']),
        'mapleModels':len(maple['assets']),'triangles':sum(e['triangles'] for e in evidence),'bytes':sum(e['bytes'] for e in evidence),
        'preservedCatalogModels':113123,'sourceCatalogUnchanged':True,'assets':evidence}
    (ROOT/'docs/REFERENCE_MODEL_INTEGRATION.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in proof.items() if k!='assets'}))

if __name__=='__main__':main()
