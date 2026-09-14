"""Read-only viewport access to original Seoul building footprints and heights.

No dependency on server.app, no inferred heights, no geometry simplification.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3
from server.database import connect_readonly, available, database_bytes
import zlib

from shapely.geometry import box, shape

MIN_BUILDING_ZOOM = 14
MAX_BUILDINGS = 6000
MAX_CANDIDATES = MAX_BUILDINGS * 4


def finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f'{label} must be a finite number')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f'{label} must be a finite number') from None
    if not math.isfinite(number):
        raise ValueError(f'{label} must be a finite number')
    return number


def parse_bbox(value):
    if not isinstance(value, str) or len(value) > 200 or len(value.split(',')) != 4:
        raise ValueError('bbox must contain west,south,east,north')
    west, south, east, north = [finite_number(part, 'bbox') for part in value.split(',')]
    if not -180 <= west < east <= 180 or not -90 <= south < north <= 90:
        raise ValueError('bbox must be ordered valid longitude/latitude coordinates')
    return west, south, east, north


def decode_source_properties(raw):
    # Legacy/official-importer TEXT remains readable; new local databases use
    # compressed JSON bytes so source evidence is retained without duplication.
    return json.loads(zlib.decompress(raw) if isinstance(raw, bytes) else raw)


def classification_source(row):
    if not row['is_apartment']:
        return 'none'
    if row['kind'] == 'building_part':
        original = decode_source_properties(row['source_properties'])
        tags = original.get('tags') or {}
        own = original.get('class') in ('apartments', 'apartment', 'apartment_building') or (isinstance(tags, dict) and tags.get('building') == 'apartments')
        if not own:
            return 'parent'
    return 'source'


def feature_from_row(row):
    # Overture documents height and min_height differently from raw OSM tags.
    # Until that normalization is established, elevated parts stay outline-only.
    # Preserve unusually high source records for review without drawing them as
    # established building heights. This is a display guard, not data correction.
    height_review_required = row['height_m'] is not None and row['height_m'] >= 1000
    extrude = bool(row['extrude']) and row['min_height_m'] in (None, 0) and not height_review_required
    reason = ('missing_height' if row['height_m'] is None else
              'height_outlier_needs_review' if height_review_required else
              'parent_has_parts' if row['has_parts'] else
              'elevated_height_semantics_unverified' if row['min_height_m'] not in (None, 0) else
              'source_display_excluded' if not extrude else None)
    return {'type': 'Feature', 'id': row['id'], 'geometry': json.loads(row['geometry']), 'properties': {
        'id': row['id'], 'name': row['name'], 'height_m': row['height_m'],
        'height_status': 'reported' if row['height_m'] is not None else 'missing',
        'height_review_required': height_review_required,
        'min_height_m': row['min_height_m'], 'footprint_area_m2': row['footprint_area_m2'],
        'num_floors': row['num_floors'], 'is_apartment': bool(row['is_apartment']),
        'classification_source': classification_source(row),
        'kind': row['kind'], 'parent_id': row['parent_id'], 'has_parts': bool(row['has_parts']),
        'extrude': extrude, 'extrusion_reason': reason,
        'display_top_m': row['height_m'] if extrude else None, 'display_base_m': 0 if extrude else None,
        'geometry_source': row['geometry_source'], 'height_source': row['height_source'],
        'district_id': row['district_id'],
    }}


class BuildingsAPI:
    def __init__(self, database):
        self.database = Path(database).resolve()
        self.database_uri = self.database.as_uri() + '?mode=ro'

    def connect(self):
        db = connect_readonly(self.database)
        db.row_factory = sqlite3.Row
        return db

    def meta(self):
        if not available(self.database):
            return {'available': False, 'reason': 'buildings_database_not_built',
                    'min_zoom': MIN_BUILDING_ZOOM, 'max_features': MAX_BUILDINGS}
        with self.connect() as db:
            metadata = {row['key']: json.loads(row['value']) for row in db.execute('SELECT key,value FROM metadata')}
        return {**metadata, 'available': True, 'database_bytes': database_bytes(self.database),
                'min_zoom': MIN_BUILDING_ZOOM, 'max_features': MAX_BUILDINGS}

    def features(self, bbox, zoom='14'):
        bounds = parse_bbox(bbox)
        zoom = finite_number(zoom, 'zoom')
        if not 0 <= zoom <= 22:
            raise ValueError('zoom must be between 0 and 22')
        metadata = {'available': available(self.database), 'count': 0, 'reported': 0, 'missing': 0,
                    'apartments': 0, 'min_zoom': MIN_BUILDING_ZOOM, 'max_features': MAX_BUILDINGS,
                    'hidden_at_zoom': zoom < MIN_BUILDING_ZOOM, 'truncated': False,
                    'geometry_clipped': False, 'geometry_simplified': False,
                    'height_policy': 'source_reported_or_null; no floor multiplier or placeholder',
                    'selection_policy': '12x12 viewport grid round-robin; own-height extrusions then center distance within each cell; full footprints retained'}
        result = {'type': 'FeatureCollection', 'features': [], 'metadata': metadata}
        if not metadata['available'] or metadata['hidden_at_zoom']:
            return result
        west, south, east, north = bounds
        window = box(*bounds)
        with self.connect() as db:
            # RTree limits spatial candidates before JSON/GEOS work. A second
            # exact intersection removes bbox false positives without clipping
            # full source outlines at the viewport edge.
            center_x, center_y = (west + east) / 2, (south + north) / 2
            aspect = math.cos(math.radians(center_y)) ** 2
            rows = db.execute('''
                WITH candidates AS (
                    SELECT b.rowid,b.extrude,(r.minx+r.maxx)/2 AS cx,(r.miny+r.maxy)/2 AS cy
                    FROM building_index r JOIN buildings b ON b.rowid=r.rowid
                    WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=?
                ), cells AS (
                    SELECT *,MIN(11,MAX(0,CAST((cx-?)/? AS INTEGER))) AS gx,
                             MIN(11,MAX(0,CAST((cy-?)/? AS INTEGER))) AS gy,
                             (cx-?)*(cx-?)*?+(cy-?)*(cy-?) AS distance
                    FROM candidates
                ), ranked AS (
                    SELECT rowid,distance,ROW_NUMBER() OVER (
                        PARTITION BY gx,gy ORDER BY extrude DESC,distance,rowid
                    ) AS cell_rank FROM cells
                )
                SELECT b.* FROM ranked r JOIN buildings b ON b.rowid=r.rowid
                ORDER BY r.cell_rank,r.distance,b.rowid LIMIT ?
            ''', (east, west, north, south, west, (east-west)/12, south, (north-south)/12,
                  center_x, center_x, aspect, center_y, center_y, MAX_CANDIDATES + 1))
            examined = 0
            for row in rows:
                examined += 1
                if examined > MAX_CANDIDATES:
                    metadata['truncated'] = True
                    break
                geometry = json.loads(row['geometry'])
                if not shape(geometry).intersects(window):
                    continue
                if metadata['count'] >= MAX_BUILDINGS:
                    metadata['truncated'] = True
                    break
                feature = feature_from_row(row)
                result['features'].append(feature)
                props = feature['properties']
                metadata['count'] += 1
                metadata['reported' if props['height_status'] == 'reported' else 'missing'] += 1
                metadata['apartments'] += int(props['is_apartment'])
        return result

    def detail(self, identifier):
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 100 or any(ord(c) < 32 for c in identifier):
            raise ValueError('Invalid building identifier')
        if not available(self.database):
            return None
        with self.connect() as db:
            row = db.execute('SELECT * FROM buildings WHERE id=?', (identifier,)).fetchone()
            if row is None:
                return None
            metadata = {item['key']: json.loads(item['value']) for item in db.execute('SELECT key,value FROM metadata')}
        result = feature_from_row(row)
        original = decode_source_properties(row['source_properties'])
        result['sources'] = original.get('sources', [])
        result['source_properties'] = original
        official = metadata.get('source_kind') == 'official_gis_buildings'
        identifiers = (
            {key: original[key] for key in ('A0', 'A1', 'A19') if original.get(key) not in (None, '')}
            if official else {
                'feature_id': row['id'],
                'source_record_ids': [source['record_id'] for source in result['sources'] if source.get('record_id')],
            }
        )
        result['provenance'] = {
            'release': metadata['source_release'], 'license': metadata['license'],
            'source_kind': metadata.get('source_kind', 'overture_buildings'),
            'source_crs': metadata.get('source_crs', 'EPSG:4326'),
            'source_identifiers': identifiers,
            'attribution': metadata['attribution'], 'source_urls': metadata['source_urls'],
            'geometry': metadata.get('geometry_policy') or (
                'Source polygon topology retained; coordinates transformed from its PRJ to WGS84.'
                if official else 'original unmodified Polygon/MultiPolygon coordinates and holes'
            ),
            'height': metadata.get('height_policy') or (
                'source-reported, not independently surveyed' if row['height_m'] is not None else 'not supplied by source'
            ),
            'source_height_verified': bool(metadata.get('source_height_verified', False)),
            'area': metadata.get('area_policy', 'planar original footprint area computed in EPSG:5186; not cadastral certified area'),
            'area_crs': metadata.get('area_crs', 'EPSG:5186'),
            'extrusion': metadata.get('parts_policy', 'Only own reported heights at ground level are extruded. Parents with parts and nonzero-min-height features remain outline-only; min_height is not guessed or added to height.'),
        }
        if original.get('addresses'):
            result['addresses'] = original['addresses']
        return result
