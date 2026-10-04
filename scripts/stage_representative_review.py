"""Assemble an already reviewed modeler's handoff; never infer visual approval."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def read(path):
    return json.loads(path.read_text())
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def stage(directory):
    directory = directory.resolve()
    assert directory.is_relative_to(ROOT / 'data/model-source')
    bundle = read(directory / 'handoff.json')
    assets = [a for a in bundle['assets'] if not a.get('integrationHold')]
    assert assets, 'No reviewed models ready'
    reviews, codes = [], []
    for asset in assets:
        code = Path(asset['file']).stem
        codes.append(code)
        review = read(directory / asset['review'])
        assert review['reviewstatus'] == 'coarse-visually-reviewed'
        assert not review.get('integrationHold')
        hashes = review['reviewedInputs']
        if isinstance(hashes, list):
            hashes = {x['file']: x['sha256'] for x in hashes}
        for name, digest in hashes.items():
            assert sha(directory/name) == digest, 'Input changed after review: '+name
        review['reviewedInputs'] = hashes
        reviews.append(review)
        asset['id'] = 'representative-' + code.lower()
    bundle['assets'] = assets
    bundle['sources'] = [s for s in bundle['sources'] if any(s['id'].startswith(c+'-') for c in codes)]
    bundle['expectedFootprintIds'] = sorted({f for a in assets for f in a['footprintIds']})
    inputs = read(directory/'site-footprints.json')['sites']
    source_ids = {t['id'] for s in inputs if s['code'] in codes for t in s['towers']}
    original_ids = {f for s in inputs if s['code'] in codes for f in s.get('footprintIds', [])}
    assert set(bundle['expectedFootprintIds']) == source_ids
    assert not original_ids or source_ids == original_ids
    evidence = []
    for source in sorted(directory.glob('mcp-*-evidence.json')):
        target = ROOT/'docs/model-audit/mcp'/f'{directory.name}-{source.name}'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        evidence.append({'path': str(target.relative_to(ROOT)), 'sha256': sha(target)})
    assert evidence
    bundle['mcpEvidence'] = evidence
    review = {'siteId': bundle['siteId'], 'status': 'coarse-visually-reviewed',
              'comparisons': [], 'views': [], 'limitations': [], 'reviewedInputs': {},
              'completionCredit': False}
    for record in reviews:
        review['comparisons'].extend(record['comparisons'])
        review['limitations'].extend(record['limitations'])
        review['reviewedInputs'].update(record['reviewedInputs'])
        for view in record['views']:
            source = directory/'outputs'/view['file']
            target = ROOT/'docs/model-audit/renders/representative'/directory.name/source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            review['views'].append({**view, 'file': str(target.relative_to(ROOT)), 'sha256': sha(target)})
    review['limitations'] = list(dict.fromkeys(review['limitations']))
    write(directory/'bundle.json', bundle)
    write(directory/'review.json', review)
    print(json.dumps({'sites': len(assets), 'sourceBuildings': len(source_ids), 'bundle': str(directory/'bundle.json')}))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    stage(p.parse_args().directory)
