#!/usr/bin/env python3
"""Load the preserved apartment-related public sources into one local SQLite database.

Reads only data/sources/<slug>-<date>/ folders written by fetch_apartment_sources.py. Every
file is checked against the manifest SHA-256 before it is parsed; every row of every source is
kept losslessly (typed TEXT columns + raw_json) and derived link tables are built ONLY from
identical official identifiers (K-apt code, PNU, 한국부동산원 단지고유번호). No network, no
fuzzy name matching, no invented coordinates, no floors-to-metres conversion.
"""
from __future__ import annotations

import argparse
import codecs
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import io
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import struct
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

from pyproj import Geod, Transformer
from shapely.geometry import LinearRing, Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
KAPT_CRS = 'EPSG:5174'   # K-apt map script proj4 == Korean 1985 / Modified Central Belt
SEOUL_SHEET_HEADER = ['번호', '유형', '아파트명', '지역', '세대수', '준공(예정)일', '비고']
JUSO_BUILD_COLUMNS = ['법정동코드', '시도명', '시군구명', '법정읍면동명', '법정리명', '산여부', '지번본번', '지번부번',
    '도로명코드', '도로명', '지하여부', '건물본번', '건물부번', '건축물대장건물명', '상세건물명', '건물관리번호',
    '읍면동일련번호', '행정동코드', '행정동명', '우편번호', '우편일련번호', '다량배달처명', '이동사유코드', '고시일자',
    '변동전도로명주소', '시군구용건물명', '공동주택여부', '기초구역번호', '상세주소여부', '비고1', '비고2']
RESERVED_COLUMNS = {'row_number', 'raw_json', 'seoul_flag', 'seoul_by_complex_id', 'seoul_by_address',
                    'page_number', 'detail_id', 'geometry_geojson', 'min_lon', 'min_lat', 'max_lon', 'max_lat',
                    'ring_count', 'hole_count', 'geometry_status'}

# ---------------------------------------------------------------------------------------------
# Source registry. kind decides the parser; seoul decides the flag/filter; keep decides whether
# non-Seoul rows are stored ('all' -> stored with seoul_flag, 'seoul' -> only Seoul rows stored).
# ---------------------------------------------------------------------------------------------
def csv_source(seoul=None, keep='all', restricted=False, file=r'\.csv$', **extra):
    return {'kind': 'csv', 'file': file, 'seoul': seoul, 'keep': keep, 'license_restricted': restricted, **extra}


SOURCES = {
    'kapt-seoul-complex-poi': {'kind': 'json_list', 'file': r'kapt-poi-seoul\.json$', 'seoul': None, 'keep': 'all'},
    'kapt-seoul-complex-list': {'kind': 'json_list', 'file': r'kapt-list-seoul\.json$', 'seoul': None, 'keep': 'all'},
    'kapt-basic-info-weekly': {'kind': 'xlsx', 'file': r'\.xlsx$', 'header_row': 2,
                               'seoul': {'column': '시도', 'startswith': '서울'}, 'keep': 'seoul'},
    'reb-complex-identifier-basic': csv_source(seoul={'column': '단지고유번호', 'startswith': '11',
                                                      'address_column': '주소', 'address_startswith': '서울특별시'}),
    'reb-complex-identifier-dong': csv_source(seoul={'column': '단지고유번호', 'startswith': '11'}),
    'reb-complex-name-history': csv_source(seoul={'column': '단지고유번호', 'startswith': '11'}),
    'seoul-register-summary-oa-22423': csv_source(file=r'^sheet\.csv$'),
    'seoul-housing-permit-dong-oa-22414': csv_source(file=r'^sheet\.csv$'),
    'seoul-apartment-mgmt-fee-oa-15822': csv_source(file=r'^sheet\.csv$'),
    'seoul-apartment-misc-income-oa-15819': csv_source(file=r'^sheet\.csv$'),
    'seoul-apartment-finance-report-oa-15820': csv_source(file=r'^sheet\.csv$'),
    'seoul-apartment-operations-report-oa-15821': csv_source(file=r'^sheet\.csv$'),
    'seoul-realestate-sales-oa-21275': csv_source(file=r'^sheet\.csv$', count_column='건물용도', count_value='아파트'),
    'seoul-rent-transactions-2025-oa-21276': {'kind': 'zip_csv', 'file': r'\.zip$', 'member': r'\.csv$',
                                              'seoul': None, 'keep': 'all', 'max_rows_to_load': 3_000_000,
                                              'count_column': '건물용도', 'count_value': '아파트'},
    'molit-apartment-price-2025': {'kind': 'zip_csv', 'file': r'\.zip$', 'member': r'^국토교통부_주택 공시가격 정보\(2025\)\.csv$',
                                   'seoul': {'column': '시도', 'startswith': '서울', 'cross_column': '법정동코드', 'cross_startswith': '11'},
                                   'keep': 'seoul'},
    'sh-housing-management-oa-12027': csv_source(file=r'^sheet\.csv$'),
    'lh-apartment-complexes': csv_source(seoul={'column': '주소', 'startswith': '서울'}),
    'lh-rental-complexes-built': csv_source(seoul={'column': '주소', 'startswith': '서울'}),
    'lh-rental-complexes-purchased': csv_source(seoul={'column': '주소', 'startswith': '서울'}),
    'hug-seoul-sale-apartments': csv_source(),
    'hug-seoul-sale-apartments-detail': csv_source(),
    'reb-new-apartments-2022': csv_source(seoul={'column': '시군구코드', 'startswith': '11'}),
    'gangbuk-apartments-oa-11614': csv_source(file=r'^sheet\.csv$'),
    'gangseo-apartments-oa-21838': {'kind': 'xlsx', 'file': r'\.xlsx$', 'header_row': 2, 'seoul': None, 'keep': 'all'},
    'yangcheon-apartments-oa-22047': csv_source(),
    'seodaemun-apartments': csv_source(coordinate_note='좌표(X)/좌표(Y) 열의 좌표계가 원본에 명시되지 않아 원문 그대로 보존하며 변환하지 않는다.'),
    'gangseo-apartments': csv_source(),
    'jungnang-apartments': csv_source(),
    'yangcheon-apartments': csv_source(),
    'dongjak-apartments': csv_source(),
    'seocho-apartments': csv_source(),
    'seongdong-apartments': csv_source(),
    'gwangjin-apartments': csv_source(),
    'geumcheon-apartments': csv_source(),
    'gangnam-apartment-parking': csv_source(),
    'seongbuk-apartment-parking': csv_source(),
    'gwanak-apartment-parking': csv_source(),
    'yangcheon-apartment-parking': csv_source(),
    'upis-renewal-project-zones-uq120': {'kind': 'esri_json', 'file': r'^features\.esri\.json$', 'seoul': None, 'keep': 'all'},
    'upis-renewal-districts-uq181': {'kind': 'esri_json', 'file': r'^features\.esri\.json$', 'seoul': None, 'keep': 'all'},
    'cleanup-seoul-project-list': {'kind': 'xls_biff', 'file': r'\.xls$', 'seoul': None, 'keep': 'all'},
    'seoul-redevelopment-stats-oa-22856': csv_source(file=r'^sheet\.csv$'),
    'seoul-urban-renewal-status-oa-20281': csv_source(file=r'^sheet\.csv$', restricted=True),
    'seoul-renewal-promotion-oa-20286': csv_source(file=r'^sheet\.csv$', restricted=True),
    'juso-building-db-202608': {'kind': 'zip_pipe', 'file': r'\.zip$', 'member': r'^build_seoul\.txt$',
                                'columns': JUSO_BUILD_COLUMNS, 'count_member': r'자료건수.*\.txt$',
                                'count_pattern': r'서울\(build_seoul\.txt\)\s*:\s*([\d,]+)',
                                'seoul': {'column': '시도명', 'startswith': '서울특별시'}, 'keep': 'all'},
    'hub-energy-gas-202605': {'kind': 'zip_pipe', 'file': r'\.zip$', 'member': r'\.txt$', 'columns': None,
                              'seoul': {'position': 5, 'equals': '서울특별시', 'cross_position': 3, 'cross_startswith': '11'},
                              'keep': 'seoul'},
    'hub-energy-electric-202605': {'kind': 'zip_pipe', 'file': r'\.zip$', 'member': r'\.txt$', 'columns': None,
                                   'seoul': {'position': 5, 'equals': '서울특별시', 'cross_position': 3, 'cross_startswith': '11'},
                                   'keep': 'seoul'},
    'sh-rental-complex-list': {'kind': 'html_pages', 'file': r'^page-\d{3}\.html$', 'seoul': None, 'keep': 'all'},
}
for _slug, _spec in SOURCES.items():
    _spec.setdefault('license_restricted', False)


