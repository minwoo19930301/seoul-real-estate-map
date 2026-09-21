#!/usr/bin/env python3
"""Public-source scheduling inventory; never generate geometry or infer likeness.

Default runs use the committed public-field snapshot, so CI needs no private DB.
Capture is explicit and reads downloaded source files without changing source DBs.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import os

ROOT = Path(__file__).resolve().parents[1]
AUDIT = Path('docs/model-audit')
CLASSES = {'아파트', '주상복합', '도시형 생활주택(아파트)', '도시형 생활주택(주상복합)'}
OA_URL = 'https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do'
KAPT_URL = 'https://www.data.go.kr/data/15073271/fileData.do'
PUBLIC_FIELDS = {'sourceId', 'sourceRow', 'code', 'nameKo', 'classification', 'households', 'buildingCount', 'district', 'address', 'sourceCoordinate'}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    path = Path(path)
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', delete=False) as f:
        temp = Path(f.name)
        f.write(data)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def number(value):
    value = str(value or '').strip()
    if not value or value.lower() in {'null', 'nan'}:
        return None
    if not re.fullmatch(r'\d+(?:\.0+)?', value):
        raise ValueError('Invalid nonnegative integer: ' + repr(value))
    return int(value.split('.')[0])


def capture(oa_csv, count_response, kapt_xlsx, kapt_manifest, checked_on, root, oa_updated_on):
    # This is the same streaming reader used by the existing source importer.
    sys.path.insert(0, str(ROOT))
    from scripts.import_apartment_sources import xlsx_rows
    oa = list(csv.DictReader(io.StringIO(oa_csv.read_bytes().decode('cp949'))))
    count = re.search(r'totalCount\s*:\s*(\d+)', count_response.read_text())
    if not count or len(oa) != int(count.group(1)):
        raise ValueError('OA CSV count does not match independent full-sheet count')
    rows = []
    for i, r in enumerate(oa, 2):
        if r['주소(시도)k-apt주소split'] not in {'서울', '서울특별시'}:
            raise ValueError('Unexpected non-Seoul OA record')
        point = None
        try:
            lon, lat = float(r['좌표X']), float(r['좌표Y'])
            if math.isfinite(lon) and math.isfinite(lat):
                point = [lon, lat]
        except (ValueError, TypeError):
            pass
        rows.append({'sourceId': 'oa-15818', 'sourceRow': i, 'code': r['k-아파트코드'],
                     'nameKo': r['k-아파트명'], 'classification': r['k-단지분류(아파트,주상복합등등)'],
                     'households': number(r['k-전체세대수']), 'buildingCount': number(r['k-전체동수']),
                     'district': r['주소(시군구)'], 'address': r['kapt도로명주소'], 'sourceCoordinate': point})
    if len({r['code'] for r in rows}) != len(rows):
        raise ValueError('OA has duplicate management codes')
    headers = None
    national_count = 0
    for i, cells in xlsx_rows(kapt_xlsx):
        if i == 2:
            headers = cells
        elif i > 2 and cells:
            r = {headers[k]: v for k, v in cells.items() if k in headers}
            national_count += 1
            if r.get('시도') != '서울특별시':
                continue
            rows.append({'sourceId': 'kapt-weekly', 'sourceRow': i, 'code': r.get('단지코드', ''),
                         'nameKo': r.get('단지명', ''), 'classification': r.get('단지분류', ''),
                         'households': number(r.get('세대수')), 'buildingCount': number(r.get('동수')),
                         'district': r.get('시군구', ''), 'address': r.get('도로명주소', ''), 'sourceCoordinate': None})
    km = read(kapt_manifest)
    if digest(kapt_xlsx) != km['files'][kapt_xlsx.name]['sha256']:
        raise ValueError('K-apt workbook does not match acquisition manifest')
    source_rows = Counter(r['sourceId'] for r in rows)
    snapshot = {'version': 1, 'checkedOn': checked_on, 'records': rows,
                'sources': {'oa-15818': {'url': OA_URL, 'observedPortalUpdatedOn': oa_updated_on, 'sha256': digest(oa_csv),
                    'bytes': oa_csv.stat().st_size, 'rows': len(oa), 'independentCount': int(count.group(1)),
                    'license': '공공누리 제1유형', 'dateMeaning': 'Portal update label; does not prove every row was revised on that day.'},
                    'kapt-weekly': {'url': KAPT_URL, 'downloadUrl': km['download_url'], 'noticeUrl': km['notice_url'],
                    'extractDate': km['notice_extract_date'], 'sha256': digest(kapt_xlsx), 'bytes': kapt_xlsx.stat().st_size,
                    'nationalRows': national_count, 'rows': source_rows['kapt-weekly'],
                    'license': '공공데이터포털 이용허락범위 제한 없음',
                    'dateMeaning': 'Weekly reference extract, not real-time API; repeated address rows are retained.'}},
                'locationSnapshot': {}, 'privacy': 'Allowlisted management code/name/class/count/district/road-address/coordinates only; no raw rows, contacts, resident data, phone numbers or authentication state.'}
    db_path = root / 'data/apartments.sqlite'
    if db_path.exists():
        db = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        for code, lon, lat, status, method, url, issues in db.execute('SELECT code,lon,lat,coordinate_status,location_method,coordinate_source_url,coordinate_issues FROM apartments'):
            snapshot['locationSnapshot'][code] = {'coordinate': [lon, lat] if lon is not None and lat is not None else None,
                'status': status, 'method': method, 'sourceUrl': url, 'issues': json.loads(issues),
                'validationDate': '2026-09-10', 'note': 'Previously audited display location by exact management code; not a fresh site-boundary or per-building survey.'}
        db.close()
    return snapshot


def validate_snapshot(snapshot):
    source_rows = Counter()
    oa_codes = set()
    for r in snapshot['records']:
        if set(r) != PUBLIC_FIELDS:
            raise ValueError('Snapshot record has unexpected/missing public fields')
        if not re.fullmatch(r'[A-Z]\d{8}', r['code']):
            raise ValueError('Invalid management code: ' + r['code'])
        if r['sourceId'] not in snapshot['sources']:
            raise ValueError('Unknown source')
        for field in ['households', 'buildingCount']:
            if r[field] is not None and (type(r[field]) is not int or r[field] < 0):
                raise ValueError('Invalid ' + field)
        if r['sourceId'] == 'oa-15818':
            if r['code'] in oa_codes:
                raise ValueError('Duplicate OA management code')
            oa_codes.add(r['code'])
        source_rows[r['sourceId']] += 1
    for source, meta in snapshot['sources'].items():
        if source_rows[source] != meta['rows']:
            raise ValueError('Source count mismatch: ' + source)


def checked_file(root, relative, expected):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not re.fullmatch(r'[0-9a-f]{64}', expected or ''):
        return False
    candidate = root / path
    return candidate.is_file() and digest(candidate) == expected


def successful_mcp_file(root, proof):
    if not isinstance(proof, dict) or proof.get('tool') != 'execute_blender_code' or not checked_file(root, proof.get('path', ''), proof.get('sha256')):
        return False
    try:
        calls = read(root / proof['path'])
    except (OSError, ValueError):
        return False
    return isinstance(calls, list) and any(
        isinstance(call, dict) and call.get('tool') == 'execute_blender_code'
        and call.get('isError') is False and isinstance(call.get('content'), list) and any(
            isinstance(content, dict) and 'Code executed successfully' in str(content.get('text', ''))
            for content in call['content'])
        for call in calls)


def verify_asset(root, asset, published, building_identity=None):
    if not asset or not asset['id'].startswith('bespoke-'):
        return ['not_published_bespoke']
    record = asset.get('sourceRecord', {})
    site = published.get('sites', {}).get(record.get('siteId'), {})
    review = site.get('review', {})
    errors = []
    if review.get('status') != 'visually-reviewed' or not site.get('sources') or not review.get('comparisons'):
        errors.append('photo_comparison_review_missing')
    if record.get('modelingBasis') == 'representative-photo-inference':
        references = record.get('inferredFrom', [])
        if not references or not record.get('inferenceScope') or asset['id'] not in review.get('inferenceApprovedAssets', []):
            errors.append('representative_inference_review_missing')
        for reference in references:
            source_site = published.get('sites', {}).get(reference.get('siteId'), {})
            if not any(p['id'] == reference.get('id') and p.get('sha256') == reference.get('sha256')
                       for p in source_site.get('assets', [])):
                errors.append('representative_source_proof_mismatch')
    source_hash = record.get('sourceGlbSha256')
    # Publisher may rename the raw GLB to the public asset ID. Bind the source
    # hash through the explicit asset proof rather than assuming equal filenames.
    reviewed_files = [name for name, value in review.get('reviewedInputs', {}).items()
                      if name.endswith('.glb') and value == source_hash]
    if not reviewed_files:
        errors.append('review_source_geometry_hash_mismatch')
    proof_asset = next((p for p in site.get('assets', []) if p['id'] == asset['id']), {})
    if proof_asset.get('sha256') != asset.get('sha256') or proof_asset.get('sourceSha256') != source_hash:
        errors.append('published_geometry_proof_mismatch')
    if not checked_file(root, 'public/models/' + asset['model'], asset.get('sha256')):
        errors.append('published_glb_missing_or_hash_mismatch')
    if not checked_file(root, record.get('blendSource', ''), record.get('blendSha256')):
        errors.append('editable_blend_missing_or_hash_mismatch')
    if not any(name.endswith('.blend') and value == record.get('blendSha256')
               for name, value in review.get('reviewedInputs', {}).items()):
        errors.append('review_editable_blend_hash_mismatch')
    evidence = site.get('mcpEvidence', [])
    if not evidence or not all(successful_mcp_file(root, p) for p in evidence):
        errors.append('mcp_execution_proof_missing_or_hash_mismatch')
    if not asset.get('footprintIds'):
        # New construction can lack retained source footprints. Its numbered
        # plan must instead identify one explicit, individually replaced asset.
        identity = building_identity or {}
        if not (identity.get('sourceUrl') and identity.get('retainedAssetId')
                and identity['retainedAssetId'] in asset.get('supersedes', [])):
            errors.append('building_ownership_missing')
    return errors


def build(snapshot, coverage, bespoke, published, legacy, root):
    validate_snapshot(snapshot)
    grouped = defaultdict(list)
    for r in snapshot['records']:
        grouped[r['code']].append(r)
    assets = {a['id']: a for a in bespoke['assets']}
    if len(assets) != len(bespoke['assets']):
        raise ValueError('Duplicate bespoke asset ID')
    legacy_ids = {a['id'] for a in legacy['assets']}
    definitions = {x['code']: x for x in coverage['complexes']}
    if len(definitions) != len(coverage['complexes']):
        raise ValueError('Duplicate coverage management code')
    assigned = defaultdict(set)
    for d in definitions.values():
        labels = [b['label'] for b in d.get('buildings', [])]
        ids = [b['assetId'] for b in d.get('buildings', []) if b.get('assetId')]
        if len(labels) != len(set(labels)) or len(ids) != len(set(ids)):
            raise ValueError('Duplicate building label or asset within one management code')
        for component in d.get('buildings', []):
            if component.get('assetId'):
                assigned[component['assetId']].add(d['code'])
    if any(len(v) > 1 for v in assigned.values()):
        raise ValueError('A bespoke building is assigned to multiple management codes; requires explicit shared-site allocation review')
    address_codes = defaultdict(set)
    for code, records in grouped.items():
        for r in records:
            if r['address'].strip():
                address_codes[(r['district'], re.sub(r'\s+', '', r['address']))].add(code)
    queue = []
    for code, records in sorted(grouped.items()):
        qualifying = [r for r in records if (r['households'] or 0) >= 400]
        if not qualifying:
            continue
        good = [r for r in qualifying if r['classification'] in CLASSES]
        unknown = [r for r in qualifying if not r['classification']]
        eligibility = 'eligible' if good else 'eligibility_review' if unknown else 'scope_excluded'
        preferred = next((r for r in records if r['sourceId'] == 'oa-15818'), records[0])
        household_values = sorted({r['households'] for r in records if r['households'] is not None})
        building_values = sorted({r['buildingCount'] for r in records if r['buildingCount']})
        same_address = sorted({other for r in records for other in address_codes.get((r['district'], re.sub(r'\s+', '', r['address'])), set()) if other != code})
        d = definitions.get(code, {})
        buildings = []
        for c in d.get('buildings', []):
            a = assets.get(c.get('assetId'))
            errors = verify_asset(root, a, published, c.get('buildingIdentity'))
            if c.get('reviewRequiredReason'):
                errors.append('building_correction_review_required')
            if a and c.get('photoReviewSiteId') != a.get('sourceRecord', {}).get('siteId'):
                errors.append('building_photo_review_site_mismatch')
            buildings.append({**c, 'evidenceVerified': not errors, 'verificationErrors': errors,
                              'modelingBasis': a.get('sourceRecord', {}).get('modelingBasis', 'individual-photo-review') if a else None,
                              'publishedSha256': a.get('sha256') if a else None})
        verified = sum(c['evidenceVerified'] for c in buildings)
        inferred = sum(c['evidenceVerified'] and c['modelingBasis'] == 'representative-photo-inference' for c in buildings)
        expected = d.get('expectedResidentialBuildingCount')
        evidence_full = bool(expected and len(buildings) == expected and verified == expected)
        if eligibility != 'eligible':
            status = eligibility
        elif d.get('coverageApproved') and evidence_full and d.get('photoCoverageBasis') and d.get('buildingIdentitySource'):
            status = 'complete_residential_buildings'
        elif buildings:
            status = 'coverage_review_needed' if d.get('coverageReviewRequired') or evidence_full else 'partial'
        else:
            status = 'not_started'
        addresses = sorted({r['address'] for r in records if r['address']})
        queue.append({'code': code, 'nameKo': preferred['nameKo'], 'district': preferred['district'],
            'eligibility': eligibility, 'eligibilityBasis': 'At least one official apartment-class record has >=400 households; values are never summed.' if good else 'Households >=400 but official apartment classification is missing.' if unknown else 'Only explicitly non-apartment classifications meet threshold.',
            'householdEvidence': records, 'householdValues': household_values, 'householdDisagreement': len(household_values) > 1,
            'officialBuildingCountValues': building_values, 'addresses': addresses,
            'location': snapshot.get('locationSnapshot', {}).get(code, {'coordinate': None, 'status': 'not_previously_resolved'}),
            'physicalSiteId': d.get('physicalSiteId'), 'physicalSiteMappingStatus': 'reviewed_explicit' if d.get('physicalSiteId') else 'unresolved',
            'sameAddressManagementCodes': same_address, 'sameAddressMeaning': 'Review candidates only; never merged or summed automatically.',
            'modelStatus': status, 'expectedResidentialBuildingCount': expected,
            'verifiedBespokeBuildingCount': verified, 'representativeInferredBuildingCount': inferred, 'buildings': buildings,
            'coverageBasis': {k: d[k] for k in ['photoCoverageBasis', 'buildingIdentitySource', 'limits', 'reviewReason'] if k in d},
            'legacyAssetIds': ['apt-' + code.lower()] if 'apt-' + code.lower() in legacy_ids else [],
            'legacyMeaning': 'Fallback/template inventory only; no visual completion credit.'})
    disposition = Counter(r['modelStatus'] for r in queue)
    all_kapt = [r for r in snapshot['records'] if r['sourceId'] == 'kapt-weekly']
    kapt_counts = Counter(r['code'] for r in all_kapt)
    summary = {'version': 1, 'checkedOn': snapshot['checkedOn'], 'sources': snapshot['sources'],
        'managementCodes': len(queue), 'eligibleManagementCodes': sum(r['eligibility'] == 'eligible' for r in queue),
        'eligibilityReviewManagementCodes': sum(r['eligibility'] == 'eligibility_review' for r in queue),
        'explicitNonApartmentExcludedCodes': sum(r['eligibility'] == 'scope_excluded' for r in queue),
        'completedManagementCodes': disposition['complete_residential_buildings'],
        'representativeInferredBuildingCount': sum(r['representativeInferredBuildingCount'] for r in queue),
        'remainingEligibleManagementCodes': sum(r['eligibility'] == 'eligible' and r['modelStatus'] != 'complete_residential_buildings' for r in queue),
        'modelStatusCounts': dict(sorted(disposition.items())),
        'sourceEligibleUniqueCodes': {s: len({r['code'] for r in snapshot['records'] if r['sourceId'] == s and r['classification'] in CLASSES and (r['households'] or 0) >= 400}) for s in snapshot['sources']},
        'kaptSeoulUniqueCodes': len(kapt_counts), 'kaptRepeatedCodes': sum(v > 1 for v in kapt_counts.values()),
        'kaptExtraAddressRows': sum(v - 1 for v in kapt_counts.values()),
        'unknownUniquePhysicalSiteCount': None, 'sameAddressCandidateCodes': sum(bool(r['sameAddressManagementCodes']) for r in queue),
        'coordinatesUnresolvedEligible': sum(not r['location'].get('coordinate') for r in queue if r['eligibility'] == 'eligible'),
        'scope': 'Official management-code scheduling inventory; completion means all identified residential buildings have verified Blender MCP and visual-review evidence. Representative-photo inference is explicitly counted separately from individual photo review. Shared podiums, landscape and unseen facades are not thereby certified. Not proof that all real Seoul complexes are registered.'}
    return queue, summary


def markdown(summary, queue):
    s = summary
    examples = [r for r in queue if r['buildings'] or r['code'] in {'A10023043', 'A10023188'}]
    lines = ['# 서울 400세대 이상 아파트 개별 모델링 현황', '',
        f"공식 자료 확인일: {s['checkedOn']}. `scripts/build_apartment_bespoke_queue.py`로 생성합니다. **대상 {s['eligibleManagementCodes']:,} 관리코드, 주거동 전체 검토 완료 {s['completedManagementCodes']:,}, 미완료 {s['remainingEligibleManagementCodes']:,}**입니다. 분류 보강 검토 {s['eligibilityReviewManagementCodes']}건과 명시적 비아파트 제외 {s['explicitNonApartmentExcludedCodes']}건은 큐에 별도로 남깁니다.", '',
        '## 모수와 중복', '',
        f"[서울시 OA-15818]({OA_URL}) 최신 전체 CSV {s['sources']['oa-15818']['rows']:,}행을 독립 Sheet totalCount와 대조했습니다. 400세대 이상 아파트 분류는 {s['sourceEligibleUniqueCodes']['oa-15818']:,}코드입니다. [국토교통부·K-apt 주간자료]({KAPT_URL}) {s['sources']['kapt-weekly']['extractDate']} 추출본은 전국 {s['sources']['kapt-weekly']['nationalRows']:,}행, 서울 {s['sources']['kapt-weekly']['rows']:,}행·고유 {s['kaptSeoulUniqueCodes']:,}코드이고 이 중 대상은 {s['sourceEligibleUniqueCodes']['kapt-weekly']:,}코드입니다. 두 자료의 관리코드 합집합이 대상 모수입니다.", '',
        f"K-apt 서울 자료의 {s['kaptRepeatedCodes']}코드에는 복수 주소 등에 따른 추가 {s['kaptExtraAddressRows']}행이 있습니다. 원본 행 번호와 값은 보존하지만 세대수를 합산하지 않습니다. 서로 다른 관리코드의 동일 주소도 자동으로 같은 단지로 합치지 않습니다. 동일 주소 검토 후보가 있는 큐 기록은 {s['sameAddressCandidateCodes']}개입니다. 실제 고유 단지 수는 아직 확정하지 않았습니다.", '',
        '어느 한 공식 아파트 분류 자료에서 400세대 이상이면 포함합니다. 출처 간 값이 다르거나 서울시 원본이 0이어도 덮어쓰지 않습니다. 메이플자이의 서울시 0/K-apt 3,307, 타워팰리스1차의 0/1,297은 각각 같은 관리코드의 두 근거로 남습니다. 원베일리는 이미 A10023043·2,990세대·23동으로 포함되어 있어 별도 신규 단지로 중복 추가하지 않습니다. 미분류 기록은 이름만으로 아파트로 확정하지 않습니다.', '',
        '## 완료 기준', '',
        '관리코드별 명시적인 주거동 목록, 동별 bespoke ID, 실제 사진·배치도 대조 기록, 검토된 원본 GLB SHA, 게시 GLB SHA, 편집 .blend SHA, 실제 MCP 실행 기록 SHA가 모두 일치해야 완료로 계산합니다. 기존 generic/reference 모델, 동일색·높은 삼각형 수, 파일 생성만으로 완료 처리하지 않습니다. 해시 불일치나 사라진 파일은 완료를 자동 해제합니다.', '',
        '2026-09-22 사용자 지시에 따라 대표 동의 사진 검토된 외관을 같은 단지의 다른 동에 적용할 수 있습니다. 동별 배치·층수·윤곽은 따로 유지하며, 대표 모델 ID·해시와 추정 범위를 기록합니다. 표의 대표 외관 추정 동은 각 동의 모든 면을 사진으로 확인했다는 뜻이 아닙니다.', '',
        '| 관리코드 | 단지 | 상태 | 검증된 bespoke / 확인된 주거동 | 대표 외관 추정 동 |', '|---|---|---|---:|---:|']
    for r in examples:
        lines.append(f"| {r['code']} | {r['nameKo']} | {r['modelStatus']} | {r['verifiedBespokeBuildingCount']} / {r['expectedResidentialBuildingCount'] or '미확정'} | {r['representativeInferredBuildingCount']} |")
    lines += ['', '타워팰리스·SKY-L65의 완료는 명시된 주거타워에 한정합니다. 공용 저층부·스포츠센터·조경까지 완공 모델이라는 뜻이 아닙니다. 메이플 주거29동에는 대표 외관 추정18동이 포함되며, 등록 높이와 장식·설비를 포함한 모델 높이는 별도로 기록합니다. 원베일리는 주거23동 중 검증된 동만 집계합니다. 하이페리온은 구조설계자의 배치도로 A/C가 아파트, B가 오피스텔임을 확인했습니다. 아파트 수는 A/C 두 동만 계산하며, 기존 높이와 2004년 구조자료의 최고높이 기준 대조가 남아 완료를 보류합니다.', '',
        '## 위치·자료 한계와 재현', '',
        f"대상 중 {s['coordinatesUnresolvedEligible']}코드는 이전 위치 감사의 해결 좌표가 없습니다. 해결된 좌표도 2026-09-10 당시 관리코드별 대표점이며 건물별 위치·현재 서울 경계 검증을 대신하지 않습니다. 제작 단계에서 원본 건물 윤곽·공식 배치도·동 번호를 별도 확인해야 합니다. 코드와 실제 단지의 대응은 검토된 경우에만 `physicalSiteId`에 기록합니다.", '',
        'K-apt는 주간 참고 추출물이며 실시간 자료가 아닙니다. 갱신일은 개별 행의 최신성이나 서울 모든 실제 단지의 수록을 보장하지 않습니다. 큐는 대상 확정과 완료 추적을 위한 것으로 도시 전체 모델링 완료 보고가 아닙니다.', '',
        '고정 공개 입력은 `apartments-400-sources.json.gz`, 명시적 동별 대응은 `apartments-400-coverage.json`, 결과는 `apartments-400-queue.jsonl.gz`와 `apartments-400-summary.json`입니다. 원본 연락처·관리인원·인증 상태·개별 주민 자료는 넣지 않았습니다. 원본 CSV/XLSX 전체는 이 공개 출력에 복사하지 않습니다.', '',
        '```sh', 'python scripts/build_apartment_bespoke_queue.py', 'python -m unittest discover -s tests -p test_apartment_bespoke_queue.py -v', '```', '',
        '새 다운로드를 고정 입력으로 바꿀 때만 `--capture --oa-csv … --oa-count-response … --kapt-xlsx … --kapt-manifest … --checked-on YYYY-MM-DD --oa-updated-on YYYY-MM-DD`를 명시합니다. 기존 source DB·모델·runtime은 수정하지 않습니다.']
    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--capture', action='store_true')
    for arg in ['oa-csv', 'oa-count-response', 'kapt-xlsx', 'kapt-manifest']:
        p.add_argument('--' + arg, type=Path)
    p.add_argument('--checked-on', help='Source acquisition date for explicit capture')
    p.add_argument('--oa-updated-on', help='Portal update date verified during this explicit capture')
    args = p.parse_args()
    root = args.root.resolve()
    dest = root / AUDIT
    source_path = dest / 'apartments-400-sources.json.gz'
    if args.capture:
        if not all([args.oa_csv, args.oa_count_response, args.kapt_xlsx, args.kapt_manifest, args.oa_updated_on, args.checked_on]):
            p.error('--capture requires all four source paths, --checked-on and --oa-updated-on')
        snapshot = capture(args.oa_csv, args.oa_count_response, args.kapt_xlsx, args.kapt_manifest, args.checked_on, root, args.oa_updated_on)
        validate_snapshot(snapshot)
        atomic(source_path, gzip.compress(canonical(snapshot), mtime=0))
    snapshot = read(source_path)
    queue, summary = build(snapshot, read(dest / 'apartments-400-coverage.json'), read(root / 'public/models/bespoke-manifest.json'),
        read(dest / 'published-bespoke.json'), read(root / 'public/models/manifest.json'), root)
    raw = b''.join(canonical(r) for r in queue)
    summary['queueSha256Uncompressed'] = hashlib.sha256(raw).hexdigest()
    summary['sourceSnapshotSha256'] = digest(source_path)
    summary['coverageDefinitionSha256'] = digest(dest / 'apartments-400-coverage.json')
    atomic(dest / 'apartments-400-queue.jsonl.gz', gzip.compress(raw, mtime=0))
    atomic(dest / 'apartments-400-summary.json', canonical(summary))
    atomic(dest / 'apartments-400-summary.md', markdown(summary, queue).encode())
    print(json.dumps({k: v for k, v in summary.items() if k not in ['sources', 'scope']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
