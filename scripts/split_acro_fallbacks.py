#!/usr/bin/env python3
"""Partition the immutable Acro archive using byte-exact authoring provenance.

Run .venv/bin/python scripts/split_acro_fallbacks.py. Only correction assets and
their audit/deployment entries change; the original archive remains untouched.
"""
import copy
import hashlib
import json
import math
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import shape, MultiPoint, Point
from shapely.ops import transform, unary_union

from build_district_landmarks import Mesh, projected, special_geometry, unprojected
from split_caelitus_fallback import ROOT, decode, encode, sha

SOURCE = 'apt-a10027205'
SOURCE_SHA = 'e02dd03abb3fd65981303758bf47d491d3ff41df0c593ce87b9fb94d7ca38401'
TOWERS = {
    100: '60227661-442c-454d-bb39-c5d658cf9e76',
    101: '0c8493ba-7cf2-44f4-a58a-2e2ccbbf8780',
    102: '621b7234-768f-4d6c-aa4f-a13617070687',
    103: 'f829af9c-7a4e-41dc-a623-50e8643d5bf0',
    104: 'bff8d9a4-e070-4c11-b4b3-d9524f7add37',
    105: '3215cfd2-c848-447e-af64-a35af547beea',
    106: '66bb84cf-890d-4b55-8779-a03872b28f23',
    107: '60a7320d-708b-4cd0-a1e1-5df6edf8f936',
    108: '70fc9f5a-58df-4d0b-8352-f90e337735ff',
    109: 'aecd9e1e-1d74-4198-90bb-e3a40edeebeb',
    110: '534d7d9c-978e-43dc-a409-87cf4b185358',
    111: '685bb7ca-aeb1-4942-ac11-4e5f59cca6b6',
    112: '977ad181-cc0b-49e6-9891-ef49c12ef42b',
    113: '028604ad-2a6b-46e7-87e7-129d5ca7b935',
    114: '42cae3e1-e6dd-46b6-8ade-f511b0302155',
}
CONNECTOR_110 = 'ce2823b4-6bb2-4b4a-b1f6-21f035384ce1'
NEIGHBOR = '8be35ba6-cad9-427a-b6c9-21b83caf3501'
PRESERVED_METADATA_SHA = {
    100: '48eceaca53cf3006bada7bb9569ca619f46613754c1cdea5cc241418ccded54d',
    109: '4484dab54d7a4f4ef2082abcd5ca1d5aa54e2e02478d76673d2e813fc326bd25',
}
IDENTITY_EVIDENCE = {
    'sourceId': CONNECTOR_110, 'tower': 110, 'osmWay': 543323180,
    'basis': 'Named OSM relation 7766718 version 1 explicitly contains the 20-floor way as an outer member. Its later standalone-building tag did not remove building:part=yes. Reviewed ownership restores this part to tower 110 without changing either archived source mesh.',
    'sources': [
        {'url': 'https://api.openstreetmap.org/api/0.6/relation/7766718/1',
         'sha256': 'cf1b0f60afa70ef923655208067af8d48cf03590fab67bff22c6f7730cd5dacb',
         'name': '110', 'outerWayIds': [543323179, 543323180, 543323181]},
        {'url': 'https://api.openstreetmap.org/api/0.6/relation/7766718/2',
         'sha256': '0b1986d5c170271db05f4281113709be28621805fb65869a88bce8e42f964dce',
         'name': '110', 'outerWayIds': [543323179, 543323181]},
        {'url': 'https://api.openstreetmap.org/api/0.6/relation/7766718/5',
         'sha256': '3aa9752f995c63afcea3affe2c23c15bf4547d73cd7919a1c86b967de7da2d3b',
         'name': '110', 'outerWayIds': [543323179, 543323181]},
        {'url': 'https://api.openstreetmap.org/api/0.6/way/543323180/3',
         'sha256': '1910f282c91c5cb80538917e1cd73af9cf883c334db4b95fabcdb6c5b40f2e15',
         'tags': {'building': 'apartments', 'building:levels': '20', 'building:part': 'yes', 'start_date': '2016'}},
    ],
    'limitation': 'The current relation omits this part. Attribution is a documented historical-source correction; it does not alter upstream OSM or claim a new residential building.',
}


