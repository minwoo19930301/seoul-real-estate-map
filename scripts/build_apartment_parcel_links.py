#!/usr/bin/env python3
"""Link apartment complexes to transactions, prices, registers and permits by exact parcel number.

Every join key is a 19-digit PNU (법정동코드 10 + 필지구분 1 + 본번 4 + 부번 4) built from
official code columns. Registers and permits carry district/dong *names* instead of codes; those
names are converted with the official code pairs observed in the Seoul transaction dataset, and a
name that maps to more than one code is refused. Complex names are never compared.

Input: data/apartment_sources.sqlite (read-only). Output: data/apartment_parcel_links.sqlite.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import statistics
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LAND_TYPE = {'1': '1', '대지': '1', '2': '2', '산': '2'}


def digits(value, width):
    value = (value or '').strip()
    if not value.isdigit() or len(value) > width:
        return None
    return value.zfill(width)


def make_pnu(bjd10, land_type, main, sub):
    # The 법정동코드 must already be exactly 10 digits; padding a short code would invent a parcel.
    bjd10 = (bjd10 or '').strip()
    if len(bjd10) != 10 or not bjd10.isdigit():
        return None
    land = LAND_TYPE.get((land_type or '').strip())
    main, sub = digits(main, 4), digits(sub or '0', 4)
    if not (bjd10 and len(bjd10) == 10 and land and main):
        return None
    if main == '0000' and sub == '0000':
        return None
    return bjd10 + land + main + (sub or '0000')


def number(value):
    value = (value or '').strip().replace(',', '')
    try:
        n = float(value)
    except ValueError:
        return None
    return int(n) if n == int(n) else n


def complex_pnus(src):
    """Official complex code -> PNUs, from K-apt list parcels (exact-code namespace shared with OA-15818)."""
    result = defaultdict(set)
    for code, pnu, status in src.execute('SELECT kapt_code, derived_pnu, pnu_derivation_status FROM kapt_reb_link'):
        if pnu and len(pnu) == 19 and pnu.isdigit() and str(status or '').startswith('derived'):
            result[code].add(pnu)
    # 한국부동산원 complexes reached by an exact PNU match contribute their own registered parcel.
    for code, pnu in src.execute('''SELECT l.kapt_code, b.필지고유번호 FROM kapt_reb_link l
            JOIN reb_complex_identifier_basic b ON b.단지고유번호=l.reb_complex_id
            WHERE l.match_status='pnu_exact_single' '''):
        if pnu and len(pnu) == 19 and pnu.isdigit():
            result[code].add(pnu)
    return result


def name_code_map(src):
    """(자치구명, 법정동명) -> 10-digit 법정동코드 from official code pairs; ambiguous names are dropped."""
    seen = defaultdict(set)
    for table, gu_code, dong_code in (('seoul_realestate_sales_oa_21275', '자치구코드', '법정동코드'),
                                      ('seoul_rent_transactions_2025_oa_21276', '자치구코드', '법정동코드')):
        for gu_name, gu, dong_name, dong in src.execute(
                f'SELECT DISTINCT 자치구명, {gu_code}, 법정동명, {dong_code} FROM {table}'):
            gu, dong = digits(gu, 5), digits(dong, 5)
            if gu and dong and gu_name and dong_name:
                seen[(gu_name.strip(), dong_name.strip())].add(gu + dong)
    mapping = {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}
    return mapping, sorted(k for k, v in seen.items() if len(v) > 1)


def register_pnu(mapping, sigungu_name, dong_name, land_name, main, sub):
    gu = (sigungu_name or '').replace('서울특별시', '').strip()
    code = mapping.get((gu, (dong_name or '').strip()))
    if not code:
        return None
    return make_pnu(code, land_name, main, sub)


def build(source, output):
    src = sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True)
    pnus = complex_pnus(src)
    by_pnu = defaultdict(set)
    for code, values in pnus.items():
        for p in values:
            by_pnu[p].add(code)
    mapping, ambiguous = name_code_map(src)
    stats = {'complexes_with_pnu': len(pnus), 'distinct_complex_pnus': len(by_pnu),
             'pnus_shared_by_several_complexes': sum(1 for c in by_pnu.values() if len(c) > 1),
             'district_dong_names_mapped': len(mapping), 'district_dong_names_ambiguous': ambiguous}
    rows = defaultdict(list)
    counts = Counter()

    def attach(kind, pnu, record):
        counts[f'{kind}_rows_scanned'] += 1
        if pnu is None:
            counts[f'{kind}_rows_without_pnu'] += 1
            return
        for code in by_pnu.get(pnu, ()):
            rows[kind].append((code, pnu, *record))

    for r in src.execute('''SELECT 자치구코드, 법정동코드, 지번구분, 본번, 부번, 계약일, 물건금액_만원, 건물면적_m2, 층,
            건물명, 건축년도, 취소일, 건물용도 FROM seoul_realestate_sales_oa_21275'''):
        gu, dong = digits(r[0], 5), digits(r[1], 5)
        attach('sale', make_pnu((gu or '') + (dong or ''), r[2], r[3], r[4]) if gu and dong else None,
               (r[5], number(r[6]), number(r[7]), r[8], r[9], r[10], r[11] or None, r[12]))
    for r in src.execute('''SELECT 자치구코드, 법정동코드, 지번구분코드, 본번, 부번, 계약일, 전월세구분, 보증금_만원, 임대료_만원,
            임대면적, 층, 건물명, 건물용도 FROM seoul_rent_transactions_2025_oa_21276'''):
        gu, dong = digits(r[0], 5), digits(r[1], 5)
        attach('rent', make_pnu((gu or '') + (dong or ''), r[2], r[3], r[4]) if gu and dong else None,
               (r[5], r[6], number(r[7]), number(r[8]), number(r[9]), r[10], r[11], r[12]))
    price_values = defaultdict(list)
    for r in src.execute('SELECT 법정동코드, 특수지코드, 본번, 부번, 공시가격, 기준연도, 기준월, 동명, 호명, 전용면적 FROM molit_apartment_price_2025'):
        counts['price_rows_scanned'] += 1
        # 특수지코드 0 = 일반 번지(대지). Other codes (산·블록 등) are not converted.
        pnu = make_pnu(r[0], '1', r[2], r[3]) if (r[1] or '').strip() == '0' else None
        if pnu is None:
            counts['price_rows_without_pnu'] += 1
            continue
        value = number(r[4])
        for code in by_pnu.get(pnu, ()):
            price_values[(code, pnu, f'{r[5]}-{int(r[6]):02d}' if (r[6] or '').strip().isdigit() else r[5])].append((value, number(r[9])))
    for r in src.execute('''SELECT 시군구코드명, 법정동코드명, 대지구분코드명, 주지번, 부지번, 건축물대장일련번호, 대장종류코드명,
            주용도코드명, 세대수, 주건축물수, 총주차수, 대지면적, 연면적, 건폐율, 용적률, 사용승인일자 FROM seoul_register_summary_oa_22423'''):
        attach('register', register_pnu(mapping, r[0], r[1], r[2], r[3], r[4]), tuple(r[5:]))
    for r in src.execute('''SELECT 시군구코드명, 법정동코드명, 대지구분코드명, 주지번, 부지번, 주택대장일련번호, 건물명, 동명, 주부속구분코드명,
            주용도코드명, 지상층수, 지하층수, 높이 FROM seoul_housing_permit_dong_oa_22414'''):
        attach('permit', register_pnu(mapping, r[0], r[1], r[2], r[3], r[4]), (r[5], r[6], r[7], r[8], r[9], number(r[10]), number(r[11]), number(r[12])))

    output = Path(output)
    fd, temporary = tempfile.mkstemp(prefix=output.stem + '-', suffix='.sqlite', dir=output.parent)
    os.close(fd)
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript('''
                CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE complex_pnu(code TEXT NOT NULL, pnu TEXT NOT NULL, PRIMARY KEY(code, pnu));
                CREATE TABLE sales(code TEXT, pnu TEXT, contract_date TEXT, price_manwon REAL, area_m2 REAL, floor TEXT,
                    building_name TEXT, built_year TEXT, cancel_date TEXT, building_use TEXT);
                CREATE TABLE rents(code TEXT, pnu TEXT, contract_date TEXT, rent_type TEXT, deposit_manwon REAL, monthly_manwon REAL,
                    area_m2 REAL, floor TEXT, building_name TEXT, building_use TEXT);
                CREATE TABLE price_summary(code TEXT, pnu TEXT, basis TEXT, unit_count INTEGER, median_won REAL, min_won REAL, max_won REAL,
                    median_won_per_m2 REAL);
                CREATE TABLE registers(code TEXT, pnu TEXT, register_serial TEXT, register_kind TEXT, main_use TEXT, households TEXT,
                    main_buildings TEXT, parking TEXT, site_area TEXT, total_floor_area TEXT, coverage_ratio TEXT, floor_area_ratio TEXT,
                    approval_date TEXT);
                CREATE TABLE permit_dongs(code TEXT, pnu TEXT, housing_register_serial TEXT, building_name TEXT, dong_name TEXT,
                    main_or_annex TEXT, main_use TEXT, ground_floors REAL, basement_floors REAL, height_m REAL);''')
            db.executemany('INSERT INTO complex_pnu VALUES(?,?)', ((c, p) for c, v in pnus.items() for p in sorted(v)))
            db.executemany('INSERT INTO sales VALUES(?,?,?,?,?,?,?,?,?,?)', rows['sale'])
            db.executemany('INSERT INTO rents VALUES(?,?,?,?,?,?,?,?,?,?)', rows['rent'])
            db.executemany('INSERT INTO registers VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', rows['register'])
            db.executemany('INSERT INTO permit_dongs VALUES(?,?,?,?,?,?,?,?,?,?)', rows['permit'])
            for (code, pnu, basis), values in price_values.items():
                prices = [v for v, _ in values if isinstance(v, (int, float)) and v > 0]
                per_m2 = [v / a for v, a in values if isinstance(v, (int, float)) and v > 0 and isinstance(a, (int, float)) and a > 0]
                db.execute('INSERT INTO price_summary VALUES(?,?,?,?,?,?,?,?)', (code, pnu, basis, len(values),
                    statistics.median(prices) if prices else None, min(prices) if prices else None, max(prices) if prices else None,
                    statistics.median(per_m2) if per_m2 else None))
            for table in ('sales', 'rents', 'price_summary', 'registers', 'permit_dongs'):
                db.execute(f'CREATE INDEX {table}_code ON {table}(code)')
            linked = {t: db.execute(f'SELECT COUNT(DISTINCT code), COUNT(*) FROM {t}').fetchone()
                      for t in ('sales', 'rents', 'price_summary', 'registers', 'permit_dongs')}
            stats.update(counts)
            stats['linked'] = {t: {'complexes': a, 'rows': b} for t, (a, b) in linked.items()}
            meta = {'schema_version': 1, 'built_at': datetime.now(timezone.utc).isoformat(), 'source': str(Path(source).resolve()),
                    'join_rule': 'exact 19-digit PNU only; register/permit district and dong names converted with unambiguous official code pairs; complex names never compared',
                    'price_rule': '특수지코드 0 rows only; unit prices summarised per complex parcel, not per household',
                    'height_note': 'permit_dongs.height_m is the housing-permit 높이 field as registered; not field-verified',
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
    parser.add_argument('--output', type=Path, default=ROOT / 'data/apartment_parcel_links.sqlite')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
