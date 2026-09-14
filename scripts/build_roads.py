#!/usr/bin/env python3
"""Build local roads from a retained, complete OSM Overpass geometry response."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import zlib

from shapely.geometry import LineString, shape
from shapely.ops import unary_union
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[1]
ROADWAYS = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
            'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'residential',
            'unclassified', 'living_street', 'service', 'road', 'track'}
MAJOR = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
         'secondary', 'secondary_link', 'tertiary', 'tertiary_link'}


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def classify(tags):
    """Separate mapped sidewalk ways only; no offset geometry or access inference."""
    highway = tags.get('highway')
    if tags.get('area') == 'yes':
        return None
    if highway in ROADWAYS:
        return 'roadway', highway
    if highway == 'steps':
        return 'steps', 'steps'
    if highway == 'footway':
        subtype = tags.get('footway')
        return 'walkway', subtype if subtype in ('sidewalk', 'crossing') else 'footway'
    if highway in ('pedestrian', 'path'):
        return 'walkway', highway
    if highway == 'cycleway' and tags.get('foot') in ('yes', 'designated', 'permissive'):
        return 'walkway', 'shared_cycleway'
    return None


def source_elements(source):
    raw = Path(source).read_bytes()
    document = json.loads(gzip.decompress(raw) if str(source).endswith('.gz') else raw)
    if document.get('remark') or not isinstance(document.get('elements'), list):
        raise ValueError('Incomplete or invalid Overpass response; previous database retained')
    # A combined POI query may repeat a road with tags/center only. Prefer the
    # actual geometry response, never replace it with an inferred straight line.
    ways = {}
    for item in document['elements']:
        if item.get('type') == 'way' and 'highway' in item.get('tags', {}):
            previous = ways.get(item['id'])
            if previous is None or len(item.get('geometry', [])) > len(previous.get('geometry', [])):
                ways[item['id']] = item
    if not ways:
        raise ValueError('Source contains no highway ways')
    return document, ways, hashlib.sha256(raw).hexdigest()


def build_database(source, database, boundary=None, endpoint=None):
    source, database = Path(source).resolve(), Path(database).resolve()
    document, ways, digest = source_elements(source)
    area = None
    if boundary:
        boundary_data = json.loads(Path(boundary).read_text())
        geometries = [f['geometry'] for f in boundary_data['features']] if boundary_data['type'] == 'FeatureCollection' else [boundary_data.get('geometry', boundary_data)]
        area = prep(unary_union([shape(g) for g in geometries]))
    database.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=database.name + '.', suffix='.tmp', dir=database.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    counts, subtypes, skipped = Counter(), Counter(), Counter()
    total_vertices, with_sidewalk_tag = 0, 0
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript('''
                CREATE TABLE roads (rowid INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
                  name TEXT, category TEXT NOT NULL, subtype TEXT NOT NULL, highway TEXT NOT NULL,
                  min_zoom INTEGER NOT NULL, geometry TEXT NOT NULL, vertex_count INTEGER NOT NULL,
                  tags BLOB NOT NULL);
                CREATE VIRTUAL TABLE road_index USING rtree(rowid,minx,maxx,miny,maxy);
                CREATE TABLE metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE INDEX roads_category ON roads(category,min_zoom);
            ''')
            for identifier, item in sorted(ways.items()):
                tags = item.get('tags') or {}
                classification = classify(tags)
                if classification is None:
                    skipped['area' if tags.get('area') == 'yes' else 'unsupported_highway'] += 1
                    continue
                geometry = item.get('geometry')
                if not isinstance(geometry, list) or len(geometry) < 2:
                    raise ValueError(f'Highway way {identifier} lacks full geometry')
                coordinates = []
                for point in geometry:
                    if not isinstance(point, dict):
                        raise ValueError(f'Highway way {identifier} has a missing coordinate')
                    lon, lat = point.get('lon'), point.get('lat')
                    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (lon, lat)) or not -180 <= lon <= 180 or not -90 <= lat <= 90:
                        raise ValueError(f'Highway way {identifier} has an invalid coordinate')
                    coordinates.append([lon, lat])
                if len(set(map(tuple, coordinates))) < 2:
                    skipped['degenerate'] += 1
                    continue
                line = LineString(coordinates)
                if area is not None and not area.intersects(line):
                    skipped['outside_seoul'] += 1
                    continue
                category, subtype = classification
                min_zoom = 11 if tags['highway'] in MAJOR else 13 if category == 'roadway' else 14
                geom = {'type': 'LineString', 'coordinates': coordinates}
                cursor = db.execute('INSERT INTO roads(id,name,category,subtype,highway,min_zoom,geometry,vertex_count,tags) VALUES(?,?,?,?,?,?,?,?,?)',
                    (f'osm:way:{identifier}', tags.get('name:ko') or tags.get('name'), category, subtype, tags['highway'], min_zoom, encode(geom), len(coordinates), zlib.compress(encode(tags).encode(), 6)))
                west, south, east, north = line.bounds
                db.execute('INSERT INTO road_index VALUES(?,?,?,?,?)', (cursor.lastrowid, west, east, south, north))
                counts[category] += 1
                subtypes[subtype] += 1
                total_vertices += len(coordinates)
                with_sidewalk_tag += category == 'roadway' and any(k == 'sidewalk' or k.startswith('sidewalk:') for k in tags)
            if not sum(counts.values()):
                raise ValueError('No road lines intersect the selected boundary')
            bounds = db.execute('SELECT MIN(minx),MIN(miny),MAX(maxx),MAX(maxy) FROM road_index').fetchone()
            metadata = {
                'schema_version': 1, 'source': 'OpenStreetMap', 'source_kind': 'osm_highway_ways',
                'source_endpoint': endpoint, 'source_file': source.name, 'source_sha256': digest,
                'source_osm_timestamp': document.get('osm3s', {}).get('timestamp_osm_base'),
                'built_at': datetime.now(timezone.utc).isoformat(),
                'attribution': '© OpenStreetMap contributors', 'license': 'ODbL-1.0',
                'license_url': 'https://www.openstreetmap.org/copyright',
                'source_url': 'https://www.openstreetmap.org',
                'scope': 'Seoul administrative boundary intersecting full ways' if boundary else 'supplied source extent',
                'boundary_file': str(Path(boundary).name) if boundary else None,
                'source_query_bbox': [126.734, 37.413, 127.270, 37.716],
                'bounds': bounds, 'source_highway_way_count': len(ways),
                'total_count': sum(counts.values()), 'counts': dict(counts), 'subtypes': dict(subtypes),
                'source_vertex_count': total_vertices, 'skipped': dict(skipped),
                'roadways_with_sidewalk_tags': with_sidewalk_tag,
                'geometry_policy': 'Original full OSM way coordinates preserved; no clipping, simplification, or invented sidewalk offsets',
                'sidewalk_policy': 'sidewalk only when highway=footway and footway=sidewalk on a separate mapped way',
                'coverage_complete': False,
                'coverage_note': 'All returned supported OSM ways intersecting Seoul, not a complete survey of every road or sidewalk. Separate sidewalk mapping may be absent.',
                'access_note': 'Tags retained; paths, shared cycleways and restricted/private ways are not a guarantee of public pedestrian access. Not a routing or accessibility service.',
                'tags_encoding': 'zlib-compressed UTF-8 JSON',
            }
            db.executemany('INSERT INTO metadata VALUES(?,?)', [(key, encode(value)) for key, value in metadata.items()])
        os.replace(temporary, database)
        return metadata
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--database', type=Path, default=ROOT / 'data/roads.sqlite')
    parser.add_argument('--boundary', type=Path, default=ROOT / 'data/building-source/seoul-boundary.geojson')
    parser.add_argument('--endpoint', default='https://overpass.kumi.systems/api/interpreter')
    args = parser.parse_args()
    print(json.dumps(build_database(args.source, args.database, args.boundary, args.endpoint), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
