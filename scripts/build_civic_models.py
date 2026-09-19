"""Append source-based civic/company GLBs and explicitly upgrade the existing City Hall."""
import collections,hashlib,json,os,sqlite3,tempfile
from pathlib import Path
from shapely.geometry import shape
from shapely.ops import transform
from build_district_landmarks import Mesh,projected,unprojected,raw_asset_records
from civic_facade import civic_geometry
from public_facade import public_facade
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'public/models'

def _atomic_write(path, data):
    """Replace one file only after its sibling temporary file is complete."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.'+path.name+'.', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _publish_batch(model_files, metadata, manifest_path):
    """Publish immutable GLBs, then metadata, switching the manifest last.

    On a handled failure restore metadata before deleting any new GLBs. If
    restoration itself fails, retain the GLBs so a switched manifest still has
    its referenced files. Existing GLBs are never replaced or deleted.
    """
    if manifest_path not in metadata:
        raise ValueError('Publication requires a final manifest')
    if set(model_files).intersection(metadata):
        raise ValueError('Model and metadata destinations overlap')
    for path in model_files:
        if path.exists():
            raise FileExistsError('Refusing to overwrite model: '+str(path))
    backups = {path: path.read_bytes() if path.exists() else None for path in metadata}
    order = [path for path in metadata if path != manifest_path]+[manifest_path]
    attempted_models = []
    attempted_metadata = []
    try:
        for path, data in model_files.items():
            if path.exists():
                raise FileExistsError('Model appeared during publication: '+str(path))
            attempted_models.append(path)
            _atomic_write(path, data)
        for path in order:
            attempted_metadata.append(path)
            _atomic_write(path, metadata[path])
    except BaseException as error:
        restoration_errors = []
        for path in reversed(attempted_metadata):
            try:
                if backups[path] is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_write(path, backups[path])
            except BaseException as restore_error:
                restoration_errors.append(str(path)+': '+str(restore_error))
        if restoration_errors:
            raise RuntimeError('Metadata rollback failed; new GLBs retained: '+
                               '; '.join(restoration_errors)) from error
        for path in attempted_models:
            path.unlink(missing_ok=True)
        raise


def build():
    provenance=ROOT/'docs/CIVIC_COMPANY_PROVENANCE.json'
    assert not provenance.exists(),'Refusing to overwrite a completed batch'
    mf=OUT/'manifest.json';text=mf.read_text();manifest=json.loads(text);raw=raw_asset_records(text);old={a['id']:a for a in manifest['assets']}
    matches=json.loads((OUT/'footprint-matches.json').read_text());owners={bid:mid for mid,ids in matches.items() for bid in ids}
    candidates=json.loads((ROOT/'docs/civic-company-candidates.json').read_text());upgrades=json.loads((ROOT/'docs/city-hall-upgrade.json').read_text());refs={r['nameKo']:r for r in json.loads((ROOT/'docs/civic-height-references.json').read_text())}
    assert len(upgrades)==1 and upgrades[0]['nameKo']=='서울특별시청'
    assert all(c['id'] not in old for c in candidates)
    upgraded_id=upgrades[0]['id'];assert old[upgraded_id]['nameKo']=='서울특별시청'
    assert hashlib.sha256((OUT/old[upgraded_id]['model']).read_bytes()).hexdigest()==old[upgraded_id]['sha256']
    db=sqlite3.connect((ROOT/'data/buildings.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    added=[];evidence=[];replacements={};model_files={}
    with tempfile.TemporaryDirectory(prefix='civic-glb-') as td:
      for c in candidates+upgrades:
        for bid in c['buildingIds']:assert bid not in owners or owners[bid]==upgraded_id and c['id']==upgraded_id
        anchor=(c['coordinate']['lon'],c['coordinate']['lat']);mesh=Mesh();parts=[];seed=int(hashlib.sha256(c['id'].encode()).hexdigest()[:8],16)
        for bid in c['buildingIds']:
          b=db.execute('select * from buildings where id=?',(bid,)).fetchone();assert b is not None
          local=transform(lambda x,y,z=None:projected(x,y,anchor),shape(json.loads(b['geometry'])))
          assert local.is_valid
          if b['height_m'] and b['height_m']>0:height=b['height_m'];basis='retained source building height, not independently surveyed'
          elif c['nameKo'] in refs:height=refs[c['nameKo']]['heightM'];basis=refs[c['nameKo']]['basis']
          elif b['num_floors']:height=b['num_floors']*3.05;basis='source storeys × estimated 3.05m'
          elif c['kind']=='cultural-site':height=max(6,min(12,local.area**.5*.38));basis='illustrative heritage/cultural envelope estimated from footprint size, not a measurement'
          else:height=12;basis='illustrative 12m fallback; source height and floors missing'
          floors=b['num_floors'] or max(1,round(height/3.5))
          specialized=False
          for poly in [local] if local.geom_type=='Polygon' else list(local.geoms):
            assert poly.area>0
            if civic_geometry(mesh,poly,c['nameKo'],height,floors,seed):specialized=True
            else:public_facade(mesh,poly,height,floors,'district-public-office')
          parts.append({'buildingId':bid,'sourceHeightM':b['height_m'],'sourceFloors':b['num_floors'],'modelHeightEnvelopeM':height,'heightBasis':basis,'specializedSilhouette':specialized})
        filename=c['id']+('-civic.glb' if c['id']==upgraded_id else '.glb');path=Path(td)/filename
        assert Path(filename).name==filename and not (OUT/filename).exists(), 'Refusing to overwrite '+filename
        stats,offset=mesh.save(path);lon,lat=unprojected(offset[0],offset[2],anchor)
        sources=[{'url':url,'supports':['retained building identity and source footprint']} for url in c['sourceUrls']]
        if c['nameKo'] in refs:sources.append({'url':refs[c['nameKo']]['sourceUrl'],'supports':refs[c['nameKo']]['supports']})
        asset={'id':c['id'],'model':filename,'name':c['nameKo'],'nameKo':c['nameKo'],'category':c['kind'],'district':c['district'],'minZoom':14.5,'units':'metres',**stats,'rootTransform':'identity','coordinate':{'lon':lon,'lat':lat,'basis':'bounds centre of source footprint model'},'yawDegFromEast':0,'heightDatum':'Local terrain at anchor. Source height or documented estimate; no additional terrain height multiplier.','referenceUrl':c['sourceUrls'][0],'sources':sources,'heightEstimated':True,'sourceHeightAvailableForEveryBuilding':all(p['sourceHeightM'] is not None for p in parts),'footprintIds':c['buildingIds'],'buildingCount':len(c['buildingIds']),'modelingEstimates':{'facade':'Source-informed procedural silhouette, roof, glazing and materials; not photo-surveyed','details':'docs/CIVIC_MODEL_DESIGN.md','heightBasis':[p['heightBasis'] for p in parts],'membership':'exact named retained source building IDs'},'validation':{'noExternalResources':True}}
        if c['id']==upgraded_id:replacements[c['id']]=asset
        else:added.append(asset)
        evidence.append({'id':c['id'],'selection':c,'buildings':parts});print(c['nameKo'],stats['triangles'],'triangles',flush=True)
      # Retain staged bytes; no published file changes until metadata validates.
      for asset in added+list(replacements.values()):
        data=(Path(td)/asset['model']).read_bytes()
        assert hashlib.sha256(data).hexdigest()==asset['sha256']
        assert OUT/asset['model'] not in model_files, 'Duplicate model filename'
        model_files[OUT/asset['model']]=data
        matches[asset['id']]=asset['footprintIds']
    allassets=[replacements.get(a['id'],a) for a in manifest['assets']]+added
    manifest['civicExpansion']={'count':len(added),'upgradedIds':list(replacements),'provenance':'../../docs/CIVIC_COMPANY_PROVENANCE.json'}
    manifest['districtExpansion']['count']=sum(bool(a.get('district')) for a in allassets)
    meta={k:v for k,v in manifest.items() if k!='assets'};prefix=json.dumps(meta,ensure_ascii=False,indent=2)[:-2]+',\n  "assets": [\n'
    entries=['    '+raw[a['id']] if a['id'] in raw and a['id'] not in replacements else '\n'.join('    '+line for line in json.dumps(a,ensure_ascii=False,indent=2).splitlines()) for a in allassets]
    manifest_text=prefix+',\n'.join(entries)+'\n  ]\n}\n'
    decoded=json.loads(manifest_text)
    assert len(decoded['assets'])==len(old)+len(added)
    assert len({a['id'] for a in decoded['assets']})==len(decoded['assets'])
    assert len({a['model'] for a in decoded['assets']})==len(decoded['assets'])
    reread=raw_asset_records(manifest_text)
    assert all(reread[k]==v for k,v in raw.items() if k not in replacements)
    result={'generator':'scripts/build_civic_models.py','newModels':len(added),'categories':dict(collections.Counter(a['category'] for a in added)),'upgrades':[{'id':upgraded_id,'reason':'User requested a source-informed City Hall model; replace generic extrusion with curved glass shell','before':old[upgraded_id],'afterSha256':replacements[upgraded_id]['sha256']}],'assets':evidence}
    metadata={
        OUT/'footprint-matches.json':(json.dumps(matches,ensure_ascii=False,indent=2)+'\n').encode(),
        provenance:(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode(),
        mf:manifest_text.encode(),
    }
    for data in metadata.values():json.loads(data)
    _publish_batch(model_files,metadata,mf)
    print('Total models',len(allassets),'new civic',len(added),'upgraded',len(replacements))
if __name__=='__main__':build()
