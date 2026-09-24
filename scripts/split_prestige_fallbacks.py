#!/usr/bin/env python3
"""Conserve archived Prestige meshes and correct the mislabeled 125 singleton.

Run with .venv/bin/python scripts/split_prestige_fallbacks.py. Existing generic
corrections and all original catalog files remain unchanged.
"""
import copy
import hashlib
import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import transform

from build_district_landmarks import projected, special_geometry, unprojected
from split_acro_fallbacks import FeatureMesh
from split_banpo_fallbacks import partition
from split_caelitus_fallback import ROOT, decode, sha
from publish_bespoke_models import replace_batch

TOWERS = {
    101: '2541ff4f-21d3-4ea5-8250-7d0950910d90', 102: 'eef0c80b-2e4b-4820-b6cb-fbce636fb4ea',
    103: '02fc7e0f-5c24-41ce-9707-1c697a10762d', 104: '7220e8e0-ce7f-490b-92ba-57f09aa09d8c',
    105: '8d6ab8b4-1c90-44ea-894d-85f51054c107', 106: 'cd628397-c01c-4bd0-b67f-b29dc7c88923',
    107: '48c7ac76-ad32-45db-af1d-51dcc23ad52c', 108: '45ef175c-213d-48cc-8d7d-cfff01202638',
    109: 'd7b8c3be-2a27-4e31-ae90-f805747aa664', 110: '5c068973-bfc6-4148-b5a4-be1a8e87eb94',
    111: '5bc96bb1-8a13-4115-b4db-f5ad97d1e2bf', 112: '697147a0-de7d-4fa2-ab82-758800796ded',
    113: 'ae891078-f1d8-463f-b7ae-ecb6387c3e48', 114: '97eb6fd0-2c0b-45cc-81d2-a66441aecb85',
    115: '76147cfe-8510-4d14-9736-6dfaee75bb1b', 116: '0f40242b-1f64-427c-b5dd-fafdd2ba2ecd',
    117: 'f8b46fce-7de9-4fed-9ab2-43cb981bd3bb', 118: '7dca6e17-aa57-4e45-8cba-d79383ec82bf',
    119: 'b85eaa33-701e-4c04-9394-7aead423be08', 120: '94e5374f-559d-4fb3-ac52-5d8258334774',
    121: '867da145-5d02-42d1-9d26-ef381dd0b7d6', 122: '6ab4af87-98a4-423b-95b9-9534220c15da',
    123: '862e6d08-7acc-4e9b-bd17-56745a737e83', 124: 'f1290d9e-8fb3-4d06-9cde-654603528257',
    125: 'e5b827c0-047d-47e7-8bd9-9f2613e45148', 126: 'b21842a2-9832-4a21-bcc5-1c571f309556',
    127: '2e9c2654-8b83-481c-b454-540c5dea2a68', 128: '6ffdd952-2910-46e0-8ac1-6994a4dba839',
}
SOURCE_HASHES = {
    'apt-a13776509': 'e9510f9a7d8a6ad3e82a29bcfa89f707ce44923e72eaef4cc580204047d916ff',
    'apt-a13776508': '25ce92589d5735e5ed311c96d2a805ac1ae71198510ec2cffead33cc8fadbb0c',
    'apt-a13780001': '32e80cf8af229081e9202cce7440826203288ee94dc63169f8fd62297b502dbe',
}
MAIN_NUMBERS = [102, *range(104, 124)]
SHOPS = ['af87fb1a-62e3-4208-9f31-8162551b7cac', '2922e743-4d1e-4765-b0aa-d89f904d3bea']
PRUGIO = ['e3069b86-ce0d-40bc-bae0-ce992d17b840', '02ce4ed4-d5a5-4972-8cbb-65493c52d1af', '9f08c45e-b1cc-40ae-b963-05e5968996ea']


