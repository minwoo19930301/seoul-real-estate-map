#!/usr/bin/env python3
"""Conserve Banpo Xi fallback triangles and expose 44 independent bindings.

Run with .venv/bin/python scripts/split_banpo_xi_fallbacks.py. --stage-only
writes review artifacts under ignored data/model-source only. Deployment hashes
are deliberately regenerated separately by the publishing workflow.
"""
import argparse
import copy
import json
import math
import sqlite3
from collections import Counter

import numpy as np
from shapely.geometry import shape, MultiPoint, Point
from shapely.ops import transform

from split_caelitus_fallback import ROOT, decode, encode, sha
from split_prestige_fallbacks import canonical_sha, replay, triangle_signatures
from publish_bespoke_models import replace_batch

SOURCE = 'apt-a13704104'
SINGLETON = 'apt-a10020044'
SOURCE_SHA = 'e4066ceee7746e353fe7f88ef794a892ee541cef1dad9bc583c4bb32a50b5e6a'
SINGLETON_SHA = '1ff87eec0916a91fe001a5a0df80543916bcaf44fec41b2d28e4b36e0dcbea73'
MODELING_SHA = '45660daf8938c9731fcd51b74310084afd0ebf3e7744b2652a62a45bd1b3d3d1'
PRIOR_IDS = ['apt-a14003002', 'apt-a15088614', 'apt-a15805111', 'apt-a10022556',
    'apt-a10023043', 'apt-a13780006', 'apt-a10027205', 'apt-a13776509',
    'apt-a13776508', 'apt-a13780001']
PRIOR_SHA = 'bb787ec5b2219ea68a6e90e11691e8aa34b48f488acc4af84dd4bab65eff90ce'
COMPOUND_NUMBERS = [*range(105, 115), 120, 121, 122, *range(124, 139), 141]
NEIGHBORS = ['2e5f75ff-42ce-4cf0-952c-64f0735f6c58', '7eae0834-799e-4a2e-b963-edbb342deee6',
    '88a1957d-d202-484c-8e56-fedd5c316caa', '786be1de-75f8-4622-9be6-24cbb978fa6b',
    '8bcaad2c-8395-44c4-afb4-1d99b911e669', 'fe21f8a0-f308-4952-9790-ac83682dc009',
    'b5bc1824-73fc-40a0-86ce-d64bdaf05579', '0c23dbe6-8aea-47d3-a991-8e951fcf6034',
    '1ce6c515-cc4f-43d5-9702-a4a6df1ed74e', 'b08cf7d7-c2ca-4fdf-9d71-fd85fc55499b',
    'cba1e402-f59c-42ac-8782-eb6ad55e7ff7', '9c166851-f70b-4153-bc83-e52fb8d5cdc8',
    'ea2097a6-e3d9-4b23-8b2f-9829260a0d97', '67317851-d3e8-494b-a24a-daf895619c43',
    'd668078b-45a9-434c-9073-feb490277b67', 'd82acd35-cd42-4662-a8eb-ba3e1913ffdc']
