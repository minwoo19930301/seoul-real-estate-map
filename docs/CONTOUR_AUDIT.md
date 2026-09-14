# 등고선·표고점 원본 전수 감사

감사일: 2026-09-08 KST. 대상은 이 컴퓨터의 `data/seoul-contours.zip`과 `data/terrain.sqlite`입니다. 원본과 DB는 읽기 전용으로 검사했고 감사 전후 파일 SHA-256이 같았습니다. 서버 재시작·자료 재생성은 하지 않았습니다.

## 결론

**제공 ZIP에 들어 있는 등고선 8,570개와 표고점 45,870개의 높이·원본 도형은 DB에 빠짐없이 들어 있습니다.** 개수만 맞춘 결과가 아닙니다. SHP의 모든 좌표, 선의 파트 구분과 순서, DBF의 모든 HEIGHT를 DB 레코드와 1:1로 비교했고 불일치가 0건이었습니다.

이 결과는 **이 원본 ZIP의 선·점과 높이를 100% 보존했다는 뜻**입니다. 서울의 모든 지점을 직접 측량했다거나 모든 지점에 원본 높이 기록이 있다는 뜻은 아닙니다. 원본 자체는 5m 높이 간격의 선과 별도 표고점 자료입니다. 그 사이를 채운 2.5D 지면은 보간 추정입니다.

`UFID`, `CONT`/`NUME`, `SCLS`, `FMTA`, `SHAPE_LEN` 같은 기타 DBF 속성까지 SQLite의 개별 컬럼에 모두 옮긴 것은 아닙니다. 이 속성들은 원본 ZIP에 보존되어 있습니다. DB는 선·점 순번, 도형, HEIGHT, 등고선 분류에서 도출한 `major` 등을 저장합니다. 따라서 표현을 **“원본 모든 속성 전체 적재”로 확대하면 부정확합니다.**

## 전수 비교 결과

| 비교 항목 | 등고선 | 표고점 |
|---|---:|---:|
| SHP 물리 레코드 | 8,570 | 45,870 |
| SHX 인덱스 항목 | 8,570 | 45,870 |
| DBF 물리 레코드 | 8,570 | 45,870 |
| SQLite 원본 레코드 | 8,570 | 45,870 |
| DBF 삭제 플래그 `*` | 0 | 0 |
| SHP null 도형 | 0 | 0 |
| 빠진·추가된 DB ID | 0 | 0 |
| HEIGHT 불일치 | 0 | 0 |
| 전체 좌표·파트 순서 불일치 | 0 | 0 |
| 검사한 XY 좌표쌍 | 4,413,952 | 45,870 |
| 검사한 파트 | 10,013 | 45,870 |
| 공간 인덱스 누락·원본 경계 미포함 | 0 | 0 |
| 높이 범위 | 5–770m | −0.54–740.2m |

등고선은 LineString 7,620개와 MultiLineString 950개입니다. 표고점은 모두 Point이며, 음수 높이 2개도 그대로 보존되었습니다. 등고선 `DIVI == CTD001`과 DB `major`, 표고점의 별도 DB `x`·`y` 컬럼도 전부 일치합니다.

원본 PRJ는 두 레이어 모두 EPSG:5174입니다. DB 원본 WKB도 그 좌표를 그대로 보존합니다. 비교에는 좌표 변환, 반올림, 도형 단순화, 오차 허용값을 사용하지 않았습니다. 원본 DBF HEIGHT 문자열을 64비트 실수로 읽었을 때의 값과 SQLite REAL의 비트 표현을 비교했습니다. 이는 기록값 보존 여부 검사이며 DBF 소수 8자리만큼의 현장 정확도를 뜻하지 않습니다.

RTree는 부동소수점 경계를 바깥쪽으로 반올림하므로 좌표 바이트 자체가 원본 경계와 같지는 않습니다. 모든 인덱스 경계가 원본을 포함하는지 별도로 검사했고 실패는 0건입니다. 관찰된 최대 바깥쪽 차이는 약 0.06245m로 원본 도형에는 영향을 주지 않습니다.

## 무엇을 어떻게 확인했는가

기존 적재 함수나 `iterShapeRecords()`를 재사용하지 않았습니다. 삭제 표시된 DBF 행을 반복자가 건너뛰면서 개수만 일치하는 문제를 놓치지 않도록 ZIP 내부 SHP/SHX/DBF를 물리 레코드 단위로 직접 읽었습니다.

