"""Read-only details for official apartment complexes and renewal-zone polygons.

Values come from data/apartment_sources.sqlite (scripts/import_apartment_sources.py).
Joins use identical official identifiers only: the Seoul/K-apt complex code and the
한국부동산원 complex id reached through an exact PNU match. No name matching.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from server.database import connect_readonly, available, database_bytes

from server.places import parse_bbox

MAX_ZONES = 400
# 롯데월드타워 555m보다 높은 인허가 높이 기록은 입력 오류로 보고 최대값 계산에서 뺀다(원본은 보존).
MAX_PLAUSIBLE_HEIGHT_M = 600
ZONE_TABLES = {
    'project': ('upis_renewal_project_zones_uq120', '정비사업 사업장 구역'),
    'district': ('upis_renewal_districts_uq181', '정비구역·재정비촉진지구'),
}
ZONE_SOURCE_URL = 'https://urban.seoul.go.kr/view/map/main.html'
KAPT_URL = 'https://www.k-apt.go.kr/'
REB_URL = 'https://www.data.go.kr/data/15106861/fileData.do'
FEE_URL = 'https://data.seoul.go.kr/dataList/OA-15822/S/1/datasetView.do'
BASIC_FIELDS = ('단지명', '단지분류', '도로명주소', '분양형태', '사용승인일', '동수', '세대수', '분양세대수', '임대세대수',
                '관리방식', '난방방식', '복도유형', '시공사', '시행사', '최고층수', '최고층수_건축물대장상', '지하층수',
                '총주차대수', '지상주차대수', '지하주차대수', '승강기_승객용', '전기차전용주차면수_지상', '전기차전용주차면수_지하')


def clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def number(value):
    value = clean(value)
    if value is None:
        return None
    try:
        n = float(value.replace(',', ''))
    except ValueError:
        return None
    return int(n) if n == int(n) else n


class ApartmentDetailsAPI:
    def __init__(self, database, parcel_database=None):
        self.database = Path(database).resolve()
        self.parcel_database = Path(parcel_database or self.database.with_name('apartment_parcel_links.sqlite')).resolve()
        self.address_database = self.database.with_name('apartment_address_links.sqlite')

    def available(self):
        return available(self.database)

    def connect(self):
        connection = connect_readonly(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def detail(self, code):
        if not isinstance(code, str) or not code or len(code) > 20 or not code.isascii() or not code.isalnum():
            raise ValueError('invalid complex code')
        if not self.available():
            return {'available': False, 'code': code, 'reason': 'apartment_sources_database_not_built'}
        result = {'available': True, 'code': code, 'kapt_basic': None, 'reb': [], 'management_fee': None,
                  'join_policy': '같은 단지코드·필지번호(PNU)·한국부동산원 단지고유번호만 사용, 이름 비교 없음'}
        with self.connect() as db:
            row = db.execute('SELECT * FROM kapt_basic_info_weekly WHERE 단지코드=? LIMIT 1', (code,)).fetchone()
            if row is not None:
                result['kapt_basic'] = {k: clean(row[k]) for k in BASIC_FIELDS if k in row.keys()}
                result['kapt_basic']['source_url'] = KAPT_URL
                result['kapt_basic']['source'] = 'K-apt 관리비공개의무단지 기본정보 (2026-09-09 추출)'
            for link in db.execute('''SELECT l.reb_complex_id, l.match_status, l.derived_pnu, l.reb_name_register,
                    l.reb_households, s.dong_count, s.max_floors
                    FROM kapt_reb_link l LEFT JOIN reb_dong_summary s ON s.reb_complex_id=l.reb_complex_id
                    WHERE l.kapt_code=? AND l.reb_complex_id IS NOT NULL AND l.reb_complex_id<>''
                    ORDER BY l.reb_complex_id''', (code,)):
                result['reb'].append({'reb_complex_id': link['reb_complex_id'], 'match_status': link['match_status'],
                    'pnu': link['derived_pnu'], 'name_register': clean(link['reb_name_register']),
                    'households': number(link['reb_households']), 'dong_count': number(link['dong_count']),
                    'max_ground_floors': number(link['max_floors']), 'source_url': REB_URL})
            latest = db.execute('SELECT MAX(년월) FROM seoul_apartment_mgmt_fee_oa_15822 WHERE 아파트코드=?', (code,)).fetchone()[0]
            if latest:
                items = db.execute('SELECT 비용명, 금액 FROM seoul_apartment_mgmt_fee_oa_15822 WHERE 아파트코드=? AND 년월=? ORDER BY row_number',
                                   (code, latest)).fetchall()
                amounts = [(clean(i['비용명']), number(i['금액'])) for i in items]
                result['management_fee'] = {'month': latest, 'item_count': len(amounts),
                    'total_won': sum(a for _, a in amounts if isinstance(a, (int, float))),
                    'items': [{'name': n, 'amount_won': a} for n, a in amounts], 'source_url': FEE_URL,
                    'note': '단지 전체의 월 부과 항목 합계이며 세대당 금액이 아니다.'}
        result['parcel'] = self.parcel(code)
        result['address_links'] = self.address_links(code)
        return result

    def address_links(self, code):
        """District/SH/LH/parking lists, 도로명주소 건물DB dongs and energy (scripts/build_apartment_address_links.py)."""
        if not available(self.address_database):
            return {'available': False, 'reason': 'apartment_address_links_not_built'}
        db = connect_readonly(self.address_database)
        db.row_factory = sqlite3.Row
        with db:
            lists = [dict(r) for r in db.execute('''SELECT source_table, source_label, source_count, method FROM list_links
                WHERE code=? ORDER BY source_table, source_row''', (code,))]
            dongs = [dict(r) for r in db.execute('''SELECT detail_name, register_name, building_mgmt_no FROM building_db_dongs
                WHERE code=? ORDER BY detail_name''', (code,))]
            energy = [dict(r) for r in db.execute('SELECT kind, month, amount_sum, source_rows FROM energy WHERE code=?', (code,))]
        return {'available': True, 'lists': lists, 'building_db_dongs': {'count': len(dongs), 'items': dongs[:120]},
                'energy': energy, 'energy_note': '건축HUB 지번별 에너지 사용량 합계. 원본에 단위 표기가 없다.',
                'join_rule': '주소를 도로명주소 건물DB에서 필지번호 하나로 확정한 경우만 연결, 단지명 비교 없음'}

    def parcel(self, code):
        """Transactions, prices, registers and permits joined by exact PNU (scripts/build_apartment_parcel_links.py)."""
        if not available(self.parcel_database):
            return {'available': False, 'reason': 'apartment_parcel_links_not_built'}
        db = connect_readonly(self.parcel_database)
        db.row_factory = sqlite3.Row
        with db:
            pnus = [r[0] for r in db.execute('SELECT pnu FROM complex_pnu WHERE code=? ORDER BY pnu', (code,))]
            sales = db.execute('''SELECT contract_date, price_manwon, area_m2, floor, building_name FROM sales
                WHERE code=? AND (cancel_date IS NULL OR cancel_date='') AND building_use='아파트'
                ORDER BY contract_date DESC LIMIT 5''', (code,)).fetchall()
            sale_count = db.execute("SELECT COUNT(*) FROM sales WHERE code=? AND (cancel_date IS NULL OR cancel_date='') AND building_use='아파트'", (code,)).fetchone()[0]
            rent = db.execute('''SELECT COUNT(*) n, SUM(rent_type='전세') jeonse, SUM(rent_type='월세') wolse FROM rents
                WHERE code=? AND building_use='아파트' ''', (code,)).fetchone()
            price = db.execute('SELECT basis, unit_count, median_won, min_won, max_won, median_won_per_m2 FROM price_summary WHERE code=? ORDER BY unit_count DESC', (code,)).fetchall()
            registers = db.execute('''SELECT register_kind, main_use, households, main_buildings, parking, floor_area_ratio, coverage_ratio, approval_date
                FROM registers WHERE code=? ORDER BY register_serial''', (code,)).fetchall()
            dongs = db.execute('''SELECT dong_name, ground_floors, basement_floors, height_m FROM permit_dongs
                WHERE code=? AND main_or_annex LIKE '주%' AND main_use='공동주택' ORDER BY height_m DESC''', (code,)).fetchall()
        return {'available': True, 'pnus': pnus, 'join_rule': '같은 필지번호(PNU)만 연결, 단지명 비교 없음',
            'sales': {'count_apartment_uncancelled': sale_count, 'recent': [dict(r) for r in sales],
                      'source_url': 'https://data.seoul.go.kr/dataList/OA-21275/S/1/datasetView.do',
                      'note': '같은 필지의 아파트 거래. 한 필지에 여러 단지가 있으면 섞일 수 있다.'},
            'rents_2025': {'count': rent['n'] or 0, 'jeonse': rent['jeonse'] or 0, 'wolse': rent['wolse'] or 0,
                           'source_url': 'https://data.seoul.go.kr/dataList/OA-21276/F/1/datasetView.do'},
            'official_price_2025': [dict(r) for r in price],
            'registers': [dict(r) for r in registers],
            'permit_dongs': {'count': len(dongs), 'max_height_m': max((d['height_m'] for d in dongs if isinstance(d['height_m'], (int, float)) and 0 < d['height_m'] <= MAX_PLAUSIBLE_HEIGHT_M), default=None),
                             'suspect_height_count': sum(1 for d in dongs if isinstance(d['height_m'], (int, float)) and d['height_m'] > MAX_PLAUSIBLE_HEIGHT_M),
                             'max_ground_floors': max((d['ground_floors'] for d in dongs if isinstance(d['ground_floors'], (int, float)) and d['ground_floors'] > 0), default=None),
                             'items': [dict(d) for d in dongs[:60]],
                             'note': '주택인허가 동별개요 기록. 재건축 등 계획 중인 허가가 섞일 수 있고, 높이 0은 미기재로 본다. 준공 후 실측이 아니다.'}}

    def zones(self, bbox, kinds='project,district'):
        west, south, east, north = parse_bbox(bbox)
        kinds = [k.strip() for k in (kinds or '').split(',') if k.strip()]
        if not kinds or any(k not in ZONE_TABLES for k in kinds):
            raise ValueError('kinds must contain only ' + ','.join(ZONE_TABLES))
        metadata = {'available': self.available(), 'limit': MAX_ZONES, 'truncated': False, 'count': 0,
                    'source_url': ZONE_SOURCE_URL, 'note': '서울도시공간포털 공개 조회 도형. 대량 재배포 허락은 확인하지 않았다.'}
        if not self.available():
            return {'type': 'FeatureCollection', 'features': [], 'metadata': metadata}
        features = []
        with self.connect() as db:
            for kind in kinds:
                table, label = ZONE_TABLES[kind]
                rows = db.execute(f'''SELECT objectid, present_sn, sclas_cl, dgm_nm, signgu_se, geometry_geojson
                    FROM {table} WHERE max_lon>=? AND min_lon<=? AND max_lat>=? AND min_lat<=?
                    AND geometry_geojson IS NOT NULL ORDER BY CAST(dgm_ar AS REAL) DESC LIMIT ?''',
                    (west, east, south, north, MAX_ZONES + 1)).fetchall()
                if len(rows) > MAX_ZONES:
                    metadata['truncated'] = True
                for r in rows[:MAX_ZONES]:
                    features.append({'type': 'Feature', 'id': f'{kind}:{r["objectid"]}',
                        'properties': {'kind': kind, 'kind_label': label, 'name': clean(r['dgm_nm']), 'code': clean(r['sclas_cl']),
                                       'present_sn': clean(r['present_sn']), 'district_code': clean(r['signgu_se'])},
                        'geometry': json.loads(r['geometry_geojson'])})
        metadata['count'] = len(features)
        return {'type': 'FeatureCollection', 'features': features, 'metadata': metadata}
