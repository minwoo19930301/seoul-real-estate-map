"""Check authored GLB surfaces against independently supplied stepped envelopes.

The input regions use local east/north metres; GLB uses x/up/south. This checks
triangle interiors too, so a roof spanning a low wing cannot evade validation
just because its vertices lie outside the wing. Boundary setbacks tolerate
shared higher walls without treating them as low-wing roof geometry.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import MultiPoint, Polygon, shape
from shapely.ops import unary_union


def read_triangles(path):
    data = Path(path).read_bytes()
    if data[:4] != b'glTF' or struct.unpack_from('<II', data, 4) != (2, len(data)):
        raise ValueError('Expected a complete GLB version 2 file')
    length, kind = struct.unpack_from('<II', data, 12)
    if kind != 0x4e4f534a:
        raise ValueError('Missing GLB JSON chunk')
    document = json.loads(data[20:20 + length])
    binary_length, binary_kind = struct.unpack_from('<II', data, 20 + length)
    binary = data[28 + length:]
    if binary_kind != 0x004e4942 or len(binary) != binary_length:
        raise ValueError('Missing or incomplete GLB binary chunk')
    if document.get('images') or document.get('textures'):
        raise ValueError('Expected image-free authored geometry')
    nodes = document['nodes']
    if len(document['scenes']) != 1:
        raise ValueError('Expected one authored scene')
    if any(set(n) - {'name', 'mesh', 'children'} for n in nodes):
        raise ValueError('Bake scene transforms before envelope validation')
    visited = set()

    def visit(index):
        if index in visited or not 0 <= index < len(nodes):
            raise ValueError('Duplicated, cyclic or invalid scene node')
        visited.add(index)
        for child in nodes[index].get('children', []):
            visit(child)

    for root in document['scenes'][0]['nodes']:
        visit(root)
    if visited != set(range(len(nodes))):
        raise ValueError('Unreachable authored scene node')
    if sorted(n['mesh'] for n in nodes if 'mesh' in n) != list(range(len(document['meshes']))):
        raise ValueError('Expected each authored mesh exactly once')

    def accessor(index):
        a = document['accessors'][index]
        view = document['bufferViews'][a['bufferView']]
        if a.get('sparse') or a.get('normalized') or view.get('buffer', 0) != 0:
            raise ValueError('Unsupported accessor encoding')
        dtype = np.dtype({5121: 'u1', 5123: '<u2', 5125: '<u4', 5126: '<f4'}[a['componentType']])
        width = {'SCALAR': 1, 'VEC3': 3}[a['type']]
        return np.ndarray((a['count'], width), dtype=dtype, buffer=binary,
                          offset=view.get('byteOffset', 0) + a.get('byteOffset', 0),
                          strides=(view.get('byteStride', width * dtype.itemsize), dtype.itemsize)).copy()

    pieces = []
    for mesh in document['meshes']:
        for primitive in mesh['primitives']:
            if primitive.get('mode', 4) != 4 or primitive.get('targets'):
                raise ValueError('Expected static triangle primitives')
            vertices = accessor(primitive['attributes']['POSITION'])
            indices = accessor(primitive['indices']).reshape(-1) if 'indices' in primitive else np.arange(len(vertices))
            pieces.append(vertices[indices.reshape(-1, 3)])
    triangles = np.concatenate(pieces).astype(np.float64)
    if not np.isfinite(triangles).all():
        raise ValueError('Non-finite authored geometry')
    return triangles


def above_ceiling(triangle, ceiling):
    """Clip a triangle to the upper half-space, preserving interpolated edges."""
    output = []
    previous = triangle[-1]
    for current in triangle:
        inside, prior_inside = current[1] >= ceiling, previous[1] >= ceiling
        if inside != prior_inside:
            t = (ceiling - previous[1]) / (current[1] - previous[1])
            output.append(previous + t * (current - previous))
        if inside:
            output.append(current)
        previous = current
    return np.asarray(output)


def inspect_regions(triangles, regions, boundary_tolerance=.03, height_tolerance=.02):
    if not isinstance(regions, list) or not regions:
        raise ValueError('At least one independently supplied height region is required')
    if len({r['id'] for r in regions}) != len(regions):
        raise ValueError('Height region identifiers must be unique')
    if not all(math.isfinite(v) and v >= 0 for v in [boundary_tolerance, height_tolerance]):
        raise ValueError('Geometry tolerances must be finite and nonnegative')
    triangles = np.asarray(triangles, dtype=float)
    horizontal = triangles[:, :, [0, 2]] * [1, -1]
    triangle_max = triangles[:, :, 1].max(axis=1)
    triangle_min = triangles[:, :, 1].min(axis=1)
    reports = []
    for region in regions:
        polygon = shape(region['geometry']) if 'geometry' in region else Polygon(region['rings'][0], region['rings'][1:])
        if not polygon.is_valid or polygon.is_empty or not math.isfinite(region['height_m']) or region['height_m'] <= 0:
            raise ValueError('Invalid height region')
        interior = polygon.buffer(-boundary_tolerance)
        if interior.is_empty:
            raise ValueError('Height region too narrow for configured boundary tolerance')
        ceiling = region['height_m'] + height_tolerance
        lower, upper = np.asarray(interior.bounds[:2]), np.asarray(interior.bounds[2:])
        overlaps = (horizontal.max(axis=1) >= lower).all(axis=1) & (horizontal.min(axis=1) <= upper).all(axis=1)
        candidates = np.flatnonzero((triangle_max > ceiling) & overlaps)
        fully_above = candidates[triangle_min[candidates] >= ceiling]
        violations = []
        if len(fully_above):
            projections = shapely.convex_hull(shapely.multipoints(horizontal[fully_above]))
            violations.extend(fully_above[shapely.intersects(projections, interior)].tolist())
        for index in candidates[triangle_min[candidates] < ceiling]:
            clipped = above_ceiling(triangles[index], ceiling)
            projection = MultiPoint(clipped[:, [0, 2]] * [1, -1]).convex_hull
            if projection.intersects(interior):
                violations.append(int(index))
        # A near-roof cap must cover every interior part, not merely reach the
        # expected maximum at a parapet vertex while omitting an entire wing.
        near_roof = overlaps & (triangle_min >= region['height_m'] - 2.5) & (triangle_max <= ceiling)
        caps = shapely.polygons(horizontal[near_roof])
        caps = caps[shapely.area(caps) > 1e-8]
        roof = unary_union(caps) if len(caps) else Polygon()
        uncovered = interior.difference(roof).area
        reports.append({'id': region['id'], 'heightM': region['height_m'],
                        'areaM2': polygon.area, 'interiorAreaM2': interior.area,
                        'overHeightTriangles': len(violations),
                        'exampleTriangleIndices': violations[:8],
                        'uncoveredNearRoofAreaM2': uncovered,
                        'roofCoverageRatio': 1 - uncovered / interior.area})
    return reports


def validate(path, specification, boundary_tolerance=.03):
    triangles = read_triangles(path)
    records = inspect_regions(triangles, specification['regions'], boundary_tolerance=boundary_tolerance)
    failure = [r for r in records if r['overHeightTriangles'] or r['roofCoverageRatio'] < .999]
    result = {'file': str(path), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
              'triangleCount': len(triangles), 'boundaryToleranceM': boundary_tolerance, 'heightToleranceM': .02,
              'roofBandM': 2.5, 'regions': records, 'passed': not failure}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('glb', type=Path)
    parser.add_argument('specification', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--boundary-tolerance', type=float, default=.03,
                        help='Explicitly recorded maximum boundary detail projection in metres')
    args = parser.parse_args()
    result = validate(args.glb, json.loads(args.specification.read_text()), args.boundary_tolerance)
    encoded = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(encoded)
    print(encoded, end='')
    raise SystemExit(0 if result['passed'] else 1)
