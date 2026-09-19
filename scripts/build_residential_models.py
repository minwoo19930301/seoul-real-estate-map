"""Build a resumable batch of residential GLBs; publish the manifest last."""
import argparse
import collections
import concurrent.futures
import hashlib
import json
import math
import os
import sqlite3
from pathlib import Path
import numpy as np
from shapely.geometry import shape
from shapely.ops import transform, unary_union
from build_district_landmarks import Mesh, projected, unprojected, raw_asset_records
from build_civic_models import _atomic_write, _publish_batch
from residential_facade import residential_geometry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'public/models'
CACHE = ROOT/'data/model-source/residential-batch'
FALLBACK_FLOORS = {'villa':4,'apartment':5,'mixed-use':8,'officetel':10}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fingerprint(candidates, database_path=None):
    """Hash the retained rows used by geometry, including changes in SQLite WAL."""
    database_path = database_path or ROOT/'data/buildings.sqlite'
    building_ids = sorted({bid for c in candidates for bid in c['buildingIds']})
    fingerprint = hashlib.sha256()
    db = sqlite3.connect(database_path.as_uri()+'?mode=ro', uri=True)
    try:
        db.execute('BEGIN')  # One consistent read snapshot for the whole batch.
        for bid in building_ids:
            row = db.execute(
                'SELECT id, geometry, height_m, min_height_m, num_floors '
                'FROM buildings WHERE id=?', (bid,),
            ).fetchone()
            if row is None:
                raise ValueError('Missing residential source row '+bid)
            fingerprint.update(json.dumps(row, separators=(',', ':')).encode())
            fingerprint.update(b'\n')
    finally:
        db.close()
    return fingerprint.hexdigest()


def height(row, kind, child_rows=()):
    if row['height_m'] is not None and math.isfinite(row['height_m']) and 0 < row['height_m'] < 1000:
        value = row['height_m']
        basis = 'retained source height; not independently measured'
    elif row['num_floors'] and 0 < row['num_floors'] <= 200:
        value = row['num_floors'] * 3.05
        basis = 'retained source floors multiplied by estimated 3.05m'
    else:
        child_heights = [r['height_m'] for r in child_rows if r['height_m'] and 0 < r['height_m'] < 1000]
        value = max(child_heights) if child_heights else FALLBACK_FLOORS[kind]*3.05
        basis = 'maximum retained child height used for unspecified parent area' if child_heights else f'illustrative {FALLBACK_FLOORS[kind]}-storey fallback; source height and floors unavailable'
    floors = row['num_floors'] if row['num_floors'] and 0 < row['num_floors'] <= 200 else max(1, round(value/3.05))
    return float(value), int(floors), basis


class RaisedMesh:
    """Honor explicit building-part minimum heights without moving its outline."""
    def __init__(self, mesh, base): self.mesh, self.base = mesh, base
    def solid(self, poly, bottom, top, body, roof):
        self.mesh.solid(poly, bottom+self.base, top+self.base, body, roof)
    def quad(self, material, a, b, c, d, color):
        self.mesh.quad(material, *((x,y+self.base,z) for x,y,z in (a,b,c,d)), color)


def polygons(geometry):
    if geometry.is_empty: return []
    if geometry.geom_type == 'Polygon': return [geometry]
    if hasattr(geometry,'geoms'): return [p for g in geometry.geoms for p in polygons(g)]
    return []