1. ZIP의 모든 멤버 CRC를 검사했습니다.
2. SHP 파일 길이·레코드 번호·타입·내용 길이와 SHX의 오프셋·길이를 모든 항목에서 맞췄습니다. 마지막 레코드 뒤에 읽지 않은 데이터가 남지 않았습니다.
3. DBF 헤더 개수·행 길이·필드 길이·모든 삭제 플래그를 검사했습니다. 삭제 레코드, null 도형, 비정상 높이는 없었습니다.
4. 물리 원본 레코드 번호와 같은 SQLite ID를 찾아 HEIGHT와 전체 좌표를 대조했습니다. 선은 모든 파트 길이와 순서를 함께 비교했습니다.
5. 원본과 DB 각각에서 모든 레코드의 ID·도형 타입·파트 길이·좌표 및 ID·높이 스트림의 SHA-256을 만들었습니다. 네 쌍이 모두 일치했습니다.
6. 전체 DB ID와 공간 인덱스 ID의 동일성, 각 공간 인덱스의 원본 도형 포함 여부를 확인했습니다. `PRAGMA integrity_check` 결과는 `ok`였습니다.
7. 2/8/25/60m 표시용 단순화 캐시는 각 8,570개이고 원본 없는 캐시는 0개였습니다. 이 캐시는 원본을 대체하지 않습니다. 이번 검사는 캐시 생성 자체의 정확도까지 재검증한 것은 아닙니다.

## 원본 적재와 화면·보간 범위의 차이

- **원본 적재:** 위 선·점과 HEIGHT는 ZIP 대비 100% 보존됐습니다. 이는 데이터 파일 내 기록의 완전성 검사입니다.
- **화면 표시:** 낮은 줌에서는 10/25m 간격으로 선을 거르고 형태를 단순화합니다. 표고점은 줌 13 미만에서 숨깁니다. 응답은 최대 등고선 2,500개·좌표 80,000개·표고점 1,800개로 제한됩니다. 따라서 넓은 화면의 선·점이 모두 보이지 않을 수 있습니다. 이는 DB 원본 누락과 다릅니다.
- **높이 조회:** 클릭 지점 자체의 측정값을 만드는 대신 1km 미만 거리의 가장 가까운 원본 표고점의 기록 높이와 거리를 반환합니다. 조건을 만족하는 점이 없으면 값 없음으로 처리합니다.
- **2.5D:** 등고선 30m 표본과 원본 표고점을 합친 보간 제약점으로 TIN 표면을 만듭니다. 회색으로 표시되지 않은 곳도 원본 선·점 사이에서는 추정 지형입니다. 표면 연속성을 위해 외곽에는 높이 연장이 포함되며 이 값을 원본 표고점 조회에 사용하지 않습니다.
- **공간 범위:** 원본의 사각형 extent는 서울 행정경계가 아닙니다. 전체 적재율을 서울 행정구역의 측량 면적 비율로 해석할 수 없습니다.

동일 세션에서 별도로 검사한 보간 지원 마스크는 Overture 서울 행정경계(`data/building-source/seoul-boundary.geojson`) 내부 z12 픽셀 중심 661,951개 중 654,166개가 지원됨, 7,785개가 지원 밖이었습니다. 픽셀 간격 약 30.3m 표본 기준 **보간 지원 비율 98.824%**입니다. 이는 별도 마스크 표본 검사 결과이며 **실측 높이 보유율·원본 적재율·정밀한 면적 측량 결과가 아닙니다.** 경계 버전과 픽셀 표본에 따라 수치가 달라집니다. 위 SHP 전수 비교 스크립트는 이 별도 비율을 다시 계산하지 않습니다.

