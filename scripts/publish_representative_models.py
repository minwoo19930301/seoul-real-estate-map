"""Validate and optionally publish coarse photo-informed models; never bespoke credit.

Default is validation only. --publish installs a fully reviewed bundle atomically.
"""
import argparse
import importlib.util
import math
import re
import subprocess
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location('bespoke_publisher', Path(__file__).with_name('publish_bespoke_models.py'))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
ROOT = base.ROOT
METHOD = 'representative-photo-informed'


def local(directory, name):
    path = (directory / name).resolve()
    if not path.is_relative_to(directory.resolve()) or not path.is_file():
        raise ValueError('Missing local input or path outside bundle: ' + name)
    return path


def geometry_bounds(coordinate, geometry):
    lon, lat = coordinate['lon'], coordinate['lat']
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in [lon, lat]) or not (126 < lon < 128 and 37 < lat < 38.5):
        raise ValueError('Expected a finite Seoul geographic anchor')
    lo, hi = geometry['min'], geometry['max']
    if len(lo) != 3 or len(hi) != 3 or not all(math.isfinite(v) for v in lo + hi) or any(hi[i] <= lo[i] for i in range(3)):
        raise ValueError('Invalid model bounds')
    if abs(lo[1]) > .01 or max(abs(lo[0]), abs(hi[0]), abs(lo[2]), abs(hi[2])) > 3000:
        raise ValueError('Expected ground-zero local metres, not geographic/world coordinates')
    sx = 111319.49079327358 * math.cos(math.radians(lat))
    sy = 111319.49079327358
    return [lon + lo[0]/sx, lat-hi[2]/sy, lon+hi[0]/sx, lat-lo[2]/sy]


def validate_ownership(assets, protected, existing):
    ids = {a['id'] for a in protected + existing}
    footprints = {f for a in protected + existing for f in a.get('footprintIds', [])}
    for asset in assets:
        aid = base.safe_id(asset['id'])
        if aid in ids:
            raise ValueError('Duplicate or preserved model ID: ' + aid)
        ids.add(aid)
        owned = asset.get('footprintIds', [])
        if not owned or any(not isinstance(f, str) or not f for f in owned) or len(owned) != len(set(owned)):
            raise ValueError('Unique nonempty footprint ownership required')
        if footprints.intersection(owned):
            raise ValueError('Duplicate or protected footprint ownership')
        footprints.update(owned)
        # Compound generic supersession can hide unrelated towers. Footprint-based
        # overlap handling already provides replacement with load/draw fallback.
        if asset.get('supersedes', []):
            raise ValueError('Representative models may not supersede preserved models')


