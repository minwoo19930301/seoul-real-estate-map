#!/usr/bin/env python3
"""Split the seven archived Shinbanpo Xi towers without changing their triangles."""
import argparse
import json
from collections import Counter

from split_caelitus_fallback import ROOT, decode, sha
from split_banpo_fallbacks import partition
from split_prestige_fallbacks import canonical_sha, replay, triangle_signatures
from publish_bespoke_models import replace_batch

SOURCE = 'apt-a10026004'
SOURCE_SHA = '8b9bd8a22b4347b3653b6729d81c08befafbf5eb0b46a848a95701fc251e045a'
STAGE = ROOT / 'data/model-source/bespoke/shinbanpo-xi-fallback-review'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def prepare():
    folder = ROOT / 'public/models'
    base = json.loads((folder / 'manifest.json').read_text())
    matches = json.loads((folder / 'footprint-matches.json').read_text())
    current = json.loads((folder / 'generic-corrections.json').read_text())
    identity = json.loads((ROOT / 'docs/model-audit/shinbanpo-xi-source-identity.json').read_text())
    assert identity['sourceSha256'] == '2d33001f7ed5e6ff4c925df15a7388833d2a22ef071ab88809f3ee8aa49d2802'
    towers = {row['number']: row['sourceId'] for row in identity['towers']}
    assert sorted(towers) == list(range(101, 108))
    assert len(set(towers.values())) == 7 and set(matches[SOURCE]) == set(towers.values())
    source = next(a for a in base['assets'] if a['id'] == SOURCE)
    original = (folder / source['model']).read_bytes()
    assert sha(original) == source['sha256'] == SOURCE_SHA
    owners, authoring = replay(source, original, matches[SOURCE], 'docs/APARTMENT_400_PROVENANCE.json')
    cfg = {'site': 'shinbanpo-xi', 'source': SOURCE, 'sha': SOURCE_SHA, 'count': 7,
        'removeApartmentCode': True,
        'parts': [(f'fallback-shinbanpo-xi-{n}', f'신반포자이 {n}동', towers[n]) for n in towers],
        'limits': ['All seven source footprints belong to the independently reviewed numbered Shinbanpo Xi set. No residual or neighboring footprint is removed.',
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
    assert len(correction['assets']) == 7
    for asset in correction['assets']:
        assert len(asset['footprintIds']) == 1
        fid = asset['footprintIds'][0]
        assert triangle_signatures(documents[folder / asset['model']]) == signatures[fid], 'Source emission ownership differs from geometry partition'
        assert asset['coordinate'] == source['coordinate']
        assert 'apartmentCode' not in asset and 'householdCount' not in asset
    assert sum(a['triangles'] for a in correction['assets']) == 3861
    prior = [c for c in current['corrections'] if c['sourceId'] != SOURCE]
    proof['sourceAuthoringReplay'] = authoring
    proof['preservedPriorCorrectionIds'] = [c['sourceId'] for c in prior]
    proof['preservedPriorCorrectionsCanonicalSha256'] = canonical_sha(prior)
    proof['ownershipMethod'] += ' Independent byte-exact authoring replay and per-source triangle-signature multiplicity also agree with every partition.'
    documents[ROOT / 'docs/model-audit/shinbanpo-xi-generic-split.json'] = encoded(proof)
    binding = {'version': 1, 'complex': '신반포자이', 'sourceIdentity': 'docs/model-audit/shinbanpo-xi-source-identity.json',
        'sourceArchive': SOURCE, 'sourceArchiveSha256': SOURCE_SHA, 'bindings': []}
    for n, asset in zip(towers, correction['assets']):
        assert asset['id'] == f'fallback-shinbanpo-xi-{n}' and asset['footprintIds'] == [towers[n]]
        binding['bindings'].append({'number': n, 'sourceFootprintId': towers[n], 'fallbackAssetId': asset['id'],
            'supersedes': [asset['id']], 'fallbackModel': asset['model'], 'fallbackSha256': asset['sha256']})
    documents[ROOT / 'docs/model-audit/shinbanpo-xi-fallback-bindings.json'] = encoded(binding)
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
