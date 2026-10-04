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


def partition_by_replayed_source(cfg, folder, source, ids, owners, authoring, remainingId=None):
    original = (folder / source['model']).read_bytes()
    assert authoring['byteExact'] and authoring['sha256'] == sha(original) == cfg['sha']
    gltf, primitives = decode(original)
    assert len(gltf['nodes']) == 1 and set(gltf['nodes'][0]) == {'mesh', 'name'}
    selected = {fid for _, _, fid in cfg['parts']}
    assert len(selected) == len(cfg['parts']) and selected.issubset(ids)
    remaining = [fid for fid in ids if fid not in selected]
    residual_id = safe_id(remainingId) if remainingId is not None else source['id']
    groups = ([(residual_id, cfg['remainingName'], remaining)] if remaining else []) + [(aid, name, [fid]) for aid, name, fid in cfg['parts']]
    assert len({aid for aid, _, _ in groups}) == len(groups), 'Duplicate output IDs'
    if remainingId is not None:
        assert len(groups) >= 2, 'Repartition needs at least two outputs'
        assert all(aid != source['id'] for aid, _, _ in groups), 'Repartition must use new IDs'
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
            searchable=bool(remaining) and aid == residual_id, residentialCompletionCredit=False)
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
    correction = {'sourceId': source['id'], 'sourceSha256': cfg['sha'], 'sourceFootprintIds': ids, 'assets': outputs}
    if remainingId is not None:
        correction['kind'] = 'repartition'
    return correction, documents, proof


def effective_sources(base_assets, matches, corrections):
    """Resolve ownership and base ancestry in the exact published correction order."""
    assets = {a['id']: a for a in base_assets}
    footprints = copy.deepcopy(matches)
    ancestors = {a['id']: a['id'] for a in base_assets}
    touched = set()
    for correction in corrections:
        sid = correction['sourceId']
        assert sid in assets and assets[sid]['sha256'] == correction['sourceSha256'], 'Stale correction source'
        assert set(footprints[sid]) == set(correction['sourceFootprintIds']), 'Correction ownership differs'
        ancestor = ancestors.pop(sid)
        assets.pop(sid)
        footprints.pop(sid)
        output_ids = [a['id'] for a in correction['assets']]
        assert len(output_ids) == len(set(output_ids)), 'Duplicate corrected IDs'
        output_footprints = [fid for a in correction['assets'] for fid in a['footprintIds']]
        assert len(output_footprints) == len(set(output_footprints)), 'Duplicate corrected footprint ownership'
        assert set(output_footprints) == set(correction['sourceFootprintIds']), 'Incomplete corrected ownership'
        for asset in correction['assets']:
            aid = asset['id']
            assert aid not in assets, 'Correction overwrites another asset'
            assets[aid] = asset
            footprints[aid] = list(asset['footprintIds'])
            ancestors[aid] = ancestor
            touched.add(aid)
        touched.add(sid)
    return assets, footprints, ancestors, touched


def replay_current_residual(frozen, folder, source, ids, base_assets, base_matches, ancestor_id):
    """Replay the original base, then reproduce the current residual byte for byte."""
    assert frozen['ancestorAssetId'] == ancestor_id, 'Residual ancestor differs'
    ancestor = base_assets[ancestor_id]
    ancestor_ids = base_matches[ancestor_id]
    assert len(ids) == len(set(ids)) and set(ids) < set(ancestor_ids), 'Invalid current residual subset'
    original = (folder / ancestor['model']).read_bytes()
    assert sha(original) == ancestor['sha256'], 'Original ancestor hash differs'
    if 'ancestorSha256' in frozen:
        assert frozen['ancestorSha256'] == sha(original), 'Frozen ancestor hash differs'
    owners, original_proof = replay(ancestor, original, ancestor_ids, frozen['provenance'])
    gltf, primitives = decode(original)
    masks, current_owners = [], {}
    for primitive, _, indices in primitives:
        material = primitive['material']
        assert material not in current_owners, 'Duplicate material ownership stream'
        tags = owners[material]
        assert len(tags) == len(indices) and set(tags).issubset(ancestor_ids), 'Invalid original owners'
        mask = np.array([fid in ids for fid in tags])
        assert mask.any(), 'Empty residual material'
        masks.append(mask)
        current_owners[material] = [fid for fid in tags if fid in ids]
    assert set(fid for tags in current_owners.values() for fid in tags) == set(ids), 'Missing residual owners'
    ranges = []
    for fid in ids:
        by_material = {}
        for material, tags in current_owners.items():
            indices = [i for i, owner in enumerate(tags) if owner == fid]
            if indices:
                start, end = indices[0], indices[-1] + 1
                assert indices == list(range(start, end)), 'Non-contiguous current source ownership'
            else:
                start = end = 0
            by_material[material] = [start, end]
        ranges.append({'sourceId': fid, 'triangleRangesByMaterial': by_material})
    reconstructed, stats = encode(gltf, primitives, masks, source['id'])
    current = (folder / source['model']).read_bytes()
    assert sha(current) == source['sha256'] == frozen['sha256'], 'Current residual hash differs'
    assert reconstructed == current, 'Current residual byte-exact replay differs'
    assert stats['triangles'] == source['triangles'], 'Current residual triangle count differs'
    assert source['coordinate'] == ancestor['coordinate'], 'Residual terrain anchor changed'
    return current_owners, {'byteExact': True, 'sha256': sha(current),
        'currentResidualReplay': {'byteExact': True, 'sourceId': source['id'], 'sha256': sha(current),
                                  'footprintIds': ids, 'triangles': stats['triangles']},
        'triangleRangesBySource': ranges,
        'rangeConvention': 'Half-open [start,end) current residual indexed triangle ranges per material after filtering original owners.',
        'ancestorAssetId': ancestor_id, 'ancestorSha256': sha(original),
        'ancestorAuthoringReplay': original_proof}