STAGE = ROOT / 'data/model-source/bespoke/banpo-xi-fallback-review'


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def exact_partition(cfg, folder, base, matches, source_owners):
    """Select original indexed emissions; geometry validates but never guesses owners."""
    asset = next(a for a in base['assets'] if a['id'] == SOURCE)
    original = (folder / asset['model']).read_bytes()
    gltf, primitives = decode(original)
    assert len(gltf['nodes']) == 1 and set(gltf['nodes'][0]) == {'mesh', 'name'}
    groups = [(SOURCE, cfg['remainingName'], NEIGHBORS)] + [(pid, name + ' (기존 추정 모형)', [fid]) for pid, name, fid in cfg['parts']]
    group_index = {fid: i for i, (_, _, subset) in enumerate(groups) for fid in subset}
    assert set(group_index) == set(matches[SOURCE]) and sum(len(g[2]) for g in groups) == 45
    anchor = asset['coordinate']
    scale = 6378137 * math.cos(math.radians(anchor['lat']))
    lat0 = math.log(math.tan(math.pi / 4 + math.radians(anchor['lat']) / 2))
    def project(x, y, z=None):
        return scale * math.radians(x - anchor['lon']), -scale * (math.log(math.tan(math.pi / 4 + math.radians(y) / 2)) - lat0)
    with sqlite3.connect(f'file:{ROOT}/data/buildings.sqlite?mode=ro', uri=True) as db:
        rows = {fid: db.execute('SELECT name,height_m,geometry FROM buildings WHERE id=?', (fid,)).fetchone() for fid in matches[SOURCE]}
    shapes = {fid: transform(project, shape(json.loads(row[2]))) for fid, row in rows.items()}
    source_buffers = {fid: poly.buffer(.15) for fid, poly in shapes.items()}
    source_hulls = {fid: poly.convex_hull.buffer(.15) for fid, poly in shapes.items()}
    assignments, ambiguities, flat_owners, parents, vertices = [], [], [], [], {}
    hull_triangles, maximum = 0, 0
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    for primitive, attrs, indices in primitives:
        tagged = source_owners[primitive['material']]
        assert len(tagged) == len(indices)
        selected = []
        for index, (triangle, fid) in enumerate(zip(attrs['POSITION'][indices], tagged)):
            owner = group_index[fid]
            projected_vertices = MultiPoint(triangle[:, [0, 2]])
            outline = projected_vertices.convex_hull
            candidate_sources = [other for other, poly in source_buffers.items() if poly.covers(outline)]
            used_hull = not candidate_sources
            if used_hull:
                candidate_sources = [other for other, poly in source_hulls.items() if poly.covers(outline)]
                hull_triangles += 1
            candidates = sorted({group_index[other] for other in candidate_sources})
            assert fid in candidate_sources, ('Source replay disagrees with geometry', fid, index, candidate_sources)
            if len(candidate_sources) > 1:
                assert not used_hull and outline.convex_hull.geom_type in {'Point', 'LineString'}, ('Only shared source boundaries can use exact-emission ownership', fid, primitive['material'], index, used_hull, outline.convex_hull.geom_type, outline.convex_hull.area, candidate_sources, triangle.tolist())
                others = [other for other in candidate_sources if other != fid]
                overlap = max(shapes[fid].intersection(shapes[other]).area for other in others)
                distances = {other: max(shapes[other].boundary.distance(p) for p in projected_vertices.geoms) for other in [fid, *others]}
                assert overlap < 1e-9 and max(distances.values()) <= .15, 'Ambiguity is not a zero-area shared boundary'
                ambiguities.append({'material': primitive['material'], 'triangleIndex': index, 'emissionSourceId': fid,
                    'otherSourceIds': others, 'candidateGroups': [groups[i][0] for i in candidates],
                    'positiveAreaOverlapM2': overlap, 'maximumVertexDistanceToSourceBoundaryM': distances})
            selected.append(owner)
            maximum = max(maximum, max(shapes[fid].distance(Point(float(v[0]), float(v[2]))) for v in triangle))
            current = len(parents)
            parents.append(current)
            flat_owners.append(owner)
            for vertex in triangle:
                key = vertex.tobytes()
                if key in vertices:
                    parents[find(current)] = find(vertices[key])
                else:
                    vertices[key] = current
        assignments.append(np.array(selected))
    components = {}
    for index, owner in enumerate(flat_owners):
        components.setdefault(find(index), set()).add(owner)
    outputs, documents = [], {}
    for index, (pid, name, subset) in enumerate(groups):
        data, stats = encode(gltf, primitives, [a == index for a in assignments], pid)
        model = f'generic-corrections/{pid}.glb'
        part = copy.deepcopy(asset)
        part.update(stats, id=pid, model=model, name=name, nameKo=name, buildingCount=len(subset), footprintIds=subset,
            searchable=pid == SOURCE, residentialCompletionCredit=False)
        part.pop('apartmentCode', None)
        part.pop('householdCount', None)
        low, high = stats['bounds']['min'], stats['bounds']['max']
        def lon(x): return anchor['lon'] + math.degrees(x / scale)
        def lat(z): return math.degrees(2 * math.atan(math.exp(lat0 - z / scale)) - math.pi / 2)
        part['geoBounds'] = [lon(low[0]), lat(high[2]), lon(high[0]), lat(low[2])]
        part['measuredGlbDimensions'] = stats['dimensions']
        part['genericCorrection'] = {'sourceId': SOURCE, 'sourceSha256': SOURCE_SHA,
            'operation': 'Exact original source-emission triangle partition; unchanged vertex attributes, materials and original terrain anchor.'}
        outputs.append(part)
        documents[folder / model] = data
    assert sum(a['triangles'] for a in outputs) == asset['triangles'] == 22551
    proof = {'version': 1, 'sourceId': SOURCE, 'sourceSha256': SOURCE_SHA, 'sourceTriangles': asset['triangles'], 'sourceCoordinate': anchor,
        'sourceFootprints': [{'id': fid, 'sourceName': row[0], 'sourceHeightM': row[1], 'localFootprint': shapes[fid].__geo_interface__} for fid, row in rows.items()],
        'triangleCountsByGroup': {a['id']: a['triangles'] for a in outputs}, 'groupFootprints': {a['id']: a['footprintIds'] for a in outputs},
        'vertexConnectedComponents': len(components), 'crossGroupComponents': sum(len(v) > 1 for v in components.values()),
        'ownershipToleranceM': .15, 'trianglesAssignedWithinUniqueSourceConvexHull': hull_triangles,
        'maximumVertexDistanceOutsideSourceFootprintM': maximum,
        'ownershipMethod': 'Every indexed original triangle uses its byte-exact generator emission source. Independent full projected triangle or line coverage by the individual source polygon, otherwise a uniquely covering individual source convex hull, must agree. Only zero-area shared-boundary spatial ambiguities use the proven original emission identity; no nearest-footprint attribution is allowed.',
        'sharedBoundaryAmbiguityCount': len(ambiguities), 'sharedBoundaryAmbiguities': ambiguities,
        'outputs': [{k: a[k] for k in ['id', 'model', 'sha256', 'bytes', 'triangles', 'bounds', 'footprintIds']} for a in outputs], 'limits': cfg['limits']}
    return {'sourceId': SOURCE, 'sourceSha256': SOURCE_SHA, 'sourceFootprintIds': matches[SOURCE], 'assets': outputs}, documents, proof


