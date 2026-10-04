#!/usr/bin/env python3
"""Partition archived 잠실엘스 compounds while retaining unrelated and standalone buildings."""
import argparse
import json
from collections import Counter

from split_caelitus_fallback import ROOT, decode, sha
from split_authoring_fallbacks import partition
from split_prestige_fallbacks import canonical_sha, replay, triangle_signatures
from publish_bespoke_models import replace_batch

STAGE = ROOT / 'data/model-source/bespoke/jamsil-els-fallback-review'
CONFIGS = [('apt-a13822004', '914dcc4eeeaa107d7222d1697b56a2568326ffba771c4924696e52101f68c028', [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172], ['77cbfbc8-cb15-438a-85ba-77783c8acb46', 'b76d1c50-9695-44c9-abd0-9bd950751ea5'], 'docs/DISTRICT_LANDMARK_PROVENANCE.json')]
SINGLETONS = [(121, 'residential-5ffec150-2a79-4581-8599-3dc2a60b75c9', 'ed2bb0984dd089983f9b153b81fecfbf623d608240d6a31ce54ef10bce5a16f0'), (122, 'residential-2054abab-825b-4a26-ac58-95c70223e349', '0761688ab43c9c1bc0b3c62b41865019c24bd9b0d18bc7b7d9c2fd5199f3489b')]


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def prepare():
    folder = ROOT / 'public/models'
    base = json.loads((folder / 'manifest.json').read_text())
    matches = json.loads((folder / 'footprint-matches.json').read_text())
    current = json.loads((folder / 'generic-corrections.json').read_text())
    identity = json.loads((ROOT / 'docs/model-audit/jamsil-els-source-identity.json').read_text())
    assert identity['sourceSha256'] == 'e8f2a54420654efcd85cb945797623d85384efa60529f88393acee96645f26e0'
    towers = {row['number']: row['sourceId'] for row in identity['towers']}
    assert sorted(towers) == [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172] and len(set(towers.values())) == 72
    added, documents, proofs, bindings = [], {}, [], []
    for source_id, source_sha, numbers, neighbors, provenance in CONFIGS:
        source = next(a for a in base['assets'] if a['id'] == source_id)
        original = (folder / source['model']).read_bytes()
        assert sha(original) == source['sha256'] == source_sha
        assert set(matches[source_id]) == {towers[n] for n in numbers} | set(neighbors)
        owners, authoring = replay(source, original, matches[source_id], provenance)
        cfg = {'site': 'jamsil-els-' + str(numbers[0]), 'source': source_id, 'sha': source_sha,
            'count': len(matches[source_id]), 'removeApartmentCode': True,
            'remainingName': '잠실엘스 주변 비주거 건물 (기존 추정 모형)',
            'parts': [(f'fallback-jamsil-els-{n}', f'잠실엘스 {n}동', towers[n]) for n in numbers],
            'limits': ['Only original indexed triangles, attributes, materials and shared terrain anchor are partitioned; no photo-completion credit.',
                'All unrelated source buildings remain in original compound residuals. Standalone residential assets remain byte-for-byte unchanged.',
                'Only independently verified source identities receive numbered fallback labels; every archived GLB remains unchanged.',
                'Original concave-footprint convex-hull approximations are retained and explicitly counted.']}
        correction, files, proof = partition(cfg, folder, base, matches, owners, authoring)
        gltf, primitives = decode(original)
        signatures = {fid: Counter() for fid in matches[source_id]}
        for primitive, attributes, indices in primitives:
            tagged = owners[primitive['material']]
            assert len(tagged) == len(indices)
            material = json.dumps(gltf['materials'][primitive['material']], sort_keys=True, separators=(',', ':')).encode()
            for fid, index in zip(tagged, indices):
                signatures[fid][sha(material + b''.join(k.encode() + attributes[k][index].tobytes() for k in sorted(attributes)))] += 1
        for asset in correction['assets']:
            expected = sum((signatures[fid] for fid in asset['footprintIds']), Counter())
            assert triangle_signatures(files[folder / asset['model']]) == expected, 'Per-source triangle emission ownership differs'
            assert asset['coordinate'] == source['coordinate'] and 'apartmentCode' not in asset and 'householdCount' not in asset
        assert sum(a['triangles'] for a in correction['assets']) == source['triangles']
        proof['sourceAuthoringReplay'] = authoring
        proof['ownershipMethod'] += ' Independently regenerated byte-exact archived GLB and checked per-source triangle-signature multiplicity against every output.'
        files[ROOT / f"docs/model-audit/{cfg['site']}-generic-split.json"] = encoded(proof)
        documents.update(files)
        for n in numbers:
            asset = next(a for a in correction['assets'] if a['id'] == f'fallback-jamsil-els-{n}')
            assert asset['footprintIds'] == [towers[n]]
            bindings.append({'number': n, 'sourceFootprintId': towers[n], 'fallbackAssetId': asset['id'],
                'supersedes': [asset['id']], 'fallbackModel': asset['model'], 'fallbackSha256': asset['sha256']})
        added.append(correction)
        proofs.append(proof)
    singleton_records = []
    for number, asset_id, asset_sha in SINGLETONS:
        asset = next(a for a in base['assets'] if a['id'] == asset_id)
        assert matches[asset_id] == [towers[number]]
        assert sha((folder / asset['model']).read_bytes()) == asset['sha256'] == asset_sha
        singleton_records.append({'number': number, 'assetId': asset_id, 'sha256': asset_sha, 'sourceFootprintId': towers[number]})
        bindings.append({'number': number, 'sourceFootprintId': towers[number], 'fallbackAssetId': asset_id, 'supersedes': [asset_id], 'fallbackModel': asset['model'], 'fallbackSha256': asset_sha})
    assert sorted(b['number'] for b in bindings) == sorted(towers)
    source_ids = {c['sourceId'] for c in added}
    prior = [c for c in current['corrections'] if c['sourceId'] not in source_ids]
    binding = {'version': 1, 'complex': '잠실엘스', 'sourceIdentity': 'docs/model-audit/jamsil-els-source-identity.json',
        'bindings': sorted(bindings,key=lambda b:b['number']), 'preservedResidualSourceIds': sorted(fid for cfg in CONFIGS for fid in cfg[3]), 'unchangedSingletons':singleton_records}
    audit = {'version': 1, 'sources': proofs, 'preservedPriorCorrectionIds': [c['sourceId'] for c in prior],
        'preservedPriorCorrectionsCanonicalSha256': canonical_sha(prior), 'sourceTriangles': sum(p['sourceTriangles'] for p in proofs),
        'hullApproximationTriangles': sum(p['trianglesAssignedWithinSourceConvexHull'] for p in proofs)}
    documents[ROOT / 'docs/model-audit/jamsil-els-generic-split.json'] = encoded(audit)
    documents[ROOT / 'docs/model-audit/jamsil-els-fallback-bindings.json'] = encoded(binding)
    current['corrections'] = [*prior, *added]
    documents[folder / 'generic-corrections.json'] = encoded(current)
    return documents, audit, binding


def main(stage_only):
    documents, audit, binding = prepare()
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
    print(json.dumps({'stageOnly': stage_only, 'sourceTriangles': audit['sourceTriangles'], 'outputs': len(binding['bindings']),
        'hullApproximationTriangles': audit['hullApproximationTriangles'], 'priorCorrections': len(audit['preservedPriorCorrectionIds'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-only', action='store_true')
    main(parser.parse_args().stage_only)
