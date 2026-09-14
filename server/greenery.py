"""Small, read-only geometry responses for decorative tree exclusion checks."""
from __future__ import annotations

import math

from server.buildings import BuildingsAPI, parse_bbox
from server.roads import RoadsAPI

MAX_EXTENT_M = 2000


def narrow_bounds(bbox):
    bounds = parse_bbox(bbox)
    west, south, east, north = bounds
    # Use the widest latitude of the rectangle and a conservative metres/degree
    # scale. This limit bounds query work; it is not a surveying calculation.
    equator_distance = 0 if south <= 0 <= north else min(abs(south), abs(north))
    width = (east - west) * 111_320 * math.cos(math.radians(equator_distance))
    height = (north - south) * 111_320
    if width > MAX_EXTENT_M or height > MAX_EXTENT_M:
        raise ValueError('greenery bbox width and height must each be at most 2000 metres')
    return bounds, width, height


def geometry_only(collection, road=False):
    features = []
    for feature in collection['features']:
        properties = feature.get('properties') or {}
        identifier = feature.get('id', properties.get('id'))
        item = {
            'type': 'Feature',
            'geometry': feature['geometry'],
            'properties': {key: properties[key] for key in ('highway', 'category', 'subtype') if key in properties} if road else {},
        }
        if identifier is not None:
            item['id'] = identifier
        features.append(item)
    # Keep availability/truncation/zoom metadata so incomplete coverage still
    # suppresses tree placement. Source coordinates and holes are untouched.
    return {**collection, 'features': features}


class GreeneryAPI:
    def __init__(self, buildings_database, roads_database):
        self.buildings = BuildingsAPI(buildings_database)
        self.roads = RoadsAPI(roads_database)

    def features(self, bbox):
        bounds, width, height = narrow_bounds(bbox)
        normalized = ','.join(str(value) for value in bounds)
        buildings = self.buildings.features(normalized, '16')
        roads = self.roads.features(normalized, '16')
        return {
            'buildings': geometry_only(buildings),
            'roads': geometry_only(roads, road=True),
            'metadata': {
                'purpose': 'tree_exclusion_geometry', 'zoom': 16,
                'max_extent_m': MAX_EXTENT_M,
                'width_m': round(width, 3), 'height_m': round(height, 3),
            },
        }
