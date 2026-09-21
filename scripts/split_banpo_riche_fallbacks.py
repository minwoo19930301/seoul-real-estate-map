#!/usr/bin/env python3
"""Split the eight archived Banpo Riche towers and retain the ninth singleton without changing their triangles."""
import argparse
import json
from collections import Counter

from split_caelitus_fallback import ROOT, decode, sha
from split_banpo_fallbacks import partition
from split_prestige_fallbacks import canonical_sha, replay, triangle_signatures
from publish_bespoke_models import replace_batch

SOURCE = 'apt-a13776301'
SOURCE_SHA = 'f2c766bb7349be0d6d8a8f6c3d8d22ee9642470be97d3f6ccae4c0648ed9409e'
STAGE = ROOT / 'data/model-source/bespoke/banpo-riche-fallback-review'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def prepare():
    folder = ROOT / 'public/models'
    base = json.loads((folder / 'manifest.json').read_text())
    matches = json.loads((folder / 'footprint-matches.json').read_text())
    current = json.loads((folder / 'generic-corrections.json').read_text())
    identity = json.loads((ROOT / 'docs/model-audit/banpo-riche-source-identity.json').read_text())
    assert identity['sourceSha256'] == '7ec9460889ed3209cf9b543ddc91d8e63179186c8cd97a6214f73c65d4733819'
    all_towers = {row['number']: row['sourceId'] for row in identity['towers']}
    towers = {n: fid for n, fid in all_towers.items() if n != 106}
    assert sorted(towers) == [101, 102, 103, 104, 105, 107, 108, 109]
    assert len(set(towers.values())) == 8 and set(matches[SOURCE]) == set(towers.values())
    source = next(a for a in base['assets'] if a['id'] == SOURCE)
    original = (folder / source['model']).read_bytes()
    assert sha(original) == source['sha256'] == SOURCE_SHA
    owners, authoring = replay(source, original, matches[SOURCE], 'docs/APARTMENT_400_PROVENANCE.json')
    cfg = {'site': 'banpo-riche', 'source': SOURCE, 'sha': SOURCE_SHA, 'count': 8,
        'removeApartmentCode': True,
        'parts': [(f'fallback-banpo-riche-{n}', f'반포리체 {n}동', towers[n]) for n in towers],
        'limits': ['All eight source footprints belong to the independently reviewed numbered Shinbanpo Xi set. No residual or neighboring footprint is removed.',
            'This preserves original geometry, heights, material attributes and shared terrain anchor; it earns no photo-model completion credit.',
            'Any original roofplant or concave-footprint approximation is retained, not reinterpreted as surveyed geometry.']}
    correction, documents, proof = partition(cfg, folder, base, matches)
    gltf, primitives = decode(original)
    signatures = {fid: Counter() for fid in towers.values()}
    for primitive, attributes, indices in primitives:
        tagged = owners[primitive['material']]
        assert len(tagged) == len(indices)
        material = json.dumps(gltf['materials'][primitive['material']], sort_keys=True, separators=(',', ':')).encode()
        for fid, index in zip(tagged, indices):
            signatures[fid][sha(material + b''.join(k.encode() + attributes[k][index].tobytes() for k in sorted(attributes)))] += 1
    assert len(correction['assets']) == 8
    for asset in correction['assets']:
        assert len(asset['footprintIds']) == 1
        fid = asset['footprintIds'][0]
        assert triangle_signatures(documents[folder / asset['model']]) == signatures[fid], 'Source emission ownership differs from geometry partition'
        assert asset['coordinate'] == source['coordinate']
        assert 'apartmentCode' not in asset and 'householdCount' not in asset
    assert sum(a['triangles'] for a in correction['assets']) == source['triangles']
    prior = [c for c in current['corrections'] if c['sourceId'] != SOURCE]
    proof['sourceAuthoringReplay'] = authoring
    proof['preservedPriorCorrectionIds'] = [c['sourceId'] for c in prior]
    proof['preservedPriorCorrectionsCanonicalSha256'] = canonical_sha(prior)
    proof['ownershipMethod'] += ' Independent byte-exact authoring replay and per-source triangle-signature multiplicity also agree with every partition.'
    documents[ROOT / 'docs/model-audit/banpo-riche-generic-split.json'] = encoded(proof)
    binding = {'version': 1, 'complex': '반포리체', 'sourceIdentity': 'docs/model-audit/banpo-riche-source-identity.json',
        'sourceArchive': SOURCE, 'sourceArchiveSha256': SOURCE_SHA, 'bindings': []}
    for n, asset in zip(towers, correction['assets']):
        assert asset['id'] == f'fallback-banpo-riche-{n}' and asset['footprintIds'] == [towers[n]]
        binding['bindings'].append({'number': n, 'sourceFootprintId': towers[n], 'fallbackAssetId': asset['id'],
            'supersedes': [asset['id']], 'fallbackModel': asset['model'], 'fallbackSha256': asset['sha256']})
    singleton = next(a for a in base['assets'] if a['id'] == 'residential-025a7bbd-1c33-4f47-90fd-1f874b5ba0d8')
    assert singleton['footprintIds'] == matches[singleton['id']] == [all_towers[106]]
    assert sha((folder / singleton['model']).read_bytes()) == singleton['sha256'] == 'cd663fd2aa110228d11a4e131b54a8cef07cd164d9c81a48189c88abb3282e8f'
    binding['bindings'].append({'number': 106, 'sourceFootprintId': all_towers[106], 'fallbackAssetId': singleton['id'],
        'supersedes': [singleton['id']], 'fallbackModel': singleton['model'], 'fallbackSha256': singleton['sha256']})
    binding['bindings'].sort(key=lambda b: b['number'])
    binding['preservedSingleton106'] = {'id': singleton['id'], 'sha256': singleton['sha256'], 'metadataAndBytesUnchanged': True}
    documents[ROOT / 'docs/model-audit/banpo-riche-fallback-bindings.json'] = encoded(binding)
    current['corrections'] = [*prior, correction]
    documents[folder / 'generic-corrections.json'] = encoded(current)
    return documents, proof, binding


def main(stage_only):
    documents, proof, binding = prepare()
    STAGE.mkdir(parents=True, exist_ok=True)
    for path, data in documents.items():
        dest = STAGE / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    (STAGE / 'published-model-binding-map.json').write_bytes(encoded(binding))
    if not stage_only:
        path = ROOT / 'public/data/deployment-assets.json'
        deployment = json.loads(path.read_text())
        for file, data in documents.items():
            if file.is_relative_to(ROOT / 'public/models'):
                deployment['files'][str(file.relative_to(ROOT))] = sha(data)
        documents[path] = encoded(deployment)
        replace_batch([], documents)
    print(json.dumps({'stageOnly': stage_only, 'sourceTriangles': proof['sourceTriangles'], 'outputs': len(binding['bindings']),
        'maximumInheritedProjectionM': proof['maximumVertexDistanceOutsideSourceFootprintM'],
        'hullApproximationTriangles': proof['trianglesAssignedWithinUniqueSourceConvexHull'],
        'byteExactSourceReplay': proof['sourceAuthoringReplay']['byteExact']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-only', action='store_true')
    main(parser.parse_args().stage_only)
