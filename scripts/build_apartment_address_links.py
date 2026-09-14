#!/usr/bin/env python3
"""Link remaining apartment lists to complexes through exact official addresses.

The 도로명주소 건물DB (행정안전부, 2026-08) maps every Seoul building's road address and lot
address to its 19-digit PNU. District inventories, SH/LH lists and parking lists carry road or lot
address strings; each string is parsed into (자치구, 도로명, 건물본번, 건물부번) or
(자치구, 법정동, 산, 본번, 부번) and looked up in that table. Only an address that resolves to
exactly one PNU is linked, and a complex is linked only when that PNU is one of its own parcels.
Complex names are never compared. Output: data/apartment_address_links.sqlite.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GU_RE = re.compile(r'([가-힣]{1,4}구)(?=\s|$)')
ROAD_RE = re.compile(r'([가-힣A-Za-z0-9·]+(?:로|길))\s*(지하\s*)?(\d+)(?:-(\d+))?(?![\d-])')
LOT_RE = re.compile(r'([가-힣0-9]+(?:동|가|리))\s+(산\s*)?(\d+)(?:-(\d+))?(?![\d-])')

# table -> (fixed district or None, [address columns], label column, households column)
TABLES = {
    'sh_housing_management_oa_12027': (None, ['주소'], '단지명', '세대수', '구명'),
    'lh_apartment_complexes': (None, ['주소'], '단지명', '세대수', None),
    'lh_rental_complexes_built': (None, ['주소'], '단지명', '세대수', None),
    'lh_rental_complexes_purchased': (None, ['주소'], '단지명', '세대수', None),
    'gangbuk_apartments_oa_11614': ('강북구', ['새주소'], '단지명', '세대수_임대포함', None),
    'gangseo_apartments_oa_21838': ('강서구', ['도로명주소', '번지수'], '단_지_명', '세대수', None),
    'gangseo_apartments': ('강서구', ['도로명주소', '번지수'], '단_지_명', '세대수', None),
    'yangcheon_apartments_oa_22047': ('양천구', ['도로명주소', '지번_주소'], '건물명', '호수', None),
    'yangcheon_apartments': ('양천구', ['도로명주소', '지번_주소'], '건물명', '호수', None),
    'seodaemun_apartments': ('서대문구', ['도로명주소'], '아파트명', '전체세대수', None),
    'jungnang_apartments': ('중랑구', ['소재지도로명주소', '번지수'], '단지명', '세대수', None),
    'dongjak_apartments': ('동작구', ['도로명주소', '번지'], '아파트명', '총호수', None),
    'seocho_apartments': ('서초구', ['주소'], '아파트명', '세대수', None),
    'seongdong_apartments': ('성동구', ['도로명주소', '지번주소'], '공동주택명칭', '세대수', None),
    'gwangjin_apartments': ('광진구', ['아파트소재지'], '단지명', '세대수', None),
    'geumcheon_apartments': ('금천구', ['위치_주소'], '아파트명', '세대수', None),
    'gangnam_apartment_parking': ('강남구', ['도로명주소'], '아파트명', '주차면수', None),
    'seongbuk_apartment_parking': ('성북구', ['도로명주소', '지번주소'], '공동주택명', '주차면수', None),
    'gwanak_apartment_parking': ('관악구', ['도로명주소'], '아파트명', '주차면수', None),
    'yangcheon_apartment_parking': ('양천구', ['도로명주소', '지번주소'], '건물명_주택', '허가면수_면', None),
    'cleanup_seoul_project_list': (None, ['대표지번'], '사업장명', '진행단계', '자치구'),
    'seoul_redevelopment_stats_oa_22856': (None, ['도로명주소', '지번주소'], '구역명', '사업추진단계', '자치구'),
}
SH_DETAIL_GLOB = 'sh-rental-complex-detail-*/addresses.json'


def pad(value, width=4):
    value = str(value or '').strip()
    return value.zfill(width) if value.isdigit() and len(value) <= width else None


def lot_pnu(bjd10, san, main, sub):
    bjd10 = str(bjd10 or '').strip()
    main, sub = pad(main), pad(sub or '0')
    if len(bjd10) != 10 or not bjd10.isdigit() or not main or (main == '0000' and sub == '0000'):
        return None
    return bjd10 + ('2' if str(san).strip() == '1' else '1') + main + sub


def build_indexes(src):
    road, lot, dong_names = defaultdict(set), defaultdict(set), defaultdict(set)
    buildings = []
    for r in src.execute('''SELECT 법정동코드, 시군구명, 법정읍면동명, 산여부, 지번본번, 지번부번, 도로명, 지하여부, 건물본번, 건물부번,
            건축물대장건물명, 상세건물명, 건물관리번호, 공동주택여부 FROM juso_building_db_202608'''):
        pnu = lot_pnu(r[0], r[3], r[4], r[5])
        if not pnu:
            continue
        gu = (r[1] or '').strip()
        if r[6] and pad(r[8]):
            road[(gu, r[6].strip(), '1' if str(r[7]).strip() == '1' else '0', pad(r[8]), pad(r[9] or '0'))].add(pnu)
        lot[(gu, (r[2] or '').strip(), '1' if str(r[3]).strip() == '1' else '0', pad(r[4]), pad(r[5] or '0'))].add(pnu)
        if str(r[13]).strip() == '1':
            buildings.append((pnu, r[12], (r[10] or '').strip() or None, (r[11] or '').strip() or None, r[6], pad(r[8]), pad(r[9] or '0')))
    return road, lot, buildings


def resolve(text, fixed_gu, road, lot, gu_hint=None):
    """Return (pnu, method) when the address resolves to exactly one PNU, else (None, reason)."""
    text = re.sub(r'\s+', ' ', str(text or '').replace('서울특별시', ' ').replace('서울시', ' ')).strip()
    text = re.sub(r'(\d)번지(일대)?', r'\1', text)
    if text in ('-', '—'):
        text = ''
    if not text:
        return None, 'empty'
    found = GU_RE.search(text)
    gu = found.group(1) if found else (gu_hint or fixed_gu)
    if not gu:
        return None, 'no_district'
    head = text.split('(')[0]
    for match in ROAD_RE.finditer(head):
        key = (gu, match.group(1), '1' if match.group(2) else '0', pad(match.group(3)), pad(match.group(4) or '0'))
        hits = road.get(key)
        if hits:
            return (next(iter(hits)), 'road_exact') if len(hits) == 1 else (None, 'road_ambiguous')
    for match in LOT_RE.finditer(text):
        key = (gu, match.group(1), '1' if match.group(2) else '0', pad(match.group(3)), pad(match.group(4) or '0'))
        hits = lot.get(key)
        if hits:
            return (next(iter(hits)), 'lot_exact') if len(hits) == 1 else (None, 'lot_ambiguous')
    return None, 'not_in_building_db'


def build(source, parcel_db, output):
    src = sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True)
    links = sqlite3.connect(Path(parcel_db).resolve().as_uri() + '?mode=ro', uri=True)
    complex_by_pnu = defaultdict(set)
    for code, pnu in links.execute('SELECT code, pnu FROM complex_pnu'):
        complex_by_pnu[pnu].add(code)
    road, lot, buildings = build_indexes(src)
    stats = {'road_keys': len(road), 'lot_keys': len(lot), 'apartment_buildings_in_building_db': len(buildings), 'tables': {}}
    list_rows, dong_rows = [], []
    for table, (fixed_gu, columns, label_col, count_col, gu_col) in TABLES.items():
        counter = Counter()
        cols = ', '.join(f'"{c}"' for c in [*columns, label_col, count_col] + ([gu_col] if gu_col else []))
        for row_number, *values in src.execute(f'SELECT row_number, {cols} FROM {table}'):
            addresses, label, count = values[:len(columns)], values[len(columns)], values[len(columns) + 1]
            gu_hint = values[len(columns) + 2] if gu_col else None
            pnu, method = None, 'empty'
            for address in addresses:
                # A bare lot number column (e.g. 번지수) only makes sense together with the table's own district
                candidate = address
                if address and re.fullmatch(r'\s*산?\s*\d+(?:-\d+)?.*', str(address)):
                    continue
                pnu, method = resolve(candidate, fixed_gu, road, lot, gu_hint)
                if pnu:
                    break
            counter[method] += 1
            codes = sorted(complex_by_pnu.get(pnu, ())) if pnu else []
            if pnu and not codes:
                counter['resolved_but_no_complex_on_parcel'] += 1
            for code in codes:
                list_rows.append((code, pnu, table, row_number, label, count, method))
            counter['rows'] += 1
            counter['linked_rows'] += bool(codes)
        stats['tables'][table] = dict(counter)
    sh_files = sorted((ROOT / 'data/sources').glob(SH_DETAIL_GLOB))
    if sh_files:
        counter = Counter()
        names = {r[0]: (r[1], r[2]) for r in src.execute('SELECT detail_id, 아파트명, 지역 FROM sh_rental_complex_list')}
        for rec in json.loads(sh_files[-1].read_text(encoding='utf-8')):
            label, district = names.get(rec['detail_id'], (None, None))
            pnu, method = resolve(rec.get('단지위치'), None, road, lot, district)
            counter[method] += 1; counter['rows'] += 1
            codes = sorted(complex_by_pnu.get(pnu, ())) if pnu else []
            if pnu and not codes:
                counter['resolved_but_no_complex_on_parcel'] += 1
            for code in codes:
                list_rows.append((code, pnu, 'sh_rental_complex_detail', int(rec['detail_id']), label, rec.get('세대수'), method))
            counter['linked_rows'] += bool(codes)
        stats['tables']['sh_rental_complex_detail'] = dict(counter) | {'source_file': str(sh_files[-1].relative_to(ROOT))}
    energy = defaultdict(lambda: [0.0, 0, None])
    for kind, table in (('electric', 'hub_energy_electric_202605'), ('gas', 'hub_energy_gas_202605')):
        seen = Counter()
        for month, gu, dong, san, main, sub, amount in src.execute(
                f'SELECT col_01, col_03, col_04, col_08, col_09, col_10, col_17 FROM {table}'):
            gu, dong = str(gu or '').strip(), str(dong or '').strip()
            pnu = lot_pnu(gu + dong, san, main, sub) if len(gu) == 5 and len(dong) == 5 else None
            try:
                value = float(str(amount).replace(',', ''))
            except ValueError:
                value = None
            seen['rows'] += 1
            if pnu is None or value is None:
                seen['rows_without_pnu_or_value'] += 1
                continue
            for code in complex_by_pnu.get(pnu, ()):
                bucket = energy[(code, kind)]
                bucket[0] += value; bucket[1] += 1; bucket[2] = month
                seen['linked_rows'] += 1
        stats['tables'][table] = dict(seen)
    for pnu, mgmt, register_name, detail_name, road_name, main, sub in buildings:
        for code in complex_by_pnu.get(pnu, ()):
            dong_rows.append((code, pnu, mgmt, register_name, detail_name, road_name, main, sub))
    output = Path(output)
    fd, temporary = tempfile.mkstemp(prefix=output.stem + '-', suffix='.sqlite', dir=output.parent)
    os.close(fd)
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript('''CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE list_links(code TEXT, pnu TEXT, source_table TEXT, source_row INTEGER, source_label TEXT, source_count TEXT, method TEXT);
                CREATE TABLE building_db_dongs(code TEXT, pnu TEXT, building_mgmt_no TEXT, register_name TEXT, detail_name TEXT,
                    road_name TEXT, building_main TEXT, building_sub TEXT);
                CREATE TABLE energy(code TEXT, kind TEXT, month TEXT, amount_sum REAL, source_rows INTEGER);''')
            db.executemany('INSERT INTO energy VALUES(?,?,?,?,?)', ((c, k, v[2], v[0], v[1]) for (c, k), v in energy.items()))
            db.execute('CREATE INDEX energy_code ON energy(code)')
            stats['energy'] = {k: sum(1 for (c, kk) in energy if kk == k) for k in ('electric', 'gas')}
            db.executemany('INSERT INTO list_links VALUES(?,?,?,?,?,?,?)', list_rows)
            db.executemany('INSERT INTO building_db_dongs VALUES(?,?,?,?,?,?,?,?)', dong_rows)
            db.execute('CREATE INDEX list_links_code ON list_links(code)')
            db.execute('CREATE INDEX building_db_dongs_code ON building_db_dongs(code)')
            stats['list_links'] = {'rows': len(list_rows), 'complexes': len({r[0] for r in list_rows})}
            stats['building_db_dongs'] = {'rows': len(dong_rows), 'complexes': len({r[0] for r in dong_rows})}
            meta = {'schema_version': 1, 'built_at': datetime.now(timezone.utc).isoformat(),
                    'energy_note': '건축HUB 지번별 에너지 17번째 열 합계. 원본에 열 설명·단위가 없어 단위를 표시하지 않는다.',
                    'rule': 'address -> exactly one PNU via 도로명주소 건물DB (road or lot key); complex linked only if PNU is its parcel; names never compared',
                    'stats': stats}
            db.executemany('INSERT INTO metadata VALUES(?,?)', ((k, json.dumps(v, ensure_ascii=False)) for k, v in meta.items()))
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('integrity check failed')
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'data/apartment_sources.sqlite')
    parser.add_argument('--parcel-links', type=Path, default=ROOT / 'data/apartment_parcel_links.sqlite')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/apartment_address_links.sqlite')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.parcel_links, args.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