로컬 출처 메타데이터는 [서울열린데이터광장 OA-22241](https://data.seoul.go.kr/dataList/OA-22241/F/1/datasetView.do), 2023년 기준, 첨부일 2025-03-20을 기록하고 있습니다. 원본의 수직 기준과 현장 오차는 이 감사에서 확인하지 않았습니다. 공사 이후 지형, 건물, 교량, 옹벽, 지하 공간의 현재 높이를 보장하지 않습니다.

## 입력과 전체 스트림 지문

| 대상 | SHA-256 |
|---|---|
| 원본 ZIP (45,852,601 bytes) | `4fbe3c7e061b5974e7403ec116855304ed8ae321eebcc0d12c31ca8fb7be30bf` |
| SQLite (114,352,128 bytes) | `174c2be320eb9db0f18d918e9b75c0f708623c06bbf5776a2d882f40fe5bc28d` |
| 등고선 전체 도형 — 원본=DB | `3739a0b046533e1207c985a05c1c0abb78b06e1624496dfc5d00d9bd648198bc` |
| 등고선 전체 높이 — 원본=DB | `542e0126adb72995f58091dbd3c3803bb6d185c77ff6b4400b2673701998f0ef` |
| 표고점 전체 도형 — 원본=DB | `658ecf54fd257aaf77dbdc9da8c68787dbb49e842ea9262ca5e08aba1d725242` |
| 표고점 전체 높이 — 원본=DB | `d22b6ce60529d07352bd8040948ed718df52fec12ea08c7e82186363f6fa2f6e` |

DB 메타데이터 `source_sha256`도 실제 ZIP과 일치합니다. 감사 전후 ZIP과 DB의 파일 지문이 같으므로 이 검사는 두 파일을 수정하지 않았습니다. 이후 재생성된 DB는 SQLite 파일 지문이 달라질 수 있어 다시 비교해야 합니다.

## 재현

기존 프로젝트 `.venv`의 numpy·pyproj·shapely를 사용했습니다. 아래 독립 검사 코드를 `/tmp/seoul-contour-audit.py`로 저장한 뒤 프로젝트에서 실행합니다. 성공 시 `passed: true`와 각 검사 통계를 출력합니다. 불일치·삭제 레코드·잘못된 구조를 발견하면 예외로 중단합니다. 원본/DB 파일을 새로 만들거나 바꾸는 코드는 없습니다.

```sh
.venv/bin/python /tmp/seoul-contour-audit.py "$PWD" > /tmp/seoul-contour-audit.json
```

```python
"""Independent read-only audit: decode physical SHP/SHX/DBF, then compare SQLite."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import struct
import sys
import zipfile

import numpy as np
from pyproj import CRS
from shapely import from_wkb


ROOT = Path(sys.argv[1]).resolve()
SOURCE = ROOT / 'data/seoul-contours.zip'
DATABASE = ROOT / 'data/terrain.sqlite'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


before = {'source': sha(SOURCE), 'database': sha(DATABASE)}
report = {'audited_at_utc': datetime.now(timezone.utc).isoformat(),
          'source_sha256': before['source'], 'database_sha256': before['database'],
          'source_bytes': SOURCE.stat().st_size, 'database_bytes': DATABASE.stat().st_size,
          'comparison': 'all physical records; exact float64 HEIGHT and all ordered XY coordinates/parts, no tolerance',
          'layers': {}}

with sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True) as db, zipfile.ZipFile(SOURCE) as archive:
    db.execute('PRAGMA query_only=ON')
    report['sqlite_integrity_check'] = [r[0] for r in db.execute('PRAGMA integrity_check')]
    require(report['sqlite_integrity_check'] == ['ok'], 'SQLite integrity failure')
    require(archive.testzip() is None, 'ZIP CRC failure')
    report['zip_crc_check'] = 'all members passed'
    metadata = {k: json.loads(v) for k, v in db.execute('SELECT key,value FROM metadata')}
    require(metadata['source_sha256'] == before['source'], 'metadata source hash mismatch')
    report['metadata_source_sha256_matches'] = True
    report['source_metadata'] = metadata
    for table, stem, expected_type, index in (
        ('contours', '등고선 5000/N3L_F001', 3, 'contour_index'),
        ('spots', '표고 5000/N3P_F002', 1, 'spot_index'),
    ):
        shp, shx, dbf = [archive.read(stem + '.' + ext) for ext in ('shp', 'shx', 'dbf')]
        require(len(shp) == struct.unpack_from('>I', shp, 24)[0] * 2, table + ' SHP file length')
        require(len(shx) == struct.unpack_from('>I', shx, 24)[0] * 2, table + ' SHX file length')
        require(struct.unpack_from('>I', shp, 0)[0] == 9994, table + ' SHP magic')
        require(struct.unpack_from('<I', shp, 28)[0] == 1000, table + ' SHP version')
        require(struct.unpack_from('<I', shp, 32)[0] == expected_type, table + ' SHP type')
        require((len(shx) - 100) % 8 == 0, table + ' incomplete SHX')
        count, header_length, record_length = struct.unpack_from('<IHH', dbf, 4)
        require((len(shx) - 100) // 8 == count, table + ' SHX/DBF count')
        require(dbf[header_length - 1] == 13, table + ' DBF header terminator')
        require(len(dbf) >= header_length + count * record_length, table + ' truncated DBF')
        require(dbf[header_length + count * record_length:] in (b'', b'\x1a'), table + ' unexpected DBF tail')
        fields, field_offset = {}, 1
        for offset in range(32, header_length - 1, 32):
            descriptor = dbf[offset:offset + 32]
            name = descriptor[:11].split(b'\0', 1)[0].decode('ascii')
            width = descriptor[16]
            fields[name] = {'offset': field_offset, 'width': width,
                            'type': chr(descriptor[11]), 'decimals': descriptor[17]}
            field_offset += width
        require(field_offset == record_length, table + ' DBF field lengths')
        require(fields['HEIGHT']['type'] == 'N', table + ' HEIGHT type')
        crs = CRS.from_wkt(archive.read(stem + '.prj').decode())
        require(crs.to_epsg() == 5174, table + ' CRS')
        db_ids = {r[0] for r in db.execute(f'SELECT id FROM {table}')}
        index_rows = {r[0]: r[1:] for r in db.execute(f'SELECT id,minx,maxx,miny,maxy FROM {index}')}
        require(db_ids == set(range(1, count + 1)), table + ' missing/extra/reordered IDs')
        require(set(index_rows) == db_ids, table + ' spatial index IDs')
        stats = {'physical_dbf_records': count, 'physical_shp_records': 0, 'shx_entries': count,
                 'database_rows': len(db_ids), 'deleted_dbf_records': 0, 'null_shapes': 0,
                 'source_crs_epsg': crs.to_epsg(), 'dbf_fields': fields,
                 'total_vertices': 0, 'total_parts': 0, 'geometry_types': Counter(),
                 'height_range_m': [math.inf, -math.inf], 'negative_height_count': 0,
                 'null_or_nonfinite_height_count': 0, 'height_mismatches': 0,
                 'geometry_mismatches': 0, 'major_mismatches': 0, 'spot_xy_mismatches': 0,
                 'rtree_missing': 0, 'rtree_not_enclosing_source': 0, 'max_rtree_outward_rounding_m': 0.0,
                 'bounds_native': [math.inf, math.inf, -math.inf, -math.inf]}
        hashes = {side: {kind: hashlib.sha256() for kind in ('geometry', 'height')} for side in ('source', 'database')}
        offset = 100
        for identifier in range(1, count + 1):
            label = f'{table} physical record {identifier}'
            start = header_length + (identifier - 1) * record_length
            record = dbf[start:start + record_length]
            stats['deleted_dbf_records'] += int(record[:1] == b'*')
            require(record[:1] in (b' ', b'*'), label + ' invalid deletion flag')
            require(record[:1] != b'*', label + ' deleted physical source record: stop for explicit assessment')
            field = fields['HEIGHT']
            height_text = record[field['offset']:field['offset'] + field['width']].decode('ascii').strip()
            height = float(height_text)
            require(math.isfinite(height), label + ' nonfinite HEIGHT')
            record_number, words = struct.unpack_from('>II', shp, offset)
            require(record_number == identifier, label + ' SHP record number')
            index_offset, index_words = struct.unpack_from('>II', shx, 100 + (identifier - 1) * 8)
            require((index_offset * 2, index_words) == (offset, words), label + ' SHX offset/size')
            payload = memoryview(shp)[offset + 8:offset + 8 + words * 2]
            require(len(payload) == words * 2, label + ' truncated payload')
            shape_type = struct.unpack_from('<I', payload, 0)[0]
            stats['null_shapes'] += int(shape_type == 0)
            require(shape_type == expected_type, label + ' unexpected shape type')
            if shape_type == 3:
                part_count, point_count = struct.unpack_from('<II', payload, 36)
                starts = np.frombuffer(payload, dtype='<u4', count=part_count, offset=44)
                require(part_count > 0 and starts[0] == 0, label + ' first part')
                ends = np.append(starts[1:], point_count)
                require(np.all(ends > starts), label + ' empty/misordered part')
                require(len(payload) == 44 + part_count * 4 + point_count * 16, label + ' shape bytes')
                source_xy = np.frombuffer(payload, dtype='<f8', count=point_count * 2, offset=44 + part_count * 4).reshape((-1, 2))
                source_lengths = (ends - starts).astype('<u4')
            else:
                require(len(payload) == 20, label + ' point bytes')
                point_count, part_count = 1, 1
                source_xy = np.frombuffer(payload, dtype='<f8', count=2, offset=4).reshape((-1, 2))
                source_lengths = np.array([1], dtype='<u4')
            require(np.isfinite(source_xy).all(), label + ' nonfinite XY')
            row = db.execute(f'SELECT height_m,wkb FROM {table} WHERE id=?', (identifier,)).fetchone()
            geometry = from_wkb(row[1])
            db_parts = list(geometry.geoms) if geometry.geom_type == 'MultiLineString' else [geometry]
            db_xy = np.concatenate([np.asarray(part.coords, dtype='<f8') for part in db_parts])
            db_lengths = np.array([len(part.coords) for part in db_parts], dtype='<u4')
            expected_geometry = 'Point' if shape_type == 1 else ('LineString' if part_count == 1 else 'MultiLineString')
            same_geometry = (geometry.geom_type == expected_geometry and
                             source_lengths.tobytes() == db_lengths.tobytes() and
                             source_xy.tobytes() == db_xy.tobytes())
            stats['geometry_mismatches'] += int(not same_geometry)
            stats['height_mismatches'] += int(struct.pack('<d', height) != struct.pack('<d', row[0]))
            for side, xy, lengths, value in [('source', source_xy, source_lengths, height), ('database', db_xy, db_lengths, row[0])]:
                hashes[side]['geometry'].update(struct.pack('<QII', identifier, shape_type, len(lengths)) + lengths.tobytes() + xy.tobytes())
                hashes[side]['height'].update(struct.pack('<Qd', identifier, value))
            if table == 'contours':
                field = fields['DIVI']
                divi = record[field['offset']:field['offset'] + field['width']].decode('ascii').strip()
                major = db.execute('SELECT major FROM contours WHERE id=?', (identifier,)).fetchone()[0]
                stats['major_mismatches'] += int(major != int(divi == 'CTD001'))
                require(height % 5 == 0, label + ' non-5m HEIGHT')
            else:
                xy = db.execute('SELECT x,y FROM spots WHERE id=?', (identifier,)).fetchone()
                stats['spot_xy_mismatches'] += int(struct.pack('<dd', *xy) != source_xy.tobytes())
            low, high = source_xy.min(axis=0), source_xy.max(axis=0)
            x1, x2, y1, y2 = index_rows[identifier]
            stats['rtree_not_enclosing_source'] += int(not (x1 <= low[0] <= high[0] <= x2 and y1 <= low[1] <= high[1] <= y2))
            slack = [low[0] - x1, x2 - high[0], low[1] - y1, y2 - high[1]]
            stats['max_rtree_outward_rounding_m'] = max(stats['max_rtree_outward_rounding_m'], *map(float, slack))
            bounds = stats['bounds_native']
            stats['bounds_native'] = [min(bounds[0], float(low[0])), min(bounds[1], float(low[1])), max(bounds[2], float(high[0])), max(bounds[3], float(high[1]))]
            stats['physical_shp_records'] += 1
            stats['total_vertices'] += point_count
            stats['total_parts'] += part_count
            stats['geometry_types'][geometry.geom_type] += 1
            stats['height_range_m'] = [min(stats['height_range_m'][0], height), max(stats['height_range_m'][1], height)]
            stats['negative_height_count'] += int(height < 0)
            offset += 8 + words * 2
        require(offset == len(shp), table + ' trailing unparsed SHP records/bytes')
        for key in ('geometry_mismatches', 'height_mismatches', 'major_mismatches', 'spot_xy_mismatches', 'rtree_not_enclosing_source'):
            require(stats[key] == 0, f'{table} {key}: {stats[key]}')
        stats['digests'] = {side: {kind: h.hexdigest() for kind, h in kinds.items()} for side, kinds in hashes.items()}
        require(stats['digests']['source'] == stats['digests']['database'], table + ' full-stream hashes differ')
        report['layers'][table] = stats
    report['lod_counts_by_tolerance_m'] = {r[0]: r[1] for r in db.execute('SELECT tolerance_m,count(*) FROM contour_lod GROUP BY tolerance_m')}
    require(report['lod_counts_by_tolerance_m'] == {2: 8570, 8: 8570, 25: 8570, 60: 8570}, 'LOD missing')
    report['lod_orphans'] = db.execute('SELECT count(*) FROM contour_lod l LEFT JOIN contours c ON c.id=l.contour_id WHERE c.id IS NULL').fetchone()[0]
    require(report['lod_orphans'] == 0, 'LOD orphans')

after = {'source': sha(SOURCE), 'database': sha(DATABASE)}
require(before == after, 'Audit input files changed during read-only audit')
report['source_and_database_unchanged_after_audit'] = True
report['passed'] = True
print(json.dumps(report, ensure_ascii=False, indent=2))
```
