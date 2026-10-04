#!/usr/bin/env python3
"""Partition archived 헬리오시티 compounds while retaining unrelated and standalone buildings."""
import argparse
import json
from collections import Counter

from split_caelitus_fallback import ROOT, decode, sha
from split_banpo_fallbacks import partition
from split_prestige_fallbacks import canonical_sha, replay, triangle_signatures
from publish_bespoke_models import replace_batch

STAGE = ROOT / 'data/model-source/bespoke/songpa-helio-city-fallback-review'
CONFIGS = [('apt-a10025850', '9ea0796ab3e5112ce4fb8add8b1ae397d6a36a2ee18e1e2456823ce6f8a68194', [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 201, 202, 203, 206, 207, 208, 209, 210, 211, 212, 215, 216, 217, 218, 219, 301, 302, 303, 304, 307, 308, 309, 310, 311, 312, 313, 314, 317, 318], ['38db8e87-fdcc-442a-af91-399011a1bca5', 'ba086155-4b2e-4ff0-bc94-7d4332247390'], 'docs/DISTRICT_LANDMARK_PROVENANCE.json'), ('apt-a13816101', '4d48faee8c09840f4f0eb5622a635f6bb276276cc167a5fd98c95491152f2fdb', [501, 502, 503], ['9e79815f-3605-4078-866b-fe621bbcb84e', 'a0780b82-e755-4461-87f7-61abb4240153', 'b3991be5-1364-4f48-8cd8-55f471c58002', 'f009ac31-aa08-444e-b7c8-4f42556014fd'], 'docs/APARTMENT_100_PROVENANCE.json')]
SINGLETONS = [(204, 'residential-bce3fee3-b118-4456-8715-7f29036e7d73', '5541fae78d4deb8e71ef64a504ef61bfc602b021724dfa0ad8a8ed72b87a1df9'), (205, 'residential-e6b9bc96-67cd-4247-ab45-7b65c36632c8', 'a20fc5a50813e0ca1a545d480a968c762582b2cc5a1c2874fedce77007caad72'), (213, 'residential-d5f3d71e-1729-4d8a-a5dd-1f055d7fc548', '28584397b11ed14c83c1fdf3ed02161ea114ac278467cfa95f0965768d2765df'), (214, 'residential-2349f4fa-9ceb-4610-a305-81dba6146d9c', '5371232331a73cdd386f57c82ead2b5b0400f00f1be461bcd6e45532166f758e'), (305, 'residential-55839ea5-8f6d-42b4-b35b-3b712d4d302f', 'e6361452992c4bf706c30ef8b2115a854a39fa6ef2059deafa4b326ce93e0236'), (306, 'residential-01f5767a-a531-4f50-814d-a5e6bead5ea5', 'b1b1832748cbbb78edca3b72520050971a233ba1fbe73b38f33443e48b3b0c32'), (315, 'residential-812b93b2-58ce-4c9d-bd03-b82934641679', 'f5a92acc9c01aa342ba59d998c7b424fdcec6bc290d7eefdf41ae5fa3e286b8b'), (316, 'residential-93e845db-bb82-402b-ad87-3536f1e65524', 'a93d99e033916d2c6731c131c5f8e7cf421ccb0aad2d7d634a585e87768f95de'), (401, 'residential-209b120d-e99d-4ea1-8889-1496d2ca02ee', '6336de5205f35ec2f1ea3106383f735e34c176b0314ed4a4e524fdc0a425da1a'), (402, 'residential-2e22a04a-56fe-44e4-8ffa-8628b69e0ea7', '1ed67a74ec2fc72e2e45ac7329d1de5e13c45031174a3f8314113cd0e9032543'), (403, 'residential-ba8ba5d6-cd19-437c-9e02-910e2daec5a1', '68e25da4b1f9b0f2ee1da0fe4ad7aeb405ec6f79cac8a93114ed3d2279629202'), (404, 'residential-5b3f61e9-90b9-4465-a919-18215ffee910', 'b63c91393eea44bcdbbd77964eaa51282b44ffe29eb1762fd6bd5d9d1f6a3585'), (405, 'residential-cc4fa4dd-c758-4321-8ca4-aa8c0fb1b287', '29b441a6bfea4790fef8d6bb167ef5d7b8f98e77e692764c8e2832f303cb28ee'), (406, 'residential-63c2d36a-b64e-48c2-bd23-2943cd1d00f2', 'e7910141133644af63b571b5d550fc97edbaec7d7467d8eaa783966fbe62829e'), (407, 'residential-b688edfd-55bc-4cf7-9dd0-ffc7b5da7f24', 'e8763f56ce7af1745c5372adf8f211e4900ee12d07556dc6278fdf1ba9d4b61d'), (408, 'residential-c596d101-b5cd-49f0-8eb1-830b4fbdbfc5', '30abeed2e8c1a0e5920adbd49262598904901f722f841bbe3ae5b34fd1a6f7ca'), (409, 'residential-f54af8fa-c7f2-425c-8585-57864db10284', 'b37b39670955b4bae07887cf6b491436826e7e9c5c50f891d2e47dd2ccb57206'), (410, 'residential-bef4e53f-b60e-41c9-8e8b-20f60321bc07', '1990699093a0cfc9708691ecf1d9248c59a5b56d71d3214afcd4ede5a0e7110d'), (411, 'residential-458c07e6-4d3b-4d99-8bf4-13f802531a79', '47058820165e8775d008ea51d2bf369549976f39a22acbc05dc7b920426adac6'), (412, 'residential-a0ba17f3-b406-4dcd-ba64-9f4bfbca719e', 'ccd19b83b2457ba88284e0a2ea957cded35baac90244a10207c34a67c4d54640'), (413, 'residential-95d26c1b-f9f6-4938-aa64-6058d74eecea', 'c77fa42358aacc97e2e63af035c406cfefdb0cbc3d4a7ab592b4024c8f909923'), (414, 'residential-695097e0-f3da-4404-a119-d3c7c92820fa', '5e2d63520b20873ca46bf9c9b5b68b2c34beb58351f2fc51b90bd0b214dff16c'), (415, 'residential-5c9d6e10-6105-4402-8ed3-e9c8a80ae992', 'a28458da38bd3edf93df28d62f9484f2ac29e5af1da9cf426ee070f3f5af5549'), (416, 'residential-4670493a-116a-4db3-a130-9a4f976c8620', 'f5eaeb62133800d5dbd7aa9b4c83d61723397fdae338cfb6c81401a619979cd6'), (417, 'residential-e5face72-a93c-42f8-905f-2c1a2b69eb2b', 'd4c4a78936090b61c8790ad78658a021f1121d3880fdff332603f6246fcb0278'), (418, 'residential-e6715201-19f8-41aa-846c-31c0b1ab1498', 'e8d3b36d8e6a8067b25baeaea41a5ec2d9cc6bf883b0491adfa9f8098e916e59'), (504, 'residential-ff97096e-e8fe-4498-9d73-f10e2e55cb28', '375afdf364bf35f1b0c21aa4abf2f49e58063ff68a6dd3b686400070c62875d9'), (505, 'residential-e4965b07-16cb-4201-86c7-323dff6b3c4f', 'a498c27c49ff1b54b048769fe98bc6f4dde60fb3e56a6c843fc3fee633ca61e3'), (506, 'residential-89748c37-435c-4e97-a1d1-fd2534d52f50', '988688efda94e1d047ea405b3838b050ab767595ac0d136ff85bacf7c9b7fcfd'), (507, 'residential-67051558-7429-4d9f-98ec-63c35c75a07a', '29cdafa490d418e6e9414f9c86c64eaf90250d11df113d8891144c515c93d5ac'), (508, 'residential-4a19be9f-e4b9-4c2d-8477-842c2872ced1', 'acc85db93a0b7e0ecb21729790270a732a6c84e3221ab62bda3de042ed8ad8e1'), (509, 'residential-056fe3f0-a5b5-4e4d-86ab-5d7eba5b2669', '425cf42347222f71810c3d673cb26a56a5378cbbc47ae7afd818391047dbd335'), (510, 'residential-a34c4cec-0c00-409e-ba5d-7d8d63ed8c9c', '9f41e4c42c2f7e7cb41ea453450183ae22cf309e8e9288bc3d591c4cae9f6fe2'), (511, 'residential-39dfaeca-f4c8-479d-b37e-196de931378c', '5e37e358647458786ff001472a16d28bfa8e78e75054b48002b0a13cb3913f19'), (512, 'residential-951c7442-f681-4578-bfd5-7757d89128e4', 'a4eba5ee3886ee57ee7b80b394dcff4a9898b2acb51030c2875cb4c1b9bf8aa0'), (513, 'residential-0433cb59-4807-4fa4-90dc-e7cffe918bb9', 'ad0cab448c001712bd23f9aa3f29d7413340b75aec1854a416646ab9175b06fe'), (514, 'residential-5b90b67b-0eb2-498d-a775-e60461a3e7c5', 'eaab586633a397fa2ffb87158dca829a011d6baed199452e2f0c93917b0c3ff8'), (515, 'residential-7fc4e445-c96a-4907-9f68-16d6ca2a34b0', 'eb8dfbf27e3f5eb1750bc4ee19296f018b6bb7181dc567778ec761cdadd74161'), (516, 'residential-7c368048-d9c4-4461-90f3-9e94b3156580', '21548ba9bd046dee4625f598482f9b026b6793661231d58f1440114ab45f0f0c'), (517, 'residential-e9d72269-63af-4e69-829c-cca2de1807ba', '27f9f15d0d907ffb175cc62a7633c8e6354c7c722df089696f218bfeea233ac6')]


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def prepare():
    folder = ROOT / 'public/models'
    base = json.loads((folder / 'manifest.json').read_text())
    matches = json.loads((folder / 'footprint-matches.json').read_text())
    current = json.loads((folder / 'generic-corrections.json').read_text())
    identity = json.loads((ROOT / 'docs/model-audit/songpa-helio-city-source-identity.json').read_text())
    assert identity['sourceSha256'] == '227fbfd6ceb76dd3850c9746b4211f7ed9cd3fbeec2400c95537acde8e7e90bb'
    towers = {row['number']: row['sourceId'] for row in identity['towers']}
    assert sorted(towers) == [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516, 517] and len(set(towers.values())) == 84
    added, documents, proofs, bindings = [], {}, [], []
    for source_id, source_sha, numbers, neighbors, provenance in CONFIGS:
        source = next(a for a in base['assets'] if a['id'] == source_id)
        original = (folder / source['model']).read_bytes()
        assert sha(original) == source['sha256'] == source_sha
        assert set(matches[source_id]) == {towers[n] for n in numbers} | set(neighbors)
        owners, authoring = replay(source, original, matches[source_id], provenance)
        cfg = {'site': 'songpa-helio-city-' + str(numbers[0]), 'source': source_id, 'sha': source_sha,
            'count': len(matches[source_id]), 'removeApartmentCode': True,
            'remainingName': '헬리오시티 대상 외 건물 (기존 추정 모형)',
            'parts': [(f'fallback-songpa-helio-city-{n}', f'헬리오시티 {n}동', towers[n]) for n in numbers],
            'limits': ['Only original indexed triangles, attributes, materials and shared terrain anchor are partitioned; no photo-completion credit.',
                'All unrelated source buildings remain in original compound residuals. Standalone residential assets remain byte-for-byte unchanged.',
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
            asset = next(a for a in correction['assets'] if a['id'] == f'fallback-songpa-helio-city-{n}')
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
    binding = {'version': 1, 'complex': '헬리오시티', 'sourceIdentity': 'docs/model-audit/songpa-helio-city-source-identity.json',
        'bindings': sorted(bindings,key=lambda b:b['number']), 'preservedResidualSourceIds': sorted(fid for cfg in CONFIGS for fid in cfg[3]), 'unchangedSingletons':singleton_records}
    audit = {'version': 1, 'sources': proofs, 'preservedPriorCorrectionIds': [c['sourceId'] for c in prior],
        'preservedPriorCorrectionsCanonicalSha256': canonical_sha(prior), 'sourceTriangles': sum(p['sourceTriangles'] for p in proofs),
        'hullApproximationTriangles': sum(p['trianglesAssignedWithinUniqueSourceConvexHull'] for p in proofs)}
    documents[ROOT / 'docs/model-audit/songpa-helio-city-generic-split.json'] = encoded(audit)
    documents[ROOT / 'docs/model-audit/songpa-helio-city-fallback-bindings.json'] = encoded(binding)
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