def prepare():
    folder = ROOT / 'public/models'
    base = json.loads((folder / 'manifest.json').read_text())
    matches = json.loads((folder / 'footprint-matches.json').read_text())
    existing = json.loads((folder / 'generic-corrections.json').read_text())
    identity = json.loads((ROOT / 'docs/model-audit/banpo-xi-source-identity.json').read_text())
    assert identity['sources']['modelingSourceSha256'] == MODELING_SHA
    towers = {t['number']: t['sourceId'] for t in identity['towers']}
    assert sorted(towers) == list(range(101, 145)) and len(set(towers.values())) == 44
    assert identity['sources']['boundary']['way'] == '165196918'
    assert all(t['membershipEvidence']['strict_covers'] and not t['sourceChildIds'] for t in identity['towers'])
    prior = [c for c in existing['corrections'] if c['sourceId'] in PRIOR_IDS]
    assert [c['sourceId'] for c in prior] == PRIOR_IDS and canonical_sha(prior) == PRIOR_SHA
    for correction in prior:
        for asset in correction['assets']:
            assert sha((folder / asset['model']).read_bytes()) == asset['sha256']
    assets = {a['id']: a for a in base['assets']}
    source = assets[SOURCE]
    original = (folder / source['model']).read_bytes()
    assert sha(original) == source['sha256'] == SOURCE_SHA
    assert len(matches[SOURCE]) == 45
    assert set(matches[SOURCE]) == {towers[n] for n in COMPOUND_NUMBERS} | set(NEIGHBORS)
    owners, authoring = replay(source, original, matches[SOURCE], 'docs/DISTRICT_LANDMARK_PROVENANCE.json')
    cfg = {'site': 'banpo-xi', 'source': SOURCE, 'sha': SOURCE_SHA, 'count': 45,
        'remainingName': '반포자이 원본 모형의 별도 건물 16동 (기존 추정 모형)',
        'removeApartmentCode': True,
        'parts': [(f'fallback-banpo-xi-{n}', f'반포자이 {n}동', towers[n]) for n in COMPOUND_NUMBERS],
        'limits': ['Only 29 of the 44 reviewed Banpo Xi residential towers occur in this archive. Sixteen other source buildings remain in the residual and have no Banpo Xi residential completion credit.',
            'All archived triangles, source heights, vertex attributes, materials, terrain anchors and modeling approximations are preserved. No new photo-model completion is claimed.',
            'The residual label describes archive membership only; the identities of its sixteen source buildings have not been newly certified. No whole-complex apartment code or household count is assigned to any partition.']}
    correction, documents, proof = exact_partition(cfg, folder, base, matches, owners)
    gltf, primitives = decode(original)
    source_signatures = {fid: Counter() for fid in matches[SOURCE]}
    for primitive, attributes, indices in primitives:
        tagged = owners[primitive['material']]
        assert len(indices) == len(tagged)
        material = json.dumps(gltf['materials'][primitive['material']], sort_keys=True, separators=(',', ':')).encode()
        for fid, index in zip(tagged, indices):
            source_signatures[fid][sha(material + b''.join(k.encode() + attributes[k][index].tobytes() for k in sorted(attributes)))] += 1
    for part in correction['assets']:
        expected = Counter()
        for fid in part['footprintIds']:
            expected.update(source_signatures[fid])
        assert triangle_signatures(documents[folder / part['model']]) == expected, 'Independent geometry partition disagrees with byte-exact source replay'
        assert 'apartmentCode' not in part and 'householdCount' not in part
    proof['sourceAuthoringReplay'] = authoring
    proof['ownershipMethod'] += ' Byte-exact original generator replay independently verifies every output triangle against its original source feature.'
    proof['preservedPriorCorrectionIds'] = PRIOR_IDS
    proof['preservedPriorCorrectionsCanonicalSha256'] = PRIOR_SHA
    documents[ROOT / 'docs/model-audit/banpo-xi-generic-split.json'] = json_bytes(proof)

    singleton = assets[SINGLETON]
    raw = (folder / singleton['model']).read_bytes()
    assert sha(raw) == singleton['sha256'] == SINGLETON_SHA
    assert matches[SINGLETON] == singleton['footprintIds'] == [towers[116]]
    _, singleton_replay = replay(singleton, raw, matches[SINGLETON], 'docs/APARTMENT_100_PROVENANCE.json')
    corrected = copy.deepcopy(singleton)
    corrected.update(name='반포자이 116동 (기존 추정 모형)', nameKo='반포자이 116동 (기존 추정 모형)')
    corrected.pop('apartmentCode', None)
    corrected.pop('householdCount', None)
    corrected['sourceIdentity'] = {'sourceFootprintId': towers[116], 'correctedNumber': 116,
        'basis': 'The complete numbered 116 source polygon is inside the reviewed Banpo Xi boundary. The nearest-complex archive label was incorrect.',
        'archivedSourceName': singleton['nameKo'], 'removedApartmentCode': singleton.get('apartmentCode'),
        'removedHouseholdCount': singleton.get('householdCount'), 'geometryChanged': False,
        'sourceProvenance': 'docs/APARTMENT_100_PROVENANCE.json', 'identityEvidence': 'docs/model-audit/banpo-xi-source-identity.json'}
    identity_correction = {'kind': 'metadata-only', 'sourceId': SINGLETON, 'sourceSha256': SINGLETON_SHA,
        'sourceFootprintIds': matches[SINGLETON], 'assets': [corrected]}
    documents[ROOT / 'docs/model-audit/banpo-xi-116-identity.json'] = json_bytes({'version': 1, 'kind': 'metadata-only',
        'sourceId': SINGLETON, 'sourceSha256': SINGLETON_SHA, 'sourceModel': singleton['model'],
        'sourceAuthoringReplay': singleton_replay, 'sourceIdentity': corrected['sourceIdentity'],
        'limits': ['Only names and incorrect complex identity metadata change. Original GLB bytes and every rendering property remain unchanged. No completion credit.']})
    result = copy.deepcopy(existing)
    result['corrections'] = [c for c in existing['corrections'] if c['sourceId'] not in {SOURCE, SINGLETON}] + [correction, identity_correction]
    effective = dict(assets)
    effective_matches = dict(matches)
    for item in result['corrections']:
        effective.pop(item['sourceId'], None)
        effective_matches.pop(item['sourceId'], None)
        for asset in item['assets']:
            effective[asset['id']] = asset
            effective_matches[asset['id']] = asset['footprintIds']
    bindings = []
    for number, fid in sorted(towers.items()):
        fallback = f'fallback-banpo-xi-{number}' if number in COMPOUND_NUMBERS else SINGLETON if number == 116 else f'residential-{fid}'
        asset = effective[fallback]
        assert effective_matches[fallback] == asset['footprintIds'] == [fid]
        assert [aid for aid, ids in effective_matches.items() if fid in ids] == [fallback]
        raw = documents.get(folder / asset['model']) or (folder / asset['model']).read_bytes()
        assert sha(raw) == asset['sha256']
        bindings.append({'number': number, 'sourceFootprintId': fid, 'fallbackAssetId': fallback,
            'supersedes': [fallback], 'fallbackModel': asset['model'], 'fallbackSha256': asset['sha256'],
            'archivedSourceAssetId': SOURCE if number in COMPOUND_NUMBERS else fallback})
    assert len({b['fallbackAssetId'] for b in bindings}) == 44
    # Only geographically intersecting catalog shards can contain these sources.
    tower_bounds = [shape(t['geometry']).bounds for t in identity['towers']]
    bounds = [min(b[0] for b in tower_bounds), min(b[1] for b in tower_bounds),
        max(b[2] for b in tower_bounds), max(b[3] for b in tower_bounds)]
    index_path = folder / base['catalogIndex']
    index_bytes = index_path.read_bytes()
    catalog = json.loads(index_bytes)
    checked_tiles = []
    for tile in catalog['tiles']:
        low_x, low_y, high_x, high_y = tile['bounds']
        if high_x < bounds[0] or low_x > bounds[2] or high_y < bounds[1] or low_y > bounds[3]:
            continue
        data = (folder / tile['path']).read_bytes()
        assert sha(data) == tile['sha256']
        tile_assets = json.loads(data)['assets']
        assert len(tile_assets) == tile['count']
        assert not any(set(a.get('footprintIds', [])) & set(towers.values()) for a in tile_assets), 'Streamed catalog independently claims a reviewed tower'
        checked_tiles.append({'path': tile['path'], 'sha256': tile['sha256'], 'assetCount': tile['count']})
    binding_document = {'version': 1, 'complex': '반포자이', 'residentialBuildingCount': 44,
        'sourceIdentity': 'docs/model-audit/banpo-xi-source-identity.json', 'modelingSourceSha256': MODELING_SHA,
        'bindings': bindings, 'residual': {'assetId': SOURCE, 'sourceFootprintIds': NEIGHBORS},
        'catalogOwnershipAudit': {'catalogIndex': base['catalogIndex'], 'catalogIndexSha256': sha(index_bytes),
            'reviewedTowerBounds': bounds, 'checkedTiles': checked_tiles, 'additionalOwners': 0},
        'limits': ['Fallback bindings establish independent replacement only and claim no residential or photo-model completion.',
            '103 retains its existing fallback unchanged. The unresolved official 57.7m / 27F conflict does not authorize any height adjustment.',
            'Fourteen residential singleton GLBs remain unchanged. The 116 singleton changes identity metadata only.']}
    documents[ROOT / 'docs/model-audit/banpo-xi-fallback-bindings.json'] = json_bytes(binding_document)
    documents[folder / 'generic-corrections.json'] = json_bytes(result)
    return documents, binding_document, proof


