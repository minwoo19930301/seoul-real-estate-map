#!/usr/bin/env python3
"""Build a local atomic RTree database from the retained Overture Seoul source.

Input is manifest.json plus district-data/*.ndjson.gz from the original source
package, not the flight renderer's chunks (which contain fallback heights).
No downloads, credentials, geometry simplification or estimated height values.
"""
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
import time
import zlib

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 3


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def optional_number(value, positive=False):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid source numeric value')
    if positive and value <= 0:
        raise ValueError('Source height/floors must be positive or null')
    return value


def source_for(properties, key):
    sources = properties.get('sources') or []
    direct = [s.get('dataset') for s in sources if s.get('property') in (key, '/' + key) and s.get('dataset')]
    root = [s.get('dataset') for s in sources if s.get('property', '') == '' and s.get('dataset')]
    return '; '.join(dict.fromkeys(direct or root)) or None


def apartment_tag(properties):
    tags = properties.get('tags') or {}
    if not isinstance(tags, dict):
        tags = {}
    # A name containing "아파트", a residential subtype or a floor count does
    # not establish an apartment. Only an explicit source classification does.
    return properties.get('class') in ('apartments', 'apartment', 'apartment_building') or tags.get('building') == 'apartments'


def source_files(source_dir, manifest):
    root = source_dir.resolve()
    selected = []
    for record in manifest['files']:
        if record.get('type') not in ('building', 'building_part'):
            continue
        path = (root / record['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Source manifest points outside its directory or to a missing file')
        selected.append((record, path))
    if not selected:
        raise ValueError('No building source files in manifest')
    return selected


def build_database(source_dir, database):
    source_dir, database = Path(source_dir).resolve(), Path(database).resolve()
    manifest_path = source_dir / 'manifest.json'
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest.get('schemaVersion') != 1 or not isinstance(manifest.get('files'), list):
        raise ValueError('Unsupported Seoul source manifest')
    selected = source_files(source_dir, manifest)
    digest = hashlib.sha256(raw_manifest).hexdigest()
    # Verify every compressed source file before either reusing or replacing a
    # database. A partially copied source never overwrites the last good DB.
    file_hashes = []
    for record, path in selected:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = record.get('sha256')
        if expected and expected != actual:
            raise ValueError(f'Source checksum mismatch: {path.name}')
        file_hashes.append({'path': record['path'], 'sha256': actual})
    source_hash = hashlib.sha256(encode({'manifest': digest, 'files': file_hashes}).encode()).hexdigest()
    if database.is_file():
        try:
            with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as old:
                old_meta = {key: json.loads(value) for key, value in old.execute('SELECT key,value FROM metadata')}
            if old_meta.get('schema_version') == SCHEMA_VERSION and old_meta.get('source_hash') == source_hash:
                return {**old_meta, 'reused': True}
        except sqlite3.DatabaseError:
            pass
    database.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(prefix=database.stem + '-', suffix='.sqlite.tmp', dir=database.parent, delete=False)
    temporary.close()
    temp_path = Path(temporary.name)
    started = time.monotonic()
    to_metric = Transformer.from_crs(4326, 5186, always_xy=True)
    counts, by_kind = Counter(), {'building': Counter(), 'building_part': Counter()}
    sources, height_sources = Counter(), Counter()
    district_ids = set()
    try:
        with sqlite3.connect(temp_path) as db:
            db.executescript('''
                PRAGMA journal_mode=OFF;
                PRAGMA synchronous=OFF;
                CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE buildings(
                    rowid INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, name TEXT,
                    height_m REAL, min_height_m REAL, num_floors INTEGER,
                    footprint_area_m2 REAL NOT NULL, is_apartment INTEGER NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('building','building_part')),
                    parent_id TEXT, has_parts INTEGER NOT NULL, extrude INTEGER NOT NULL,
                    geometry_source TEXT, height_source TEXT, district_id TEXT,
                    geometry TEXT NOT NULL, source_properties BLOB NOT NULL
                );
                CREATE VIRTUAL TABLE building_index USING rtree(rowid,minx,maxx,miny,maxy);
            ''')
            for file_index, (record, path) in enumerate(selected):
                with gzip.open(path, 'rt', encoding='utf-8') as stream:
                    for line in stream:
                        feature = json.loads(line)
                        if feature.get('type') != 'Feature' or not isinstance(feature.get('id'), str):
                            raise ValueError('Source has an invalid GeoJSON feature')
                        props = feature['properties']
                        kind = props.get('feature_type', record['type'])
                        if kind != record['type']:
                            raise ValueError('Source feature kind differs from manifest')
                        geometry = feature['geometry']
                        footprint = shape(geometry)
                        if footprint.geom_type not in ('Polygon', 'MultiPolygon') or footprint.is_empty or not footprint.is_valid:
                            raise ValueError(f'Invalid original building geometry: {feature["id"]}')
                        minx, miny, maxx, maxy = footprint.bounds
                        if not -180 <= minx <= maxx <= 180 or not -90 <= miny <= maxy <= 90:
                            raise ValueError('Source footprint is not WGS84')
                        area = transform(to_metric.transform, footprint).area
                        if not math.isfinite(area) or area <= 0:
                            raise ValueError('Invalid footprint area')
                        height = optional_number(props.get('height'), positive=True)
                        min_height = optional_number(props.get('min_height'))
                        floors = optional_number(props.get('num_floors'), positive=True)
                        if floors is not None and int(floors) != floors:
                            raise ValueError('Source floor count is not an integer')
                        names = props.get('names') or {}
                        name = names.get('primary') if isinstance(names, dict) else None
                        if name is not None and not isinstance(name, str):
                            raise ValueError('Invalid building name')
                        parent_id = props.get('building_id') if kind == 'building_part' else None
                        if kind == 'building_part' and not isinstance(parent_id, str):
                            raise ValueError('Building part is missing its parent ID')
                        district = (props.get('_seoul') or {}).get('district_id')
                        if district:
                            district_ids.add(district)
                        has_parts = bool(props.get('has_parts')) if kind == 'building' else False
                        is_apartment = apartment_tag(props)
                        geom_source = source_for(props, 'geometry')
                        height_source = source_for(props, 'height') if height is not None else None
                        row = (feature['id'], name, height, min_height, floors, area, int(is_apartment),
                               kind, parent_id, int(has_parts), int(height is not None and not has_parts and min_height in (None, 0) and not props.get('is_underground')),
                               geom_source, height_source, district, encode(geometry), zlib.compress(encode(props).encode('utf-8')))
                        cursor = db.execute('''INSERT INTO buildings(id,name,height_m,min_height_m,num_floors,footprint_area_m2,
                            is_apartment,kind,parent_id,has_parts,extrude,geometry_source,height_source,district_id,geometry,source_properties)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', row)
                        db.execute('INSERT INTO building_index VALUES(?,?,?,?,?)', (cursor.lastrowid, minx, maxx, miny, maxy))
                        for counter in (counts, by_kind[kind]):
                            counter['count'] += 1
                            counter['reported' if height is not None else 'missing'] += 1
                            counter['apartments'] += int(is_apartment)
                        if geom_source:
                            sources[geom_source] += 1
                        if height_source:
                            height_sources[height_source] += 1
                if (file_index + 1) % 10 == 0:
                    print(f'{file_index + 1}/{len(selected)} source files · {counts["count"]:,} features', flush=True)
            db.execute('CREATE INDEX buildings_parent ON buildings(parent_id)')
            # Parent suppression is based on actual retained parts too, not just
            # a flag. No parent height is inherited by an unmeasured part.
            db.execute("UPDATE buildings SET has_parts=1,extrude=0 WHERE kind='building' AND id IN (SELECT parent_id FROM buildings WHERE kind='building_part')")
            # Explicit parent classification is inherited by its parts, while
            # the untouched source properties identify the original tag owner.
            db.execute("UPDATE buildings SET is_apartment=1 WHERE kind='building_part' AND parent_id IN (SELECT id FROM buildings WHERE kind='building' AND is_apartment=1)")
            counts['apartments'] = db.execute('SELECT COUNT(*) FROM buildings WHERE is_apartment=1').fetchone()[0]
            for kind in by_kind:
                by_kind[kind]['apartments'] = db.execute('SELECT COUNT(*) FROM buildings WHERE kind=? AND is_apartment=1', (kind,)).fetchone()[0]
            orphan_count = db.execute("SELECT COUNT(*) FROM buildings p LEFT JOIN buildings b ON p.parent_id=b.id WHERE p.kind='building_part' AND b.id IS NULL").fetchone()[0]
            if orphan_count:
                raise ValueError(f'{orphan_count} building parts have no source parent')
            suppressed = db.execute("SELECT COUNT(*) FROM buildings WHERE kind='building' AND has_parts=1 AND height_m IS NOT NULL").fetchone()[0]
            bbox = manifest.get('bbox') or {}
            metadata = {
                'schema_version': SCHEMA_VERSION, 'source_hash': source_hash,
                'source_properties_encoding': 'zlib-json-utf8',
                'source_manifest_sha256': digest, 'source_release': manifest.get('release'),
                'source_urls': manifest.get('sourceUrls', []),
                'license': manifest.get('license'), 'attribution': manifest.get('attribution'),
                'scope': manifest.get('selectionPolicy', 'Original features intersecting Seoul administrative territory, assigned once to one of 25 districts; no completeness guarantee'),
                'bounds': [bbox.get('minLon'), bbox.get('minLat'), bbox.get('maxLon'), bbox.get('maxLat')],
                'district_count': len(district_ids), 'counts': dict(counts),
                'total_count': counts['count'], 'reported_count': counts['reported'],
                'missing_count': counts['missing'], 'apartment_count': counts['apartments'],
                'by_kind': {key: dict(value) for key, value in by_kind.items()},
                'geometry_sources': dict(sources), 'height_sources': dict(height_sources),
                'suppressed_parent_extrusions': suppressed,
                'suppressed_elevated_extrusions': db.execute('SELECT COUNT(*) FROM buildings WHERE min_height_m IS NOT NULL AND min_height_m != 0 AND height_m IS NOT NULL').fetchone()[0],
                'height_policy': 'Own positive source height or null; reported is not independently surveyed. Never infer from floors, parent height, name, or a default.',
                'parts_policy': 'Original parent footprint remains visible and queryable; suppress full parent extrusion whenever source parts exist. Only ground-level parts with their own reported heights are extruded. Nonzero min_height features are outline-only because Overture/OSM height semantics are unverified; no base-plus-height calculation. Incomplete part heights remain visibly missing.',
                'apartment_policy': 'Explicit source class apartments/apartment/apartment_building or building=apartments tag; parts inherit only their tagged parent classification, exposed as classification_source=parent. No name inference.',
                'area_crs': 'EPSG:5186', 'area_policy': 'Original footprint area, holes excluded; not floor area or certified cadastral area',
                'geometry_policy': 'Original Polygon/MultiPolygon coordinates and holes retained with no simplification or viewport clipping',
                'created_at': datetime.now(timezone.utc).isoformat(), 'build_seconds': round(time.monotonic() - started, 2),
            }
            db.executemany('INSERT INTO metadata VALUES(?,?)', [(key, encode(value)) for key, value in metadata.items()])
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite integrity check failed')
            db.commit()
        # Temp file and target share a filesystem; readers see the entire old
        # database or the entire new one, never an unfinished import.
        with temp_path.open('rb') as file:
            os.fsync(file.fileno())
        os.replace(temp_path, database)
        return {**metadata, 'reused': False, 'database_bytes': database.stat().st_size}
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--database', type=Path, default=ROOT / 'data' / 'buildings.sqlite')
    args = parser.parse_args()
    result = build_database(args.source_dir, args.database)
    print(encode({key: result[key] for key in ['reused', 'total_count', 'reported_count', 'missing_count', 'apartment_count']}), flush=True)