def canonical_sha(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


class FeatureMesh(Mesh):
    """Tag successful emissions before the original generator packs vertices."""
    def __init__(self):
        super().__init__()
        self.source_id = None
        self.owners = [[], [], []]

    def tri(self, material, a, b, c, color):
        before = len(self.p[material])
        super().tri(material, a, b, c, color)
        if len(self.p[material]) != before:
            assert len(self.p[material]) == before + 3
            self.owners[material].append(self.source_id)


def replay_original(asset, original, ids):
    """Fail closed unless source data and ordered emissions rebuild every byte."""
    provenance = json.loads((ROOT / 'docs/LANDMARK_EXPANSION_PROVENANCE.json').read_text())
    evidence = next(a for a in provenance['assets'] if a['id'] == SOURCE)
    candidate = evidence['selection']
    assert set(candidate['buildingIds']) == set(ids)
    anchor = (candidate['coordinate']['lon'], candidate['coordinate']['lat'])
    with sqlite3.connect(f'file:{ROOT}/data/buildings.sqlite?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute('SELECT * FROM buildings WHERE id IN (' + ','.join('?' for _ in ids) + ')', ids)]
    assert [r['id'] for r in rows] == [r['buildingId'] for r in evidence['buildings']], 'Frozen authoring source order changed'
    mesh = FeatureMesh()
    seed = int(hashlib.sha256(SOURCE.encode()).hexdigest()[:8], 16)
    ranges = []
    for row, frozen in zip(rows, evidence['buildings']):
        assert row['height_m'] == frozen['sourceHeightM'] and row['num_floors'] == frozen['sourceFloors']
        mesh.source_id = row['id']
        starts = [len(v) for v in mesh.owners]
        local = transform(lambda x, y, z=None: projected(x, y, anchor), shape(json.loads(row['geometry'])))
        if not local.is_valid:
            local = local.buffer(0)
        polys = [local] if local.geom_type == 'Polygon' else list(local.geoms)
        floors = max(2, min(100, int(row['num_floors'] or candidate.get('floors') or candidate.get('estimatedFloors') or 15)))
        measured = row['height_m'] if row['height_m'] and row['height_m'] > 3 else None
        height = measured or floors * 3.05
        shade = ((seed + int(hashlib.md5(row['id'].encode()).hexdigest()[:5], 16)) % 9) / 100
        body, roof = [.69 + shade, .70 + shade, .68 + shade], [.39 + shade, .44 + shade, .42 + shade]
        for poly in polys:
            if poly.area < 2:
                continue
            poly = poly.simplify(.18, preserve_topology=True)
            assert not special_geometry(mesh, poly, candidate['nameKo'], height, floors, seed, body, roof)
            bodytop = height - min(2.4, height * .045) if measured else height
            mesh.solid(poly, 0, bodytop, body, roof)
            mesh.detail(poly, bodytop, floors, seed, roof_ceiling=height if measured else None)
        ranges.append({'sourceId': row['id'], 'triangleRangesByMaterial': [[start, len(owners)] for start, owners in zip(starts, mesh.owners)]})
    with tempfile.TemporaryDirectory(prefix='acro-source-replay-') as tmp:
        path = Path(tmp) / f'{SOURCE}.glb'
        _, offset = mesh.save(path)
        assert path.read_bytes() == original, 'Original authoring replay is not byte exact; do not publish guessed ownership'
    assert tuple(unprojected(offset[0], offset[2], anchor)) == (asset['coordinate']['lon'], asset['coordinate']['lat'])
    return mesh.owners, rows, {'byteExact': True, 'sha256': sha(original),
        'generator': 'scripts/build_district_landmarks.py', 'generatorSha256': sha((ROOT / 'scripts/build_district_landmarks.py').read_bytes()),
        'frozenAssetProvenanceSha256': canonical_sha(evidence), 'authoringAnchor': list(anchor),
        'triangleRangesBySource': ranges,
        'rangeConvention': 'Each half-open [start,end) counts original indexed triangles in the specified material primitive. The generator preserves emission order while packing vertices.'}


def partition(folder, base, matches):
    asset = next(a for a in base['assets'] if a['id'] == SOURCE)
    original = (folder / asset['model']).read_bytes()
    assert sha(original) == asset['sha256'] == SOURCE_SHA
    ids = matches[SOURCE]
    assert len(ids) == len(set(ids)) == 17
    assert set(ids) == set(TOWERS.values()) | {CONNECTOR_110, NEIGHBOR}
    gltf, primitives = decode(original)
    assert len(gltf['nodes']) == 1 and set(gltf['nodes'][0]) == {'mesh', 'name'}
    source_owners, rows, replay = replay_original(asset, original, ids)
    groups = [(SOURCE, '반포파크빌 (기존 추정 모형)', [NEIGHBOR])]
    groups += [(f'fallback-acro-riverpark-{number}', f'아크로리버파크 {number}동 (기존 추정 모형)', [fid] + ([CONNECTOR_110] if number == 110 else [])) for number, fid in TOWERS.items()]
    group_index = {fid: i for i, (_, _, subset) in enumerate(groups) for fid in subset}
    anchor = asset['coordinate']
    scale = 6378137 * math.cos(math.radians(anchor['lat']))
    lat0 = math.log(math.tan(math.pi / 4 + math.radians(anchor['lat']) / 2))
    def project(x, y, z=None):
        return scale * math.radians(x - anchor['lon']), -scale * (math.log(math.tan(math.pi / 4 + math.radians(y) / 2)) - lat0)
    shapes = {r['id']: transform(project, shape(json.loads(r['geometry']))) for r in rows}
    polys = [unary_union([shapes[fid] for fid in subset]) for _, _, subset in groups]
    buffers = [p.buffer(.15) for p in polys]
    hulls = [unary_union([shapes[fid].convex_hull for fid in subset]).buffer(.15) for _, _, subset in groups]
    assignments, owners, parents, vertices = [], [], [], {}
    maximum, hull_triangles = 0, 0
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    for primitive, attrs, indices in primitives:
        tagged = source_owners[primitive['material']]
        assert len(tagged) == len(indices)
        assigned = []
        for triangle, fid in zip(attrs['POSITION'][indices], tagged):
            owner = group_index[fid]
            outline = MultiPoint(triangle[:, [0, 2]])
            candidates = [i for i, poly in enumerate(buffers) if poly.covers(outline)]
            if not candidates:
                candidates = [i for i, hull in enumerate(hulls) if hull.covers(outline)]
                hull_triangles += 1
            assert candidates == [owner], 'Geometry must independently agree with exact original source ownership'
            assigned.append(owner)
            maximum = max(maximum, max(polys[owner].distance(Point(float(v[0]), float(v[2]))) for v in triangle))
            index = len(parents)
            parents.append(index)
            owners.append(owner)
            for vertex in triangle:
                key = vertex.tobytes()
                if key in vertices:
                    parents[find(index)] = find(vertices[key])
                else:
                    vertices[key] = index
        assignments.append(np.array(assigned))
    components = {}
    for i, owner in enumerate(owners):
        components.setdefault(find(i), set()).add(owner)
    assert all(len(v) == 1 for v in components.values()), 'Component crosses ownership'
    previous = next(c for c in json.loads((folder / 'generic-corrections.json').read_text())['corrections'] if c['sourceId'] == SOURCE)
    outputs, documents = [], {}
    for i, (pid, name, subset) in enumerate(groups):
        data, stats = encode(gltf, primitives, [a == i for a in assignments], pid)
        model = f'generic-corrections/{pid}.glb'
        new = copy.deepcopy(asset)
        new.update(stats, id=pid, model=model, name=name, nameKo=name, buildingCount=len(subset), footprintIds=subset, searchable=pid == SOURCE, residentialCompletionCredit=False)
        new.pop('householdCount', None)
        if pid == SOURCE:
            new.pop('apartmentCode', None)
        low, high = stats['bounds']['min'], stats['bounds']['max']
        def lon(x): return anchor['lon'] + math.degrees(x / scale)
        def lat(z): return math.degrees(2 * math.atan(math.exp(lat0 - z / scale)) - math.pi / 2)
        new['geoBounds'] = [lon(low[0]), lat(high[2]), lon(high[0]), lat(low[2])]
        new['measuredGlbDimensions'] = stats['dimensions']
        new['genericCorrection'] = {'sourceId': SOURCE, 'sourceSha256': SOURCE_SHA, 'operation': 'Exact triangle partition; unchanged vertex attributes, materials and original terrain anchor.'}
        number = next((n for n in PRESERVED_METADATA_SHA if pid == f'fallback-acro-riverpark-{n}'), None)
        if number is not None:
            old = next(a for a in previous['assets'] if a['id'] == pid)
            assert canonical_sha(old) == PRESERVED_METADATA_SHA[number], 'Previously published metadata changed'
            assert old == new and data == (folder / old['model']).read_bytes(), 'Previously published fallback changed'
            new = copy.deepcopy(old)
        outputs.append(new)
        documents[folder / model] = data
    assert sum(a['triangles'] for a in outputs) == asset['triangles'] == 22153
    proof = {'version': 2, 'sourceId': SOURCE, 'sourceSha256': SOURCE_SHA,
        'sourceTriangles': asset['triangles'], 'sourceCoordinate': anchor,
        'sourceFootprints': [{'id': r['id'], 'sourceName': r['name'], 'sourceHeightM': r['height_m'], 'localFootprint': shapes[r['id']].__geo_interface__} for r in rows],
        'triangleCountsByGroup': {a['id']: a['triangles'] for a in outputs}, 'groupFootprints': {a['id']: a['footprintIds'] for a in outputs},
        'vertexConnectedComponents': len(components), 'crossGroupComponents': 0, 'ownershipToleranceM': .15,
        'ownershipMethod': 'Byte-exact original generator replay tags every original triangle by source feature. Independent full source polygon or uniquely covering union of individual source convex hulls must agree with every group. Vertex-connected components cannot cross groups.',
        'trianglesAssignedWithinUniqueSourceConvexHull': hull_triangles, 'maximumVertexDistanceOutsideSourceFootprintM': maximum,
        'sourceAuthoringReplay': replay, 'reviewed110PartIdentity': IDENTITY_EVIDENCE,
        'preservedMetadataSha256': {f'fallback-acro-riverpark-{n}': digest for n, digest in PRESERVED_METADATA_SHA.items()},
        'outputs': [{k: a[k] for k in ['id', 'model', 'sha256', 'bytes', 'triangles', 'bounds', 'footprintIds']} for a in outputs],
        'limits': ['Fifteen numbered tower fallbacks preserve all seventeen original source meshes. Tower110 includes its historically identified20-floor part. Only the unrelated Banpo Parkville remains as the residual.',
            'This split preserves source geometry and heights, including their existing approximations. It adds no residential or photo-completion credit. Source child height steps belong in separately reviewed bespoke assets.']}
    documents[ROOT / 'docs/model-audit/acro-riverpark-generic-split.json'] = (json.dumps(proof, ensure_ascii=False, indent=2) + '\n').encode()
    return {'sourceId': SOURCE, 'sourceSha256': SOURCE_SHA, 'sourceFootprintIds': ids, 'assets': outputs}, documents, proof


if __name__ == '__main__':
    from split_banpo_fallbacks import main
    main(['acro-riverpark'])