# ---------------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------------
def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def table_name(slug):
    name = slug.replace('-', '_')
    if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
        raise ValueError('slug does not form a safe table name: ' + slug)
    return name


def quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def sanitize_columns(headers):
    """Original header -> safe identifier. Keeps Korean letters; guarantees uniqueness and a mapping."""
    result = []
    seen = set()
    for index, original in enumerate(headers):
        text = unicodedata.normalize('NFKC', original or '').strip()
        name = re.sub(r'[^0-9A-Za-z가-힣_]+', '_', text).strip('_').lower()
        name = re.sub(r'_+', '_', name)
        if not name:
            name = f'col_{index + 1}'
        if name[0].isdigit():
            name = 'c_' + name
        if name in RESERVED_COLUMNS:
            name += '_src'
        base, counter = name, 2
        while name in seen:
            name = f'{base}_{counter}'
            counter += 1
        seen.add(name)
        result.append(name)
    return result


def text_value(value):
    """Lossless TEXT rendering of a JSON/XLSX scalar; raw_json keeps the original type."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return str(value)


def decode_strict(raw, preferred=None):
    candidates = [preferred] if preferred else []
    candidates += [e for e in ('utf-8-sig', 'cp949') if e not in candidates]
    for encoding in candidates:
        try:
            return raw.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError('file decodes strictly with none of ' + ', '.join(candidates))


def sniff_encoding(binary_stream_factory, preferred=None, probe_bytes=4 * 1024 * 1024):
    """Strict-decode a probe from the start of a stream (used for members of large zips).

    An incremental decoder tolerates only a multibyte sequence cut at the probe end; any real
    invalid byte still fails, and the full stream is decoded strictly again while loading.
    """
    with binary_stream_factory() as stream:
        probe = stream.read(probe_bytes)
    candidates = [preferred] if preferred else []
    candidates += [e for e in ('utf-8-sig', 'cp949') if e not in candidates]
    for encoding in candidates:
        try:
            codecs.getincrementaldecoder(encoding)().decode(probe, final=False)
            return encoding
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError('stream probe decodes strictly with none of ' + ', '.join(candidates))


def seoul_test(rule, headers):
    """Return (predicate(row_list) -> bool, cross_predicate or None, description)."""
    if rule is None:
        return None, None, 'source is Seoul-only; no filter applied'
    if 'position' in rule:
        index = rule['position'] - 1
        cross_index = rule.get('cross_position', 0) - 1 if 'cross_position' in rule else None
        description = f"column position {rule['position']} == {rule['equals']!r}"
    else:
        if rule['column'] not in headers:
            raise ValueError(f"Seoul filter column {rule['column']!r} missing from header {headers}")
        index = headers.index(rule['column'])
        cross_index = headers.index(rule['cross_column']) if rule.get('cross_column') in headers else None
        description = f"column {rule['column']!r} startswith {rule['startswith']!r}"
    if 'equals' in rule:
        predicate = lambda row: row[index].strip() == rule['equals']
    else:
        prefix = rule['startswith']
        predicate = lambda row: row[index].strip().startswith(prefix)
    cross = None
    if cross_index is not None:
        cross_prefix = rule['cross_startswith']
        cross = lambda row: row[cross_index].strip().startswith(cross_prefix)
        description += f"; cross-check column {rule.get('cross_column', rule.get('cross_position'))!r} startswith {cross_prefix!r}"
    return predicate, cross, description


# ---------------------------------------------------------------------------------------------
# Table writer shared by all parsers
# ---------------------------------------------------------------------------------------------
class TableWriter:
    def __init__(self, db, table, headers, extra_columns=(), limit_rows=None):
        self.db = db
        self.table = table
        self.headers = list(headers)
        self.columns = sanitize_columns(self.headers)
        self.extra = list(extra_columns)
        self.limit = limit_rows
        self.count = 0
        self.batch = []
        db.execute(f'DROP TABLE IF EXISTS {quote(table)}')
        definitions = ['row_number INTEGER NOT NULL'] + [f'{quote(c)} TEXT' for c in self.columns] \
            + [f'{quote(name)} {kind}' for name, kind in self.extra] + ['raw_json TEXT NOT NULL']
        db.execute(f'CREATE TABLE {quote(table)}({", ".join(definitions)})')
        db.execute('DELETE FROM columns WHERE table_name=?', (table,))
        db.executemany('INSERT INTO columns VALUES(?,?,?,?)',
                       ((table, i + 1, original, column) for i, (original, column) in enumerate(zip(self.headers, self.columns))))
        self.sql = f'INSERT INTO {quote(table)} VALUES({",".join("?" for _ in range(2 + len(self.columns) + len(self.extra)))})'

    def full(self):
        return self.limit is not None and self.count >= self.limit

    def add(self, row_number, values, raw, extra=()):
        if len(values) != len(self.columns):
            raise ValueError(f'{self.table}: row {row_number} has {len(values)} values for {len(self.columns)} columns')
        self.batch.append((row_number, *values, *extra, json.dumps(raw, ensure_ascii=False)))
        self.count += 1
        if len(self.batch) >= 5000:
            self.flush()

    def flush(self):
        if self.batch:
            self.db.executemany(self.sql, self.batch)
            self.batch = []


# ---------------------------------------------------------------------------------------------
# Parsers. Each returns a dict of facts for the sources table.
# ---------------------------------------------------------------------------------------------
def load_delimited_rows(db, table, spec, headers, rows, *, limit_rows, raw_row_numbers=None, count_hint=None):
    """rows: iterable of lists (already split). Applies the Seoul rule and width validation."""
    predicate, cross, description = seoul_test(spec.get('seoul'), headers)
    keep_all = spec.get('keep', 'all') == 'all' or predicate is None
    extra = [('seoul_flag', 'INTEGER')] if predicate is not None and keep_all else []
    if spec.get('seoul') and 'address_column' in spec['seoul']:
        extra = [('seoul_by_complex_id', 'INTEGER'), ('seoul_by_address', 'INTEGER'), ('seoul_flag', 'INTEGER')]
        address_index = headers.index(spec['seoul']['address_column'])
        address_prefix = spec['seoul']['address_startswith']
    writer = TableWriter(db, table, headers, extra, limit_rows)
    unique_headers = len(set(headers)) == len(headers)
    file_rows = seoul_rows = cross_rows = cross_disagreements = 0
    counted = 0
    count_index = headers.index(spec['count_column']) if spec.get('count_column') in headers else None
    seoul_by_address = seoul_by_id = both = 0
    for index, row in enumerate(rows):
        file_rows += 1
        row_number = raw_row_numbers[index] if raw_row_numbers else index + 1
        if len(row) != len(headers):
            raise ValueError(f'{table}: row {row_number} has {len(row)} fields but the header has {len(headers)} (truncated or malformed file)')
        if count_index is not None and row[count_index].strip() == spec['count_value']:
            counted += 1
        is_seoul = predicate(row) if predicate else True
        if predicate:
            seoul_rows += is_seoul
            if cross:
                crossed = cross(row)
                cross_rows += crossed
                cross_disagreements += crossed != is_seoul
        raw = dict(zip(headers, row)) if unique_headers else {'header': headers, 'values': row}
        if extra and extra[0][0] == 'seoul_by_complex_id':
            by_address = row[address_index].strip().startswith(address_prefix)
            seoul_by_id += is_seoul
            seoul_by_address += by_address
            both += is_seoul and by_address
            extra_values = (int(is_seoul), int(by_address), int(is_seoul or by_address))
        elif extra:
            extra_values = (int(is_seoul),)
        else:
            extra_values = ()
        if (keep_all or is_seoul) and not writer.full():
            writer.add(row_number, row, raw, extra_values)
    writer.flush()
    facts = {'row_count_file': file_rows, 'row_count_loaded': writer.count,
             'seoul_row_count': seoul_rows if predicate else writer.count, 'seoul_rule': description,
             'columns': writer.columns, 'notes': {}}
    if cross:
        facts['notes']['seoul_cross_check'] = {'rows_matching_cross_rule': cross_rows,
                                               'rows_where_rules_disagree': cross_disagreements}
    if count_index is not None:
        facts['notes'][f"rows_where_{spec['count_column']}_is_{spec['count_value']}"] = counted
    if extra and extra[0][0] == 'seoul_by_complex_id':
        facts['notes']['seoul_by_complex_id_prefix_11'] = seoul_by_id
        facts['notes']['seoul_by_address_prefix'] = seoul_by_address
        facts['notes']['seoul_by_both'] = both
        facts['seoul_row_count'] = seoul_by_id + seoul_by_address - both
    if count_hint is not None:
        facts['count_hint'] = count_hint
    return facts


def parse_csv_source(db, table, spec, directory, filename, file_info, limit_rows):
    raw = (directory / filename).read_bytes()
    text, encoding = decode_strict(raw, file_info.get('encoding'))
    reader = csv.reader(io.StringIO(text, newline=''))
    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError(f'{filename}: empty CSV') from None
    if file_info.get('header') and headers[:len(file_info['header'])] != file_info['header']:
        raise ValueError(f'{filename}: header differs from the manifest header')
    facts = load_delimited_rows(db, table, spec, headers, reader, limit_rows=limit_rows)
    if limit_rows is None and file_info.get('row_count') is not None and facts['row_count_file'] != file_info['row_count']:
        raise ValueError(f"{filename}: parsed {facts['row_count_file']} rows but the manifest recorded {file_info['row_count']}")
    facts.update(encoding=encoding, header=headers, format='csv')
    return facts


def member_names(name):
    """A zip entry without the UTF-8 flag is decoded as cp437 by zipfile; offer the cp949 reading too."""
    names = [name]
    try:
        names.append(name.encode('cp437').decode('cp949'))
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return names


def zip_member(archive, pattern):
    names = [n for n in archive.namelist() if any(re.search(pattern, alias) for alias in member_names(n))]
    if len(names) != 1:
        raise ValueError(f'expected exactly one zip member matching {pattern!r}, found {names}')
    return names[0]


def parse_zip_csv_source(db, table, spec, directory, filename, file_info, limit_rows):
    with zipfile.ZipFile(directory / filename) as archive:
        member = zip_member(archive, spec['member'])
        member_bytes = archive.getinfo(member).file_size
        encoding = sniff_encoding(lambda: archive.open(member))
        with archive.open(member) as stream:
            reader = csv.reader(io.TextIOWrapper(stream, encoding=encoding, newline=''))
            headers = next(reader)
            facts = load_delimited_rows(db, table, spec, headers, reader, limit_rows=limit_rows)
    limit = spec.get('max_rows_to_load')
    if limit is not None and facts['row_count_file'] > limit:
        # Policy: over the limit only the count/header are recorded. Load happened already, so undo.
        db.execute(f'DELETE FROM {quote(table)}')
        facts['row_count_loaded'] = 0
        facts['notes']['not_loaded_reason'] = f'row count exceeds {limit}; header and count recorded only'
    facts.update(encoding=encoding, header=headers, format='zip/csv', member=member, member_bytes=member_bytes)
    return facts


def parse_zip_pipe_source(db, table, spec, directory, filename, file_info, limit_rows):
    with zipfile.ZipFile(directory / filename) as archive:
        member = zip_member(archive, spec['member'])
        member_bytes = archive.getinfo(member).file_size
        encoding = sniff_encoding(lambda: archive.open(member))
        independent = None
        if spec.get('count_member'):
            count_member = zip_member(archive, spec['count_member'])
            count_text, _ = decode_strict(archive.read(count_member))
            match = re.search(spec['count_pattern'], count_text)
            if not match:
                raise ValueError(f'{count_member}: count pattern {spec["count_pattern"]!r} not found')
            independent = int(match.group(1).replace(',', ''))

        def rows(stream):
            for line in io.TextIOWrapper(stream, encoding=encoding, newline=''):
                line = line.rstrip('\r\n')
                if line == '':
                    continue
                yield line.split('|')

        with archive.open(member) as stream:
            iterator = rows(stream)
            if spec.get('columns'):
                headers = list(spec['columns'])
                first = next(iterator)
                if len(first) != len(headers):
                    raise ValueError(f'{member}: first row has {len(first)} fields; the documented layout has {len(headers)}')
                iterator = itertools.chain([first], iterator)
                header_note = 'no header line in file; column names from the 도로명주소 건물DB layout, width verified on every row'
            else:
                first = next(iterator)
                headers = [f'col_{i + 1:02d}' for i in range(len(first))]
                iterator = itertools.chain([first], iterator)
                header_note = f'no header line in file; {len(first)} positional columns (semantics not documented in the download)'
            facts = load_delimited_rows(db, table, spec, headers, iterator, limit_rows=limit_rows)
    if independent is not None and limit_rows is None and facts['row_count_file'] != independent:
        raise ValueError(f'{member}: parsed {facts["row_count_file"]} rows but the archive count file says {independent}')
    facts.update(encoding=encoding, header=headers, format='zip/pipe-delimited txt', member=member,
                 member_bytes=member_bytes, independent_count=independent)
    facts['notes']['header'] = header_note
    return facts


def parse_json_list_source(db, table, spec, directory, filename, file_info, limit_rows):
    payload = json.loads((directory / filename).read_text(encoding='utf-8'))
    records = payload.get('resultList') if isinstance(payload, dict) else None
    if not isinstance(records, list) or not records:
        raise ValueError(f'{filename}: resultList missing or empty')
    headers = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f'{filename}: resultList entries must be objects')
        for key in record:
            if key not in headers:
                headers.append(key)
    writer = TableWriter(db, table, headers, (), limit_rows)
    for index, record in enumerate(records):
        if writer.full():
            break
        writer.add(index + 1, [text_value(record.get(key)) for key in headers], record)
    writer.flush()
    return {'row_count_file': len(records), 'row_count_loaded': writer.count, 'seoul_row_count': writer.count,
            'encoding': 'utf-8 (json)', 'header': headers, 'format': 'json resultList', 'columns': writer.columns,
            'seoul_rule': 'request was bjdCode=11 (Seoul); no filter applied', 'notes': {}}


def column_index(reference):
    letters = re.match(r'[A-Z]+', reference).group(0)
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - 64)
    return index - 1


def xlsx_rows(path):
    """Yield (excel_row_number, {col_index: text}) for the first worksheet, streaming."""
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    rel_ns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        sheets = workbook.find(ns + 'sheets').findall(ns + 'sheet')
        if not sheets:
            raise ValueError('workbook has no sheets')
        rel_id = sheets[0].get(rel_ns + 'id')
        rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        target = next(r.get('Target') for r in rels if r.get('Id') == rel_id)
        sheet_path = 'xl/' + target.lstrip('/').removeprefix('xl/')
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            sst = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            shared = [''.join(t.text or '' for t in si.iter(ns + 't')) for si in sst.findall(ns + 'si')]
        with archive.open(sheet_path) as stream:
            for _, element in ET.iterparse(stream, events=('end',)):
                if element.tag != ns + 'row':
                    continue
                cells = {}
                for cell in element.findall(ns + 'c'):
                    kind = cell.get('t')
                    if kind == 'inlineStr':
                        value = ''.join(t.text or '' for t in cell.iter(ns + 't'))
                    else:
                        node = cell.find(ns + 'v')
                        value = node.text if node is not None else None
                        if kind == 's' and value is not None:
                            value = shared[int(value)]
                    if value is not None:
                        cells[column_index(cell.get('r'))] = value
                yield int(element.get('r')), cells
                element.clear()


def parse_xlsx_source(db, table, spec, directory, filename, file_info, limit_rows):
    header_row = spec['header_row']
    preface = []
    headers = None
    writer = None
    file_rows = seoul_rows = 0
    predicate = None
    keep_all = spec.get('keep', 'all') == 'all'
    for row_number, cells in xlsx_rows(directory / filename):
        if headers is None:
            if row_number < header_row:
                preface.append({'row': row_number, 'cells': cells})
                continue
            if row_number != header_row:
                raise ValueError(f'{filename}: header row {header_row} is missing (found row {row_number})')
            width = max(cells) + 1 if cells else 0
            headers = [cells.get(i, '') for i in range(width)]
            if any(not h.strip() for h in headers):
                raise ValueError(f'{filename}: blank header cell in row {header_row}: {headers}')
            predicate, _, description = seoul_test(spec.get('seoul'), headers)
            extra = [('seoul_flag', 'INTEGER')] if predicate is not None and keep_all else []
            writer = TableWriter(db, table, headers, extra, limit_rows)
            continue
        if not cells:
            continue   # a row element with no stored cells carries no data
        if max(cells) >= len(headers):
            raise ValueError(f'{filename}: row {row_number} has a value beyond the header width')
        file_rows += 1
        values = [cells.get(i) for i in range(len(headers))]
        is_seoul = predicate([v or '' for v in values]) if predicate else True
        seoul_rows += is_seoul
        if (keep_all or is_seoul) and not writer.full():
            writer.add(row_number, values, dict(zip(headers, values)), (int(is_seoul),) if writer.extra else ())
    if writer is None:
        raise ValueError(f'{filename}: header row {header_row} not found')
    writer.flush()
    return {'row_count_file': file_rows, 'row_count_loaded': writer.count,
            'seoul_row_count': seoul_rows if predicate else writer.count, 'encoding': 'xlsx (OOXML)',
            'header': headers, 'format': 'xlsx', 'columns': writer.columns,
            'seoul_rule': description if predicate else 'source is Seoul-only; no filter applied',
            'notes': {'header_row': header_row, 'preface_rows': preface,
                      'value_note': 'cell values are the literal XML values; numeric/date cells stay as stored numbers (Excel serials are not converted)'}}


def esri_rings_to_geojson(rings):
    """Esri polygon rings -> GeoJSON. Clockwise rings are exteriors, counter-clockwise rings holes."""
    exteriors, holes, dropped = [], [], 0
    for ring in rings:
        coordinates = [tuple(point[:2]) for point in ring]
        if len(coordinates) < 4 or coordinates[0] != coordinates[-1]:
            if len(coordinates) >= 3 and coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])
            else:
                dropped += 1
                continue
        linear = LinearRing(coordinates)
        (holes if linear.is_ccw else exteriors).append(coordinates)
    if not exteriors and holes:   # no clockwise ring: treat every ring as an exterior (Esri fallback)
        exteriors, holes = holes, []
    polygons = [[exterior] for exterior in exteriors]
    unassigned = 0
    for hole in holes:
        probe = Polygon(hole).representative_point()
        parent = next((p for p in polygons if Polygon(p[0]).covers(probe)), None)
        if parent is None:
            polygons.append([hole])
            unassigned += 1
        else:
            parent.append(hole)
    if not polygons:
        return None, {'dropped_rings': dropped, 'unassigned_holes': unassigned}
    geometry = ({'type': 'Polygon', 'coordinates': polygons[0]} if len(polygons) == 1
                else {'type': 'MultiPolygon', 'coordinates': polygons})
    return geometry, {'dropped_rings': dropped, 'unassigned_holes': unassigned, 'hole_count': len(holes)}


def parse_esri_json_source(db, table, spec, directory, filename, file_info, limit_rows):
    payload = json.loads((directory / filename).read_text(encoding='utf-8'))
    features = payload.get('features')
    if not isinstance(features, list) or not features:
        raise ValueError(f'{filename}: features missing or empty')
    if payload.get('spatialReference', {}).get('wkid') != 4326:
        raise ValueError(f'{filename}: expected spatialReference wkid 4326, got {payload.get("spatialReference")}')
    headers = [f['name'] for f in payload.get('fields', []) if f.get('type') != 'esriFieldTypeGeometry']
    for feature in features:
        for key in feature.get('attributes', {}):
            if key not in headers:
                headers.append(key)
    extra = [('geometry_geojson', 'TEXT'), ('min_lon', 'REAL'), ('min_lat', 'REAL'), ('max_lon', 'REAL'),
             ('max_lat', 'REAL'), ('ring_count', 'INTEGER'), ('hole_count', 'INTEGER'), ('geometry_status', 'TEXT')]
    writer = TableWriter(db, table, headers, extra, limit_rows)
    status = Counter()
    for index, feature in enumerate(features):
        if writer.full():
            break
        attributes = feature.get('attributes', {})
        rings = (feature.get('geometry') or {}).get('rings')
        if rings:
            geometry, info = esri_rings_to_geojson(rings)
            flat = [pt for ring in rings for pt in ring]
            bbox = (min(p[0] for p in flat), min(p[1] for p in flat), max(p[0] for p in flat), max(p[1] for p in flat))
            state = 'polygon' if geometry and geometry['type'] == 'Polygon' else 'multipolygon' if geometry else 'invalid_rings'
            if info.get('dropped_rings') or info.get('unassigned_holes'):
                state += '_with_ring_anomalies'
            extra_values = (json.dumps(geometry) if geometry else None, *bbox, len(rings), info.get('hole_count', 0), state)
        else:
            extra_values = (None, None, None, None, None, 0, 0, 'no_geometry')
        status[extra_values[-1]] += 1
        writer.add(index + 1, [text_value(attributes.get(k)) for k in headers], feature, extra_values)
    writer.flush()
    return {'row_count_file': len(features), 'row_count_loaded': writer.count, 'seoul_row_count': writer.count,
            'encoding': 'utf-8 (esri json)', 'header': headers, 'format': 'esri json features', 'columns': writer.columns,
            'seoul_rule': 'Seoul service; no filter applied',
            'notes': {'geometry_crs': 'EPSG:4326 as returned by outSR=4326', 'geometry_status_counts': dict(status),
                      'date_note': 'esriFieldTypeDate values are epoch milliseconds kept as-is',
                      'native_spatial_reference': 'EPSG:5174 (wkid 102086) per layer.json'}}


class ListTableParser(HTMLParser):
    """Collect every <table> as rows of cell texts plus goDetail('id') references."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._table = None
        self._row = None
        self._cell = None
        self._detail = None
        self.total_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            self._table = []
        elif tag == 'tr' and self._table is not None:
            self._row = []
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = []
            self._detail = None
        elif tag == 'a' and self._cell is not None:
            match = re.search(r"goDetail\('([^']*)'\)", attrs.get('onclick') or '')
            if match:
                self._detail = match.group(1)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._cell is not None and self._row is not None:
            self._row.append((re.sub(r'\s+', ' ', ''.join(self._cell)).strip(), self._detail))
            self._cell = None
        elif tag == 'tr' and self._row is not None and self._table is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == 'table' and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_html_pages_source(db, table, spec, directory, filenames, files_info, limit_rows):
    headers = SEOUL_SHEET_HEADER
    writer = TableWriter(db, table, headers, [('page_number', 'INTEGER'), ('detail_id', 'TEXT')], limit_rows)
    totals = set()
    row_number = 0
    detail_ids = Counter()
    for filename in filenames:
        text = (directory / filename).read_text(encoding='utf-8')
        parser = ListTableParser()
        parser.feed(text)
        candidates = [t for t in parser.tables if t and [c[0] for c in t[0]] == headers]
        if len(candidates) != 1:
            raise ValueError(f'{filename}: expected exactly one list table with header {headers}')
        match = re.search(r'총\s*<strong[^>]*>\s*([\d,]+)\s*</strong>\s*건', text)
        if match:
            totals.add(int(match.group(1).replace(',', '')))
        page = int(re.search(r'(\d+)', filename).group(1))
        for cells in candidates[0][1:]:
            if len(cells) != len(headers):
                raise ValueError(f'{filename}: list row has {len(cells)} cells, expected {len(headers)}')
            row_number += 1
            values = [c[0] for c in cells]
            detail = cells[2][1]
            if detail:
                detail_ids[detail] += 1
            raw = dict(zip(headers, values)) | {'page': page, 'detail_id': detail, 'file': filename}
            if not writer.full():
                writer.add(row_number, values, raw, (page, detail))
    writer.flush()
    if len(totals) != 1:
        raise ValueError(f'list pages disagree on the total count: {sorted(totals)}')
    total = totals.pop()
    if limit_rows is None and total != row_number:
        raise ValueError(f'list pages contain {row_number} rows but the page total says {total}')
    return {'row_count_file': row_number, 'row_count_loaded': writer.count, 'seoul_row_count': writer.count,
            'encoding': 'utf-8 (html)', 'header': headers, 'format': 'html list pages', 'columns': writer.columns,
            'independent_count': total, 'seoul_rule': 'SH (Seoul) list; no filter applied',
            'notes': {'pages': len(filenames), 'detail_ids_unique': len(detail_ids),
                      'detail_ids_repeated': sum(1 for v in detail_ids.values() if v > 1),
                      'detail_id_note': "detail_id is the goDetail('id') argument of the complex link; detail pages were not collected"}}


