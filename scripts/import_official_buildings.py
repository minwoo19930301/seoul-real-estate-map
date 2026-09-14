#!/usr/bin/env python3
"""Import a locally downloaded Seoul AL_D010 SHP ZIP; never downloads or logs in.

Preserves the ZIP, reads its PRJ, retains source attributes, and atomically replaces
the building database after backing up the previous SQLite database. Validated
against generated fixtures only: the official Seoul archive is not yet obtained.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import time
from zipfile import BadZipFile, ZipFile
import zlib

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
import shapefile
from shapely.geometry import mapping, shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 3
IMPORTER_VERSION = 1
SOURCE_URL = 'https://www.vworld.kr/dtmk/dtmk_ntads_s002.do?svcCde=NA&dsId=18'
HEIGHT_SOURCE = '국토부 건축물대장'
GEOMETRY_SOURCE = '국토교통부 GIS건물통합정보 AL_D010'
FIELDS = {f'A{i}' for i in range(29)}
MAX_UNCOMPRESSED_BYTES = 4 * 1024**3


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def text_id(value, label):
    # DBF numeric integer fields may be Python ints; IDs may exceed JS's exact
    # integer range. Floats are rejected rather than accepting rounded IDs.
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f'{label} must be an exact string or integer')
    value = str(value).strip()
    if not value or len(value) > 40 or any(ord(c) < 32 for c in value):
        raise ValueError(f'Invalid {label}')
    return value


def positive_number(value, label, integer=False):
    if value is None or isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, bool):
        raise ValueError(f'Invalid {label}')
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f'Invalid {label}') from None
    if not math.isfinite(number):
        raise ValueError(f'Non-finite {label}')
    if number <= 0:
        return None
    if integer and number != int(number):
        raise ValueError(f'{label} must be an integer')
    return int(number) if integer else number


def use_code(value):
    if value is None or value == '':
        return None
    if isinstance(value, float):
        if not math.isfinite(value) or value != int(value):
            raise ValueError('Invalid A8 use code')
        value = int(value)
    value = str(value).strip()
    if not value.isascii() or not value.isdigit() or len(value) > 5:
        raise ValueError('Invalid A8 use code')
    return value.zfill(5)


def clean_properties(properties):
    # Preserve all official columns, including IDs and nonpositive raw heights.
    # Decimal precision in numeric DBF values is limited by the source format.
    result = {}
    for key, value in properties.items():
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f'Non-finite source field {key}')
        result[key] = value
    return result


def select_members(archive, layer=None):
    members = {}
    for entry in archive.infolist():
        if entry.is_dir():
            continue
        name = PurePosixPath(entry.filename)
        if name.suffix.lower() not in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
            continue
        stem = str(name.with_suffix(''))
        group = members.setdefault(stem, {})
        ext = name.suffix.lower()
        if ext in group:
            raise ValueError('Duplicate shapefile component in ZIP')
        group[ext] = entry
    choices = [stem for stem, parts in members.items() if '.shp' in parts]
    if layer is not None:
        if layer not in choices:
            raise ValueError('--layer must match the full ZIP member stem, without .shp')
        selected = layer
    elif len(choices) == 1:
        selected = choices[0]
    else:
        raise ValueError(f'ZIP must have one SHP layer or use --layer; found {choices}')
    parts = members[selected]
    missing = {'.shp', '.shx', '.dbf', '.prj'} - parts.keys()
    if missing:
        raise ValueError(f'Missing required shapefile components: {sorted(missing)}; PRJ is mandatory')
    if sum(entry.file_size for entry in parts.values()) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError('Selected shapefile exceeds the 4 GiB extraction limit')
    return selected, parts


def read_encoding(parts, directory, override):
    if override:
        return override
    if '.cpg' in parts:
        value = (directory / 'source.cpg').read_text(encoding='utf-8-sig').strip()
        aliases = {'949': 'cp949', '51949': 'cp949', '65001': 'utf-8', 'UTF8': 'utf-8'}
        return aliases.get(value.upper(), value)
    return 'cp949'


def current_identity(database):
    if not database.exists():
        return None
    stat = database.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def preserve_source(source, destination, expected_hash):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if digest_file(destination) != expected_hash:
            raise ValueError('Retained source archive checksum mismatch')
        return
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.zip.tmp', delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copyfile(source, temporary)
        if digest_file(temporary) != expected_hash:
            raise ValueError('Source archive changed while copying')
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def create_schema(db):
    # Physical schema shared with server/buildings.py and build_buildings.py.
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
        CREATE INDEX buildings_parent ON buildings(parent_id);
    ''')


def import_database(source, database, source_date, layer=None, encoding=None):
    source, database = Path(source).resolve(), Path(database).resolve()
    # The date comes from the actual selected download row, never the file's
    # modification time or this script's research date.
    if date.fromisoformat(source_date).isoformat() != source_date:
        raise ValueError('--source-date must use YYYY-MM-DD')
    source_hash = digest_file(source)
    config_hash = hashlib.sha256(encode({
        'source_hash': source_hash, 'source_date': source_date,
        'layer': layer, 'encoding': encoding, 'importer_version': IMPORTER_VERSION,
    }).encode()).hexdigest()
    original_identity = current_identity(database)
    if database.is_file():
        try:
            with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
                old_meta = {key: json.loads(value) for key, value in db.execute('SELECT key,value FROM metadata')}
            if old_meta.get('official_import_config_hash') == config_hash:
                retained = database.parent / 'sources' / f'official-seoul-{source_hash}.zip'
                preserve_source(source, retained, source_hash)
                return {**old_meta, 'reused': True, 'database_bytes': database.stat().st_size}
        except sqlite3.DatabaseError:
            pass
    database.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=database.stem + '-official-', suffix='.sqlite.tmp',
                                     dir=database.parent, delete=False) as stream:
        temporary = Path(stream.name)
    retained = database.parent / 'sources' / f'official-seoul-{source_hash}.zip'
    started = time.monotonic()
    counts, districts, height_raw = Counter(), set(), Counter()
    bounds = [math.inf, math.inf, -math.inf, -math.inf]
    try:
        with ZipFile(source) as archive, tempfile.TemporaryDirectory(prefix='official-seoul-') as directory_name:
            selected, parts = select_members(archive, layer)
            directory = Path(directory_name)
            for ext, entry in parts.items():
                # Never extract archive paths: even traversal-like member names
                # are read into known, flat temporary filenames.
                with archive.open(entry) as incoming, (directory / ('source' + ext)).open('wb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
            prj_bytes = (directory / 'source.prj').read_bytes()
            try:
                prj_text = prj_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                prj_text = prj_bytes.decode('cp949')
            source_crs = CRS.from_wkt(prj_text)
            if not (source_crs.is_projected or source_crs.is_geographic):
                raise ValueError('PRJ must describe a geographic or projected horizontal CRS')
            to_wgs = Transformer.from_crs(source_crs, 4326, always_xy=True)
            to_area = Transformer.from_crs(4326, 5186, always_xy=True)
            resolved_encoding = read_encoding(parts, directory, encoding)
            with shapefile.Reader(shp=str(directory / 'source.shp'), shx=str(directory / 'source.shx'),
                                  dbf=str(directory / 'source.dbf'), encoding=resolved_encoding) as reader, sqlite3.connect(temporary) as db:
                field_names = [field[0] for field in reader.fields[1:]]
                if 'A29' in field_names or 'A30' in field_names:
                    raise ValueError('CH_D010 change/delta data is unsupported; download the full AL_D010 dataset')
                if not FIELDS.issubset(field_names):
                    raise ValueError(f'Not the verified AL_D010 A0–A28 schema; missing {sorted(FIELDS-set(field_names))}')
                if reader.shapeType not in (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM):
                    raise ValueError('Source layer must contain building polygons')
                create_schema(db)
                for record_number, item in enumerate(reader.iterShapeRecords(), 1):
                    props = clean_properties(item.record.as_dict())
                    # Keep identifier values exact in browser JSON as well as in
                    # the database key; JS cannot represent a 28-digit integer.
                    for key in ('A0', 'A1', 'A2', 'A3', 'A19', 'A21', 'A23'):
                        if props.get(key) not in (None, ''):
                            props[key] = text_id(props[key], key)
                    gis_id = text_id(props['A1'], 'A1 GIS ID')
                    shape_id = text_id(props['A0'], 'A0 shape ID')
                    district = text_id(props['A3'], 'A3 legal district')
                    if len(district) != 10 or not district.isdigit() or not district.startswith('11'):
                        raise ValueError(f'Record {record_number} is not a Seoul legal district')
                    district = district[:5]
                    footprint = shape(item.shape.__geo_interface__)
                    if footprint.is_empty or not footprint.is_valid or footprint.geom_type not in ('Polygon', 'MultiPolygon'):
                        raise ValueError(f'Invalid source polygon at record {record_number}; original DB retained')
                    wgs = transform(to_wgs.transform, footprint)
                    minx, miny, maxx, maxy = wgs.bounds
                    # A broad Seoul sanity envelope catches wrong/mislabeled CRS.
                    # It is not a replacement for the official administrative boundary.
                    if not 126 <= minx < maxx <= 128 or not 37 <= miny < maxy <= 38 or not wgs.is_valid:
                        raise ValueError(f'Projected geometry is outside Seoul sanity bounds at record {record_number}')
                    area = transform(to_area.transform, wgs).area
                    if not math.isfinite(area) or area <= 0:
                        raise ValueError(f'Invalid footprint area at record {record_number}')
                    height = positive_number(props['A16'], 'A16 height')
                    floors = positive_number(props['A26'], 'A26 floors', integer=True)
                    code = use_code(props['A8'])
                    name = ' '.join(str(props[key]).strip() for key in ('A24', 'A25') if props.get(key) not in (None, '')) or None
                    if name and any(ord(c) < 32 for c in name):
                        raise ValueError(f'Control character in building name at record {record_number}')
                    identifier = f'official:{gis_id}:{shape_id}'
                    props.update({
                        '_official': {'table': 'AL_D010', 'record_number': record_number,
                                      'source_use_code': code, 'source_crs': source_crs.to_string(),
                                      'height_status': 'official_record' if height is not None else 'missing',
                                      'source_height_verified': False},
                        'sources': [
                            {'property': '/geometry', 'dataset': GEOMETRY_SOURCE},
                            *([{'property': '/height', 'dataset': HEIGHT_SOURCE}] if height is not None else []),
                        ],
                    })
                    row = (identifier, name, height, None, floors, area, int(code == '02001'),
                           'building', None, 0, int(height is not None), GEOMETRY_SOURCE,
                           HEIGHT_SOURCE if height is not None else None, district,
                           encode(mapping(wgs)), zlib.compress(encode(props).encode('utf-8')))
                    cursor = db.execute('''INSERT INTO buildings(id,name,height_m,min_height_m,num_floors,footprint_area_m2,
                        is_apartment,kind,parent_id,has_parts,extrude,geometry_source,height_source,district_id,geometry,source_properties)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', row)
                    db.execute('INSERT INTO building_index VALUES(?,?,?,?,?)', (cursor.lastrowid, minx, maxx, miny, maxy))
                    counts['count'] += 1
                    counts['reported' if height is not None else 'missing'] += 1
                    counts['apartments'] += int(code == '02001')
                    raw = props['A16']
                    height_raw['positive' if height is not None else 'empty' if raw is None or str(raw).strip() == '' else 'nonpositive'] += 1
                    districts.add(district)
                    bounds = [min(bounds[0], minx), min(bounds[1], miny), max(bounds[2], maxx), max(bounds[3], maxy)]
                if not counts['count']:
                    raise ValueError('Source contains no usable building records')
                if counts['count'] != reader.numRecords:
                    raise ValueError('Source has deleted/mismatched records; investigate before importing')
                metadata = {
                    'schema_version': SCHEMA_VERSION, 'official_importer_version': IMPORTER_VERSION,
                    'source_kind': 'official_gis_buildings', 'source_properties_encoding': 'zlib-json-utf8',
                    'official_import_config_hash': config_hash, 'source_hash': source_hash,
                    'source_release': source_date, 'source_urls': [SOURCE_URL, 'https://www.data.go.kr/data/15083092/fileData.do'],
                    'source_format': 'official_AL_D010_SHP', 'source_archive_name': source.name,
                    'retained_source': str(retained.relative_to(database.parent)), 'source_layer': selected,
                    'source_crs': source_crs.to_string(), 'source_prj': prj_text, 'source_encoding': resolved_encoding,
                    'license': 'VWorld display: CC BY; data.go.kr: unrestricted; linked CCL target conflicts (BY-NC-ND), unresolved',
                    'attribution': '국토교통부 · 원천 지방자치단체 · VWorld GIS건물통합정보',
                    'scope': 'Rows in the downloaded Seoul archive; legal-district prefix 11 validated; no completeness guarantee',
                    'bounds': bounds, 'district_count': len(districts), 'counts': dict(counts),
                    'total_count': counts['count'], 'reported_count': counts['reported'],
                    'missing_count': counts['missing'], 'apartment_count': counts['apartments'],
                    'by_kind': {'building': dict(counts), 'building_part': {'count': 0, 'reported': 0, 'missing': 0, 'apartments': 0}},
                    'geometry_sources': {GEOMETRY_SOURCE: counts['count']},
                    'height_sources': {HEIGHT_SOURCE: counts['reported']}, 'raw_height_counts': dict(height_raw),
                    'source_height_verified': False, 'suppressed_parent_extrusions': 0,
                    'height_policy': 'Positive A16 building-register height or null; 0/negative/empty are missing. Not independently surveyed. No floor multiplier.',
                    'parts_policy': 'AL_D010 source footprints only; no inferred building parts or roof shape.',
                    'apartment_policy': 'Normalized source A8 == 02001 only; 02000 is broader communal housing.',
                    'area_crs': 'EPSG:5186', 'area_policy': 'Computed footprint area excluding holes; original registered A12 remains in source_properties.',
                    'geometry_policy': 'Source polygon topology retained and transformed using its PRJ; no repair, simplification, or viewport clipping.',
                    'created_at': datetime.now(timezone.utc).isoformat(), 'build_seconds': round(time.monotonic() - started, 2),
                }
                db.executemany('INSERT INTO metadata VALUES(?,?)', [(key, encode(value)) for key, value in metadata.items()])
                if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('SQLite integrity check failed')
                db.commit()
        preserve_source(source, retained, source_hash)
        if digest_file(source) != source_hash:
            raise ValueError('Source archive changed during import')
        if current_identity(database) != original_identity:
            raise ValueError('Target database changed during import; refusing to replace another build')
        backup_path = None
        if database.is_file():
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup_path = database.with_name(f'{database.stem}.previous-{stamp}.sqlite')
            with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as previous, sqlite3.connect(backup_path) as backup:
                previous.backup(backup)
                if backup.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('Previous database backup integrity check failed')
        if current_identity(database) != original_identity:
            raise ValueError('Target database changed during backup; refusing replacement')
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, database)
        return {**metadata, 'reused': False, 'database_bytes': database.stat().st_size,
                'previous_database_backup': str(backup_path) if backup_path else None}
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Locally downloaded Seoul full AL_D010 ZIP')
    parser.add_argument('--source-date', required=True, help='YYYY-MM-DD reference date shown for this download')
    parser.add_argument('--database', type=Path, default=ROOT / 'data' / 'buildings.sqlite')
    parser.add_argument('--layer', help='ZIP member stem if the ZIP contains multiple SHP layers')
    parser.add_argument('--encoding', help='DBF encoding override; defaults to CPG, otherwise cp949')
    args = parser.parse_args()
    try:
        result = import_database(args.source, args.database, args.source_date, args.layer, args.encoding)
    except (ValueError, OSError, sqlite3.Error, BadZipFile, shapefile.ShapefileException, CRSError, LookupError) as error:
        parser.exit(1, f'Import failed: {error}\n')
    print(encode({key: result.get(key) for key in (
        'reused', 'total_count', 'reported_count', 'missing_count', 'apartment_count',
        'source_height_verified', 'retained_source', 'previous_database_backup',
    )}))
    print('Restart the local API to use the replaced building database.', flush=True)


if __name__ == '__main__':
    main()
