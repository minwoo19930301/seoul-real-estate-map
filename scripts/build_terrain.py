#!/usr/bin/env python3
"""Build a local, explicitly estimated terrain surface from official Seoul vectors.

Reproducible setup (isolated from the other data builders):
  uv venv --python 3.12 .venv-terrain
  uv pip install --python .venv-terrain/bin/python numpy scipy pyproj pyshp pillow
  .venv-terrain/bin/python scripts/build_terrain.py --source ../seoul-contours-feasibility/seoul-contours.zip

RGB tiles contain continuous visual heights, NOT surveyed point observations.
Separate L-mode PNG masks and RGBA overlays distinguish supported interpolation from sparse/hull
extrapolation. They must never be used as a source for exact click elevations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import time
import zipfile

import numpy as np
from PIL import Image
from pyproj import CRS, Transformer
import scipy
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import ConvexHull, cKDTree
import shapefile

ROOT = Path(__file__).resolve().parents[1]
TILE_SIZE = 256
RADIUS = 6378137.0
WORLD_SIZE = 2 * math.pi * RADIUS
SOURCE_URL = 'https://data.seoul.go.kr/dataList/OA-22241/F/1/datasetView.do'


def log(message):
    print(message, flush=True)


def encode_mapbox_rgb(heights):
    """Mapbox terrain RGB: height = -10000 + (R*65536+G*256+B)*0.1 m."""
    value = np.asarray(heights, dtype=np.float64)
    if not np.isfinite(value).all():
        raise ValueError('Raster DEM cannot contain NaN or infinity')
    encoded = np.rint((value + 10000.0) * 10.0)
    if np.any(encoded < 0) or np.any(encoded > 16777215):
        raise ValueError('Height is outside Mapbox RGB representable range')
    encoded = encoded.astype(np.uint32)
    return np.stack(((encoded >> 16) & 255, (encoded >> 8) & 255, encoded & 255), axis=-1).astype(np.uint8)


def decode_mapbox_rgb(rgb):
    rgb = np.asarray(rgb, dtype=np.uint32)
    return -10000.0 + (rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]) * 0.1


def tile_mercator_grid(zoom, tile_x, tile_y, size=TILE_SIZE):
    """Pixel CENTER coordinates on one globally indexed XYZ Web Mercator grid.

    Adjacent tiles have adjacent sample centers, not duplicated edge pixels.
    Deriving coordinates from global integer pixel IDs avoids independent-grid
    alignment and interpolation seams. North is the first image row.
    """
    resolution = WORLD_SIZE / (size * 2 ** zoom)
    xs = -WORLD_SIZE / 2 + (tile_x * size + np.arange(size) + 0.5) * resolution
    ys = WORLD_SIZE / 2 - (tile_y * size + np.arange(size) + 0.5) * resolution
    return np.meshgrid(xs, ys)


def mercator_tile(x, y, zoom):
    count = 2 ** zoom
    return (math.floor((x + WORLD_SIZE / 2) / WORLD_SIZE * count),
            math.floor((WORLD_SIZE / 2 - y) / WORLD_SIZE * count))


def tile_ranges(bounds_mercator, zoom):
    west, south, east, north = bounds_mercator
    xmin, ymin = mercator_tile(west, north, zoom)
    xmax, ymax = mercator_tile(east, south, zoom)
    return range(xmin, xmax + 1), range(ymin, ymax + 1)


def sample_polyline(points, spacing=30.0):
    """Equal arc-length sampling in the source CRS, including open endpoints."""
    xy = np.asarray(points, dtype=np.float64)
    if len(xy) < 2:
        return xy.reshape((-1, 2))
    lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    keep = np.r_[True, lengths > 1e-9]
    xy = xy[keep]
    if len(xy) < 2:
        return xy
    distances = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    closed = np.linalg.norm(xy[0] - xy[-1]) < 0.01
    intervals = max(3 if closed else 1, math.ceil(distances[-1] / spacing))
    steps = np.linspace(0.0, distances[-1], intervals + 1)
    return np.column_stack([np.interp(steps, distances, xy[:, axis]) for axis in (0, 1)])


def deduplicate(points, heights, priorities, precision=0.01):
    """Merge 1 cm coordinate bins; source spots take priority over contours.

    If multiple values share the winning priority, average them deterministically.
    This averaging creates an interpolation constraint, not a new original spot.
    """
    points = np.asarray(points, dtype=np.float64)
    heights = np.asarray(heights, dtype=np.float64)
    priorities = np.asarray(priorities, dtype=np.uint8)
    rounded = np.rint(points / precision).astype(np.int64)
    _, inverse, counts = np.unique(rounded, axis=0, return_inverse=True, return_counts=True)
    groups = len(counts)
    max_priority = np.zeros(groups, dtype=np.uint8)
    np.maximum.at(max_priority, inverse, priorities)
    included = priorities == max_priority[inverse]
    selected_groups = inverse[included]
    selected_counts = np.bincount(selected_groups, minlength=groups)
    unique_xy = np.column_stack([
        np.bincount(selected_groups, weights=points[included, axis], minlength=groups) / selected_counts
        for axis in (0, 1)
    ])
    unique_z = np.bincount(selected_groups, weights=heights[included], minlength=groups) / selected_counts
    zmin = np.full(groups, np.inf)
    zmax = np.full(groups, -np.inf)
    np.minimum.at(zmin, inverse, heights)
    np.maximum.at(zmax, inverse, heights)
    return unique_xy, unique_z, {
        'coordinate_merge_tolerance_m': precision,
        'duplicates_removed': int(len(points) - groups),
        'groups_with_height_disagreement_over_0_5m': int(np.sum(zmax - zmin > 0.5)),
        'policy': '1 cm coordinate bins; original spot height wins over contour sample; same-priority duplicates are averaged',
    }


def shape_reader(archive, stem):
    return shapefile.Reader(**{ext: io.BytesIO(archive.read(f'{stem}.{ext}')) for ext in ('shp', 'shx', 'dbf')}, encoding='cp949')


def source_constraints(source, spacing):
    xy_parts, z_parts, priority_parts = [], [], []
    raw_vertices = 0
    contour_samples = 0
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        line_stem = next(name[:-4] for name in names if name.endswith('/N3L_F001.shp'))
        spot_stem = next(name[:-4] for name in names if name.endswith('/N3P_F002.shp'))
        crs = CRS.from_wkt(archive.read(f'{line_stem}.prj').decode())
        lines = shape_reader(archive, line_stem)
        for row in lines.iterShapeRecords():
            height = float(row.record.as_dict()['HEIGHT'])
            if not np.isfinite(height):
                raise ValueError('Nonfinite official contour height')
            geometry = row.shape
            raw_vertices += len(geometry.points)
            cuts = list(geometry.parts) + [len(geometry.points)]
            for start, end in zip(cuts, cuts[1:]):
                sample = sample_polyline(geometry.points[start:end], spacing)
                xy_parts.append(sample)
                z_parts.append(np.full(len(sample), height))
                priority_parts.append(np.zeros(len(sample), dtype=np.uint8))
                contour_samples += len(sample)
        spots = shape_reader(archive, spot_stem)
        spot_rows = [(row.shape.points[0], float(row.record.as_dict()['HEIGHT'])) for row in spots.iterShapeRecords()]
        spot_xy = np.asarray([row[0] for row in spot_rows])
        spot_z = np.asarray([row[1] for row in spot_rows])
        xy_parts.append(spot_xy)
        z_parts.append(spot_z)
        priority_parts.append(np.ones(len(spot_rows), dtype=np.uint8))
        source_meta = {
            'contour_feature_count': len(lines),
            'contour_original_vertex_count': raw_vertices,
            'contour_sample_count_before_deduplication': contour_samples,
            'spot_height_count': len(spot_rows),
            'source_crs': crs.to_string(),
            'source_contour_interval_m': 5,
            'contour_sample_spacing_m': spacing,
            'spot_height_range_m': [float(spot_z.min()), float(spot_z.max())],
        }
    points, heights, merge_meta = deduplicate(np.vstack(xy_parts), np.concatenate(z_parts), np.concatenate(priority_parts))
    if not np.isfinite(points).all() or not np.isfinite(heights).all():
        raise ValueError('Source constraints contain nonfinite values')
    return points, heights, crs, {**source_meta, **merge_meta}


class TerrainSurface:
    def __init__(self, points, heights, crs, max_nearest_m=300.0, max_triangle_edge_m=1500.0):
        self.points = np.asarray(points)
        self.heights = np.asarray(heights)
        self.interpolator = LinearNDInterpolator(self.points, self.heights, fill_value=np.nan)
        self.tree = cKDTree(self.points)
        hull_indices = ConvexHull(self.points).vertices
        self.hull_points = self.points[hull_indices]
        self.hull_heights = self.heights[hull_indices]
        self.transform = Transformer.from_crs(3857, crs, always_xy=True)
        self.max_nearest_m = max_nearest_m
        self.max_triangle_edge_m = max_triangle_edge_m
        triangles = self.points[self.interpolator.tri.simplices]
        self.triangle_edges = np.maximum.reduce([
            np.linalg.norm(triangles[:, first] - triangles[:, second], axis=1)
            for first, second in [(0, 1), (1, 2), (2, 0)]
        ])

    def boundary_padding(self, coords):
        # Project onto the closest convex-hull segment and interpolate the two
        # boundary heights. This agrees continuously with the TIN at the hull;
        # selecting the nearest source point would create artificial steps.
        best_distance = np.full(len(coords), np.inf)
        values = np.zeros(len(coords))
        for index, start in enumerate(self.hull_points):
            end_index = (index + 1) % len(self.hull_points)
            end = self.hull_points[end_index]
            segment = end - start
            relative = coords - start
            fraction = np.clip(np.sum(relative * segment, axis=1) / np.dot(segment, segment), 0, 1)
            distance = np.sum((relative - fraction[:, None] * segment) ** 2, axis=1)
            closer = distance < best_distance
            best_distance[closer] = distance[closer]
            values[closer] = self.hull_heights[index] + fraction[closer] * (self.hull_heights[end_index] - self.hull_heights[index])
        return values

    def evaluate(self, mercator_x, mercator_y):
        x, y = self.transform.transform(mercator_x, mercator_y)
        shape = np.shape(x)
        coords = np.column_stack([np.asarray(x).ravel(), np.asarray(y).ravel()])
        heights = np.asarray(self.interpolator(coords))
        nearest_distance, _ = self.tree.query(coords, workers=1)
        inside = np.isfinite(heights)
        # No artificial zero elevation at the data boundary. Outside the source
        # hull, extend the closest hull-segment height solely as visual padding (mask=0).
        heights[~inside] = self.boundary_padding(coords[~inside])
        simplex = self.interpolator.tri.find_simplex(coords)
        max_edge = self.triangle_edges[np.maximum(simplex, 0)]
        supported = inside & (nearest_distance <= self.max_nearest_m) & (max_edge <= self.max_triangle_edge_m)
        return heights.reshape(shape), (supported.reshape(shape).astype(np.uint8) * 255)

    def tile(self, zoom, tile_x, tile_y):
        return self.evaluate(*tile_mercator_grid(zoom, tile_x, tile_y))


def coverage_overlay(mask):
    overlay = np.empty((*np.shape(mask), 4), dtype=np.uint8)
    overlay[..., :3] = [113, 128, 140]
    overlay[..., 3] = np.where(np.asarray(mask) == 255, 0, 180)
    return overlay


def save_tile(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    Image.fromarray(values).save(temporary, format='PNG', optimize=False, compress_level=6)
    temporary.replace(path)


def summarize_seams(directory, zoom, xs, ys):
    """Audit adjacent pixel gradients, rather than requiring duplicated edges.

    Correct DEMs sample centers: a tile boundary has the same one-pixel spacing
    as the interior. Report boundary jumps next to all interior gradients so
    accidental zero/padded tile edges can be spotted and regression-tested.
    """
    boundaries, interiors = [], []
    minimum, maximum = np.inf, -np.inf
    for y in ys:
        previous = None
        for x in xs:
            tile = decode_mapbox_rgb(np.asarray(Image.open(directory / str(zoom) / str(x) / f'{y}.png')))
            minimum = min(minimum, float(tile.min()))
            maximum = max(maximum, float(tile.max()))
            interiors.extend([np.abs(np.diff(tile, axis=0)).ravel()[::16], np.abs(np.diff(tile, axis=1)).ravel()[::16]])
            if previous is not None:
                boundaries.append(np.abs(tile[:, 0] - previous[:, -1]))
            if y > ys.start:
                north = decode_mapbox_rgb(np.asarray(Image.open(directory / str(zoom) / str(x) / f'{y-1}.png')))
                boundaries.append(np.abs(tile[0, :] - north[-1, :]))
            previous = tile
    seam = np.concatenate(boundaries) if boundaries else np.zeros(1)
    interior = np.concatenate(interiors)
    return {
        'boundary_sample_pairs': int(len(seam)),
        'boundary_jump_m': {'max': float(seam.max()), 'p99': float(np.percentile(seam, 99))},
        'interior_jump_m': {'max': float(interior.max()), 'p99': float(np.percentile(interior, 99))},
        'decoded_height_range_m': [minimum, maximum],
        'pixel_alignment': 'global XYZ Web Mercator pixel centers; neighboring tile pixels are one grid step apart',
    }


def build(args):
    started = time.monotonic()
    source = args.source.resolve()
    output = args.output.resolve()
    terrain_dir = output / 'terrain'
    terrain_dir.mkdir(parents=True, exist_ok=True)
    log('Sampling official contour geometry and spot heights…')
    points, heights, crs, source_meta = source_constraints(source, args.spacing)
    log(f'{source_meta["contour_original_vertex_count"]:,} original vertices → {len(points):,} unique constraints')
    cache = terrain_dir / 'constraints.npz'
    np.savez_compressed(cache, points=points, heights=heights, epsg=crs.to_epsg())
    log('Triangulating source constraints…')
    surface = TerrainSurface(points, heights, crs, args.support_radius, args.max_triangle_edge)
    local_to_merc = Transformer.from_crs(crs, 3857, always_xy=True)
    local_to_wgs = Transformer.from_crs(crs, 4326, always_xy=True)
    merc_to_wgs = Transformer.from_crs(3857, 4326, always_xy=True)
    hull = points[ConvexHull(points).vertices]
    hull_lon, hull_lat = local_to_wgs.transform(hull[:, 0], hull[:, 1])
    hull_ring = np.column_stack([hull_lon, hull_lat]).tolist()
    hull_ring.append(hull_ring[0])
    (terrain_dir / 'source-hull.geojson').write_text(json.dumps({
        'type': 'Feature',
        'properties': {'estimated': True, 'role': 'interpolation convex hull; not Seoul administrative boundary or surveyed validity'},
        'geometry': {'type': 'Polygon', 'coordinates': [hull_ring]},
    }, ensure_ascii=False) + '\n')
    mx, my = local_to_merc.transform(hull[:, 0], hull[:, 1])
    # EPSG3857 meters are scale-inflated at Seoul latitude. Convert ground padding
    # to Mercator meters, so the promised buffer really is at least 6 km locally.
    padding = args.padding / math.cos(math.radians(float(np.mean(hull_lat))))
    bounds_merc = [float(mx.min() - padding), float(my.min() - padding), float(mx.max() + padding), float(my.max() + padding)]
    west, south = merc_to_wgs.transform(bounds_merc[0], bounds_merc[1])
    east, north = merc_to_wgs.transform(bounds_merc[2], bounds_merc[3])
    counts, validity, seams = {}, {}, {}
    for zoom in range(args.minzoom, args.maxzoom + 1):
        xs, ys = tile_ranges(bounds_merc, zoom)
        total = len(xs) * len(ys)
        supported_count = 0
        log(f'z{zoom}: {total} tiles ({len(xs)}×{len(ys)})')
        for row, y in enumerate(ys):
            for x in xs:
                values, mask = surface.tile(zoom, x, y)
                save_tile(terrain_dir / str(zoom) / str(x) / f'{y}.png', encode_mapbox_rgb(values))
                save_tile(terrain_dir / 'mask' / str(zoom) / str(x) / f'{y}.png', mask)
                save_tile(terrain_dir / 'coverage' / str(zoom) / str(x) / f'{y}.png', coverage_overlay(mask))
                supported_count += int(np.count_nonzero(mask))
            if (row + 1) % 5 == 0 or row == len(ys) - 1:
                log(f'  row {row + 1}/{len(ys)} · {time.monotonic() - started:.1f}s')
        counts[str(zoom)] = total
        validity[str(zoom)] = {'supported_pixels': supported_count, 'total_pixels': total * TILE_SIZE ** 2,
                               'x_range': [xs.start, xs.stop - 1], 'y_range': [ys.start, ys.stop - 1]}
        seams[str(zoom)] = summarize_seams(terrain_dir, zoom, xs, ys)
    meta = {
        'version': 1,
        'id': 'seoul-official-contours-interpolated-terrain',
        'title': '서울 공식 등고선·표고점 보간 지형',
        'tiles': ['/data/terrain/{z}/{x}/{y}.png'],
        'coverage_tiles': ['/data/terrain/coverage/{z}/{x}/{y}.png'],
        'source_hull_url': '/data/terrain/source-hull.geojson',
        'bounds': [west, south, east, north],
        'minzoom': args.minzoom, 'maxzoom': args.maxzoom,
        'encoding': 'mapbox', 'tileSize': TILE_SIZE,
        'scheme': 'xyz', 'estimated': True,
        'method': 'EPSG:5174 contour arc-length sampling + original spot heights; scipy LinearNDInterpolator (piecewise-linear Delaunay TIN), sampled at global Web Mercator pixel centers',
        'source_point_count': len(points),
        'source': {'url': SOURCE_URL, 'zip_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), **source_meta},
        'height_unit': 'metres',
        'vertical_datum': 'Not explicitly declared in source PRJ/field metadata; not independently verified',
        'quantization_m': 0.1,
        'source_height_range_m': [float(heights.min()), float(heights.max())],
        'source_bounds': [float(np.min(hull_lon)), float(np.min(hull_lat)), float(np.max(hull_lon)), float(np.max(hull_lat))],
        'validity': {
            'mask_tiles': ['/data/terrain/mask/{z}/{x}/{y}.png'],
            'mask_format': '8-bit grayscale PNG; 255 = supported estimated interpolation, 0 = sparse/unsupported interpolation or visual-only hull padding',
            'noDataValue': None,
            'source_hull': '/data/terrain/source-hull.geojson',
            'max_nearest_constraint_distance_m': args.support_radius,
            'max_triangle_edge_m': args.max_triangle_edge,
            'padding_ground_m': args.padding,
            'padding_method': 'Closest convex-hull segment height, linearly interpolated at the projection; continuous at the source boundary, visual use only',
            'warning': 'The DEM has no numeric NoData sentinel. Read the mask and source extent before interpreting it. Even mask=255 is inferred terrain, never an original point measurement.',
        },
        'limitations': [
            '모든 지면 높이는 원본 등고선·표고점에서 보간한 추정 지형이며 현장 검증하지 않았습니다.',
            '5 m 등고 간격은 수평 해상도 또는 수직 정확도를 뜻하지 않습니다.',
            f'{args.spacing:g} m 선 샘플링은 작은 계단·담장·도로 단차·급경사와 수직면을 보존하지 못합니다.',
            '데이터 공백·하천·source hull 가장자리에는 보간 또는 시각적 외삽이 포함됩니다. 별도 유효 마스크를 확인하세요.',
            '원본 근접 표고점 조회와 3D 지형값은 서로 다릅니다. 클릭 지점의 실측 고도나 안전·설계 판단에 사용하지 마세요.',
            '낮은 줌 타일은 동일한 보간 표면을 성긴 격자에서 표본화하며 새 지형 정보를 추가하지 않습니다.',
        ],
        'tile_counts': counts,
        'raster_validity_counts': validity,
        'seam_audit': seams,
        'builder': {'numpy': np.__version__, 'scipy': scipy.__version__, 'created_at': datetime.now(timezone.utc).isoformat(),
                    'elapsed_seconds': round(time.monotonic() - started, 2)},
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / 'terrain.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    log(f'Wrote {sum(counts.values())} terrain tiles + masks and {output / "terrain.json"}')
    log(json.dumps({'seconds': round(time.monotonic() - started, 2), 'source_point_count': len(points), 'bounds': meta['bounds']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'public' / 'data')
    parser.add_argument('--spacing', type=float, default=30.0)
    parser.add_argument('--minzoom', type=int, default=10)
    parser.add_argument('--maxzoom', type=int, default=13)
    parser.add_argument('--padding', type=float, default=6000.0)
    parser.add_argument('--support-radius', type=float, default=300.0)
    parser.add_argument('--max-triangle-edge', type=float, default=1500.0)
    args = parser.parse_args()
    if not 10 <= args.spacing <= 100 or not 0 <= args.minzoom <= args.maxzoom <= 16 or args.padding < 1000:
        parser.error('Require spacing 10–100m, 0 <= minzoom <= maxzoom <=16, and padding >=1000m')
    build(args)