def main(stage_only=False):
    documents, bindings, proof = prepare()
    STAGE.mkdir(parents=True, exist_ok=True)
    (STAGE / 'published-model-binding-map.json').write_bytes(json_bytes(bindings))
    (STAGE / 'generic-split-proof.json').write_bytes(json_bytes(proof))
    (STAGE / 'source-inventory.json').write_bytes(json_bytes({'modelingSourceSha256': MODELING_SHA,
        'sourceIdentity': bindings['sourceIdentity'], 'catalogOwnershipAudit': bindings['catalogOwnershipAudit'],
        'bindings': bindings['bindings'], 'retainedOtherSources': [f for f in proof['sourceFootprints'] if f['id'] in NEIGHBORS],
        'preservedPriorCorrectionIds': PRIOR_IDS, 'preservedPriorCorrectionsCanonicalSha256': PRIOR_SHA}))
    for path, data in documents.items():
        relative = path.relative_to(ROOT)
        staged = STAGE / 'prepared' / relative
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(data)
    if not stage_only:
        replace_batch([], documents)
    print(json.dumps({'staged': True, 'published': not stage_only, 'bindings': 44,
        'newPartitionGlbs': sum(p.suffix == '.glb' for p in documents), 'preservedOtherSourceFootprints': 16,
        'sourceTriangles': proof['sourceTriangles'], 'priorCorrectionsPreserved': len(PRIOR_IDS),
        'bindingMap': str(STAGE / 'published-model-binding-map.json'),
        'deploymentAssetsChanged': False}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-only', action='store_true')
    main(parser.parse_args().stage_only)
