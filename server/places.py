"""Offline name search and bounded landmark points; no network at request time."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3
from server.database import connect_readonly, available, database_bytes
import unicodedata

KINDS = ('station', 'bridge', 'junction', 'residential', 'neighborhood', 'building')
MAX_RESULTS = 50
MAX_LANDMARKS = 300


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def integer(value, label, minimum, maximum):
    if isinstance(value, bool):
        raise ValueError(f'{label} must be an integer between {minimum} and {maximum}')
    try:
        n = int(value)
        if float(value) != n or not minimum <= n <= maximum:
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f'{label} must be an integer between {minimum} and {maximum}') from None
    return n


def parse_bbox(value):
    try:
        if not isinstance(value, str) or len(value) > 200:
            raise ValueError
        west, south, east, north = map(float, value.split(','))
        if not all(math.isfinite(n) for n in (west, south, east, north)):
            raise ValueError
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('bbox must contain ordered finite west,south,east,north') from None
    return west, south, east, north


def result_from_row(row):
    result = {key: row[key] for key in ('id', 'name', 'subtitle', 'kind', 'zoom', 'priority',
                                       'source_url', 'location_method', 'building_id', 'district_name')}
    result['center'] = [row['lon'], row['lat']]
    for key in ('household_count','official_complex_code','apartment_class','household_count_source',
                'source_updated_at','coordinate_status','coordinate_source_url'):
        result[key] = row[key] if key in row.keys() else None
    result['household_count_status'] = 'official_reported' if result['official_complex_code'] and result['household_count'] is not None else 'missing'
    return result


def household_filter(connection, minimum):
    """Household controls apply only to residential pins, preserving other kinds."""
    if minimum is None or minimum == '':
        return '', ()
    minimum = integer(minimum, 'min_households', 0, 1000000)
    columns = {row[1] for row in connection.execute('PRAGMA table_info(places)')}
    if 'household_count' not in columns:
        return " AND p.kind<>'residential'", ()
    return " AND (p.kind<>'residential' OR (p.household_count>=? AND p.apartment_class IN ('아파트','주상복합','도시형 생활주택(아파트)','도시형 생활주택(주상복합)')))", (minimum,)


class PlacesAPI:
    def __init__(self, database):
        self.database = Path(database).resolve()

    def connect(self):
        connection = connect_readonly(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def meta(self):
        if not available(self.database):
            return {'available': False, 'reason': 'places_database_not_built',
                    'max_results': MAX_RESULTS, 'max_landmarks': MAX_LANDMARKS}
        with self.connect() as connection:
            metadata = {r['key']: json.loads(r['value']) for r in connection.execute('SELECT * FROM metadata')}
        return {**metadata, 'available': True, 'max_results': MAX_RESULTS,
                'max_landmarks': MAX_LANDMARKS}

    def search(self, query, limit=12, min_households=None):
        limit = integer(limit, 'limit', 1, MAX_RESULTS)
        if min_households is not None and min_households != '':
            min_households = integer(min_households, 'min_households', 0, 1000000)
        if not isinstance(query, str) or len(query) > 100:
            raise ValueError('q must be a string of at most 100 characters')
        query = normalize(query)
        if not query or not available(self.database):
            return {'results': [], 'metadata': {'available': available(self.database), 'limit': limit,
                                                'truncated': False}}
        # Normalization removes SQL wildcard punctuation; values stay bound parameters.
        # Alias equality lets 강남역 find source name 강남 without changing its label.
        with self.connect() as connection:
            restriction, restriction_args = household_filter(connection,min_households)
            rows = connection.execute('''
                SELECT p.*, MIN(CASE WHEN a.normalized=? THEN 0
                    WHEN a.normalized LIKE ? THEN 1 ELSE 2 END) AS match_rank
                FROM aliases a JOIN places p ON p.rowid=a.place_rowid
                WHERE a.normalized LIKE ?
            ''' + restriction + '''
                GROUP BY p.rowid ORDER BY CASE WHEN match_rank=0 THEN 0 ELSE 1 END,
                    p.priority DESC, match_rank, LENGTH(p.name), p.name, p.id
                LIMIT ?
            ''', (query, query + '%', '%' + query + '%', *restriction_args, limit + 1)).fetchall()
        return {'results': [result_from_row(row) for row in rows[:limit]],
                'metadata': {'available': True, 'limit': limit, 'truncated': len(rows) > limit,
                             'search_scope': 'cached_source_names_and_aliases'}}

    def features(self, bbox, zoom=15, kinds='station,bridge,junction,residential', min_households=None):
        west, south, east, north = parse_bbox(bbox)
        if min_households is not None and min_households != '':
            min_households = integer(min_households, 'min_households', 0, 1000000)
        try:
            if isinstance(zoom, bool):
                raise ValueError
            zoom = float(zoom)
            if not math.isfinite(zoom) or not 0 <= zoom <= 24:
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            raise ValueError('zoom must be a finite number between 0 and 24') from None
        if isinstance(kinds, str):
            kinds = [kind.strip() for kind in kinds.split(',') if kind.strip()]
        if not isinstance(kinds, (tuple, list)) or any(kind not in KINDS for kind in kinds):
            raise ValueError('kinds must contain only ' + ','.join(KINDS))
        kinds = list(dict.fromkeys(kinds))
        metadata = {'available': available(self.database), 'limit': MAX_LANDMARKS, 'truncated': False,
                    'kinds': kinds, 'count': 0, 'min_households': min_households,
                    'household_filter_scope': 'residential_only'}
        if not kinds or not available(self.database):
            return {'type': 'FeatureCollection', 'features': [], 'metadata': metadata}
        placeholders = ','.join('?' for _ in kinds)
        with self.connect() as connection:
            restriction, restriction_args = household_filter(connection,min_households)
            rows = connection.execute(f'''SELECT p.* FROM place_index r JOIN places p ON p.rowid=r.rowid
                WHERE r.maxx>=? AND r.minx<=? AND r.maxy>=? AND r.miny<=?
                AND p.lon>=? AND p.lon<=? AND p.lat>=? AND p.lat<=?
                AND p.kind IN ({placeholders}) AND p.min_zoom<=?
                {restriction}
                ORDER BY p.priority DESC, p.name, p.id LIMIT ?''',
                (west, east, south, north, west, east, south, north, *kinds, zoom, *restriction_args, MAX_LANDMARKS + 1)).fetchall()
        features = []
        for row in rows[:MAX_LANDMARKS]:
            props = result_from_row(row)
            center = props.pop('center')
            features.append({'type': 'Feature', 'id': row['id'], 'properties': props,
                             'geometry': {'type': 'Point', 'coordinates': center}})
        metadata.update(count=len(features), truncated=len(rows) > MAX_LANDMARKS)
        return {'type': 'FeatureCollection', 'features': features, 'metadata': metadata}
