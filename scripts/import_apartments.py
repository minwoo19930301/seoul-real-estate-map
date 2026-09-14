#!/usr/bin/env python3
"""Audit official Seoul OA-15818 complex records and resolve display locations.

No network, invented household totals, building-register aggregation or fuzzy joins.
Optional K-apt POI supplement joins strictly on the identical official complex code.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
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

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.places import normalize

DATASET_URL = 'https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do'
KAPT_URL = 'https://www.k-apt.go.kr/kaptinfo/openKaptLocation.do'
KAPT_SOURCE = '국토교통부·한국부동산원 공동주택관리정보시스템(K-apt) 단지 위치 POI'
# The K-apt map script converts its metre coordinates with a proj4 string identical to the
# Korean 1985 / Modified Central Belt definition (EPSG:5174); verified against 2,703 official
# Seoul coordinates (median 16.8 m). The code namespace (A########) is shared with OA-15818.
KAPT_CRS = 'EPSG:5174'
KAPT_MAX_SPREAD_M = 100.0
KAPT_STATUS = 'kapt_official_code_poi'
INFORMATIONAL_ISSUES = frozenset({'shared_official_coordinate_same_address',
    'official_kapt_location_disagreement_over_750m', 'kapt_osm_location_disagreement_over_750m',
    'kapt_poi_points_disagree', 'kapt_coordinate_shared_with_other_complex',
    'kapt_coordinate_outside_seoul', 'kapt_coordinate_district_mismatch', 'kapt_coordinate_missing'})
HOUSEHOLD_SOURCE = '서울시 공동주택통합정보마당 TNOHSH'
APARTMENT_CLASSES = ('아파트', '주상복합', '도시형 생활주택(아파트)', '도시형 생활주택(주상복합)')
FIELDS = {
    'code': 'k-아파트코드', 'name': 'k-아파트명', 'classification': 'k-단지분류(아파트,주상복합등등)',
    'households': 'k-전체세대수', 'district': '주소(시군구)', 'city': '주소(시도)k-apt주소split',
    'address': 'kapt도로명주소', 'lon': '좌표X', 'lat': '좌표Y',
    'updated': 'k-수정일자', 'status': '사용허가여부',
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def count_value(value):
    value = value.strip()
    if not value or value.casefold() in ('null', 'nan'):
        return None
    if not re.fullmatch(r'\d+(?:\.0+)?', value):
        raise ValueError('household total must be a nonnegative whole number: ' + repr(value))
    return int(value.split('.')[0])


def name_key(value):
    value = normalize(value)
    # Only a generic trailing designation is equivalent; district/phase/rental
    # and numbered-building tokens are never deleted or guessed.
    return value[:-3] if value.endswith('아파트') else value


def distance(a, b):
    return math.hypot((a[0]-b[0])*111320*math.cos(math.radians(a[1])), (a[1]-b[1])*111320)


def source_point(lon, lat):
    try:
        x, y = float(lon), float(lat)
        if not math.isfinite(x) or not math.isfinite(y) or not -180 <= x <= 180 or not -90 <= y <= 90:
            return None
        return Point(x, y)
    except (ValueError, TypeError):
        return None


def osm_candidates(path, districts):
    if path is None:
        return {}, 0
    payload = json.loads(Path(path).read_text())
    if payload.get('remark') or not isinstance(payload.get('elements'), list):
        raise ValueError('OSM source is missing elements or contains a partial-response remark')
    index = defaultdict(dict)
    for element in payload['elements']:
        tags = element.get('tags') or {}
        if tags.get('landuse') != 'residential' or not (tags.get('name:ko') or tags.get('name')):
            continue
        coordinates = element if element.get('type') == 'node' else element.get('center', {})
        point = source_point(coordinates.get('lon'), coordinates.get('lat'))
        if point is None:
            continue
        district = next((name for name, geom in districts.items() if geom.covers(point)), None)
        if district is None:
            continue
        identifier = f"osm:{element['type']}/{element['id']}"
        candidate = {'id': identifier, 'name': tags.get('name:ko') or tags['name'],
                     'lon': point.x, 'lat': point.y, 'district': district,
                     'source_url': f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
                     'method': 'osm_node' if element['type'] == 'node' else 'osm_bounds_center'}
        for key in ('name', 'name:ko', 'alt_name', 'alt_name:ko', 'official_name'):
            for alias in (tags.get(key) or '').split(';'):
                normalized = name_key(alias)
                if normalized:
                    index[(district, normalized)][identifier] = candidate
    return index, sum(len(c) for c in index.values())


def kapt_candidates(path, seoul, max_spread_m=KAPT_MAX_SPREAD_M):
    """Per-code K-apt POI candidates. Same official code namespace as OA-15818; no name matching.

    A code with several POI points is usable only when every point lies within max_spread_m of
    every other (the mean of that tight cluster is used, and the spread is recorded). A coordinate
    that another complex code also uses is never a distinct location for either complex.
    """
    if path is None:
        return {}, {}
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    rows = payload.get('resultList')
    if not isinstance(rows, list) or not rows:
        raise ValueError('K-apt POI source has no resultList')
    transformer = Transformer.from_crs(KAPT_CRS, 'EPSG:4326', always_xy=True)
    grouped = defaultdict(list)
    coordinate_codes = defaultdict(set)
    for row in rows:
        code = str(row.get('kaptCode') or '').strip()
        if not code:
            raise ValueError('K-apt POI row without kaptCode')
        x, y = row.get('xCoord'), row.get('yCoord')
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)) \
                or not math.isfinite(x) or not math.isfinite(y):
            grouped[code].append({'name': row.get('kaptName'), 'x': x, 'y': y, 'lon': None, 'lat': None})
            continue
        lon, lat = transformer.transform(x, y)
        grouped[code].append({'name': row.get('kaptName'), 'x': x, 'y': y, 'lon': lon, 'lat': lat})
        coordinate_codes[(round(x, 3), round(y, 3))].add(code)
    candidates = {}
    stats = Counter()
    for code, points in grouped.items():
        located = [p for p in points if p['lon'] is not None]
        entry = {'id': 'kapt:' + code, 'name': points[0]['name'], 'point_count': len(points), 'located_point_count': len(located),
                 'points': points, 'source_url': KAPT_URL, 'method': None, 'lon': None, 'lat': None, 'spread_m': None, 'unusable': None}
        if not located:
            entry['unusable'] = 'kapt_coordinate_missing'
        else:
            spread = max((distance((a['lon'], a['lat']), (b['lon'], b['lat'])) for a in located for b in located), default=0.0)
            entry['spread_m'] = round(spread, 1)
            shared = any(len(coordinate_codes[(round(p['x'], 3), round(p['y'], 3))]) > 1 for p in located)
            lon = sum(p['lon'] for p in located) / len(located)
            lat = sum(p['lat'] for p in located) / len(located)
            if spread > max_spread_m:
                entry['unusable'] = 'kapt_poi_points_disagree'
            elif shared:
                entry['unusable'] = 'kapt_coordinate_shared_with_other_complex'
            elif not seoul.covers(Point(lon, lat)):
                entry['unusable'] = 'kapt_coordinate_outside_seoul'
            else:
                entry.update(lon=lon, lat=lat, method='kapt_poi' if len(located) == 1 else 'kapt_poi_cluster_mean')
            if entry['unusable'] is None or entry['unusable'] not in ('kapt_coordinate_missing',):
                entry['reference_lon'], entry['reference_lat'] = lon, lat
        stats[entry['unusable'] or 'usable'] += 1
        candidates[code] = entry
    return candidates, {'kapt_poi_record_count': len(rows), 'kapt_unique_codes': len(grouped), 'kapt_code_disposition': dict(stats),
                        'kapt_coordinates_shared_between_codes': sum(1 for codes in coordinate_codes.values() if len(codes) > 1)}


def import_database(source_csv, output, districts_path, source_date, *, osm_path=None, expected_count=None, kapt_path=None):
    datetime.strptime(source_date, '%Y-%m-%d')
    with Path(source_csv).open(encoding='cp949', newline='') as stream:
        reader = csv.DictReader(stream)
        missing = set(FIELDS.values()) - set(reader.fieldnames or [])
        if missing:
            raise ValueError('Official OA-15818 CSV missing columns: ' + ', '.join(sorted(missing)))
        raw_rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in raw_rows):
            raise ValueError('CSV row width does not match its header')
    if expected_count is not None and len(raw_rows) != expected_count:
        raise ValueError(f'CSV count {len(raw_rows)} differs from independent source count {expected_count}')
    rows = []
    seen = set()
    for raw in raw_rows:
        row = {key: raw[label].strip() for key, label in FIELDS.items()}
        if not row['code'] or row['code'] in seen:
            raise ValueError('Blank or duplicate official apartment code: ' + row['code'])
        seen.add(row['code'])
        row['households'] = count_value(row['households'])
        row['raw'] = raw
        rows.append(row)
    districts_data = json.loads(Path(districts_path).read_text())['features']
    districts = {f['properties']['names']['primary']: shape(f['geometry']) for f in districts_data}
    seoul = unary_union(list(districts.values()))
    candidates, _ = osm_candidates(osm_path, districts)
    kapt_map, kapt_stats = kapt_candidates(kapt_path, seoul)
    coordinate_groups = defaultdict(list)
    for row in rows:
        point = source_point(row['lon'], row['lat'])
        if point:
            coordinate_groups[(point.x, point.y)].append(row)
    duplicate_groups = {k: v for k, v in coordinate_groups.items() if len(v) > 1}
    records = []
    for row in rows:
        official = source_point(row['lon'], row['lat'])
        expected_district = districts.get(row['district'])
        issues = []
        if row['city'] not in ('서울', '서울시', '서울특별시'):
            issues.append('source_city_not_seoul')
        if row['status'] != 'Y':
            issues.append('source_record_not_approved')
        if not row['name']:
            issues.append('missing_name')
        if official is None:
            issues.append('missing_or_invalid_official_coordinate')
        elif not seoul.covers(official):
            issues.append('official_coordinate_outside_seoul')
        elif expected_district is None or not expected_district.covers(official):
            issues.append('official_coordinate_district_mismatch')
        shared_address = False
        if official and (official.x, official.y) in duplicate_groups:
            group = duplicate_groups[(official.x, official.y)]
            addresses = {normalize(r['address']) for r in group}
            shared_address = len(addresses) == 1 and '' not in addresses
            issues.append('shared_official_coordinate_same_address' if shared_address else 'duplicate_coordinate_different_addresses')
        exact = list(candidates.get((row['district'], name_key(row['name'])), {}).values())
        match = exact[0] if len(exact) == 1 else None
        delta = distance((official.x, official.y), (match['lon'], match['lat'])) if official and match else None
        if delta is not None and delta > 750:
            issues.append('official_osm_name_location_disagreement_over_750m')
        # Severity is fixed before K-apt evidence is added: K-apt issues are informational and
        # never demote a valid official coordinate.
        severe = set(issues) - INFORMATIONAL_ISSUES
        invalid_record = any(i in severe for i in ('source_city_not_seoul','source_record_not_approved','missing_name'))
        kapt = kapt_map.get(row['code'])
        official_kapt_distance = kapt_osm_distance = None
        kapt_usable = (kapt is not None and kapt['unusable'] is None and expected_district is not None
                       and expected_district.covers(Point(kapt['lon'], kapt['lat'])))
        if kapt is not None:
            if kapt['unusable']:
                issues.append(kapt['unusable'])
            elif not kapt_usable:
                issues.append('kapt_coordinate_district_mismatch')
            if kapt.get('reference_lon') is not None:
                kapt_point = (kapt['reference_lon'], kapt['reference_lat'])
                if official:
                    official_kapt_distance = distance((official.x, official.y), kapt_point)
                if match:
                    kapt_osm_distance = distance(kapt_point, (match['lon'], match['lat']))
            # Disagreement flags describe two individually acceptable locations that still differ;
            # a coordinate already rejected above carries its own reason instead.
            if kapt_usable and official_kapt_distance is not None and not severe and official_kapt_distance > 750:
                issues.append('official_kapt_location_disagreement_over_750m')
            if kapt_usable and kapt_osm_distance is not None and kapt_osm_distance > 750:
                issues.append('kapt_osm_location_disagreement_over_750m')
        if severe and kapt_usable and not invalid_record:
            lon, lat = kapt['lon'], kapt['lat']
            location_method = kapt['method']
            coordinate_status = KAPT_STATUS
            coordinate_source_url = kapt['source_url']
        elif severe and match and not invalid_record:
            lon, lat = match['lon'], match['lat']
            location_method = match['method']
            coordinate_status = 'osm_exact_name_and_district'
            coordinate_source_url = match['source_url']
        elif not severe and official:
            lon, lat = official.x, official.y
            location_method = 'official_reported_coordinate'
            coordinate_status = 'official_shared_address' if shared_address else 'official_reported'
            coordinate_source_url = DATASET_URL
        else:
            lon = lat = None
            location_method = None
            coordinate_status = 'unresolved'
            coordinate_source_url = None
        records.append({**row, 'resolved_lon': lon, 'resolved_lat': lat,
            'location_method': location_method, 'coordinate_status': coordinate_status,
            'coordinate_source_url': coordinate_source_url, 'coordinate_issues': issues,
            'matched_osm': match, 'osm_candidate_count': len(exact), 'official_osm_distance_m': delta,
            'matched_kapt': ({k: v for k, v in kapt.items() if k != 'points'} | {'points': kapt['points'][:10]}) if kapt else None,
            'official_kapt_distance_m': official_kapt_distance, 'kapt_osm_distance_m': kapt_osm_distance,
            'target_400': row['classification'] in APARTMENT_CLASSES and row['households'] is not None and row['households'] >= 400})
    targets = [r for r in records if r['target_400']]
    unresolved = [r for r in records if r['resolved_lon'] is None]
    missing_targets = [r for r in targets if r['resolved_lon'] is None]
    metadata = {
        'schema_version': 1, 'source_dataset': 'OA-15818', 'source_name': '서울시 공동주택 아파트 정보',
        'source_url': DATASET_URL, 'source_date': source_date,
        'imported_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': sha256(source_csv),
        'source_bytes': Path(source_csv).stat().st_size, 'source_row_count': len(records),
        'independent_source_count': expected_count, 'unique_official_codes': len(seen),
        'household_count_field': 'TNOHSH', 'household_count_source': HOUSEHOLD_SOURCE,
        'household_count_scope': 'Official management-complex code; ownership/rental registrations may be separate.',
        'license': '공공누리 제1유형: 출처표시', 'attribution': '서울특별시 공동주택통합정보마당',
        'source_classes': dict(Counter(r['classification'] or '(미분류)' for r in records)),
        'household_missing_count': sum(r['households'] is None for r in records),
        'household_zero_count': sum(r['households'] == 0 for r in records),
        'all_classes_ge400': sum(r['households'] is not None and r['households'] >= 400 for r in records),
        'official_complex_count_ge400': len(targets),
        'mapped_complex_count_ge400': len(targets) - len(missing_targets),
        'mapped_all_classes_count': len(records) - len(unresolved),
        'unmapped_all_classes_count': len(unresolved),
        'coordinate_status_counts': dict(Counter(r['coordinate_status'] for r in records)),
        'coordinate_status_counts_ge400': dict(Counter(r['coordinate_status'] for r in targets)),
        'duplicate_coordinate_group_count': len(duplicate_groups),
        'osm_source_sha256': sha256(osm_path) if osm_path else None,
        'kapt_source_url': KAPT_URL if kapt_path else None, 'kapt_source_sha256': sha256(kapt_path) if kapt_path else None,
        'kapt_crs': KAPT_CRS if kapt_path else None, 'kapt_max_cluster_spread_m': KAPT_MAX_SPREAD_M if kapt_path else None,
        **kapt_stats,
        'kapt_codes_in_source_dataset': sum(1 for r in records if r['matched_kapt']) if kapt_path else None,
        'kapt_located_count': sum(1 for r in records if r['coordinate_status'] == KAPT_STATUS),
        'kapt_located_count_ge400': sum(1 for r in targets if r['coordinate_status'] == KAPT_STATUS),
        'official_kapt_disagreements_over_750m': [{'code': r['code'], 'name': r['name'], 'district': r['district'],
            'distance_m': round(r['official_kapt_distance_m']), 'coordinate_status': r['coordinate_status']}
            for r in records if 'official_kapt_location_disagreement_over_750m' in r['coordinate_issues']],
        'kapt_osm_disagreements_over_750m': [{'code': r['code'], 'name': r['name'], 'district': r['district'],
            'distance_m': round(r['kapt_osm_distance_m']), 'coordinate_status': r['coordinate_status']}
            for r in records if 'kapt_osm_location_disagreement_over_750m' in r['coordinate_issues']],
        'location_precedence': 'official coordinate (validated) > K-apt POI by identical complex code > OSM exact name in the same district > unresolved',
        'unmapped_ge400': [{'code': r['code'], 'name': r['name'], 'household_count': r['households'],
                           'district': r['district'], 'issues': r['coordinate_issues']} for r in missing_targets],
        'source_coverage': 'All rows in the downloaded Seoul public dataset; not proof that every real Seoul complex is registered.',
        'coordinate_note': 'Source coordinates can be wrong. OSM supplements require a unique exact normalized name and the same district; unresolved records have no map pin.',
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=output.stem+'-',suffix='.sqlite',dir=output.parent)
    os.close(fd)
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript('''CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE apartments(code TEXT PRIMARY KEY,name TEXT NOT NULL,classification TEXT,
                household_count INTEGER,district TEXT,address TEXT,source_updated_at TEXT,
                official_lon TEXT,official_lat TEXT,lon REAL,lat REAL,location_method TEXT,
                coordinate_status TEXT NOT NULL,coordinate_source_url TEXT,coordinate_issues TEXT NOT NULL,
                matched_osm TEXT,osm_candidate_count INTEGER NOT NULL,official_osm_distance_m REAL,
                target_400 INTEGER NOT NULL,source_properties BLOB NOT NULL,
                matched_kapt TEXT,official_kapt_distance_m REAL,kapt_osm_distance_m REAL);
                CREATE INDEX apartments_households ON apartments(household_count);''')
            for r in records:
                db.execute('INSERT INTO apartments VALUES('+','.join('?' for _ in range(23))+')',
                    (r['code'],r['name'],r['classification'],r['households'],r['district'],r['address'],r['updated'],
                    r['lon'],r['lat'],r['resolved_lon'],r['resolved_lat'],r['location_method'],r['coordinate_status'],
                    r['coordinate_source_url'],json.dumps(r['coordinate_issues']),json.dumps(r['matched_osm'],ensure_ascii=False),
                    r['osm_candidate_count'],r['official_osm_distance_m'],int(r['target_400']),
                    zlib.compress(json.dumps(r['raw'],ensure_ascii=False).encode()),
                    json.dumps(r['matched_kapt'],ensure_ascii=False) if r['matched_kapt'] else None,
                    r['official_kapt_distance_m'],r['kapt_osm_distance_m']))
            db.executemany('INSERT INTO metadata VALUES(?,?)',((k,json.dumps(v,ensure_ascii=False)) for k,v in metadata.items()))
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('apartment database failed integrity check')
        os.replace(temporary,output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_csv',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'data/apartments.sqlite')
    parser.add_argument('--districts',type=Path,default=ROOT/'data/building-source/districts.geojson')
    parser.add_argument('--source-date',required=True)
    parser.add_argument('--expected-count',type=int)
    parser.add_argument('--osm',type=Path)
    parser.add_argument('--kapt-poi',type=Path,help='K-apt getKaptInfo_poi.do JSON (data/sources/kapt-seoul-complex-poi-*/kapt-poi-seoul.json)')
    args=parser.parse_args()
    print(json.dumps(import_database(args.source_csv,args.output,args.districts,args.source_date,
        osm_path=args.osm,expected_count=args.expected_count,kapt_path=args.kapt_poi),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
