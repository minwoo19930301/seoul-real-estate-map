"""Synthetic source folders verify lossless preservation, Seoul filters, exact-identifier links and loud failures."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest
import zipfile

from scripts.import_apartment_sources import biff_cells, derive_pnu, esri_rings_to_geojson, import_sources, sanitize_columns

DATE = '2026-01-01'
# 경희궁의아침3단지 in the real K-apt list: TM_중부 (EPSG:5174) metres -> WGS84 near 내수동, 종로구.
KNOWN_TM = (197511.883, 452430.721)
KNOWN_LONLAT = (126.9726, 37.5742)


def csv_bytes(header, rows, encoding):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode(encoding)


def make_xlsx(path, rows):
    """Minimal OOXML workbook with inlineStr cells; rows is a list of lists (None = absent cell)."""
    def column(index):
        letters = ''
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters
    cells = []
    for r, row in enumerate(rows, start=1):
        items = ''.join(f'<c r="{column(c)}{r}" t="inlineStr"><is><t>{v}</t></is></c>' for c, v in enumerate(row) if v is not None)
        cells.append(f'<row r="{r}">{items}</row>')
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                         '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="sheet1" sheetId="1" r:id="rId3"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{ns}"><sheetData>{"".join(cells)}</sheetData></worksheet>')


def biff_record(kind, body):
    return struct.pack('<HH', kind, len(body)) + body


def unicode_string(text, rich_runs=0):
    flags = 0x01 | (0x08 if rich_runs else 0)
    header = struct.pack('<HB', len(text), flags) + (struct.pack('<H', rich_runs) if rich_runs else b'')
    return header + text.encode('utf-16-le') + b'\0' * (4 * rich_runs)


class ApartmentSourcesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sources = self.root / 'sources'
        self.output = self.root / 'apartment_sources.sqlite'
        self.apartments = self.root / 'apartments.sqlite'
        self.write_apartments_db()
        self.write_all_sources()

    def tearDown(self):
        self.temp.cleanup()

    # ----------------------------------------------------------------------------- fixtures
    def write_source(self, slug, title, files, license_text='이용허락범위 제한 없음 (공공데이터포털 표기)', **extra):
        directory = self.sources / f'{slug}-{DATE}'
        directory.mkdir(parents=True, exist_ok=True)
        manifest_files = {}
        for name, (payload, info) in files.items():
            path = directory / name
            path.write_bytes(payload)
            manifest_files[name] = {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(), **info}
        manifest = {'slug': slug, 'title': title, 'provider': '검증 기관', 'portal_url': 'https://example.invalid/' + slug,
                    'download_url': 'https://example.invalid/' + slug + '/download', 'license': license_text,
                    'acquired_date': DATE, 'note': '', 'files': manifest_files, **extra}
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
        return directory

    def write_apartments_db(self):
        with sqlite3.connect(self.apartments) as db:
            db.execute('CREATE TABLE apartments(code TEXT PRIMARY KEY, name TEXT, district TEXT, official_lon TEXT, official_lat TEXT)')
            db.executemany('INSERT INTO apartments VALUES(?,?,?,?,?)', [
                ('A00000001', '검증1단지', '종로구', '126.97262214256806', '37.57416500005098'),
                ('A00000002', '검증2단지', '종로구', '126.98', '37.58'),
                ('B00000001', '검증1단지', '종로구', '126.97', '37.57'),   # same name, different code: never linked
                ('A00000009', '미등록단지', '종로구', '', ''),
            ])

    def dongjak_rows(self):
        return [['1', '검증아파트', '사당동', '1-1', '서울 검증로 1', '15', '3', '300', '지역난방', '1000', '2000', '150', '2000-01-01', '2001-01-01', '분양', '02-000-0000'],
                ['2', '두번째 아파트', '상도동', '2', '서울 검증로 2', '20', '5', '600', '개별난방', '', '', '', '', '', '', '']]

    def dongjak_header(self):
        return ['연번', '아파트명', '행정동', '번지', '도로명주소', '층수', '동수', '총호수', '난방방식', '대지', '연면적', '주차장', '사업승인', '준공일자', '사업방법', '관리사무소전화번호']

    def write_dongjak(self, rows=None, row_count=None):
        rows = self.dongjak_rows() if rows is None else rows
        payload = csv_bytes(self.dongjak_header(), rows, 'cp949')
        self.write_source('dongjak-apartments', '동작구 공동주택 현황', {'dongjak.csv': (payload, {
            'encoding': 'cp949', 'header': self.dongjak_header(), 'row_count': len(rows) if row_count is None else row_count})})

    def write_all_sources(self):
        self.write_dongjak()
        poi = {'resultList': [
            {'kaptCode': 'A00000001', 'kaptName': '검증1단지', 'kaptUsedate': '20040517', 'xCoord': KNOWN_TM[0], 'yCoord': KNOWN_TM[1]},
            {'kaptCode': 'A00000001', 'kaptName': '검증1단지', 'kaptUsedate': '20040517', 'xCoord': KNOWN_TM[0] + 500, 'yCoord': KNOWN_TM[1]},
            {'kaptCode': 'A00000002', 'kaptName': '검증2단지', 'kaptUsedate': '20100101', 'xCoord': 198000.0, 'yCoord': 452000.0},
            {'kaptCode': 'A00000003', 'kaptName': '검증3단지', 'kaptUsedate': '20100101', 'xCoord': 198000.0, 'yCoord': 452000.0},
            {'kaptCode': 'A00000004', 'kaptName': '좌표없음', 'kaptUsedate': '20100101', 'xCoord': None, 'yCoord': None},
            {'kaptCode': 'A00000005', 'kaptName': '좌표영', 'kaptUsedate': '20100101', 'xCoord': 0, 'yCoord': 0},
            {'kaptCode': 'A50000008', 'kaptName': '테슽002', 'kaptUsedate': '20260908', 'xCoord': 186462.0436302159, 'yCoord': 443731.67207849503},
        ]}
        self.write_source('kapt-seoul-complex-poi', 'K-apt POI', {'kapt-poi-seoul.json': (json.dumps(poi, ensure_ascii=False).encode('utf-8'), {})},
                          license_text='페이지에 이용조건 표기 없음 (재배포 조건 미확인)')

        def listing(code, name, bun1, bun2, x=197500.0, y=452400.0, bjd='1111011800'):
            return {'kaptCode': code, 'kaptName': name, 'bjdCode': bjd, 'energyBCount': 0, 'bjdName': '서울특별시 종로구 내수동',
                    'x': x, 'y': y, 'occuFirstDate': '200406', 'kaptUsedate': '200405', 'openTerm': '', 'bun1': bun1, 'bun2': bun2,
                    'addr': f'서울특별시 종로구 내수동 {bun1} '}
        complexes = {'resultList': [
            listing('A00000001', '검증1단지', '0072', '0000', *KNOWN_TM),
            listing('A00000002', '검증2단지', None, '0000'),
            listing('A00000003', '검증3단지', 'A123', '0000'),
            listing('A00000006', '검증6단지', '0099', '0000'),
            listing('A00000007', '검증7단지', '0500', '0000'),
            listing('A00000010', '검증10단지', '123', '0000'),
        ]}
        self.write_source('kapt-seoul-complex-list', 'K-apt list', {'kapt-list-seoul.json': (json.dumps(complexes, ensure_ascii=False).encode('utf-8'), {})},
                          license_text='페이지에 이용조건 표기 없음 (재배포 조건 미확인)')
        basic_header = ['단지고유번호', '필지고유번호', '주소', '단지명_공시가격', '단지명_건축물대장', '단지명_도로명주소', '단지종류', '동수', '세대수', '사용승인일']
        basic_rows = [
            ['11110200000003', '1111011800100720000', '서울특별시 종로구 내수동 72', '검증1단지', '검증1단지', '검증1단지', '3', '3', '300', '2004-05-17'],
            ['11110200000010', '1111011800100990000', '서울특별시 종로구 내수동 99', '검증6단지', '검증6단지', '', '3', '2', '200', '2010-01-01'],
            ['11110200000011', '1111011800100990000', '서울특별시 종로구 내수동 99', '검증6단지(임대)', '검증6단지', '', '3', '1', '50', '2010-01-01'],
            ['41110200000001', '4111010100100010000', '경기도 수원시 장안구 파장동 1', '경기단지', '', '', '3', '4', '400', '2000-01-01'],
        ]
        self.write_source('reb-complex-identifier-basic', '한국부동산원 기본정보', {'basic.csv': (csv_bytes(basic_header, basic_rows, 'utf-8-sig'), {
            'encoding': 'utf-8-sig', 'header': basic_header, 'row_count': len(basic_rows)})})
        dong_header = ['단지고유번호', '동명_공시가격', '동명_건축물대장', '동명_도로명주소', '지상층수']
        dong_rows = [['11110200000003', '101', '101동', '101동', '15'], ['11110200000003', '102', '102동', '102동', '20'],
                     ['11110200000003', '103', '103동', '103동', '-1'], ['11110200000010', 'A', 'A동', '', ''],
                     ['11110200000010', 'B', 'B동', '', '7'], ['41110200000001', '1', '1동', '1동', '25']]
        self.write_source('reb-complex-identifier-dong', '한국부동산원 동정보', {'dong.csv': (csv_bytes(dong_header, dong_rows, 'utf-8-sig'), {
            'encoding': 'utf-8-sig', 'header': dong_header, 'row_count': len(dong_rows)})})
        lh_header = ['단지코드', '단지명', '주소', '상세주소', '준공일자', '매입일자', '공급유형', '형명', '공급면적', '세대수', '구분']
        lh_rows = [['C00001', '서울단지', '서울특별시 강서구 검증로 1', '', '2010-11-29', '', '국민임대', '29034', '29.78', '78', '건설'],
                   ['C00002', '경기단지', '경기도 파주시 한울로 84', '', '2010-11-29', '', '국민임대', '29034', '29.78', '78', '건설'],
                   ['C00003', '서울단지2', '서울특별시 노원구 검증로 2', '', '2011-01-01', '', '영구임대', '26', '26.0', '10', '건설']]
        self.write_source('lh-rental-complexes-built', 'LH 임대주택단지(건설)', {'lh.csv': (csv_bytes(lh_header, lh_rows, 'cp949'), {
            'encoding': 'cp949', 'header': lh_header, 'row_count': len(lh_rows)})})
        renewal_header = ['조서관리코드', '프로젝트코드', '지자체', '조서유형(구분)', '대분류', '중분류', '소분류', '위치명', '지역명', '면적기정', '면적증감코드', '면적변경', '면적변경후', '결정고시관리코드']
        renewal_rows = [['11000AGZ1', '11000PPL1', '서울특별시', '변경', '의제처리구역', '정비구역', '재개발사업지구', '검증동 1', '검증지구', '1.0', '', '', '2', '11000NTC1']]
        self.write_source('seoul-urban-renewal-status-oa-20281', '서울시 도시계획 정비사업 현황', {'sheet.csv': (csv_bytes(renewal_header, renewal_rows, 'cp949'), {
            'encoding': 'cp949', 'header': renewal_header, 'row_count': 1})}, license_text='공공누리 제4유형: 출처표시 + 상업적 이용금지 + 변경금지', independent_count=1)
        xlsx = self.root / 'weekly.xlsx'
        make_xlsx(xlsx, [['해당 자료는 참조자료입니다.'],
                         ['시도', '시군구', '읍면', '동리', '단지코드', '단지명', '단지분류', '동수', '세대수', '최고층수'],
                         ['서울특별시', '종로구', None, '내수동', 'A00000001', '검증1단지', '주상복합', '1', '150.0', '16'],
                         ['경기도', '수원시', None, '파장동', 'A40000001', '경기단지', '아파트', '4', '400', '25'],
                         ['서울특별시', '노원구', None, '중계동', 'A00000002', '검증2단지', '아파트', '2', '200', '20']])
        self.write_source('kapt-basic-info-weekly', 'K-apt 기본정보', {'weekly.xlsx': (xlsx.read_bytes(), {})},
                          license_text='페이지에 이용조건 표기 없음 (재배포 조건 미확인)')
        price_header = ['기준연도', '기준월', '법정동코드', '도로명주소', '시도', '시군구', '읍면', '동리', '특수지코드', '본번', '부번', '특수지명', '단지명', '동명', '호명', '전용면적', '공시가격', '단지코드', '동코드', '호코드', '건축물대장PK']
        price_rows = [['2025', '1', '1111010100', '서울특별시 종로구 자하문로36길 16-14', '서울특별시', '종로구', '', '청운동', '0', '1', '0', '', '검증빌리지', '1', '111', '187.49', '926000000', '3', '1', '1', '1002135465'],
                      ['2025', '1', '2611010100', '부산광역시 중구 검증로 1', '부산광역시', '중구', '', '검증동', '0', '1', '0', '', '부산단지', '1', '101', '84.9', '300000000', '4', '1', '1', '2002135465'],
                      ['2025', '1', '1111010100', '서울특별시 종로구 자하문로36길 16-14', '서울특별시', '종로구', '', '청운동', '0', '1', '0', '', '검증빌리지', '1', '112', '187.49', '926000000', '3', '1', '2', '1002135468']]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            body = io.StringIO(newline='')
            writer = csv.writer(body, quoting=csv.QUOTE_ALL)
            writer.writerow(price_header)
            writer.writerows(price_rows)
            archive.writestr('국토교통부_주택 공시가격 정보(2025).csv', body.getvalue().encode('utf-8-sig'))
            archive.writestr('국토교통부_주택 공시가격 정보(2025)_샘플데이터.csv', 'x'.encode('utf-8-sig'))
        self.write_source('molit-apartment-price-2025', '공동주택가격 2025', {'price.zip': (buffer.getvalue(), {})})
        esri = {'spatialReference': {'wkid': 4326}, 'geometryType': 'esriGeometryPolygon',
                'fields': [{'name': 'OBJECTID', 'type': 'esriFieldTypeOID'}, {'name': 'DGM_NM', 'type': 'esriFieldTypeString'},
                           {'name': 'CREATE_DAT', 'type': 'esriFieldTypeDate'}, {'name': 'SHAPE', 'type': 'esriFieldTypeGeometry'}],
                'features': [{'attributes': {'OBJECTID': 1, 'DGM_NM': '검증구역', 'CREATE_DAT': 1767139200000},
                              'geometry': {'rings': [[[127.0, 37.5], [127.0, 37.51], [127.01, 37.51], [127.01, 37.5], [127.0, 37.5]],
                                                     [[127.002, 37.502], [127.008, 37.502], [127.008, 37.508], [127.002, 37.508], [127.002, 37.502]]]}},
                             {'attributes': {'OBJECTID': 2, 'DGM_NM': '도형없음', 'CREATE_DAT': None}, 'geometry': None}]}
        self.write_source('upis-renewal-project-zones-uq120', 'UPIS 구역', {'features.esri.json': (json.dumps(esri).encode('utf-8'), {})},
                          license_text='페이지에 이용조건 표기 없음 (재배포 조건 미확인)')
        page = ('<html><body><p>총 <strong class="cBrown bold">2</strong> 건 [1/1 페이지]</p><table><thead><tr>'
                + ''.join(f'<th scope="col">{h}</th>' for h in ['번호', '유형', '아파트명', '지역', '세대수', '준공(예정)일', '비고'])
                + '</tr></thead><tbody><tr><td>2</td><td>행복주택</td><td class="txtL"><a href="#none" onclick="goDetail(\'70494\'); return false;">검증 &amp; 임대</a></td>'
                  '<td>성북구</td><td>2</td><td></td><td></td></tr>'
                  '<tr><td>1</td><td>재개발</td><td class="txtL"><a href="#none" onclick="goDetail(\'70522\'); return false;">DMC 검증</a></td>'
                  '<td>은평구</td><td>91</td><td>2021.10.29</td><td>임대완료</td></tr></tbody></table></body></html>')
        self.write_source('sh-rental-complex-list', 'SH 임대주택 단지 목록', {'page-001.html': (page.encode('utf-8'), {})},
                          license_text='페이지에 이용조건 표기 없음 (재배포 조건 미확인)')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('eais_gas_202605.txt', ('202605|1|11680|10800|서울특별시|강남구|논현동|0|0029|0001|116804166783|학동로23길|0|지상|36|0|27112\r\n'
                                                     '202605|1|26110|10100|부산광역시|중구|검증동|0|0001|0000|261104166783|검증로|0|지상|1|0|10\r\n').encode('utf-8-sig'))
        self.write_source('hub-energy-gas-202605', '건축HUB 가스', {'gas.zip': (buffer.getvalue(), {})}, license_text='페이지에 이용조건 표기 없음 (재배포 조건 미확인)')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            row = ['1111010100', '서울특별시', '종로구', '청운동', '', '0', '144', '3', '111103100012', '자하문로', '0', '94', '0', '', '', '1111010100101440003031291',
                   '01', '1111051500', '청운효자동', '03047', '', '', '', '', '', '', '0', '03047', '0', '', '']
            archive.writestr('build_seoul.txt', ('|'.join(row) + '\r\n').encode('cp949') * 2)
            archive.writestr('자료건수_건물DB.txt', '서울(build_seoul.txt) : 2\n부산(build_busan.txt) : 5\n'.encode('cp949'))
        self.write_source('juso-building-db-202608', '도로명주소 건물DB', {'build.zip': (buffer.getvalue(), {})}, license_text='페이지에 이용조건 표기 없음 (재배포 조건 미확인)')

    def run_import(self, slugs=None, **kw):
        return import_sources(self.sources, self.output, self.apartments, slugs=slugs, **kw)

    def connect(self):
        db = sqlite3.connect(self.output)
        db.row_factory = sqlite3.Row
        return db

    # ----------------------------------------------------------------------------- tests
    def test_rows_are_preserved_losslessly_with_column_mapping_and_manifest_facts(self):
        summary = self.run_import(['dongjak-apartments'])
        self.assertEqual(summary['sources']['dongjak-apartments']['row_count_loaded'], 2)
        with self.connect() as db:
            rows = db.execute('SELECT * FROM dongjak_apartments ORDER BY row_number').fetchall()
            self.assertEqual([r['row_number'] for r in rows], [1, 2])
            self.assertEqual(rows[0]['아파트명'], '검증아파트')
            self.assertEqual(rows[1]['대지'], '')   # empty strings stay empty strings, never NULL or 0
            self.assertEqual(json.loads(rows[0]['raw_json']), dict(zip(self.dongjak_header(), self.dongjak_rows()[0])))
            mapping = dict(db.execute("SELECT original_column, column FROM columns WHERE table_name='dongjak_apartments'").fetchall())
            self.assertEqual(mapping['관리사무소전화번호'], '관리사무소전화번호')
            source = db.execute("SELECT * FROM sources WHERE slug='dongjak-apartments'").fetchone()
            self.assertEqual((source['row_count_file'], source['row_count_loaded'], source['seoul_row_count'], source['license_restricted']), (2, 2, 2, 0))
            self.assertEqual(source['sha256'], hashlib.sha256((self.sources / f'dongjak-apartments-{DATE}' / 'dongjak.csv').read_bytes()).hexdigest())
            self.assertEqual(source['encoding'], 'cp949')
            self.assertEqual(source['acquired_date'], DATE)

    def test_truncated_csv_row_fails_loudly_and_preserves_previous_database(self):
        self.run_import(['dongjak-apartments'])
        before = self.output.read_bytes()
        rows = self.dongjak_rows()
        rows[1] = rows[1][:10]                       # short row: width mismatch
        self.write_dongjak(rows)
        with self.assertRaises(ValueError):
            self.run_import(['dongjak-apartments'])
        self.assertEqual(self.output.read_bytes(), before)
        self.write_dongjak(self.dongjak_rows(), row_count=3)   # manifest count disagrees with the file
        with self.assertRaises(ValueError):
            self.run_import(['dongjak-apartments'])
        self.assertEqual(self.output.read_bytes(), before)

    def test_changed_file_bytes_fail_sha_check(self):
        path = self.sources / f'dongjak-apartments-{DATE}' / 'dongjak.csv'
        path.write_bytes(path.read_bytes() + b'\r\n')
        with self.assertRaises(ValueError):
            self.run_import(['dongjak-apartments'])

    def test_nationwide_sources_flag_seoul_rows_and_seoul_only_loads_keep_nationwide_count(self):
        self.run_import(['lh-rental-complexes-built', 'kapt-basic-info-weekly', 'molit-apartment-price-2025', 'hub-energy-gas-202605', 'juso-building-db-202608'])
        with self.connect() as db:
            flags = dict(db.execute('SELECT 단지코드, seoul_flag FROM lh_rental_complexes_built').fetchall())
            self.assertEqual(flags, {'C00001': 1, 'C00002': 0, 'C00003': 1})
            sources = {r['slug']: r for r in db.execute('SELECT * FROM sources')}
            self.assertEqual((sources['lh-rental-complexes-built']['row_count_file'], sources['lh-rental-complexes-built']['seoul_row_count']), (3, 2))
            weekly = db.execute('SELECT row_number, 시도, 단지코드, 세대수 FROM kapt_basic_info_weekly ORDER BY row_number').fetchall()
            self.assertEqual([tuple(r) for r in weekly], [(3, '서울특별시', 'A00000001', '150.0'), (5, '서울특별시', 'A00000002', '200')])
            self.assertEqual((sources['kapt-basic-info-weekly']['row_count_file'], sources['kapt-basic-info-weekly']['row_count_loaded']), (3, 2))
            self.assertIn('해당 자료는', json.dumps(json.loads(sources['kapt-basic-info-weekly']['notes'])['preface_rows'], ensure_ascii=False))
            price = db.execute('SELECT row_number, 시도, 호명, 건축물대장pk FROM molit_apartment_price_2025 ORDER BY row_number').fetchall()
            self.assertEqual([tuple(r) for r in price], [(1, '서울특별시', '111', '1002135465'), (3, '서울특별시', '112', '1002135468')])
            self.assertEqual((sources['molit-apartment-price-2025']['row_count_file'], sources['molit-apartment-price-2025']['seoul_row_count']), (3, 2))
            self.assertIn("column '시도' startswith '서울'", sources['molit-apartment-price-2025']['seoul_rule'])
            gas = db.execute('SELECT * FROM hub_energy_gas_202605').fetchall()
            self.assertEqual(len(gas), 1)
            self.assertEqual((gas[0]['col_05'], gas[0]['col_17']), ('서울특별시', '27112'))
            self.assertEqual(json.loads(sources['hub-energy-gas-202605']['notes'])['seoul_cross_check']['rows_where_rules_disagree'], 0)
            juso = db.execute('SELECT * FROM juso_building_db_202608').fetchall()
            self.assertEqual(len(juso), 2)
            self.assertEqual((juso[0]['건물관리번호'], juso[0]['공동주택여부'], juso[0]['비고2']), ('1111010100101440003031291', '0', ''))
            self.assertEqual(sources['juso-building-db-202608']['independent_count'], 2)

    def test_pnu_derivation_and_exact_pnu_link(self):
        self.assertEqual(derive_pnu('1111011800', '0072', '0000'), ('1111011800100720000', 'derived_assuming_대지'))
        self.assertEqual(derive_pnu('1111011800', None, '0000')[0], None)
        self.assertEqual(derive_pnu('1111011800', 'A123', '0000')[0], None)
        self.assertEqual(derive_pnu('1111011800', '123', '0000')[0], None)
        self.assertEqual(derive_pnu('111101180', '0072', '0000')[0], None)
        summary = self.run_import(['kapt-seoul-complex-list', 'reb-complex-identifier-basic', 'reb-complex-identifier-dong'])
        link = summary['links']['kapt_reb_link']
        self.assertEqual(link['match_status_counts'], {'pnu_exact_single': 1, 'pnu_exact_multiple': 1, 'no_match': 1, 'pnu_not_derivable': 3})
        with self.connect() as db:
            rows = {(r['kapt_code'], r['reb_complex_id']): r for r in db.execute('SELECT * FROM kapt_reb_link')}
            self.assertEqual(rows[('A00000001', '11110200000003')]['match_status'], 'pnu_exact_single')
            self.assertEqual(rows[('A00000006', '11110200000010')]['match_count'], 2)
            self.assertEqual(rows[('A00000006', '11110200000011')]['match_status'], 'pnu_exact_multiple')
            self.assertEqual(rows[('A00000002', None)]['pnu_derivation_status'], 'bun_missing')
            self.assertEqual(rows[('A00000003', None)]['pnu_derivation_status'], 'bun_not_4_digit_numeric')
            self.assertEqual(rows[('A00000007', None)]['match_status'], 'no_match')
            self.assertEqual(rows[('A00000007', None)]['derived_pnu'], '1111011800105000000')
            basic = db.execute('SELECT 단지고유번호, seoul_by_complex_id, seoul_by_address, seoul_flag FROM reb_complex_identifier_basic ORDER BY row_number').fetchall()
            self.assertEqual([tuple(r) for r in basic][3], ('41110200000001', 0, 0, 0))
            dong = {r['reb_complex_id']: r for r in db.execute('SELECT * FROM reb_dong_summary')}
            self.assertEqual(set(dong), {'11110200000003', '11110200000010'})    # Seoul only
            self.assertEqual((dong['11110200000003']['dong_count'], dong['11110200000003']['max_floors'], dong['11110200000003']['floors_nonpositive_count'],
                              dong['11110200000003']['dong_count_equals_basic']), (3, 20, 1, 1))
            self.assertEqual((dong['11110200000010']['max_floors'], dong['11110200000010']['floors_missing_count'], dong['11110200000010']['dong_count_equals_basic']), (7, 1, 1))

    def test_kapt_poi_transform_duplicates_and_shared_coordinates(self):
        summary = self.run_import(['kapt-seoul-complex-poi'])
        facts = summary['links']['kapt_poi_points']
        self.assertEqual(facts['coordinate_status_counts'], {'transformed': 5, 'missing': 1, 'zero': 1})
        self.assertEqual(facts['coordinates_shared_between_codes'], 1)
        with self.connect() as db:
            rows = db.execute('SELECT * FROM kapt_poi_points ORDER BY row_number').fetchall()
            self.assertAlmostEqual(rows[0]['lon'], KNOWN_LONLAT[0], delta=0.001)
            self.assertAlmostEqual(rows[0]['lat'], KNOWN_LONLAT[1], delta=0.001)
            self.assertEqual(rows[0]['x_tm'], repr(KNOWN_TM[0]))
            self.assertEqual((rows[0]['duplicate_group_size'], rows[1]['duplicate_group_size']), (2, 2))
            self.assertEqual([r['coordinate_shared_with_other_codes'] for r in rows], [0, 0, 1, 1, 0, 0, 0])
            self.assertEqual((rows[4]['coordinate_status'], rows[4]['lon']), ('missing', None))
            self.assertEqual((rows[5]['coordinate_status'], rows[5]['lon']), ('zero', None))
            self.assertEqual(rows[6]['name'], '테슽002')   # test rows are preserved, never silently dropped

    def test_complex_link_uses_identical_code_only(self):
        summary = self.run_import(['kapt-seoul-complex-poi', 'kapt-seoul-complex-list', 'kapt-basic-info-weekly'])
        link = summary['links']['complex_kapt_link']
        self.assertEqual((link['oa15818_codes'], link['in_kapt_list'], link['in_kapt_poi'], link['in_kapt_basic_info'], link['in_none']), (4, 2, 2, 2, 2))
        with self.connect() as db:
            rows = {r['oa15818_code']: r for r in db.execute('SELECT * FROM complex_kapt_link')}
            self.assertEqual(rows['B00000001']['in_kapt_list'], 0)          # same name as A00000001 but a different code
            self.assertEqual(rows['B00000001']['kapt_list_name'], None)
            self.assertEqual(rows['A00000001']['kapt_list_name'], '검증1단지')
            self.assertLess(rows['A00000001']['distance_official_to_kapt_m'], 1.0)
            self.assertEqual(rows['A00000001']['kapt_poi_status'], 'multiple_distinct_points')
            self.assertIsNone(rows['A00000001']['kapt_poi_lon'])
            self.assertEqual(rows['A00000001']['kapt_basic_households'], '150.0')
            self.assertEqual(rows['A00000002']['kapt_poi_status'], 'single_point')
            self.assertGreater(rows['A00000002']['distance_official_to_kapt_poi_m'], 100)
            self.assertIsNone(rows['A00000009']['official_lon'])
            self.assertIsNone(rows['A00000009']['distance_official_to_kapt_m'])

    def test_license_restricted_sources_are_flagged_and_stored_raw(self):
        self.run_import(['seoul-urban-renewal-status-oa-20281', 'dongjak-apartments'])
        with self.connect() as db:
            flags = dict(db.execute('SELECT slug, license_restricted FROM sources').fetchall())
            self.assertEqual(flags, {'seoul-urban-renewal-status-oa-20281': 1, 'dongjak-apartments': 0})
            row = db.execute('SELECT * FROM seoul_urban_renewal_status_oa_20281').fetchone()
            self.assertEqual(row['지자체'], '서울특별시')
            notes = json.loads(db.execute("SELECT notes FROM sources WHERE slug='seoul-urban-renewal-status-oa-20281'").fetchone()[0])
            self.assertIn('변경금지', notes['license_note'])
            self.assertEqual(db.execute("SELECT independent_count FROM sources WHERE slug='seoul-urban-renewal-status-oa-20281'").fetchone()[0], 1)

    def test_esri_rings_html_pages_and_geometry_columns(self):
        self.run_import(['upis-renewal-project-zones-uq120', 'sh-rental-complex-list'])
        with self.connect() as db:
            zones = db.execute('SELECT * FROM upis_renewal_project_zones_uq120 ORDER BY row_number').fetchall()
            geometry = json.loads(zones[0]['geometry_geojson'])
            self.assertEqual((geometry['type'], len(geometry['coordinates']), zones[0]['hole_count'], zones[0]['geometry_status']), ('Polygon', 2, 1, 'polygon'))
            self.assertEqual((zones[0]['min_lon'], zones[0]['max_lat']), (127.0, 37.51))
            self.assertEqual((zones[0]['create_dat'], zones[1]['geometry_status'], zones[1]['geometry_geojson']), ('1767139200000', 'no_geometry', None))
            self.assertEqual(json.loads(zones[0]['raw_json'])['geometry']['rings'][1][0], [127.002, 37.502])
            sh = db.execute('SELECT * FROM sh_rental_complex_list ORDER BY row_number').fetchall()
            self.assertEqual([(r['번호'], r['아파트명'], r['detail_id'], r['비고']) for r in sh],
                             [('2', '검증 & 임대', '70494', ''), ('1', 'DMC 검증', '70522', '임대완료')])
            self.assertEqual(db.execute("SELECT independent_count FROM sources WHERE slug='sh-rental-complex-list'").fetchone()[0], 2)
        rings = [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]
        self.assertEqual(esri_rings_to_geojson(rings)[0]['type'], 'Polygon')
        two = rings + [[[5, 5], [5, 6], [6, 6], [6, 5], [5, 5]]]
        self.assertEqual(esri_rings_to_geojson(two)[0]['type'], 'MultiPolygon')

    def test_partial_refresh_keeps_other_tables_and_is_idempotent(self):
        first = self.run_import(['dongjak-apartments', 'lh-rental-complexes-built'])
        second = self.run_import(['dongjak-apartments'])
        self.assertEqual(first['sources']['dongjak-apartments'], second['sources']['dongjak-apartments'])
        with self.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM lh_rental_complexes_built').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM dongjak_apartments').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sources').fetchone()[0], 2)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertTrue(json.loads(db.execute("SELECT value FROM metadata WHERE key='partial_refresh'").fetchone()[0]))

    def test_limit_rows_keeps_file_counts(self):
        summary = self.run_import(['dongjak-apartments'], limit_rows=1)
        facts = summary['sources']['dongjak-apartments']
        self.assertEqual((facts['row_count_file'], facts['row_count_loaded']), (2, 1))

    def test_unknown_slug_and_missing_directory_fail(self):
        with self.assertRaises(ValueError):
            self.run_import(['no-such-source'])
        with self.assertRaises(FileNotFoundError):
            self.run_import(['gangbuk-apartments-oa-11614'])

    def test_biff8_reader_handles_sst_continue_split(self):
        first, second = '검증단지', '두번째'
        sst_body = struct.pack('<II', 3, 3) + unicode_string(first) + unicode_string('a' * 4)[:3 + 2]   # header + 1 char, rest continues
        continued = b'\x01' + ('a' * 3).encode('utf-16-le') + unicode_string(second)
        sheet = biff_record(0x809, struct.pack('<HHHHII', 0x0600, 0x0010, 0, 0, 0, 0))
        sheet += biff_record(0xFD, struct.pack('<HHHI', 0, 0, 0, 0)) + biff_record(0xFD, struct.pack('<HHHI', 0, 1, 0, 1))
        sheet += biff_record(0xFD, struct.pack('<HHHI', 1, 0, 0, 2)) + biff_record(0x203, struct.pack('<HHHd', 1, 1, 0, 1171.0))
        sheet += biff_record(0x27E, struct.pack('<HHHI', 1, 2, 0, (12345 << 2) | 3)) + biff_record(0x0A, b'')
        globals_part = biff_record(0x809, struct.pack('<HHHHII', 0x0600, 0x0005, 0, 0, 0, 0)) + biff_record(0x42, struct.pack('<H', 1200))
        name = '시트'.encode('utf-16-le')
        placeholder = biff_record(0x85, struct.pack('<IBBBB', 0, 0, 0, len(name) // 2, 1) + name)
        globals_part += placeholder + biff_record(0xFC, sst_body) + biff_record(0x3C, continued) + biff_record(0x0A, b'')
        offset = len(globals_part)
        globals_part = globals_part.replace(placeholder, biff_record(0x85, struct.pack('<IBBBB', offset, 0, 0, len(name) // 2, 1) + name))
        sheet_name, cells, facts = biff_cells(globals_part + sheet)
        self.assertEqual(sheet_name, '시트')
        self.assertEqual(cells[0], {0: first, 1: 'aaaa'})
        self.assertEqual(cells[1], {0: second, 1: '1171', 2: '123.45'})
        self.assertEqual(facts['sst_strings'], 3)

    def test_column_sanitizer_keeps_mapping_unique(self):
        self.assertEqual(sanitize_columns(['세대수(임대포함)', '좌표(X)', '좌표(X)', '', 'row_number']),
                         ['세대수_임대포함', '좌표_x', '좌표_x_2', 'col_4', 'row_number_src'])


if __name__ == '__main__':
    unittest.main()