def prepare(input_path=INPUT):
    batch = safe_id(input_path.stem.removesuffix('-fallback-inputs'))
    frozen = read(input_path)
    folder = ROOT / 'public/models'
    base = read(folder / 'manifest.json')
    assets = {a['id']: a for a in base['assets']}
    matches = read(folder / 'footprint-matches.json')
    existing = read(folder / 'generic-corrections.json')
    current_assets, current_matches, ancestors, touched = effective_sources(
        base['assets'], matches, existing['corrections'])
    reserved_ids = set(assets) | touched
    processed_sources = set()
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
        assert source_id not in processed_sources, 'Duplicate compound source'
        processed_sources.add(source_id)
        residual = frozen_source.get('currentResidual', False)
        assert isinstance(residual, bool), 'currentResidual must be boolean'
        if residual:
            assert source_id in touched and source_id in current_assets, 'Residual is not currently active'
            source = current_assets[source_id]
            assert source.get('genericCorrection'), 'Expected a corrected residual'
            ids = current_matches[source_id]
            remaining_id = safe_id(frozen_source['residualAssetId'])
            assert remaining_id not in reserved_ids, 'Residual ID must be new'
            owners, authoring = replay_current_residual(frozen_source, folder, source, ids,
                                                        assets, matches, ancestors[source_id])
        else:
            source = assets[source_id]
            assert source_id not in touched, 'Preserve existing corrections'
            ids = matches[source_id]
            remaining_id = None
            original = (folder / source['model']).read_bytes()
            assert sha(original) == source['sha256'] == frozen_source['sha256']
            owners, authoring = replay(source, original, ids, frozen_source['provenance'])
        assert ids == frozen_source['footprintIds'], 'Frozen current ownership differs'
        assert len(ids) == len(set(ids)), 'Duplicate current footprints'
        original = (folder / source['model']).read_bytes()
        targets = frozen_source['targets']
        parts = [(f"fallback-{t['site']}-{t['number']}", t['name'], t['sourceId']) for t in targets]
        output_ids = [aid for aid, _, _ in parts] + ([remaining_id] if remaining_id else [])
        assert len(output_ids) == len(set(output_ids)), 'Duplicate output IDs'
        assert not set(output_ids) & reserved_ids, 'Output ID already exists'
        reserved_ids.update(output_ids)
        cfg = {'site': batch + '-' + source_id, 'source': source_id, 'sha': source['sha256'],
            'count': len(ids), 'removeApartmentCode': True,
            'remainingName': '대상 외 원천 건물 (기존 추정 모형)', 'parts': parts,
            'limits': ['Only archived indexed triangles, material attributes and terrain anchors are partitioned; no photo-modeling credit.',
                frozen['scope'],
                'All unnamed, unmatched and unrelated source buildings remain in unchanged-shape residuals. Original convex-hull approximations remain archived.']}
        correction, files, proof = partition_by_replayed_source(cfg, folder, source, ids, owners, authoring, remainingId=remaining_id)
        gltf, primitives = decode(original)
        signatures = {fid: Counter() for fid in ids}
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
        residuals.extend(fid for fid in ids if fid not in selected)
        proof['sourceAuthoringReplay'] = authoring
        proof['ownershipMethod'] += ' Byte-exact archived authoring replay and per-source triangle-signature multiplicity independently checked.'
        files[ROOT / f"docs/model-audit/{cfg['site']}-generic-split.json"] = encoded(proof)
        assert not set(files) & set(documents), 'Duplicate output paths'
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
