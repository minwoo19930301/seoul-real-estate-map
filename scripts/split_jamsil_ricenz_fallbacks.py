#!/usr/bin/env python3
"""Preserve both archived compounds while separating 63 reviewed Ricenz source towers."""
import argparse
import json
from collections import Counter

from split_caelitus_fallback import ROOT, decode, sha
from split_banpo_fallbacks import partition
from split_prestige_fallbacks import canonical_sha, replay, triangle_signatures
from publish_bespoke_models import replace_batch

STAGE = ROOT / 'data/model-source/bespoke/jamsil-ricenz-fallback-review'
CONFIGS = [('apt-a13822003', 'ba4c2ea70b232af225bd93adc8bfc6ca5a035d82c1fc218c6dc3828e88d0d9bb', [201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 243, 250, 256, 258, 260, 261, 262, 264], ['a0e6ef76-5b7f-4161-af3b-c5ce51b7c9d0', 'b3b2a783-c22a-4b06-ad9d-aa2042c6feaf', 'cdbf28b1-f5fe-4436-a4c0-86a3f79be762'], 'docs/DISTRICT_LANDMARK_PROVENANCE.json'), ('apt-a13879102', 'd9c20cacc6c96539347eec9a72650c914e69acfc833810242817df3ae7693f6f', [242, 244, 245, 246, 247, 248, 249, 251, 252, 253, 254, 255, 257, 259], ['0227ab1c-fab5-418c-af97-e7b6b41c91d2', '0c2b67e5-a776-4449-8179-17be7d1ba62f', '13705a2e-7d04-4d5f-b7b1-595b8fc58566', '1a0736f0-9f0a-4fcb-8e06-ea0462b9303e', '2414cd57-fbd5-4b35-b099-533952ae9039', '2b5b34e8-cefb-4e75-9a15-f27c434e025d', '3b6eff6c-56f6-478f-a434-537cdf039f13', '3cc2d6fd-cc96-4ef4-9afe-cf7ab66ff431', '526d5888-2788-415c-b0d7-6295523a4827', '63a57252-e57e-4d60-85e7-64ba35cf7d3a', '67ea0863-ff49-4f48-a555-47c6f6e57caa', '775baa82-4b6e-4e9f-9b7b-0f18b7b599c1', '96a445bf-c8fe-4769-844e-4c0d93c171c3', 'a5398f44-e695-494b-b9da-02c5f19ce24a', 'a901dbf2-7ac3-43a8-8594-a47fa5702a30', 'cd253885-1184-4906-b907-4e9cb73fb5cb', 'dc191c1e-b6ab-4064-8ac7-029bad43bc29', 'effc1056-9aac-406a-9d64-b0dbc609cc70', 'fc98e014-5d2a-4cbd-a826-75ab4583faa7'], 'docs/DISTRICT_LANDMARK_PROVENANCE.json')]


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def prepare():
    folder = ROOT / 'public/models'
    base = json.loads((folder / 'manifest.json').read_text())
    matches = json.loads((folder / 'footprint-matches.json').read_text())
    current = json.loads((folder / 'generic-corrections.json').read_text())
    identity = json.loads((ROOT / 'docs/model-audit/jamsil-ricenz-source-identity.json').read_text())
    assert identity['sourceSha256'] == '75a281842b1ed4b388f168cff914c8183ed942acc9c045986b9583fa0e2bf108'
    towers = {row['number']: row['sourceId'] for row in identity['towers']}
    assert sorted(towers) == [n for n in range(201, 266) if n not in [263, 265]] and len(set(towers.values())) == 63
    added, documents, proofs, bindings = [], {}, [], []
    for source_id, source_sha, numbers, neighbors, provenance in CONFIGS:
        source = next(a for a in base['assets'] if a['id'] == source_id)
        original = (folder / source['model']).read_bytes()
        assert sha(original) == source['sha256'] == source_sha
        assert set(matches[source_id]) == {towers[n] for n in numbers} | set(neighbors)
        owners, authoring = replay(source, original, matches[source_id], provenance)
        cfg = {'site': 'jamsil-ricenz-' + str(numbers[0]), 'source': source_id, 'sha': source_sha,
            'count': len(matches[source_id]), 'removeApartmentCode': True,
            'remainingName': '리센츠 주변 및 미교체 건물 (기존 추정 모형)',
            'parts': [(f'fallback-jamsil-ricenz-{n}', f'잠실리센츠 {n}동', towers[n]) for n in numbers],
            'limits': ['Only original indexed triangles, attributes, materials and shared terrain anchor are partitioned; no photo-completion credit.',
                'All unrelated source buildings and boundary-conflicted263/265 remain in the original compound residuals. Their geometry and inferred source heights remain unchanged.',
                'Some verified Ricenz towers were incorrectly bundled with Jamsil5. Only independently verified source identities are relabeled; both original GLBs remain archived unchanged.',
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
            asset = next(a for a in correction['assets'] if a['id'] == f'fallback-jamsil-ricenz-{n}')
            assert asset['footprintIds'] == [towers[n]]
            bindings.append({'number': n, 'sourceFootprintId': towers[n], 'fallbackAssetId': asset['id'],
                'supersedes': [asset['id']], 'fallbackModel': asset['model'], 'fallbackSha256': asset['sha256']})
        added.append(correction)
        proofs.append(proof)
    source_ids = {c['sourceId'] for c in added}
    prior = [c for c in current['corrections'] if c['sourceId'] not in source_ids]
    binding = {'version': 1, 'complex': '잠실리센츠', 'sourceIdentity': 'docs/model-audit/jamsil-ricenz-source-identity.json',
        'bindings': sorted(bindings,key=lambda b:b['number']), 'preservedResidualSourceIds': sorted(fid for cfg in CONFIGS for fid in cfg[3]), 'withheldTowerNumbers':[263,265]}
    audit = {'version': 1, 'sources': proofs, 'preservedPriorCorrectionIds': [c['sourceId'] for c in prior],
        'preservedPriorCorrectionsCanonicalSha256': canonical_sha(prior), 'sourceTriangles': sum(p['sourceTriangles'] for p in proofs),
        'hullApproximationTriangles': sum(p['trianglesAssignedWithinUniqueSourceConvexHull'] for p in proofs)}
    documents[ROOT / 'docs/model-audit/jamsil-ricenz-generic-split.json'] = encoded(audit)
    documents[ROOT / 'docs/model-audit/jamsil-ricenz-fallback-bindings.json'] = encoded(binding)
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
