#!/usr/bin/env python3
"""Partition frozen Gracium, Arteon and La Classy sources jointly, preserving every triangle."""
import argparse
import copy
import math
import sqlite3
from pathlib import Path
import numpy as np
from shapely.geometry import shape, MultiPoint
from shapely.ops import transform
import json
from collections import Counter

from publish_bespoke_models import encoded, read, replace_batch, safe_id
from split_caelitus_fallback import ROOT, decode, encode, sha
from split_prestige_fallbacks import canonical_sha, replay, triangle_signatures

INPUT = ROOT / 'docs/model-audit/godeok-laclassy-fallback-inputs.json'
STAGE = ROOT / 'data/model-source/bespoke/godeok-laclassy-fallback-review'


def partition_by_replayed_source(cfg, folder, source, ids, owners, authoring):
    original = (folder / source['model']).read_bytes()
    assert authoring['byteExact'] and authoring['sha256'] == sha(original) == cfg['sha']
    gltf, primitives = decode(original)
    assert len(gltf['nodes']) == 1 and set(gltf['nodes'][0]) == {'mesh', 'name'}
    selected = {fid for _, _, fid in cfg['parts']}
    assert len(selected) == len(cfg['parts']) and selected.issubset(ids)
    remaining = [fid for fid in ids if fid not in selected]
    groups = ([(source['id'], cfg['remainingName'], remaining)] if remaining else []) + [(aid, name, [fid]) for aid, name, fid in cfg['parts']]
    anchor = source['coordinate']
    scale = 6378137 * math.cos(math.radians(anchor['lat']))
    lat0 = math.log(math.tan(math.pi / 4 + math.radians(anchor['lat']) / 2))
    def project(x, y, z=None):
        return scale * math.radians(x - anchor['lon']), -scale * (math.log(math.tan(math.pi / 4 + math.radians(y) / 2)) - lat0)
    with sqlite3.connect(f'file:{ROOT}/data/buildings.sqlite?mode=ro', uri=True) as db:
        shapes = {fid: transform(project, shape(json.loads(db.execute('select geometry from buildings where id=?', [fid]).fetchone()[0]))) for fid in ids}
    hull_count, outside_hull = 0, 0
    for primitive, attributes, indices in primitives:
        tags = owners[primitive['material']]
        assert len(tags) == len(indices) and set(tags).issubset(ids)
        for fid, indices3 in zip(tags, indices):
            triangle = MultiPoint(attributes['POSITION'][indices3][:, [0, 2]])
            if not shapes[fid].buffer(.15).covers(triangle):
                hull_count += 1
                if not shapes[fid].convex_hull.buffer(.15).covers(triangle):
                    outside_hull += 1
    outputs, documents = [], {}
    for aid, name, subset in groups:
        selectors = [np.array([fid in subset for fid in owners[p['material']]]) for p, _, _ in primitives]
        assert all(mask.any() for mask in selectors), 'Unexpected empty material partition'
        data, stats = encode(gltf, primitives, selectors, aid)
        model = f'generic-corrections/{aid}.glb'
        documents[folder / model] = data
        asset = copy.deepcopy(source)
        asset.update(stats, id=aid, model=model, name=name, nameKo=name, buildingCount=len(subset), footprintIds=subset,
            searchable=aid == source['id'], residentialCompletionCredit=False)
        asset.pop('householdCount', None)
        asset.pop('apartmentCode', None)
        lo, hi = stats['bounds']['min'], stats['bounds']['max']
        lon = lambda x: anchor['lon'] + math.degrees(x / scale)
        lat = lambda z: math.degrees(2 * math.atan(math.exp(lat0 - z / scale)) - math.pi / 2)
        asset['geoBounds'] = [lon(lo[0]), lat(hi[2]), lon(hi[0]), lat(lo[2])]
        asset['measuredGlbDimensions'] = stats['dimensions']
        asset['genericCorrection'] = {'sourceId': source['id'], 'sourceSha256': cfg['sha'],
            'operation': 'Exact original source-emission partition; unchanged vertex attributes, materials and terrain anchor.'}
        outputs.append(asset)
    assert sum(a['triangles'] for a in outputs) == source['triangles']
    proof = {'version': 1, 'sourceId': source['id'], 'sourceSha256': cfg['sha'], 'sourceTriangles': source['triangles'],
        'sourceCoordinate': anchor, 'groupFootprints': {aid: subset for aid, _, subset in groups},
        'ownershipMethod': 'Original source-emission indices from byte-exact authoring replay; overlapping historical plans cannot change ownership.',
        'legacyTrianglesOutsideSourcePolygonInsideItsHull': hull_count - outside_hull,
        'legacyTrianglesOutsideSourceConvexHull': outside_hull,
        'limits': cfg['limits'], 'outputs': [{k: a[k] for k in ['id', 'model', 'sha256', 'bytes', 'triangles', 'bounds', 'footprintIds']} for a in outputs]}
    return {'sourceId': source['id'], 'sourceSha256': cfg['sha'], 'sourceFootprintIds': ids, 'assets': outputs}, documents, proof