def build_one(job):
    candidate, build_key = job
    filename = candidate['id']+'.glb'
    cached_glb, cached_record = CACHE/filename, CACHE/(candidate['id']+'.json')
    if cached_glb.exists() and cached_record.exists():
        record = json.loads(cached_record.read_text())
        if record['buildKey']==build_key and digest(cached_glb)==record['asset']['sha256']:
            return record
    db = sqlite3.connect((ROOT/'data/buildings.sqlite').as_uri()+'?mode=ro',uri=True)
    db.row_factory = sqlite3.Row
    rows = {bid:dict(db.execute('SELECT * FROM buildings WHERE id=?',(bid,)).fetchone()) for bid in candidate['buildingIds']}
    parent = rows[candidate['buildingId']]
    child_rows = [r for bid,r in rows.items() if bid!=candidate['buildingId']]
    anchor = candidate['coordinate']['lon'],candidate['coordinate']['lat']
    local = lambda row:transform(lambda x,y,z=None:projected(x,y,anchor), shape(json.loads(row['geometry'])))
    parent_poly = local(parent)
    parent_height, parent_floors, parent_basis = height(parent,candidate['kind'],child_rows)
    pieces=[]
    child_polys=[]
    for child in child_rows:
        poly=local(child)
        if not poly.is_valid or poly.is_empty: raise ValueError('Invalid child geometry '+child['id'])
        top,floors,basis = height(child,candidate['kind']) if child['height_m'] or child['num_floors'] else (parent_height,parent_floors,'parent envelope estimate; child height and floors unavailable')
        base = max(0,float(child['min_height_m'] or 0))
        if base >= top: raise ValueError('Child minimum height reaches roof '+child['id'])
        pieces.append((poly,base,top,floors,basis,child['id']))
        child_polys.append(poly)
    remainder=parent_poly.difference(unary_union(child_polys)) if child_polys else parent_poly
    if not remainder.is_empty:pieces.append((remainder,0,parent_height,parent_floors,parent_basis,parent['id']))
    assert pieces
    mesh=Mesh();seed=int(hashlib.sha256(candidate['id'].encode()).hexdigest()[:8],16)
    evidence=[]
    # Taller source parts win where source polygons overlap. Lower source roofs
    # remain only on their uncovered footprint, avoiding coplanar duplicate roofs.
    covered=None
    for poly,base,top,floors,basis,bid in sorted(pieces,key=lambda p:(-p[2],p[5])):
        exposed=poly if covered is None else poly.difference(covered)
        covered=poly if covered is None else covered.union(poly)
        used=False
        for part in polygons(exposed):
            if part.area < .01: continue
            assert residential_geometry(RaisedMesh(mesh,base),part,top-base,floors,candidate['kind'],seed)
            used=True
        evidence.append({'buildingId':bid,'sourceHeightM':rows[bid]['height_m'],'sourceFloors':rows[bid]['num_floors'],'baseM':base,'topM':top,'heightBasis':basis,'hasExposedGeometry':used})
    positions=np.concatenate([np.asarray(p) for p in mesh.p if p])
    if abs(positions[:,1].min()) > .001: raise ValueError('No ground-contact source part '+candidate['id'])
    expected_top=float(positions[:,1].max())
    temp=cached_glb.with_suffix('.tmp.glb')
    stats,offset=mesh.save(temp)
    assert abs(stats['dimensions'][1]-expected_top)<.01
    os.replace(temp,cached_glb)
    lon,lat=unprojected(offset[0],offset[2],anchor)
    estimated=any(not str(e['heightBasis']).startswith('retained source height;') for e in evidence if e['hasExposedGeometry'])
    asset={'id':candidate['id'],'model':filename,'name':candidate['nameKo'],'nameKo':candidate['nameKo'],'district':candidate['district'],'category':'residential-'+candidate['kind'],'minZoom':16.5,'units':'metres',**stats,'rootTransform':'identity','coordinate':{'lon':lon,'lat':lat},'yawDegFromEast':0,'referenceUrl':candidate['sourceUrls'][0],'heightEstimated':estimated,'buildingCount':1,'footprintIds':candidate['buildingIds'],'modelingEstimates':{'facade':'Illustrative source-outline residential facade; not photo-surveyed','details':'docs/RESIDENTIAL_MODEL_DESIGN.md','heightBasis':[e['heightBasis'] for e in evidence if e['hasExposedGeometry']],'sourceRecord':'docs/residential-model-candidates.json'},'validation':{'noExternalResources':True}}
    if candidate.get('complex'):
        asset['apartmentCode']=candidate['complex']['code']
        asset['householdCount']=candidate['complex']['householdCount']
        asset['householdCountScope']='whole official complex; not this modeled building'
    record={'buildKey':build_key,'asset':asset,'evidence':{'id':candidate['id'],'buildingId':candidate['buildingId'],'parts':evidence}}
    _atomic_write(cached_record,(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n').encode())
    return record


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    provenance=ROOT/'docs/RESIDENTIAL_MODEL_PROVENANCE.json'
    assert not provenance.exists(), 'Batch already published; refusing to overwrite'
    mf=OUT/'manifest.json';original=mf.read_text();manifest=json.loads(original);raw=raw_asset_records(original)
    matches_path=OUT/'footprint-matches.json';matches=json.loads(matches_path.read_text());owned={b for v in matches.values() for b in v}
    candidates_path=ROOT/'docs/residential-model-candidates.json';candidates=json.loads(candidates_path.read_text())
    audit=json.loads((ROOT/'docs/RESIDENTIAL_SELECTION_AUDIT.json').read_text())
    assert digest(mf)==audit['baselineManifestSha256'] and len(candidates)==audit['newModels']
    assert not owned.intersection(b for c in candidates for b in c['buildingIds'])
    assert not {a['id'] for a in manifest['assets']}.intersection(c['id'] for c in candidates)
    assert len({c['id'] for c in candidates})==len(candidates)
    for a in manifest['assets']:assert digest(OUT/a['model'])==a['sha256'],a['id']
    old_records={a['id']:a for a in manifest['assets']}
    CACHE.mkdir(parents=True,exist_ok=True)
    source_hash=source_fingerprint(candidates)
    key=hashlib.sha256((digest(candidates_path)+source_hash+digest(Path(__file__))+digest(ROOT/'scripts/residential_facade.py')+digest(ROOT/'scripts/build_district_landmarks.py')).encode()).hexdigest()
    results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1,min(4,args.workers))) as pool:
        for index,record in enumerate(pool.map(build_one,((c,key) for c in candidates),chunksize=12),1):
            results.append(record)
            if index%200==0 or index==len(candidates):print(f'{index}/{len(candidates)} models ready',flush=True)
    if source_fingerprint(candidates)!=source_hash:
        raise ValueError('Residential source rows changed while building; rerun before publication')
    if args.prepare_only:return
    assert mf.read_text()==original,'Manifest changed while building'
    added=[r['asset'] for r in results]
    newmatches={**matches,**{a['id']:a['footprintIds'] for a in added}}
    meta={k:v for k,v in manifest.items() if k!='assets'}
    meta['residentialExpansion']={'count':len(added),'generator':'scripts/build_residential_models.py','provenance':'../../docs/RESIDENTIAL_MODEL_PROVENANCE.json'}
    meta['districtExpansion']['count']=sum(bool(a.get('district')) for a in manifest['assets']+added)
    prefix=json.dumps(meta,ensure_ascii=False,indent=2)[:-2]+',\n  "assets": [\n'
    entries=['    '+raw[a['id']] for a in manifest['assets']]+['    '+json.dumps(a,ensure_ascii=False,separators=(',',':')) for a in added]
    nexttext=prefix+',\n'.join(entries)+'\n  ]\n}\n'
    reread=raw_asset_records(nexttext);assert all(reread[k]==v for k,v in raw.items())
    proof={'generator':'scripts/build_residential_models.py','baselineModels':len(old_records),'newModels':len(added),'categories':dict(collections.Counter(c['kind'] for c in candidates)),'newBytes':sum(a['bytes'] for a in added),'newTriangles':sum(a['triangles'] for a in added),'preservedHashes':{a['id']:a['sha256'] for a in manifest['assets']},'sourceCandidateSha256':digest(candidates_path),'sourceInputSha256':source_hash,'assets':[r['evidence'] for r in results]}
    files={OUT/a['model']:(CACHE/a['model']).read_bytes() for a in added}
    metadata={matches_path:(json.dumps(newmatches,ensure_ascii=False,indent=2)+'\n').encode(),provenance:(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode(),mf:nexttext.encode()}
    _publish_batch(files,metadata,mf)
    print(json.dumps({k:v for k,v in proof.items() if k not in ('preservedHashes','assets')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
