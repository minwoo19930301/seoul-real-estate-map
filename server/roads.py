"""Read-only, bounded viewport queries for original OSM road and footpath ways."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3
from server.database import connect_readonly, available, database_bytes
import zlib

from shapely.geometry import box, shape

MIN_ZOOM = 11
MAX_FEATURES = 5000
MAX_VERTICES = 100000
MAX_CANDIDATES = 20000


def parse_bbox(value):
    if not isinstance(value, str) or len(value) > 200 or len(value.split(',')) != 4:
        raise ValueError('bbox must contain west,south,east,north')
    try:
        west, south, east, north = map(float, value.split(','))
    except ValueError:
        raise ValueError('bbox must contain finite coordinates') from None
    if not all(math.isfinite(n) for n in (west, south, east, north)) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError('bbox must contain ordered valid coordinates')
    return west, south, east, north


def feature_from_row(row):
    tags = json.loads(zlib.decompress(row['tags']))
    props = {key: row[key] for key in ('id', 'name', 'category', 'subtype', 'highway')}
    props.update({key.replace(':', '_'): tags.get(key) for key in (
        'foot', 'access', 'surface', 'sidewalk', 'sidewalk:left', 'sidewalk:right',
        'crossing', 'incline', 'wheelchair', 'bridge', 'tunnel', 'layer', 'motor_vehicle')})
    props['source'] = 'OpenStreetMap'
    props['restricted'] = tags.get('access') in ('no', 'private') or tags.get('foot') in ('no', 'private')
    props['separate_sidewalk'] = row['subtype'] == 'sidewalk'
    return {'type': 'Feature', 'id': row['id'], 'geometry': json.loads(row['geometry']), 'properties': props}


class RoadsAPI:
    def __init__(self, database):
        self.database = Path(database).resolve()

    def connect(self):
        db = connect_readonly(self.database)
        db.row_factory = sqlite3.Row
        return db

    def meta(self):
        policy = {'available': available(self.database), 'min_zoom': MIN_ZOOM,
                  'local_roads_min_zoom': 13, 'walkways_min_zoom': 14,
                  'max_features': MAX_FEATURES, 'max_vertices': MAX_VERTICES}
        if not policy['available']:
            return {**policy, 'reason': 'roads_database_not_built'}
        with self.connect() as db:
            metadata = {r['key']: json.loads(r['value']) for r in db.execute('SELECT key,value FROM metadata')}
        return {**metadata, **policy, 'database_bytes': database_bytes(self.database)}

    def features(self, bbox, zoom='14'):
        west, south, east, north = parse_bbox(bbox)
        try:
            zoom_number = float(zoom)
        except (ValueError, TypeError, OverflowError):
            raise ValueError('zoom must be between 0 and 22') from None
        if isinstance(zoom, bool) or not math.isfinite(zoom_number) or not 0 <= zoom_number <= 22:
            raise ValueError('zoom must be between 0 and 22')
        metadata = {'available': available(self.database), 'count': 0, 'vertices': 0,
                    'counts': {'roadway': 0, 'walkway': 0, 'steps': 0}, 'truncated': False,
                    'min_zoom': MIN_ZOOM, 'hidden_at_zoom': zoom_number < MIN_ZOOM,
                    'walkways_hidden_at_zoom': zoom_number < 14,
                    'local_roads_hidden_at_zoom': zoom_number < 13,
                    'max_features': MAX_FEATURES, 'max_vertices': MAX_VERTICES,
                    'geometry_clipped': False, 'geometry_simplified': False,
                    'selection_policy': '8x8 viewport grid and category round-robin, center distance per cell; full original ways'}
        result = {'type': 'FeatureCollection', 'features': [], 'metadata': metadata}
        if not metadata['available'] or metadata['hidden_at_zoom']:
            return result
        window = box(west, south, east, north)
        cx, cy = (west + east) / 2, (south + north) / 2
        with self.connect() as db:
            rows = db.execute('''
              WITH candidates AS (
                SELECT b.rowid,b.category,(r.minx+r.maxx)/2 AS cx,(r.miny+r.maxy)/2 AS cy
                FROM road_index r JOIN roads b ON b.rowid=r.rowid
                WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=? AND b.min_zoom<=?
              ), cells AS (
                SELECT *,MIN(7,MAX(0,CAST((cx-?)/? AS INTEGER))) AS gx,
                  MIN(7,MAX(0,CAST((cy-?)/? AS INTEGER))) AS gy,
                  (cx-?)*(cx-?)*?+(cy-?)*(cy-?) AS distance FROM candidates
              ), ranked AS (
                SELECT rowid,distance,ROW_NUMBER() OVER (PARTITION BY gx,gy,category ORDER BY distance,rowid) AS rank
                FROM cells
              ) SELECT b.* FROM ranked r JOIN roads b ON b.rowid=r.rowid
                ORDER BY r.rank,r.distance,b.rowid LIMIT ?
            ''', (east, west, north, south, zoom_number, west, (east-west)/8, south, (north-south)/8,
                  cx, cx, math.cos(math.radians(cy)) ** 2, cy, cy, MAX_CANDIDATES + 1))
            for index, row in enumerate(rows):
                if index >= MAX_CANDIDATES:
                    metadata['truncated'] = True
                    break
                feature = feature_from_row(row)
                if not shape(feature['geometry']).intersects(window):
                    continue
                if metadata['count'] >= MAX_FEATURES:
                    metadata['truncated'] = True
                    break
                if metadata['vertices'] + row['vertex_count'] > MAX_VERTICES:
                    metadata['truncated'] = True
                    continue
                result['features'].append(feature)
                metadata['count'] += 1
                metadata['vertices'] += row['vertex_count']
                metadata['counts'][row['category']] += 1
        return result