def publish(bundle_path, review_path, install=False, root=ROOT):
    root = root.resolve()
    directory = bundle_path.resolve().parent
    stage = (root/'data/model-source').resolve()
    if not directory.is_relative_to(stage) or directory == stage or not re.fullmatch(r'representative(?:-batch[0-9]+)?', directory.relative_to(stage).parts[0]):
        raise ValueError('Bundle must be in representative or representative-batchNN staging')
    b, review = base.read(bundle_path), base.read(review_path)
    site = base.safe_id(b['siteId'])
    if b.get('constructionMethod') != METHOD:
        raise ValueError('Explicit representative constructionMethod required')
    if review.get('siteId') != site or review.get('status') != 'coarse-visually-reviewed' or len(review.get('views', [])) < 2 or not all(review.get('views', [])) or not review.get('limitations'):
        raise ValueError('Site-specific coarse review with two views and limitations required')
    base.validate_mcp_evidence(b.get('mcpEvidence'), root)
    def reviewed(name):
        path = local(directory, name)
        if review.get('reviewedInputs', {}).get(name) != base.sha(path):
            raise ValueError('Input changed or missing review hash: ' + name)
        return path
    sources = b.get('sources', [])
    if not sources or len({s['id'] for s in sources}) != len(sources):
        raise ValueError('Unique source-specific evidence required')
    comparisons = review.get('comparisons', [])
    for source in sources:
        if not source.get('url', '').startswith(('https://', 'http://')) or source.get('sha256') != base.sha(reviewed(source['inputFile'])):
            raise ValueError('Source input hash or URL invalid')
        if not any(c.get('sourceId') == source['id'] and c.get('observation') for c in comparisons):
            raise ValueError('Each source needs its own review comparison')
    pub = root/'public/models'
    target = pub/'representative-manifest.json'
    current = base.read(target) if target.exists() else {'version': 1, 'assets': [], 'places': []}
    protected = base.read(pub/'bespoke-manifest.json')['assets'] + base.read(pub/'reference-manifest.json')['assets']
    generic = base.read(pub/'manifest.json')['assets']
    # Preserve generic IDs too, without preventing their footprint fallback.
    protected += [{'id': a['id']} for a in generic]
    assets = b.get('assets', [])
    if not assets:
        raise ValueError('Missing models')
    expected = b.get('expectedFootprintIds')
    actual = [fid for asset in assets for fid in asset.get('footprintIds', [])]
    if not isinstance(expected, list) or not expected or any(not isinstance(fid, str) or not fid for fid in expected) or len(expected) != len(set(expected)) or set(expected) != set(actual):
        raise ValueError('Complete selected source footprint ownership required; partial bundles are prohibited')
    validate_ownership(assets, protected, current['assets'])
    copies, outputs = [], []
    with tempfile.TemporaryDirectory(prefix='representative-') as tmp:
        for asset in assets:
            aid = asset['id']
            source, blend = reviewed(asset['file']), reviewed(asset['blendSource'])
            if source.suffix != '.glb' or blend.suffix != '.blend' or asset.get('representativeForms') not in (1, 2) or not asset.get('uncertainties'):
                raise ValueError('GLB, editable blend, 1-2 forms and explicit uncertainties required')
            normalized = Path(tmp)/(aid+'.glb')
            subprocess.run(['node', str(root/'scripts/bespoke/normalize_glb.mjs'), str(source), str(normalized)], check=True)
            g = base.read(Path(str(normalized)+'.json'))
            bounds = geometry_bounds(asset['coordinate'], g)
            model = 'representative/'+site+'/'+aid+'.glb'
            blend_dest = root/'modeling/representative'/site/blend.name
            copies.extend([(normalized, pub/model), (blend, blend_dest)])
            outputs.append({'id': aid, 'nameKo': asset['nameKo'], 'model': model, 'coordinate': asset['coordinate'],
                'dimensions': g['dimensions'], 'geoBounds': bounds, 'yawDegFromEast': 0,
                'heightDatum': 'metres; independent terrain anchor', 'quality': 'reference', 'sha256': g['sha256'],
                'referenceUrl': asset['referenceUrl'], 'category': 'apartment', 'minZoom': asset.get('minZoom', 15),
                'footprintIds': asset['footprintIds'], 'supersedes': [], 'searchable': False,
                'sourceRecord': {'siteId': site, 'method': METHOD, 'constructionMethod': METHOD, 'completionCredit': False,
                    'sources': sources, 'sourceGlbSha256': base.sha(source), 'blendSha256': base.sha(blend),
                    'blendSource': str(blend_dest.relative_to(root)), 'representativeForms': asset['representativeForms'],
                    'uncertainties': asset['uncertainties'], 'accuracy': 'Coarse representative forms reused across towers; not an individually reconstructed high-detail model'}})
        for name in b.get('recipeFiles', []):
            path = reviewed(name)
            if path.suffix not in {'.json', '.geojson', '.py'}:
                raise ValueError('Only geometry/code recipe inputs may be distributed')
            copies.append((path, root/'modeling/representative'/site/path.name))
        # Shared blend sources are copied only once.
        copies = list(dict.fromkeys(copies))
        current['assets'] += outputs
        audit_path = root/'docs/model-audit/published-representative.json'
        audit = base.read(audit_path) if audit_path.exists() else {'version': 1, 'sites': {}}
        audit['sites'][site] = {'constructionMethod': METHOD, 'completionCredit': False, 'review': review,
                                'sources': sources, 'mcpEvidence': b['mcpEvidence'], 'assets': [a['id'] for a in outputs]}
        documents = {target: base.encoded(current), audit_path: base.encoded(audit)}
        deployment_path = root/'public/data/deployment-assets.json'
        deployment = base.read(deployment_path)
        deployment['files']['public/models/representative-manifest.json'] = base.hashlib.sha256(documents[target]).hexdigest()
        for source, dest in copies:
            if dest.is_relative_to(pub):
                deployment['files'][str(dest.relative_to(root))] = base.sha(source)
        documents[deployment_path] = base.encoded(deployment)
        if install:
            previous_root = base.ROOT
            try:
                base.ROOT = root
                base.replace_batch(copies, documents)
            finally:
                base.ROOT = previous_root
        return {'siteId': site, 'assets': [a['id'] for a in outputs], 'published': install, 'completionCredit': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle', type=Path)
    p.add_argument('--review', required=True, type=Path)
    p.add_argument('--publish', action='store_true')
    args = p.parse_args()
    print(base.json.dumps(publish(args.bundle, args.review, args.publish), ensure_ascii=False))
