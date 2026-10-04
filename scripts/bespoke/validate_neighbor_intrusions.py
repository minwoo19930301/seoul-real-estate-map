"""Check GLB surfaces against a neighboring building's registered height envelope."""
import math

import numpy as np
import shapely
from shapely.geometry import shape
from shapely.ops import transform


def clip_below(vertices, height):
    result = []
    for start, end in zip(vertices, np.roll(vertices, -1, axis=0)):
        start_inside, end_inside = start[1] <= height, end[1] <= height
        if start_inside:
            result.append(start)
        if start_inside != end_inside:
            fraction = (height - start[1]) / (end[1] - start[1])
            result.append(start + fraction * (end - start))
    return np.asarray(result)


def neighbor_intrusions(triangles, anchor_lonlat, neighbor_geometry, neighbor_height_m, tolerance_m=.001):
    """Return crossing triangle indices, including crossings with no inside vertex.

    The GLB convention is X east, Y up, Z south, using the author's local
    111320 m/degree scale. Clip at the neighbor's maximum height before testing
    projected surface intersections. A shared boundary itself is allowed.
    """
    triangles = np.asarray(triangles, dtype=float)
    if triangles.ndim != 3 or triangles.shape[1:] != (3, 3) or not np.isfinite(triangles).all():
        raise ValueError('Expected finite triangle coordinates')
    if not math.isfinite(neighbor_height_m) or neighbor_height_m <= 0 or tolerance_m <= 0:
        raise ValueError('Positive neighbor height and tolerance are required')
    lon, lat = anchor_lonlat
    scale_x = 111320 * math.cos(math.radians(lat))
    neighbor = transform(lambda x, y: ((x-lon)*scale_x, -(y-lat)*111320), shape(neighbor_geometry))
    if not neighbor.is_valid or neighbor.is_empty:
        raise ValueError('Invalid neighbor footprint')
    interior = neighbor.buffer(-tolerance_m)
    ceiling = neighbor_height_m - tolerance_m
    complete = np.flatnonzero(triangles[:, :, 1].max(axis=1) <= ceiling)
    partial = np.flatnonzero((triangles[:, :, 1].min(axis=1) <= ceiling)
                            & (triangles[:, :, 1].max(axis=1) > ceiling))
    hits = []
    if len(complete):
        projections = shapely.convex_hull(shapely.multipoints(triangles[complete][:, :, [0, 2]]))
        hits.extend(complete[shapely.intersects(projections, interior)].tolist())
    for index in partial:
        clipped = clip_below(triangles[index], ceiling)
        if len(clipped) and shapely.intersects(shapely.convex_hull(shapely.MultiPoint(clipped[:, [0, 2]])), interior):
            hits.append(int(index))
    return sorted(hits)