# ---------------------------------------------------------------------------------------------
# Minimal OLE2 + BIFF8 reader (stdlib only). Strict: unknown cell records raise.
# ---------------------------------------------------------------------------------------------
def ole2_stream(data, name):
    if data[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        raise ValueError('not an OLE2 compound file')
    sector_size = 1 << struct.unpack_from('<H', data, 30)[0]
    mini_size = 1 << struct.unpack_from('<H', data, 32)[0]
    fat_count = struct.unpack_from('<I', data, 44)[0]
    dir_start = struct.unpack_from('<I', data, 48)[0]
    mini_cutoff = struct.unpack_from('<I', data, 56)[0]
    minifat_start = struct.unpack_from('<I', data, 60)[0]
    difat_start = struct.unpack_from('<I', data, 68)[0]
    per_sector = sector_size // 4

    def sector(index):
        start = 512 + index * sector_size
        return data[start:start + sector_size]

    difat = list(struct.unpack_from('<109I', data, 76))
    next_difat = difat_start
    while next_difat not in (0xFFFFFFFE, 0xFFFFFFFF):
        chunk = struct.unpack(f'<{per_sector}I', sector(next_difat))
        difat += chunk[:-1]
        next_difat = chunk[-1]
    fat = []
    for index in difat[:fat_count]:
        fat += struct.unpack(f'<{per_sector}I', sector(index))

    def chain(start, table):
        out, current, guard = [], start, 0
        while current not in (0xFFFFFFFE, 0xFFFFFFFF):
            if current >= len(table) or guard > len(table):
                raise ValueError('corrupt sector chain')
            out.append(current)
            current = table[current]
            guard += 1
        return out

    directory = b''.join(sector(s) for s in chain(dir_start, fat))
    entries = []
    for offset in range(0, len(directory), 128):
        entry = directory[offset:offset + 128]
        name_length = struct.unpack_from('<H', entry, 64)[0]
        entry_name = entry[:max(name_length - 2, 0)].decode('utf-16-le', errors='replace')
        entries.append((entry_name, entry[66], struct.unpack_from('<I', entry, 116)[0], struct.unpack_from('<I', entry, 120)[0]))
    root = entries[0]
    target = next((e for e in entries if e[0] == name and e[1] == 2), None)
    if target is None:
        raise ValueError(f'OLE2 stream {name!r} not found; entries: {[e[0] for e in entries]}')
    _, _, start, size = target
    if size < mini_cutoff:
        mini_fat = []
        for index in chain(minifat_start, fat):
            mini_fat += struct.unpack(f'<{per_sector}I', sector(index))
        mini_stream = b''.join(sector(s) for s in chain(root[2], fat))
        return b''.join(mini_stream[s * mini_size:(s + 1) * mini_size] for s in chain(start, mini_fat))[:size]
    return b''.join(sector(s) for s in chain(start, fat))[:size]


def biff_records(stream):
    position = 0
    while position + 4 <= len(stream):
        kind, length = struct.unpack_from('<HH', stream, position)
        yield kind, stream[position + 4:position + 4 + length]
        position += 4 + length


def biff_sst(record, continues):
    """Decode an SST record with its CONTINUE records into a list of strings."""
    chunks = [record] + list(continues)
    chunk, position = 0, 8
    total, unique = struct.unpack_from('<II', record, 0)

    def need(size, allow_flag=False):
        nonlocal chunk, position
        while position >= len(chunks[chunk]):
            chunk += 1
            position = 0
            if chunk >= len(chunks):
                raise ValueError('SST continues past the last CONTINUE record')
        if position + size > len(chunks[chunk]) and not allow_flag:
            raise ValueError('SST string header split across CONTINUE records is not supported')
        return None

    strings = []
    for _ in range(unique):
        need(3)
        count, flags = struct.unpack_from('<HB', chunks[chunk], position)
        position += 3
        runs = ext = 0
        if flags & 0x08:
            need(2)
            runs = struct.unpack_from('<H', chunks[chunk], position)[0]
            position += 2
        if flags & 0x04:
            need(4)
            ext = struct.unpack_from('<I', chunks[chunk], position)[0]
            position += 4
        wide = bool(flags & 0x01)
        text = ''
        remaining = count
        while remaining:
            if position >= len(chunks[chunk]):
                chunk += 1
                position = 0
                if chunk >= len(chunks):
                    raise ValueError('SST string data continues past the last CONTINUE record')
                wide = bool(chunks[chunk][position] & 0x01)
                position += 1
            available = len(chunks[chunk]) - position
            width = 2 if wide else 1
            take = min(remaining, available // width)
            if take == 0:
                raise ValueError('SST character split across a CONTINUE boundary')
            piece = chunks[chunk][position:position + take * width]
            text += piece.decode('utf-16-le') if wide else piece.decode('latin-1')
            position += take * width
            remaining -= take
        skip = runs * 4 + ext
        while skip:
            if position >= len(chunks[chunk]):
                chunk += 1
                position = 0
            step = min(skip, len(chunks[chunk]) - position)
            position += step
            skip -= step
        strings.append(text)
    if len(strings) != unique:
        raise ValueError('SST unique count mismatch')
    return strings, total


def rk_number(value):
    """MS-XLS RkNumber: bit0 = divide by 100, bit1 = signed integer (else 30-bit float mantissa)."""
    if value & 0x02:
        number = float(struct.unpack('<i', struct.pack('<I', value & 0xFFFFFFFF))[0] >> 2)
    else:
        number = struct.unpack('<d', struct.pack('<Q', (value & 0xFFFFFFFC) << 32))[0]
    return number / 100 if value & 0x01 else number


def number_text(number):
    return str(int(number)) if math.isfinite(number) and number.is_integer() and abs(number) < 1e15 else repr(number)


def biff_cells(workbook_stream):
    """Return (sheet_name, {row: {col: text}}, facts) for the first worksheet of a BIFF8 stream."""
    records = list(biff_records(workbook_stream))
    if not records or records[0][0] != 0x809 or struct.unpack_from('<H', records[0][1], 0)[0] != 0x0600:
        raise ValueError('not a BIFF8 workbook stream')
    codepage = None
    sst = []
    sheets = []
    for index, (kind, body) in enumerate(records):
        if kind == 0x42:
            codepage = struct.unpack_from('<H', body, 0)[0]
        elif kind == 0x85:
            offset = struct.unpack_from('<I', body, 0)[0]
            name_length, flags = body[6], body[7]
            name = body[8:8 + name_length * (2 if flags & 1 else 1)].decode('utf-16-le' if flags & 1 else 'cp949')
            sheets.append((offset, name))
        elif kind == 0xFC:
            continues = []
            for next_kind, next_body in records[index + 1:]:
                if next_kind != 0x3C:
                    break
                continues.append(next_body)
            sst, _ = biff_sst(body, continues)
        elif kind == 0x0A:
            break
    if not sheets:
        raise ValueError('BIFF workbook has no BOUNDSHEET record')
    offset, sheet_name = sheets[0]
    cells = defaultdict(dict)
    kinds = Counter()
    for kind, body in biff_records(workbook_stream[offset:]):
        kinds[kind] += 1
        if kind == 0x0A:
            break
        if kind == 0xFD:        # LABELSST
            row, col, _, index = struct.unpack_from('<HHHI', body, 0)
            cells[row][col] = sst[index]
        elif kind == 0x203:     # NUMBER
            row, col, _, number = struct.unpack_from('<HHHd', body, 0)
            cells[row][col] = number_text(number)
        elif kind == 0x27E:     # RK
            row, col, _, value = struct.unpack_from('<HHHI', body, 0)
            cells[row][col] = number_text(rk_number(value))
        elif kind == 0xBD:      # MULRK
            row, first = struct.unpack_from('<HH', body, 0)
            for i in range((len(body) - 6) // 6):
                value = struct.unpack_from('<I', body, 4 + i * 6 + 2)[0]
                cells[row][first + i] = number_text(rk_number(value))
        elif kind == 0x204:     # LABEL (BIFF8 unicode string)
            row, col, _, count, flags = struct.unpack_from('<HHHHB', body, 0)
            data = body[9:9 + count * (2 if flags & 1 else 1)]
            cells[row][col] = data.decode('utf-16-le') if flags & 1 else data.decode('latin-1')
        elif kind == 0x205:     # BOOLERR
            row, col, _, value, is_error = struct.unpack_from('<HHHBB', body, 0)
            cells[row][col] = ('#ERR' + str(value)) if is_error else ('TRUE' if value else 'FALSE')
        elif kind in (0x06, 0x207):
            raise ValueError('BIFF FORMULA cells are not supported by this minimal reader')
        # ROW, BLANK, MULBLANK, DIMENSIONS, XF/format records carry no cell text.
    return sheet_name, cells, {'codepage': codepage, 'sst_strings': len(sst), 'sheet_record_kinds': {hex(k): v for k, v in kinds.items()}}


def parse_xls_biff_source(db, table, spec, directory, filename, file_info, limit_rows):
    data = (directory / filename).read_bytes()
    sheet_name, cells, biff_facts = biff_cells(ole2_stream(data, 'Workbook'))
    if not cells:
        raise ValueError(f'{filename}: worksheet has no cells')
    rows_sorted = sorted(cells)
    header_row = rows_sorted[0]
    width = max(cells[header_row]) + 1
    headers = [cells[header_row].get(i, '') for i in range(width)]
    if any(not h.strip() for h in headers):
        raise ValueError(f'{filename}: blank header cell in first row: {headers}')
    writer = TableWriter(db, table, headers, (), limit_rows)
    file_rows = 0
    for row in rows_sorted[1:]:
        if max(cells[row]) >= width:
            raise ValueError(f'{filename}: row {row + 1} has a value beyond the header width')
        file_rows += 1
        values = [cells[row].get(i) for i in range(width)]
        if not writer.full():
            writer.add(row + 1, values, dict(zip(headers, values)))
    writer.flush()
    return {'row_count_file': file_rows, 'row_count_loaded': writer.count, 'seoul_row_count': writer.count,
            'encoding': 'xls (BIFF8, minimal stdlib reader)', 'header': headers, 'format': 'xls', 'columns': writer.columns,
            'seoul_rule': 'Seoul 정비사업 list; no filter applied',
            'notes': {'sheet_name': sheet_name, 'header_row_excel': header_row + 1, **biff_facts,
                      'value_note': 'numeric cells are rendered as integers when integral, otherwise repr(float); cell formats are not applied'}}


PARSERS = {'csv': parse_csv_source, 'zip_csv': parse_zip_csv_source, 'zip_pipe': parse_zip_pipe_source,
           'json_list': parse_json_list_source, 'xlsx': parse_xlsx_source, 'esri_json': parse_esri_json_source,
           'xls_biff': parse_xls_biff_source}


# ---------------------------------------------------------------------------------------------
# Source discovery and per-source import
# ---------------------------------------------------------------------------------------------
def find_source_directory(sources_dir, slug):
    matches = []
    for path in Path(sources_dir).iterdir():
        if path.is_dir() and re.fullmatch(re.escape(slug) + r'-\d{4}-\d{2}-\d{2}', path.name) and (path / 'manifest.json').is_file():
            manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
            if manifest.get('slug') == slug:
                matches.append((path.name[-10:], path, manifest))
    if not matches:
        raise FileNotFoundError(f'no source directory for {slug} under {sources_dir}')
    matches.sort()
    return matches[-1][1], matches[-1][2]


def verify_file(directory, filename, info):
    path = directory / filename
    if not path.is_file():
        raise FileNotFoundError(f'{path} listed in manifest but missing')
    size = path.stat().st_size
    if info.get('bytes') is not None and size != info['bytes']:
        raise ValueError(f'{path}: size {size} differs from manifest {info["bytes"]}')
    digest = sha256_file(path)
    if info.get('sha256') and digest != info['sha256']:
        raise ValueError(f'{path}: SHA-256 differs from manifest (file changed since acquisition)')
    return size, digest


def import_source(db, slug, spec, sources_dir, limit_rows):
    directory, manifest = find_source_directory(sources_dir, slug)
    table = table_name(slug)
    files = manifest.get('files') or {}
    selected = [name for name in files if re.search(spec['file'], name)]
    if spec['kind'] == 'html_pages':
        if not selected:
            raise ValueError(f'{slug}: no files match {spec["file"]!r}')
        selected.sort()
        total_bytes = 0
        verified = []
        for name in selected:
            size, digest = verify_file(directory, name, files[name])
            total_bytes += size
            verified.append({'file': name, 'bytes': size, 'sha256': digest})
        facts = parse_html_pages_source(db, table, spec, directory, selected, files, limit_rows)
        facts['notes']['files'] = verified
        filename, size, digest = f'{selected[0]}..{selected[-1]} ({len(selected)} files)', total_bytes, None
    else:
        if len(selected) != 1:
            raise ValueError(f'{slug}: expected exactly one data file matching {spec["file"]!r}, found {selected}')
        filename = selected[0]
        size, digest = verify_file(directory, filename, files[filename])
        facts = PARSERS[spec['kind']](db, table, spec, directory, filename, files[filename], limit_rows)
    if limit_rows is not None:
        facts['notes']['limit_rows'] = limit_rows
    if spec.get('coordinate_note'):
        facts['notes']['coordinate_note'] = spec['coordinate_note']
    if spec.get('license_restricted'):
        facts['notes']['license_note'] = '공공누리 제4유형(변경금지): raw rows preserved only; not joined, transformed or displayed'
    independent = facts.get('independent_count', manifest.get('independent_count'))
    db.execute('DELETE FROM sources WHERE slug=?', (slug,))
    db.execute('''INSERT INTO sources(slug, table_name, title, provider, portal_url, download_url, license, license_restricted,
                  acquired_date, file, bytes, sha256, encoding, format, row_count_file, row_count_loaded, seoul_row_count,
                  independent_count, seoul_rule, header_json, notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
               (slug, table, manifest.get('title'), manifest.get('provider'), manifest.get('portal_url'),
                manifest.get('download_url'), manifest.get('license'), int(bool(spec.get('license_restricted'))),
                manifest.get('acquired_date'), filename, size, digest, facts.get('encoding'), facts.get('format'),
                facts['row_count_file'], facts['row_count_loaded'], facts['seoul_row_count'], independent,
                facts.get('seoul_rule'), json.dumps(facts.get('header'), ensure_ascii=False),
                json.dumps({**facts.get('notes', {}), 'manifest_note': manifest.get('note'),
                            'member': facts.get('member'), 'member_bytes': facts.get('member_bytes')}, ensure_ascii=False)))
    return {'table': table, 'row_count_file': facts['row_count_file'], 'row_count_loaded': facts['row_count_loaded'],
            'seoul_row_count': facts['seoul_row_count'], 'independent_count': independent,
            'license_restricted': int(bool(spec.get('license_restricted')))}


# ---------------------------------------------------------------------------------------------
# Derived link tables (exact official identifiers only)
# ---------------------------------------------------------------------------------------------
def table_exists(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_kapt_poi_points(db, transformer):
    db.execute('DROP TABLE IF EXISTS kapt_poi_points')
    db.execute('''CREATE TABLE kapt_poi_points(row_number INTEGER NOT NULL, kapt_code TEXT NOT NULL, name TEXT,
                  kapt_usedate TEXT, x_tm TEXT, y_tm TEXT, lon REAL, lat REAL, coordinate_status TEXT NOT NULL,
                  duplicate_group_size INTEGER NOT NULL, coordinate_shared_with_other_codes INTEGER NOT NULL)''')
    if not table_exists(db, 'kapt_seoul_complex_poi'):
        return {'available': False}
    rows = db.execute('SELECT row_number, kaptcode, kaptname, kaptusedate, xcoord, ycoord FROM kapt_seoul_complex_poi').fetchall()
    group_size = Counter(r[1] for r in rows)
    codes_by_xy = defaultdict(set)
    parsed = []
    for row_number, code, name, usedate, x, y in rows:
        fx, fy = finite_number(x), finite_number(y)
        if fx is None or fy is None:
            status = 'missing'
        elif fx == 0 or fy == 0:
            status = 'zero'
        else:
            status = 'transformed'
            codes_by_xy[(fx, fy)].add(code)
        parsed.append((row_number, code, name, usedate, x, y, fx, fy, status))
    out = []
    for row_number, code, name, usedate, x, y, fx, fy, status in parsed:
        lon = lat = None
        if status == 'transformed':
            lon, lat = transformer.transform(fx, fy)
        shared = int(status == 'transformed' and len(codes_by_xy[(fx, fy)]) > 1)
        out.append((row_number, code, name, usedate, x, y, lon, lat, status, group_size[code], shared))
    db.executemany('INSERT INTO kapt_poi_points VALUES(?,?,?,?,?,?,?,?,?,?,?)', out)
    db.execute('CREATE INDEX kapt_poi_points_code ON kapt_poi_points(kapt_code)')
    return {'available': True, 'rows': len(out), 'unique_codes': len(group_size),
            'codes_with_multiple_rows': sum(1 for v in group_size.values() if v > 1),
            'coordinate_status_counts': dict(Counter(r[8] for r in out)),
            'coordinates_shared_between_codes': sum(1 for v in codes_by_xy.values() if len(v) > 1),
            'rows_with_coordinate_shared_by_other_codes': sum(r[10] for r in out),
            'crs': f'{KAPT_CRS} -> EPSG:4326 (pyproj, always_xy)'}


def build_complex_kapt_link(db, apartments_path, transformer, geod):
    db.execute('DROP TABLE IF EXISTS complex_kapt_link')
    db.execute('''CREATE TABLE complex_kapt_link(oa15818_code TEXT PRIMARY KEY, oa15818_name TEXT, oa15818_district TEXT,
                  official_lon REAL, official_lat REAL, in_kapt_list INTEGER NOT NULL, in_kapt_poi INTEGER NOT NULL,
                  in_kapt_basic_info INTEGER NOT NULL, kapt_list_name TEXT, kapt_list_lon REAL, kapt_list_lat REAL,
                  kapt_poi_point_count INTEGER NOT NULL, kapt_poi_located_count INTEGER NOT NULL, kapt_poi_lon REAL, kapt_poi_lat REAL,
                  kapt_poi_status TEXT, kapt_basic_name TEXT, kapt_basic_households TEXT, kapt_basic_dong_count TEXT,
                  kapt_basic_top_floor TEXT, distance_official_to_kapt_m REAL, distance_official_to_kapt_poi_m REAL,
                  match_method TEXT NOT NULL)''')
    if apartments_path is None or not Path(apartments_path).is_file():
        return {'available': False, 'reason': 'apartments.sqlite not provided'}
    with sqlite3.connect(Path(apartments_path).resolve().as_uri() + '?mode=ro', uri=True) as source:
        columns = {r[1] for r in source.execute('PRAGMA table_info(apartments)')}
        needed = {'code', 'name', 'official_lon', 'official_lat'}
        if not needed <= columns:
            raise ValueError(f'apartments.sqlite lacks columns {sorted(needed - columns)}')
        district_sql = 'district' if 'district' in columns else 'NULL'
        official = source.execute(f'SELECT code, name, {district_sql}, official_lon, official_lat FROM apartments').fetchall()
    kapt_list = {}
    if table_exists(db, 'kapt_seoul_complex_list'):
        for code, name, x, y in db.execute('SELECT kaptcode, kaptname, x, y FROM kapt_seoul_complex_list'):
            if code in kapt_list:
                raise ValueError('duplicate kaptCode in K-apt list: ' + code)
            fx, fy = finite_number(x), finite_number(y)
            lon, lat = transformer.transform(fx, fy) if fx and fy else (None, None)
            kapt_list[code] = (name, lon, lat)
    poi = defaultdict(list)
    if table_exists(db, 'kapt_poi_points'):
        for code, lon, lat, status in db.execute('SELECT kapt_code, lon, lat, coordinate_status FROM kapt_poi_points'):
            poi[code].append((lon, lat, status))
    basic = {}
    basic_duplicates = 0
    if table_exists(db, 'kapt_basic_info_weekly'):
        present = {r[1] for r in db.execute('PRAGMA table_info(kapt_basic_info_weekly)')}
        wanted = ['단지코드', '단지명', '세대수', '동수', '최고층수']
        if all(c in present for c in wanted):
            for code, name, households, dongs, floors in db.execute(
                    'SELECT "단지코드","단지명","세대수","동수","최고층수" FROM kapt_basic_info_weekly'):
                if code in basic:
                    basic_duplicates += 1
                else:
                    basic[code] = (name, households, dongs, floors)
    rows = []
    distances = []
    poi_distances = []
    for code, name, district, lon_text, lat_text in official:
        olon, olat = finite_number(lon_text), finite_number(lat_text)
        if olon is not None and not (-180 <= olon <= 180 and -90 <= (olat or 999) <= 90):
            olon = olat = None
        listed = kapt_list.get(code)
        points = poi.get(code, [])
        located = [(lo, la) for lo, la, status in points if status == 'transformed']
        poi_lon = poi_lat = None
        if not points:
            poi_status = None
        elif not located:
            poi_status = 'poi_rows_without_usable_coordinate'
        elif len(set(located)) == 1:
            poi_lon, poi_lat = located[0]
            poi_status = 'single_point' if len(located) == 1 else 'identical_points'
        else:
            poi_status = 'multiple_distinct_points'
        info = basic.get(code)
        distance = geod.inv(olon, olat, listed[1], listed[2])[2] if olon is not None and listed and listed[1] is not None else None
        poi_distance = geod.inv(olon, olat, poi_lon, poi_lat)[2] if olon is not None and poi_lon is not None else None
        if distance is not None:
            distances.append(distance)
        if poi_distance is not None:
            poi_distances.append(poi_distance)
        rows.append((code, name, district, olon, olat, int(listed is not None), int(bool(points)), int(info is not None),
                     listed[0] if listed else None, listed[1] if listed else None, listed[2] if listed else None,
                     len(points), len(located), poi_lon, poi_lat, poi_status,
                     info[0] if info else None, info[1] if info else None, info[2] if info else None, info[3] if info else None,
                     distance, poi_distance, 'identical_official_complex_code'))
    db.executemany(f'INSERT INTO complex_kapt_link VALUES({",".join("?" * 23)})', rows)
    official_codes = {r[0] for r in official}

    def distance_facts(values):
        values = sorted(values)
        return {'pairs': len(values), 'median_m': round(values[len(values) // 2], 1) if values else None,
                'over_100m': sum(d > 100 for d in values), 'over_750m': sum(d > 750 for d in values)}

    return {'available': True, 'oa15818_codes': len(rows),
            'in_kapt_list': sum(r[5] for r in rows), 'in_kapt_poi': sum(r[6] for r in rows), 'in_kapt_basic_info': sum(r[7] for r in rows),
            'in_none': sum(1 for r in rows if not (r[5] or r[6] or r[7])),
            'kapt_list_codes_not_in_oa15818': len(set(kapt_list) - official_codes),
            'kapt_poi_codes_not_in_oa15818': len(set(poi) - official_codes),
            'kapt_basic_seoul_codes_not_in_oa15818': len(set(basic) - official_codes),
            'kapt_basic_duplicate_codes_ignored': basic_duplicates,
            'distance_official_to_kapt_list': distance_facts(distances),
            'distance_official_to_kapt_poi': distance_facts(poi_distances),
            'poi_status_counts': dict(Counter(r[15] or 'no_poi_rows' for r in rows))}


def derive_pnu(bjd_code, bun1, bun2):
    """bjdCode(10) + '1'(대지) + bun1(4) + bun2(4). Only when both bun values are 4-digit numerics."""
    bjd = (bjd_code or '').strip()
    b1 = (bun1 or '').strip() if bun1 is not None else None
    b2 = (bun2 or '').strip() if bun2 is not None else None
    if not re.fullmatch(r'\d{10}', bjd):
        return None, 'bjd_code_not_10_digits'
    if b1 is None or b2 is None or b1 == '' or b2 == '':
        return None, 'bun_missing'
    if not (re.fullmatch(r'\d{4}', b1) and re.fullmatch(r'\d{4}', b2)):
        return None, 'bun_not_4_digit_numeric'
    return bjd + '1' + b1 + b2, 'derived_assuming_대지'


def build_kapt_reb_link(db):
    db.execute('DROP TABLE IF EXISTS kapt_reb_link')
    db.execute('''CREATE TABLE kapt_reb_link(kapt_code TEXT NOT NULL, kapt_name TEXT, bjd_code TEXT, bun1 TEXT, bun2 TEXT,
                  derived_pnu TEXT, pnu_derivation_status TEXT NOT NULL, reb_complex_id TEXT, reb_name_price TEXT,
                  reb_name_register TEXT, reb_name_road TEXT, reb_households TEXT, reb_dong_count TEXT,
                  match_status TEXT NOT NULL, match_count INTEGER NOT NULL)''')
    if not (table_exists(db, 'kapt_seoul_complex_list') and table_exists(db, 'reb_complex_identifier_basic')):
        return {'available': False}
    by_pnu = defaultdict(list)
    for row in db.execute('SELECT "단지고유번호","필지고유번호","단지명_공시가격","단지명_건축물대장","단지명_도로명주소","세대수","동수" '
                          'FROM reb_complex_identifier_basic WHERE seoul_flag=1'):
        by_pnu[row[1]].append(row)
    rows = []
    stats = Counter()
    for code, name, bjd, bun1, bun2 in db.execute('SELECT kaptcode, kaptname, bjdcode, bun1, bun2 FROM kapt_seoul_complex_list'):
        pnu, derivation = derive_pnu(bjd, bun1, bun2)
        if pnu is None:
            rows.append((code, name, bjd, bun1, bun2, None, derivation, None, None, None, None, None, None, 'pnu_not_derivable', 0))
            stats['pnu_not_derivable'] += 1
            continue
        matches = by_pnu.get(pnu, [])
        if not matches:
            rows.append((code, name, bjd, bun1, bun2, pnu, derivation, None, None, None, None, None, None, 'no_match', 0))
            stats['no_match'] += 1
            continue
        status = 'pnu_exact_single' if len(matches) == 1 else 'pnu_exact_multiple'
        stats[status] += 1
        for match in matches:
            rows.append((code, name, bjd, bun1, bun2, pnu, derivation, match[0], match[2], match[3], match[4], match[5], match[6],
                         status, len(matches)))
    db.executemany(f'INSERT INTO kapt_reb_link VALUES({",".join("?" * 15)})', rows)
    db.execute('CREATE INDEX kapt_reb_link_code ON kapt_reb_link(kapt_code)')
    matched_reb = {r[7] for r in rows if r[7]}
    return {'available': True, 'kapt_list_codes': sum(stats.values()), 'match_status_counts': dict(stats),
            'link_rows': len(rows), 'distinct_reb_complexes_matched': len(matched_reb),
            'reb_seoul_complexes': sum(len(v) for v in by_pnu.values()), 'reb_seoul_pnus': len(by_pnu),
            'pnu_rule': "bjdCode(10) + '1' + bun1(4) + bun2(4); 산 parcels (11th digit 2) cannot be derived from the K-apt list"}


def build_reb_dong_summary(db):
    db.execute('DROP TABLE IF EXISTS reb_dong_summary')
    db.execute('''CREATE TABLE reb_dong_summary(reb_complex_id TEXT PRIMARY KEY, dong_count INTEGER NOT NULL,
                  max_floors INTEGER, floors_missing_count INTEGER NOT NULL, floors_nonpositive_count INTEGER NOT NULL,
                  basic_dong_count TEXT, dong_count_equals_basic INTEGER)''')
    if not table_exists(db, 'reb_complex_identifier_dong'):
        return {'available': False}
    summary = {}
    for complex_id, floors in db.execute('SELECT "단지고유번호","지상층수" FROM reb_complex_identifier_dong WHERE seoul_flag=1'):
        entry = summary.setdefault(complex_id, {'count': 0, 'max': None, 'missing': 0, 'nonpositive': 0})
        entry['count'] += 1
        text = (floors or '').strip()
        if not re.fullmatch(r'-?\d+', text):
            entry['missing'] += 1
        elif int(text) <= 0:
            entry['nonpositive'] += 1
        else:
            entry['max'] = int(text) if entry['max'] is None else max(entry['max'], int(text))
    basic = {}
    if table_exists(db, 'reb_complex_identifier_basic'):
        basic = dict(db.execute('SELECT "단지고유번호","동수" FROM reb_complex_identifier_basic WHERE seoul_flag=1').fetchall())
    rows = []
    for complex_id, entry in summary.items():
        declared = basic.get(complex_id)
        equal = None
        if declared is not None and re.fullmatch(r'\d+', declared.strip()):
            equal = int(int(declared) == entry['count'])
        rows.append((complex_id, entry['count'], entry['max'], entry['missing'], entry['nonpositive'], declared, equal))
    db.executemany('INSERT INTO reb_dong_summary VALUES(?,?,?,?,?,?,?)', rows)
    return {'available': True, 'seoul_complexes': len(rows), 'dong_rows': sum(e['count'] for e in summary.values()),
            'complexes_without_positive_floor': sum(1 for e in summary.values() if e['max'] is None),
            'dong_rows_with_nonpositive_floor': sum(e['nonpositive'] for e in summary.values()),
            'dong_rows_with_missing_floor': sum(e['missing'] for e in summary.values()),
            'dong_count_equals_basic_동수': sum(1 for r in rows if r[6] == 1),
            'dong_count_differs_from_basic_동수': sum(1 for r in rows if r[6] == 0),
            'floor_note': '지상층수 is a floor count, never converted to a height'}


def build_links(db, apartments_path):
    transformer = Transformer.from_crs(KAPT_CRS, 'EPSG:4326', always_xy=True)
    geod = Geod(ellps='WGS84')
    return {'kapt_poi_points': build_kapt_poi_points(db, transformer),
            'complex_kapt_link': build_complex_kapt_link(db, apartments_path, transformer, geod),
            'kapt_reb_link': build_kapt_reb_link(db),
            'reb_dong_summary': build_reb_dong_summary(db)}


# ---------------------------------------------------------------------------------------------
# Database assembly
# ---------------------------------------------------------------------------------------------
def create_schema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources(slug TEXT PRIMARY KEY, table_name TEXT NOT NULL, title TEXT, provider TEXT,
            portal_url TEXT, download_url TEXT, license TEXT, license_restricted INTEGER NOT NULL, acquired_date TEXT,
            file TEXT, bytes INTEGER, sha256 TEXT, encoding TEXT, format TEXT, row_count_file INTEGER, row_count_loaded INTEGER,
            seoul_row_count INTEGER, independent_count INTEGER, seoul_rule TEXT, header_json TEXT, notes TEXT);
        CREATE TABLE IF NOT EXISTS columns(table_name TEXT NOT NULL, position INTEGER NOT NULL, original_column TEXT NOT NULL,
            column TEXT NOT NULL, PRIMARY KEY(table_name, position));
    ''')


def import_sources(sources_dir, output, apartments_path=None, slugs=None, limit_rows=None):
    sources_dir = Path(sources_dir)
    output = Path(output)
    unknown = set(slugs or []) - set(SOURCES)
    if unknown:
        raise ValueError('unknown source slugs: ' + ', '.join(sorted(unknown)))
    selected = list(slugs) if slugs else list(SOURCES)
    partial = bool(slugs) and output.is_file()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=output.stem + '-', suffix='.sqlite', dir=output.parent)
    os.close(descriptor)
    try:
        if partial:
            shutil.copyfile(output, temporary)
        else:
            os.unlink(temporary)
        summary = {'sources': {}, 'links': {}}
        with sqlite3.connect(temporary) as db:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            create_schema(db)
            for slug in selected:
                summary['sources'][slug] = import_source(db, slug, SOURCES[slug], sources_dir, limit_rows)
                db.commit()
            summary['links'] = build_links(db, apartments_path)
            metadata = {'schema_version': SCHEMA_VERSION, 'built_at': datetime.now(timezone.utc).isoformat(),
                        'sources_dir': str(sources_dir), 'source_count': db.execute('SELECT COUNT(*) FROM sources').fetchone()[0],
                        'partial_refresh': partial, 'refreshed_sources': selected, 'limit_rows': limit_rows,
                        'raw_json_encoding': 'JSON text (ensure_ascii=False), one object per source row',
                        'value_policy': 'all source values stored as TEXT exactly as read; no trimming, casting or unit conversion',
                        'link_policy': 'derived tables join only on identical official identifiers (K-apt code, PNU, 한국부동산원 단지고유번호); no name matching',
                        'apartments_db': str(apartments_path) if apartments_path else None,
                        'apartments_db_sha256': sha256_file(apartments_path) if apartments_path and Path(apartments_path).is_file() else None,
                        'kapt_crs': KAPT_CRS, 'links': summary['links']}
            db.execute('DELETE FROM metadata')
            db.executemany('INSERT INTO metadata VALUES(?,?)', ((k, json.dumps(v, ensure_ascii=False)) for k, v in metadata.items()))
            db.commit()
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('apartment sources database failed integrity check')
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    summary['output'] = str(output)
    summary['bytes'] = output.stat().st_size
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sources-dir', type=Path, default=ROOT / 'data/sources')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/apartment_sources.sqlite')
    parser.add_argument('--apartments', type=Path, default=ROOT / 'data/apartments.sqlite',
                        help='Official OA-15818 database (read-only) for complex_kapt_link')
    parser.add_argument('--sources', nargs='+', metavar='SLUG', help='Only (re)import these slugs; other tables are kept')
    parser.add_argument('--limit-rows', type=int, help='Load at most N rows per source (tests only; counts still cover the whole file)')
    args = parser.parse_args()
    summary = import_sources(args.sources_dir, args.output, args.apartments if args.apartments.is_file() else None,
                             args.sources, args.limit_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
