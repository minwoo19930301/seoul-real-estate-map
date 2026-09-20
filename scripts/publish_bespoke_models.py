"""Publish individually reviewed Blender models without rewriting legacy assets.

Pass one completed bundle at a time, after inspecting its Blender renders and
real source photographs. A review record documents the actual comparison; it
is not a score inferred from triangle count, filenames or unique mesh hashes.
"""
import argparse, hashlib, json, math, re, shutil, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'data/model-source/bespoke'
PUB=ROOT/'public/models'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def encoded(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def replace_batch(copies, documents):
    """Stage every byte first and roll back ordinary publication failures."""
    destinations=[dest for _,dest in copies]+list(documents)
    if len(destinations)!=len(set(destinations)):raise ValueError('Duplicate output path')
    with tempfile.TemporaryDirectory(prefix='bespoke-publish-',dir=ROOT/'data') as name:
        temp=Path(name);staged=[];installed=[]
        for index,dest in enumerate(destinations):
            dest.parent.mkdir(parents=True,exist_ok=True)
            before=temp/(str(index)+'.before');after=temp/(str(index)+'.after')
            if dest.exists():shutil.copyfile(dest,before)
            if dest in documents:after.write_bytes(documents[dest])
            else:shutil.copyfile(next(source for source,target in copies if target==dest),after)
            staged.append((after,dest,before))
        try:
            for after,dest,before in staged:after.replace(dest);installed.append((dest,before))
        except BaseException:
            for dest,before in reversed(installed):
                if before.exists():before.replace(dest)
                else:dest.unlink(missing_ok=True)
            raise
def safe_id(s):
    if not isinstance(s,str) or not re.fullmatch('[a-z0-9][a-z0-9-]*',s):raise ValueError('Unsafe model identifier')
    return s

def validate_mcp_evidence(records, root=ROOT):
    """Require recorded MCP execution in addition to the independent visual review."""
    if not isinstance(records,list) or not records:
        raise ValueError('Recorded Blender MCP execution is required')
    audit=(root/'docs/model-audit/mcp').resolve()
    for record in records:
        if not isinstance(record,dict) or not isinstance(record.get('path'),str):
            raise ValueError('Invalid Blender MCP evidence record')
        path=(root/record['path']).resolve()
        if not path.is_relative_to(audit) or not path.is_file() or path.suffix!='.json':
            raise ValueError('MCP evidence must be a local audit JSON file')
        if record.get('sha256')!=sha(path):
            raise ValueError('Blender MCP evidence hash mismatch')
        calls=read(path)
        if not isinstance(calls,list) or not any(
            isinstance(call,dict) and call.get('tool')=='execute_blender_code'
            and call.get('isError') is False and any(
                isinstance(c,dict) and 'Code executed successfully' in str(c.get('text',''))
                for c in call.get('content',[])) for call in calls):
            raise ValueError('MCP evidence has no successful Blender code execution')

def publish(bundle_path, review_path):
    bundle_path=bundle_path.resolve(); review_path=review_path.resolve()
    if not bundle_path.is_relative_to(STAGE):raise ValueError('Bundle must be in the bespoke staging directory')
    b=read(bundle_path);review=read(review_path);site=safe_id(b['siteId'])
    if review.get('siteId')!=site or review.get('status')!='visually-reviewed' or not review.get('comparisons'):
        raise ValueError('A completed, site-specific visual comparison record is required')
    if not b.get('sources') or not b.get('assets'):raise ValueError('Missing source evidence or models')
    validate_mcp_evidence(b.get('mcpEvidence'))
    current=read(PUB/'bespoke-manifest.json')
    evidence_path=ROOT/'docs/model-audit/published-bespoke.json'
    evidence=read(evidence_path) if evidence_path.exists() else {'version':1,'sites':{}}
    new=[];records=[];pending=[];blends={};recipe_copies=[]
    for filename in b.get('recipeFiles',[]):
        source=(bundle_path.parent/filename).resolve()
        if not source.is_relative_to(bundle_path.parent) or not source.is_file() or source.suffix not in {'.json','.geojson','.py'}:
            raise ValueError('Recipe inputs must be local geometry or code, not embedded reference photographs')
        recipe_copies.append((source,ROOT/'modeling/bespoke'/site/source.name))
    old_ids={a['id'] for a in read(PUB/'manifest.json')['assets']+read(PUB/'reference-manifest.json')['assets']}
    old_ids.update(a['id'] for a in current['assets'] if a.get('sourceRecord',{}).get('siteId')!=site)
    for asset in b['assets']:
        aid=safe_id(asset['id'])
        if aid in old_ids:raise ValueError('New asset must not overwrite a preserved ID')
        source=(bundle_path.parent/asset['file']).resolve()
        blend=(bundle_path.parent/asset['blendSource']).resolve()
        if not source.is_relative_to(bundle_path.parent) or not blend.is_relative_to(bundle_path.parent):raise ValueError('Source path outside site')
        if source.suffix!='.glb' or blend.suffix!='.blend' or not blend.is_file():raise ValueError('Missing editable Blender source')
        for path in [source,blend]:
            if review.get('reviewedInputs',{}).get(str(path.relative_to(bundle_path.parent)))!=sha(path):
                raise ValueError('Model changed after visual review: '+path.name)
        normalized=bundle_path.parent/'normalized'/(aid+'.glb')
        subprocess.run(['node',str(ROOT/'scripts/bespoke/normalize_glb.mjs'),str(source),str(normalized)],check=True)
        geometry=read(Path(str(normalized)+'.json'))
        if not asset.get('components') or not asset.get('referenceUrl'):raise ValueError('Missing authored component evidence')
        lon=asset['coordinate']['lon'];lat=asset['coordinate']['lat'];sx=111319.49079327358*math.cos(math.radians(lat));sy=111319.49079327358
        lo=geometry['min'];hi=geometry['max']
        model='bespoke/'+site+'/'+aid+'.glb'
        blend_dest=ROOT/'modeling/bespoke'/site/blend.name;blends[blend]=blend_dest
        output={'id':aid,'nameKo':asset['nameKo'],'model':model,'coordinate':{'lon':lon,'lat':lat},
          'dimensions':geometry['dimensions'],'yawDegFromEast':0,'heightDatum':'metres; independent terrain anchor',
          'quality':'reference','sha256':geometry['sha256'],'referenceUrl':asset['referenceUrl'],
          'category':asset['category'],'district':asset.get('district'),'minZoom':asset.get('minZoom',15),
          'geoBounds':[lon+lo[0]/sx,lat-hi[2]/sy,lon+hi[0]/sx,lat-lo[2]/sy],
          'footprintIds':sorted(set(asset.get('footprintIds',[]))),'supersedes':sorted(set(asset.get('supersedes',[]))),
          'searchable':asset.get('searchable',False),'groundOffsetM':asset.get('groundOffsetM',0),
          'sourceRecord':{'provider':'Individual Blender MCP reconstruction','siteId':site,'sources':b['sources'],
            'blendSource':str(blend_dest.relative_to(ROOT)),'blendSha256':sha(blend),'sourceGlbSha256':sha(source),'components':asset['components'],
            'buildingFacts':{key:asset[key] for key in ['floors','floorsBasis','heightM','heightBasis'] if key in asset},
            'uncertainties':asset.get('uncertainties',[]),'accuracy':'Compared to cited photographs and site plans; unmeasured dimensions remain estimates'}}
        new.append(output);records.append({'id':aid,**geometry});pending.append((normalized,PUB/model))
    ids=[a['id'] for a in new]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate site asset IDs')
    for a in new:
        if any(x in ids for x in a['supersedes']):raise ValueError('Sibling site assets cannot replace each other')
    current['assets']=[a for a in current['assets'] if a.get('sourceRecord',{}).get('siteId')!=site]+new
    current['places']=[p for p in current['places'] if p.get('siteId')!=site]+[{**p,'siteId':site} for p in b.get('places',[])]
    evidence['sites'][site]={'sources':b['sources'],'review':review,'assets':records,'mcpEvidence':b['mcpEvidence'],
      'recipeInputs':[{'path':str(dest.relative_to(ROOT)),'sha256':sha(source)} for source,dest in recipe_copies]}
    deployment_path=ROOT/'public/data/deployment-assets.json';deployment=read(deployment_path)
    manifest_bytes=encoded(current)
    deployment['files']['public/models/bespoke-manifest.json']=hashlib.sha256(manifest_bytes).hexdigest()
    for source,dest in pending:deployment['files'][str(dest.relative_to(ROOT))]=sha(source)
    replace_batch([*pending,*blends.items(),*recipe_copies],{
        PUB/'bespoke-manifest.json':manifest_bytes,evidence_path:encoded(evidence),deployment_path:encoded(deployment)})
    print(json.dumps({'siteId':site,'publishedAssets':ids,'editableBlends':[str(p.relative_to(ROOT)) for p in blends.values()]},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);p.add_argument('--review',type=Path,required=True)
    args=p.parse_args();publish(args.bundle,args.review)
