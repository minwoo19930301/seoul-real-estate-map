#!/usr/bin/env python3
"""Partition archived 잠실파크리오 compounds while retaining unrelated and standalone buildings."""
import argparse
import json
from collections import Counter

from split_caelitus_fallback import ROOT, decode, sha
from split_banpo_fallbacks import partition
from split_prestige_fallbacks import canonical_sha, replay, triangle_signatures
from publish_bespoke_models import replace_batch

STAGE = ROOT / 'data/model-source/bespoke/jamsil-parkrio-fallback-review'
CONFIGS = [('apt-a13824006', '1d127942d53e268b529afb3d07a94839c09f47ae15dba442b74663f047c67685', [109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 201, 202, 203, 204, 205, 206, 207, 208, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 314, 315, 316, 317], ['07711e8b-0b2e-4295-972d-e156e0b76d54', '2f89da55-946f-4013-9413-05acc3e89239', '3f9a8ba6-9be5-4174-80fa-82d1b31cd971', '9e6f9d09-d695-4fd9-830c-c3c57dbdf5e1', 'ea858e0b-46b9-4253-a42e-1bb9dd6e0f1c'], 'docs/LANDMARK_EXPANSION_PROVENANCE.json')]
SINGLETONS = [(101, 'residential-3a6cdb92-d9b6-48dd-8f5f-7b0f4ce2fb4b', 'f7b0eefef784294c1bfd7bdd8c273cde0ce221a6f0a3525b26ed9e502b3a487c'), (103, 'residential-60d63d61-390d-47bf-b8da-4e98f647d35f', 'b28d97ce15084d3edf863ca7615c68b3a57cb8e6f96a4af45e92e5bddc325de7'), (105, 'residential-d7cdd1ab-c8f2-4546-aaf5-f24d4ca67951', '392eeffcf1baa49de3a7945cb51605ae5ef2aa04b2b4983fbd02b675469b7a7d'), (106, 'residential-978aa1bc-027e-4b4d-be2b-b838b15becd5', '2fc15348a6dc5bbfc4ee5bff96135b5b38abf142ce3e85d05da16d171e6ab7c9'), (107, 'residential-7e6f6d87-d2ca-4d00-b25e-58ebfce2dad1', 'e2b3d0c412ed4b08bb6d20f056503e91db0de17aca8da510d75c3120bd304b2e'), (108, 'residential-ecbf7bca-1b8c-4ebd-b849-77c0719dfc26', '12db9c0c58e7737e3707a03d6093a926b2abcbc9d1d65f4a2d445ad62ef8a7ce'), (311, 'residential-cee8f323-9fd9-4906-8b42-c90156ad9a0e', '903e0a12d18ab2535cedd3eceb3473da9847d036de356acdff2e32bb09b55e57'), (312, 'residential-6782419d-350c-4a1b-8553-498eaf73f433', '5913d28547a772a89167dac4695cfd81bad80f102eaea89d7a653232c4cc1a6c'), (313, 'residential-dd7ef1ed-0ec6-4301-a795-3037e554e969', '524f4ade25bc43dcda7c36aa617c6cf9c1959efb4e769e67a55344af7d58f2f1')]


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def prepare():
    folder = ROOT / 'public/models'
    base = json.loads((folder / 'manifest.json').read_text())
    matches = json.loads((folder / 'footprint-matches.json').read_text())
    current = json.loads((folder / 'generic-corrections.json').read_text())
    identity = json.loads((ROOT / 'docs/model-audit/jamsil-parkrio-source-identity.json').read_text())
    assert identity['sourceSha256'] == '86d611524c9157de2ca80b217ec4acf9a0d893dd1ed3d2ae9153f488f7854ed3'
    towers = {row['number']: row['sourceId'] for row in identity['towers']}
    assert sorted(towers) == [101, 103, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 201, 202, 203, 204, 205, 206, 207, 208, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317] and len(set(towers.values())) == 60
    added, documents, proofs, bindings = [], {}, [], []
    for source_id, source_sha, numbers, neighbors, provenance in CONFIGS:
        source = next(a for a in base['assets'] if a['id'] == source_id)
        original = (folder / source['model']).read_bytes()
        assert sha(original) == source['sha256'] == source_sha
        assert set(matches[source_id]) == {towers[n] for n in numbers} | set(neighbors)
        owners, authoring = replay(source, original, matches[source_id], provenance)
        cfg = {'site': 'jamsil-parkrio-' + str(numbers[0]), 'source': source_id, 'sha': source_sha,
            'count': len(matches[source_id]), 'removeApartmentCode': True,
            'remainingName': '잠실파크리오 주변 및 미확정 건물 (기존 추정 모형)',
            'parts': [(f'fallback-jamsil-parkrio-{n}', f'잠실파크리오 {n}동', towers[n]) for n in numbers],
            'limits': ['Only original indexed triangles, attributes, materials and shared terrain anchor are partitioned; no photo-completion credit.',
                'All unrelated and withheld source buildings remain in original compound residuals. Boundaryconflicts102/104/119/120 and identityconflicts209/210 earn no completioncredit. Standalone residential assets remain byte-for-byte unchanged.',
                'Only independently verified source identities receive numbered fallback labels; every archived GLB remains unchanged.',
                'Original concave-footprint convex-hull approximations are retained and explicitly counted.']}
        correction, files, proof = partition(cfg, folder, base, matches)
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
            asset = next(a for a in correction['assets'] if a['id'] == f'fallback-jamsil-parkrio-{n}')
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
    binding = {'version': 1, 'complex': '잠실파크리오', 'sourceIdentity': 'docs/model-audit/jamsil-parkrio-source-identity.json',
        'bindings': sorted(bindings,key=lambda b:b['number']), 'preservedResidualSourceIds': sorted(fid for cfg in CONFIGS for fid in cfg[3]), 'unchangedSingletons':singleton_records}
    audit = {'version': 1, 'sources': proofs, 'preservedPriorCorrectionIds': [c['sourceId'] for c in prior],
        'preservedPriorCorrectionsCanonicalSha256': canonical_sha(prior), 'sourceTriangles': sum(p['sourceTriangles'] for p in proofs),
        'hullApproximationTriangles': sum(p['trianglesAssignedWithinUniqueSourceConvexHull'] for p in proofs)}
    documents[ROOT / 'docs/model-audit/jamsil-parkrio-generic-split.json'] = encoded(audit)
    documents[ROOT / 'docs/model-audit/jamsil-parkrio-fallback-bindings.json'] = encoded(binding)
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