def canonical_sha(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def triangle_signatures(data):
    document, primitives = decode(data)
    out = Counter()
    for primitive, attributes, indices in primitives:
        material = json.dumps(document['materials'][primitive['material']], sort_keys=True, separators=(',', ':')).encode()
        for index in indices:
            out[sha(material + b''.join(k.encode() + attributes[k][index].tobytes() for k in sorted(attributes)))] += 1
    return out


def replay(asset, original, ids, provenance_path):
    """Use frozen authoring order, then require the entire GLB to match exactly."""
    source = asset['id']
    evidence = next(a for a in json.loads((ROOT / provenance_path).read_text())['assets'] if a['id'] == source)
    candidate = evidence['selection']
    assert set(candidate['buildingIds']) == set(ids)
    anchor = (candidate['coordinate']['lon'], candidate['coordinate']['lat'])
    with sqlite3.connect(f'file:{ROOT}/data/buildings.sqlite?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute('SELECT * FROM buildings WHERE id IN (' + ','.join('?' for _ in ids) + ')', ids)]
    assert [r['id'] for r in rows] == [r['buildingId'] for r in evidence['buildings']]
    mesh = FeatureMesh()
    seed = int(hashlib.sha256(source.encode()).hexdigest()[:8], 16)
    ranges = []
    for row, frozen in zip(rows, evidence['buildings']):
        assert row['height_m'] == frozen['sourceHeightM'] and row['num_floors'] == frozen['sourceFloors']
        mesh.source_id = row['id']
        starts = [len(v) for v in mesh.owners]
        local = transform(lambda x, y, z=None: projected(x, y, anchor), shape(json.loads(row['geometry'])))
        if not local.is_valid:
            local = local.buffer(0)
        floors = max(2, min(100, int(row['num_floors'] or candidate.get('floors') or candidate.get('estimatedFloors') or 15)))
        measured = row['height_m'] if row['height_m'] and row['height_m'] > 3 else None
        height = measured or floors * 3.05
        shade = ((seed + int(hashlib.md5(row['id'].encode()).hexdigest()[:5], 16)) % 9) / 100
        body, roof = [.69 + shade, .70 + shade, .68 + shade], [.39 + shade, .44 + shade, .42 + shade]
        for poly in ([local] if local.geom_type == 'Polygon' else list(local.geoms)):
            if poly.area < 2:
                continue
            poly = poly.simplify(.18, preserve_topology=True)
            assert not special_geometry(mesh, poly, candidate['nameKo'], height, floors, seed, body, roof)
            bodytop = height - min(2.4, height * .045) if measured else height
            mesh.solid(poly, 0, bodytop, body, roof)
            mesh.detail(poly, bodytop, floors, seed, roof_ceiling=height if measured else None)
        ranges.append({'sourceId': row['id'], 'triangleRangesByMaterial': [[start, len(owners)] for start, owners in zip(starts, mesh.owners)]})
    with tempfile.TemporaryDirectory(prefix='prestige-source-replay-') as tmp:
        path = Path(tmp) / f'{source}.glb'
        _, offset = mesh.save(path)
        assert path.read_bytes() == original, 'Original source replay differs; publication must stop'
    assert tuple(unprojected(offset[0], offset[2], anchor)) == (asset['coordinate']['lon'], asset['coordinate']['lat'])
    return mesh.owners, {'byteExact': True, 'sha256': sha(original), 'provenancePath': provenance_path,
        'frozenAssetProvenanceSha256': canonical_sha(evidence), 'authoringAnchor': list(anchor),
        'generator': 'scripts/build_district_landmarks.py', 'generatorSha256': sha((ROOT / 'scripts/build_district_landmarks.py').read_bytes()),
        'triangleRangesBySource': ranges, 'rangeConvention': 'Half-open [start,end) original indexed triangle ranges, one range per material; original vertex packing retains emission order.'}


def prepare(folder, base, matches, existing):
    assets = {a['id']: a for a in base['assets']}
    added, documents = [], {}
    for source, numbers, neighbors, name, site, provenance in [
        ('apt-a13776509', MAIN_NUMBERS, SHOPS, '래미안퍼스티지 상가 2동 (기존 추정 모형)', 'prestige-main', 'docs/LANDMARK_EXPANSION_PROVENANCE.json'),
        ('apt-a13776508', [103], PRUGIO, '반포푸르지오 3동 (기존 추정 모형)', 'prestige-103', 'docs/APARTMENT_100_PROVENANCE.json'),
    ]:
        original = (folder / assets[source]['model']).read_bytes()
        assert sha(original) == assets[source]['sha256'] == SOURCE_HASHES[source]
        assert set(matches[source]) == set(neighbors) | {TOWERS[n] for n in numbers}
        owners, authoring = replay(assets[source], original, matches[source], provenance)
        cfg = {'site': site, 'source': source, 'sha': SOURCE_HASHES[source], 'count': len(matches[source]),
            'remainingName': name, 'parts': [(f'fallback-prestige-{n}', f'래미안퍼스티지 {n}동', TOWERS[n]) for n in numbers],
            'limits': ['Exact archived geometry partition only; all source heights and estimates remain unchanged. No residential or photo-completion credit.',
                'Main compound contains21 residential towers and2 shopping buildings. The103 archive includes3 unrelated Banpo Prugio towers. Every non-Prestige source remains in a residual.',
                'The original main-compound geometry has242 triangles requiring uniquely covering source convex hulls, up to12.293m outside concave boundaries. This inherited approximation is preserved, not repaired.']}
        correction, generated, proof = partition(cfg, folder, base, matches)
        gltf, primitives = decode(original)
        source_signatures = {fid: Counter() for fid in matches[source]}
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
            assert triangle_signatures(generated[folder / part['model']]) == expected, 'Geometric partition disagrees with exact source authoring'
            if part['id'] != source:
                part.pop('apartmentCode', None)
            if part['id'] == source and source == 'apt-a13776509':
                part['category'] = 'commercial'
        proof['sourceAuthoringReplay'] = authoring
        proof['ownershipMethod'] += ' Byte-exact original authoring replay independently verifies the original source feature of every output triangle.'
        generated[ROOT / f'docs/model-audit/{site}-generic-split.json'] = (json.dumps(proof, ensure_ascii=False, indent=2) + '\n').encode()
        added.append(correction)
        documents.update(generated)
    source = 'apt-a13780001'
    original = assets[source]
    raw = (folder / original['model']).read_bytes()
    assert sha(raw) == original['sha256'] == SOURCE_HASHES[source]
    assert matches[source] == original['footprintIds'] == [TOWERS[125]]
    _, authoring = replay(original, raw, matches[source], 'docs/APARTMENT_100_PROVENANCE.json')
    corrected = copy.deepcopy(original)
    corrected.update(name='래미안퍼스티지 125동 (기존 추정 모형)', nameKo='래미안퍼스티지 125동 (기존 추정 모형)')
    corrected.pop('householdCount', None)
    corrected.pop('apartmentCode', None)
    corrected['sourceIdentity'] = {'sourceFootprintId': TOWERS[125], 'correctedNumber': 125,
        'basis': 'Exact numbered source footprint is125동 within the reviewed Prestige site boundary; the old nearest-complex label was Shinbanpo15.',
        'archivedSourceName': original['nameKo'], 'removedApartmentCode': original.get('apartmentCode'),
        'removedHouseholdCount': original.get('householdCount'), 'geometryChanged': False,
        'sourceProvenance': 'docs/APARTMENT_100_PROVENANCE.json'}
    added.append({'kind': 'metadata-only', 'sourceId': source, 'sourceSha256': original['sha256'], 'sourceFootprintIds': matches[source], 'assets': [corrected]})
    documents[ROOT / 'docs/model-audit/prestige-125-identity.json'] = (json.dumps({'sourceId': source,
        'kind': 'metadata-only', 'sourceSha256': original['sha256'], 'sourceModel': original['model'],
        'sourceAuthoringReplay': authoring, 'sourceIdentity': corrected['sourceIdentity'],
        'limits': ['Only effective names and incorrect apartment/household identity metadata change. Original GLB path, bytes, geometry, height and all rendering properties remain unchanged. No completion credit.']}, ensure_ascii=False, indent=2) + '\n').encode()
    replacements = {c['sourceId'] for c in added}
    result = copy.deepcopy(existing)
    result['corrections'] = [c for c in existing['corrections'] if c['sourceId'] not in replacements] + added
    effective = dict(assets)
    for correction in result['corrections']:
        effective.pop(correction['sourceId'], None)
        effective.update({a['id']: a for a in correction['assets']})
    bindings = []
    for number, fid in TOWERS.items():
        if number in MAIN_NUMBERS or number == 103:
            fallback = f'fallback-prestige-{number}'
        elif number == 125:
            fallback = 'apt-a13780001'
        elif number == 126:
            fallback = 'fallback-prestige-126'
        else:
            fallback = f'residential-{fid}'
        a = effective[fallback]
        assert a['footprintIds'] == [fid]
        bindings.append({'number': number, 'sourceFootprintId': fid, 'fallbackAssetId': fallback,
            'supersedes': [fallback], 'fallbackModel': a['model'], 'fallbackSha256': a['sha256']})
    binding_document = {'version': 1, 'complex': '래미안퍼스티지', 'residentialBuildingCount': 28,
        'bindings': bindings, 'limits': ['These are fallback source bindings, not residential completion records. Two shopping buildings and three Prugio neighbors remain outside residential coverage. No complex household total is assigned to a fallback.']}
    documents[ROOT / 'docs/model-audit/prestige-fallback-bindings.json'] = (json.dumps(binding_document, ensure_ascii=False, indent=2) + '\n').encode()
    return result, documents, binding_document


def main():
    folder = ROOT / 'public/models'
    existing = json.loads((folder / 'generic-corrections.json').read_text())
    result, documents, bindings = prepare(folder, json.loads((folder / 'manifest.json').read_text()), json.loads((folder / 'footprint-matches.json').read_text()), existing)
    documents[folder / 'generic-corrections.json'] = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode()
    deployment_path = ROOT / 'public/data/deployment-assets.json'
    deployment = json.loads(deployment_path.read_text())
    for path, data in documents.items():
        if path.is_relative_to(folder):
            deployment['files'][str(path.relative_to(ROOT))] = sha(data)
    documents[deployment_path] = (json.dumps(deployment, ensure_ascii=False, indent=2) + '\n').encode()
    replace_batch([], documents)
    stage = ROOT / 'data/model-source/bespoke/raemian-prestige-fallback-review'
    stage.mkdir(parents=True, exist_ok=True)
    (stage / 'published-model-binding-map.json').write_text(json.dumps(bindings, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'numberedBindings': len(bindings['bindings']), 'changedSourceIds': list(SOURCE_HASHES),
        'newPartitionGlbs': sum(p.suffix == '.glb' for p in documents), 'identityOnly125PreservedGlb': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
