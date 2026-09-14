#!/usr/bin/env python3
"""Build a reproducible local POI index from saved OSM/Overture source records.

Reads public-source caches only. This command never downloads data or geocodes names.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import zlib

from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.places import normalize

SCHEMA_VERSION = 2
OSM_URL = 'https://www.openstreetmap.org/'
OVERTURE_URL = 'https://docs.overturemaps.org/guides/buildings/'


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def names_from_properties(properties):
    names = properties.get('names') or {}
    values = [names.get('primary')]
    common = names.get('common') or []
    values += list(common.values()) if isinstance(common, dict) else [pair[1] for pair in common if len(pair) == 2]
    values += [rule.get('value') for rule in names.get('rules', [])]
    return [v for v in values if isinstance(v, str) and v.strip()]


def osm_source_url(properties, fallback=OVERTURE_URL):
    for source in properties.get('sources', []):
        record = source.get('record_id') or ''
        match = re.fullmatch(r'([nwr])(\d+)(?:@\d+)?', record)
        if source.get('dataset') == 'OpenStreetMap' and match:
            return OSM_URL + {'n': 'node', 'w': 'way', 'r': 'relation'}[match[1]] + '/' + match[2]
    return fallback


def make_place(identifier, name, kind, point, aliases, subtitle, source_url, method,
               priority, min_zoom, zoom, building_id=None, district_name=None, source_ids=None):
    return dict(id=identifier, name=name, kind=kind, lon=point.x, lat=point.y,
                aliases=sorted(set([name, *aliases])), subtitle=subtitle, source_url=source_url,
                location_method=method, priority=priority, min_zoom=min_zoom, zoom=zoom,
                building_id=building_id, district_name=district_name, source_ids=source_ids or [identifier])


def osm_place(element):
    tags = element.get('tags') or {}
    name = tags.get('name:ko') or tags.get('name') or tags.get('bridge:name:ko') or tags.get('bridge:name')
    if not name or not isinstance(name, str):
        return None
    railway = tags.get('railway')
    if railway in ('station', 'halt'):
        # Abandoned/proposed stations are not current navigation landmarks.
        if any(tags.get(key) == 'yes' for key in ('abandoned', 'disused', 'proposed', 'construction')):
            return None
        kind, label, priority, min_zoom, zoom = 'station', '철도·지하철역', 100, 11, 16
    elif tags.get('man_made') == 'bridge' or tags.get('bridge:name') or (
            tags.get('bridge') not in (None, 'no') and re.search(r'(대교|철교|교|[Bb]ridge)$', name)):
        name = tags.get('bridge:name:ko') or tags.get('bridge:name') or name
        kind, label, priority, min_zoom, zoom = 'bridge', '다리', 95, 11, 14
    elif element.get('type') == 'node' and tags.get('highway') != 'bus_stop' and tags.get('public_transport') not in ('platform', 'stop_position') and (
            tags.get('junction') or re.search(r'(사거리|삼거리|오거리|육거리|교차로)$', name)):
        kind, label, priority, min_zoom, zoom = 'junction', '교차로', 80, 13, 16
    elif tags.get('landuse') == 'residential':
        kind, priority, min_zoom, zoom = 'residential', 85, 13, 16
        label = '아파트 주거 영역' if tags.get('residential') == 'apartments' else '이름 있는 주거 영역'
    elif tags.get('place') in ('suburb', 'quarter', 'neighbourhood', 'town'):
        kind, label, priority, min_zoom, zoom = 'neighborhood', '지역 이름', 90, 12, 14
    elif tags.get('boundary') == 'administrative' and tags.get('admin_level') in ('6', '7', '8', '9', '10'):
        kind, label, priority, min_zoom, zoom = 'neighborhood', '행정구역', 90, 12, 14
    else:
        return None
    if element.get('type') == 'node' and 'lon' in element and 'lat' in element:
        point, method = Point(element['lon'], element['lat']), 'osm_node'
    elif element.get('center'):
        point = Point(element['center']['lon'], element['center']['lat'])
        method = 'osm_bounds_center'
    elif element.get('geometry') and len(element['geometry']) >= 2:
        coordinates = [(p['lon'], p['lat']) for p in element['geometry'] if 'lon' in p and 'lat' in p]
        if len(coordinates) < 2:
            return None
        point = LineString(coordinates).interpolate(0.5, normalized=True)
        method = 'osm_line_midpoint'
    else:
        return None
    if not all(math.isfinite(n) for n in (point.x, point.y)):
        return None
    aliases = []
    alias_keys = ('name', 'name:ko', 'name:en', 'alt_name', 'alt_name:ko', 'short_name', 'official_name', 'bridge:name')
    if kind == 'bridge' and tags.get('bridge:name') and tags.get('man_made') != 'bridge':
        alias_keys = ('bridge:name', 'bridge:name:ko', 'bridge:name:en')
    for key in alias_keys:
        value = tags.get(key)
        if isinstance(value, str):
            aliases.extend(part.strip() for part in value.split(';') if part.strip())
    if kind == 'station':
        # Search-only suffix equivalence; retain the original station display name.
        aliases += [a + '역' for a in [name, *aliases] if re.fullmatch(r'[가-힣0-9·() ]+', a) and not a.endswith('역')]
    identifier = f"osm:{element['type']}/{element['id']}"
    result = make_place(identifier, name, kind, point, aliases, label + ' · OpenStreetMap',
                        OSM_URL + f"{element['type']}/{element['id']}", method,
                        priority, min_zoom, zoom)
    # Prefer a bridge's dedicated outline over individual road-segment names.
    result['_preference'] = 0 if tags.get('man_made') == 'bridge' or method == 'osm_node' else 1
    return result


def near_distance(a, b):
    # Only duplicate-pin grouping, not elevation or survey measurement.
    return math.hypot((a['lon'] - b['lon']) * 111320 * math.cos(math.radians(a['lat'])),
                      (a['lat'] - b['lat']) * 111320)


def merge_duplicate_landmarks(places):
    groups = {}
    result = []
    for place in sorted(places, key=lambda p: (p.get('_preference', 0), p['id'])):
        key = (place['kind'], normalize(place['name']))
        threshold = {'station': 500, 'bridge': 2000, 'junction': 75, 'neighborhood': 250}.get(place['kind'], 0)
        existing = next((p for p in groups.get(key, []) if threshold and near_distance(p, place) <= threshold), None)
        if existing:
            existing['aliases'] = sorted(set(existing['aliases'] + place['aliases']))
            existing['source_ids'].extend(place['source_ids'])
        else:
            groups.setdefault(key, []).append(place)
            result.append(place)
    return result


def build_database(output, buildings, districts, boundary, overpass=(), overpass_endpoint=None, apartments=None):
    districts_data = json.loads(Path(districts).read_text())['features']
    boundary_data = json.loads(Path(boundary).read_text())['features']
    seoul = unary_union([shape(f['geometry']) for f in boundary_data])
    districts_lookup = {str(f['id']): f['properties']['names']['primary'] for f in districts_data}
    places = []
    sources = []
    for feature in districts_data:
        props = feature['properties']
        name = props['names']['primary']
        places.append(make_place('district:' + str(feature['id']), name, 'neighborhood',
            shape(feature['geometry']).representative_point(), names_from_properties(props),
            '서울 자치구 · Overture / OpenStreetMap', osm_source_url(props), 'inside_source_boundary',
            90, 9, 13, district_name=name))
    sources.append({'kind': 'overture_districts', 'file': str(Path(districts).resolve().relative_to(ROOT))
                    if Path(districts).resolve().is_relative_to(ROOT) else Path(districts).name,
                    'sha256': digest(districts), 'count': len(districts_data),
                    'url': 'https://docs.overturemaps.org/guides/divisions/',
                    'location_method': 'inside_source_boundary'})
    with sqlite3.connect(Path(buildings).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        building_meta = {r['key']: json.loads(r['value']) for r in db.execute('SELECT * FROM metadata')}
        building_count = 0
        for row in db.execute("SELECT * FROM buildings WHERE kind='building' AND name IS NOT NULL AND TRIM(name)<>''"):
            geom = shape(json.loads(row['geometry']))
            point = geom.representative_point()
            if point.is_empty or not seoul.covers(point):
                continue
            raw = row['source_properties']
            props = json.loads(zlib.decompress(raw) if isinstance(raw, bytes) else raw)
            district = districts_lookup.get(row['district_id'])
            kind_label = '아파트 건물' if row['is_apartment'] else '건물'
            subtitle = ' · '.join(filter(None, (district, kind_label, '원본 도형 내부 위치')))
            official = building_meta.get('source_kind') == 'official_gis_buildings'
            source_url = building_meta.get('source_url', 'https://www.vworld.kr/') if official else osm_source_url(props)
            places.append(make_place('building:' + row['id'], row['name'], 'building', point,
                names_from_properties(props), subtitle, source_url, 'inside_source_footprint',
                40 if row['is_apartment'] else 30, 16, 17, building_id=row['id'], district_name=district))
            building_count += 1
    sources.append({'kind': building_meta.get('source_kind', 'overture_buildings'), 'count': building_count,
                    'source_hash': building_meta.get('source_hash'), 'release': building_meta.get('source_release'),
                    'url': OVERTURE_URL, 'location_method': 'inside_source_footprint'})
    osm_elements = {}
    raw_count = 0
    for path in overpass:
        payload = json.loads(Path(path).read_text())
        if payload.get('remark'):
            raise ValueError('Overpass returned a remark (possibly partial response): ' + payload['remark'])
        if not isinstance(payload.get('elements'), list):
            raise ValueError('Overpass source must contain an elements array')
        raw_count += len(payload['elements'])
        for element in payload['elements']:
            key = (element.get('type'), element.get('id'))
            previous = osm_elements.get(key, {})
            osm_elements[key] = {**previous, **element}
        sources.append({'kind': 'osm_overpass', 'file': Path(path).name, 'sha256': digest(path),
                        'url': 'https://wiki.openstreetmap.org/wiki/Overpass_API',
                        'endpoint': overpass_endpoint,
                        'osm_timestamp': payload.get('osm3s', {}).get('timestamp_osm_base'),
                        'raw_elements': len(payload['elements'])})
    osm_places = []
    outside_count = 0
    for element in osm_elements.values():
        place = osm_place(element)
        if place:
            if seoul.covers(Point(place['lon'], place['lat'])):
                osm_places.append(place)
            else:
                outside_count += 1
    premerge_count = len(osm_places)
    osm_places = merge_duplicate_landmarks(osm_places)
    # Source boundary district labels are already in the index, so drop duplicate OSM 구-area records.
    district_names = set(districts_lookup.values())
    osm_places = [p for p in osm_places if not (p['kind'] == 'neighborhood' and p['name'] in district_names)]
    places.extend(osm_places)
    apartment_meta = None
    replaced_osm_ids = set()
    if apartments is not None:
        from scripts.import_apartments import DATASET_URL, HOUSEHOLD_SOURCE
        with sqlite3.connect(Path(apartments).resolve().as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            apartment_meta = {r['key']: json.loads(r['value']) for r in db.execute('SELECT * FROM metadata')}
            official_places = []
            for row in db.execute('SELECT * FROM apartments WHERE lon IS NOT NULL AND lat IS NOT NULL'):
                match = json.loads(row['matched_osm'])
                identifier = 'seoul-apartment:' + row['code']
                aliases = [match['name']] if match else []
                source_ids = [identifier]
                if match:
                    source_ids.append(match['id'])
                    replaced_osm_ids.add(match['id'])
                households = row['household_count']
                count_label = ('전체 세대수 미등록' if households is None else '0세대 등록 · 규모 미확인'
                               if households == 0 else f'{households:,}세대')
                location_label = ('OSM 이름·구 일치 위치' if row['coordinate_status'] == 'osm_exact_name_and_district'
                                  else 'K-apt 단지코드 일치 위치' if row['coordinate_status'] == 'kapt_official_code_poi'
                                  else '동일 주소 공식 좌표 공유' if row['coordinate_status'] == 'official_shared_address'
                                  else '서울시 등록 좌표')
                subtitle = ' · '.join(filter(None, (row['district'], row['classification'] or '분류 미등록', count_label, location_label)))
                p = make_place(identifier,row['name'],'residential',Point(row['lon'],row['lat']),aliases,
                    subtitle,DATASET_URL,row['location_method'],110 if row['target_400'] else 88,
                    12 if row['target_400'] else 14,16,district_name=row['district'],source_ids=source_ids)
                p.update(household_count=households,official_complex_code=row['code'],apartment_class=row['classification'],
                         household_count_source=HOUSEHOLD_SOURCE,source_updated_at=row['source_updated_at'],
                         coordinate_status=row['coordinate_status'],coordinate_source_url=row['coordinate_source_url'])
                official_places.append(p)
        # A same-name, same-district OSM region is evidence for this official
        # complex's search name, not a second pin with unknown household count.
        places = [p for p in places if p['id'] not in replaced_osm_ids] + official_places
    metadata = {'schema_version': SCHEMA_VERSION, 'built_at': datetime.now(timezone.utc).isoformat(),
                'total_count': len(places), 'counts': dict(Counter(p['kind'] for p in places)),
                'bounds': list(seoul.bounds), 'sources': sources,
                'attribution': building_meta.get('attribution', '© OpenStreetMap contributors, Overture Maps Foundation'),
                'license': 'ODbL-1.0; preserve upstream source attribution',
                'source_urls': ['https://www.openstreetmap.org/copyright', 'https://docs.overturemaps.org/attribution/'],
                'coverage': 'Cached named source objects inside the Seoul boundary; not an exhaustive official POI directory.',
                'coordinate_note': 'Nodes retain source coordinates; area/line positions are display representatives, not entrances.',
                'residential_note': 'Named OSM landuse=residential areas; individual building names do not define a whole complex.',
                'osm_raw_count': raw_count, 'osm_unique_elements': len(osm_elements),
                'osm_landmarks_before_merge': premerge_count, 'osm_landmarks': len(osm_places),
                'osm_outside_seoul_excluded': outside_count, 'osm_available': bool(overpass)}
    if apartment_meta is not None:
        metadata['official_apartments'] = apartment_meta
        metadata['official_complex_count_ge400'] = apartment_meta['official_complex_count_ge400']
        metadata['mapped_complex_count_ge400'] = apartment_meta['mapped_complex_count_ge400']
        metadata['osm_pins_replaced_by_official_complex'] = len(replaced_osm_ids)
        metadata['attribution'] += '; 서울특별시 공동주택통합정보마당'
        metadata['residential_note'] = 'Official Seoul complex records and named OSM residential areas. Household totals belong only to the official complex code; building/dong names are never totaled.'
        metadata['source_urls'].append(apartment_meta['source_url'])
        metadata['sources'].append({'kind':'official_seoul_apartments','url':apartment_meta['source_url'],
            'count':apartment_meta['mapped_all_classes_count'],'source_date':apartment_meta['source_date'],
            'sha256':apartment_meta['source_sha256'],'license':apartment_meta['license']})
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=output.stem + '-', suffix='.sqlite', dir=output.parent)
    os.close(descriptor)
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript('''
                CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE places(rowid INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    kind TEXT NOT NULL, lon REAL NOT NULL, lat REAL NOT NULL, subtitle TEXT NOT NULL,
                    source_url TEXT NOT NULL, location_method TEXT NOT NULL, priority INTEGER NOT NULL,
                    min_zoom INTEGER NOT NULL, zoom INTEGER NOT NULL, building_id TEXT, district_name TEXT,
                    source_ids TEXT NOT NULL,household_count INTEGER,official_complex_code TEXT,
                    apartment_class TEXT,household_count_source TEXT,source_updated_at TEXT,
                    coordinate_status TEXT,coordinate_source_url TEXT);
                CREATE VIRTUAL TABLE place_index USING rtree(rowid,minx,maxx,miny,maxy);
                CREATE TABLE aliases(place_rowid INTEGER NOT NULL, normalized TEXT NOT NULL,
                    PRIMARY KEY(place_rowid,normalized));
                CREATE INDEX aliases_normalized ON aliases(normalized);
                CREATE INDEX places_kind ON places(kind);
            ''')
            for p in places:
                cursor = db.execute('''INSERT INTO places(id,name,kind,lon,lat,subtitle,source_url,location_method,
                    priority,min_zoom,zoom,building_id,district_name,source_ids,household_count,official_complex_code,
                    apartment_class,household_count_source,source_updated_at,coordinate_status,coordinate_source_url)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    tuple(p[k] for k in ('id','name','kind','lon','lat','subtitle','source_url','location_method',
                        'priority','min_zoom','zoom','building_id','district_name')) + (json.dumps(p['source_ids']),)
                    + tuple(p.get(k) for k in ('household_count','official_complex_code','apartment_class',
                        'household_count_source','source_updated_at','coordinate_status','coordinate_source_url')))
                rowid = cursor.lastrowid
                db.execute('INSERT INTO place_index VALUES(?,?,?,?,?)', (rowid,p['lon'],p['lon'],p['lat'],p['lat']))
                aliases = {normalize(a) for a in p['aliases'] if normalize(a)}
                if p['district_name']:
                    aliases.add(normalize(p['district_name'] + p['name']))
                db.executemany('INSERT INTO aliases VALUES(?,?)', ((rowid,a) for a in sorted(aliases)))
            db.executemany('INSERT INTO metadata VALUES(?,?)', ((k,json.dumps(v,ensure_ascii=False)) for k,v in metadata.items()))
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('places database failed integrity check')
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--buildings', type=Path, default=ROOT / 'data/buildings.sqlite')
    parser.add_argument('--districts', type=Path, default=ROOT / 'data/building-source/districts.geojson')
    parser.add_argument('--boundary', type=Path, default=ROOT / 'data/building-source/seoul-boundary.geojson')
    parser.add_argument('--overpass', type=Path, action='append', default=[])
    parser.add_argument('--overpass-endpoint', help='Actual endpoint used to obtain the saved response (provenance only)')
    parser.add_argument('--apartments', type=Path, default=ROOT / 'data/apartments.sqlite',
                        help='Official apartment database; included when this file exists')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/places.sqlite')
    args = parser.parse_args()
    metadata = build_database(args.output, args.buildings, args.districts, args.boundary, args.overpass,
        args.overpass_endpoint, args.apartments if args.apartments.is_file() else None)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