def prepare(input_path=INPUT):
    batch = safe_id(input_path.stem.removesuffix('-fallback-inputs'))
    frozen = read(input_path)
    folder = ROOT / 'public/models'
    base = read(folder / 'manifest.json')
    assets = {a['id']: a for a in base['assets']}
    matches = read(folder / 'footprint-matches.json')
    existing = read(folder / 'generic-corrections.json')
    identity_rows = {}
    for item in frozen['identities']:
        path = ROOT / item['path']
        assert sha(path.read_bytes()) == item['sha256']
        identity = read(path)
        assert len(identity['towers']) == item['count']
        identity_rows[item['site']] = {r['number']: r['sourceId'] for r in identity['towers']}
    bindings = {site: [] for site in identity_rows}
    added, documents, proofs, residuals = [], {}, [], []

    def bind(target, asset):
        assert identity_rows[target['site']][target['number']] == target['sourceId']
        assert asset['footprintIds'] == [target['sourceId']]
        bindings[target['site']].append({'number': target['number'], 'sourceFootprintId': target['sourceId'],
            'fallbackAssetId': asset['id'], 'supersedes': [asset['id']],
            'fallbackModel': asset['model'], 'fallbackSha256': asset['sha256']})

    for frozen_source in frozen['compounds']:
        source_id = frozen_source['assetId']
        source = assets[source_id]
        assert not any(c['sourceId'] == source_id for c in existing['corrections']), 'Preserve existing corrections'
        assert matches[source_id] == frozen_source['footprintIds']
        original = (folder / source['model']).read_bytes()
        assert sha(original) == source['sha256'] == frozen_source['sha256']
        owners, authoring = replay(source, original, matches[source_id], frozen_source['provenance'])
        targets = frozen_source['targets']
        parts = [(f"fallback-{t['site']}-{t['number']}", t['name'], t['sourceId']) for t in targets]
        cfg = {'site': batch + '-' + source_id, 'source': source_id, 'sha': source['sha256'],
            'count': len(matches[source_id]), 'removeApartmentCode': True,
            'remainingName': '대상 외 원천 건물 (기존 추정 모형)', 'parts': parts,
            'limits': ['Only archived indexed triangles, material attributes and terrain anchors are partitioned; no photo-modeling credit.',
                frozen['scope'],
                'All unnamed, unmatched and unrelated source buildings remain in unchanged-shape residuals. Original convex-hull approximations remain archived.']}
        correction, files, proof = partition_by_replayed_source(cfg, folder, source, matches[source_id], owners, authoring)
        gltf, primitives = decode(original)
        signatures = {fid: Counter() for fid in matches[source_id]}
        for primitive, attributes, indices in primitives:
            tagged = owners[primitive['material']]
            assert len(tagged) == len(indices)
            material = json.dumps(gltf['materials'][primitive['material']], sort_keys=True, separators=(',', ':')).encode()
            for fid, index in zip(tagged, indices):
                signatures[fid][sha(material + b''.join(k.encode() + attributes[k][index].tobytes() for k in sorted(attributes)))] += 1
        by_id = {a['id']: a for a in correction['assets']}
        for asset in correction['assets']:
            expected = sum((signatures[fid] for fid in asset['footprintIds']), Counter())
            assert triangle_signatures(files[folder / asset['model']]) == expected
            assert asset['coordinate'] == source['coordinate'] and 'apartmentCode' not in asset and 'householdCount' not in asset
            assert not (folder / asset['model']).exists(), 'Never overwrite a published output'
        assert sum(a['triangles'] for a in correction['assets']) == source['triangles']
        for target, (asset_id, _, _) in zip(targets, parts):
            bind(target, by_id[asset_id])
        selected = {t['sourceId'] for t in targets}
        residuals.extend(fid for fid in matches[source_id] if fid not in selected)
        proof['sourceAuthoringReplay'] = authoring
        proof['ownershipMethod'] += ' Byte-exact archived authoring replay and per-source triangle-signature multiplicity independently checked.'
        files[ROOT / f"docs/model-audit/{cfg['site']}-generic-split.json"] = encoded(proof)
        documents.update(files)
        added.append(correction)
        proofs.append(proof)
    for target in frozen['singletons']:
        asset = assets[target['assetId']]
        assert not any(c['sourceId'] == asset['id'] for c in existing['corrections'])
        assert matches[asset['id']] == [target['sourceId']]
        assert sha((folder / asset['model']).read_bytes()) == target['sha256'] == asset['sha256']
        bind(target, asset)
    for item in frozen['identities']:
        site = item['site']
        assert sorted(b['number'] for b in bindings[site]) == sorted(identity_rows[site])
        documents[ROOT / f'docs/model-audit/{site}-fallback-bindings.json'] = encoded({
            'version': 1, 'sourceIdentity': item['path'], 'bindings': sorted(bindings[site], key=lambda b: b['number']),
            'limits': ['Independent existing fallbacks only; model completion and photo review are separate.'],
            'jointSplitAudit': f'docs/model-audit/{batch}-generic-split.json'})
    audit = {'version': 1, 'frozenInputsSha256': sha(input_path.read_bytes()), 'sources': proofs,
        'preservedPriorCorrectionIds': [c['sourceId'] for c in existing['corrections']],
        'preservedPriorCorrectionsCanonicalSha256': canonical_sha(existing['corrections']),
        'sourceTriangles': sum(p['sourceTriangles'] for p in proofs),
        'hullApproximationTriangles': sum(p['legacyTrianglesOutsideSourcePolygonInsideItsHull'] for p in proofs),
        'preservedResidualSourceIds': sorted(residuals), 'unchangedStandaloneAssets': frozen['singletons']}
    documents[ROOT / f'docs/model-audit/{batch}-generic-split.json'] = encoded(audit)
    documents[folder / 'generic-corrections.json'] = encoded({**existing, 'corrections': [*existing['corrections'], *added]})
    return documents, audit, bindings


def main(stage_only, input_path=INPUT):
    documents, audit, bindings = prepare(input_path)
    stage = STAGE.parent / (safe_id(input_path.stem.removesuffix('-fallback-inputs')) + '-fallback-review')
    for path, data in documents.items():
        target = stage / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if not stage_only:
        path = ROOT / 'public/data/deployment-assets.json'
        deployment = read(path)
        for file, data in documents.items():
            if file.is_relative_to(ROOT / 'public/models'):
                deployment['files'][str(file.relative_to(ROOT))] = sha(data)
        documents[path] = encoded(deployment)
        replace_batch([], documents)
    print(json.dumps({'stageOnly': stage_only, 'sourceTriangles': audit['sourceTriangles'],
        'hullApproximationTriangles': audit['hullApproximationTriangles'],
        'preservedResidualSources': len(audit['preservedResidualSourceIds']),
        'bindings': {site: len(rows) for site, rows in bindings.items()},
        'priorCorrections': len(audit['preservedPriorCorrectionIds'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-only', action='store_true')
    parser.add_argument('--inputs', type=lambda p: Path(p).resolve(), default=INPUT)
    args = parser.parse_args()
    main(args.stage_only, args.inputs)
