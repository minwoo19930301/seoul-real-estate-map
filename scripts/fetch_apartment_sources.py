#!/usr/bin/env python3
"""Acquire apartment-related public sources anonymously and preserve them with manifests.

Every source is fetched exactly as a browser visitor could without a login, API key,
proxy or captcha. Each source directory under data/sources/<slug>-<date>/ keeps the
raw bytes, a manifest.json (request, byte count, SHA-256, licence text as shown by
the portal) and, where the portal offers one, an independent record count. Nothing
here transforms, joins or interprets the data; import scripts do that separately.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import date, datetime, timezone
import hashlib
import http.cookiejar
import io
import json
from pathlib import Path
import re
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / 'data' / 'sources'
ACQUIRED = date.today().isoformat()
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36 SeoulElevationLocal/0.1 (public data download)'
TIMEOUT = 180
SEOUL_SHEET_CSV = 'https://datafile.seoul.go.kr/bigfile/iot/sheet/csv/download.do'
SEOUL_FILE = 'https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false'
ARCGIS = 'https://urban.seoul.go.kr/proxy/proxy.jsp?http://98.33.2.225:6080/arcgis/rest/services/UPIS/20200526_WFS/MapServer'
KAPT = 'https://www.k-apt.go.kr'
KAPT_TM_CENTRAL = ('+proj=tmerc +lat_0=38 +lon_0=127.0028902777778 +k=1 +x_0=200000 +y_0=500000 '
                   '+ellps=bessel +units=m +no_defs +towgs84=-115.80,474.99,674.11,1.16,-2.31,-1.63,6.43')
LICENSE_KOGL1 = '공공누리 제1유형: 출처표시 (상업적 이용 및 변경 가능)'
LICENSE_KOGL4 = '공공누리 제4유형: 출처표시 + 상업적 이용금지 + 변경금지'
LICENSE_DATAGOKR_FREE = '이용허락범위 제한 없음 (공공데이터포털 표기)'
LICENSE_UNSTATED = '페이지에 이용조건 표기 없음 (재배포 조건 미확인)'


class Session:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, url, *, data=None, headers=None, method=None, timeout=TIMEOUT):
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header('User-Agent', UA)
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        return self.opener.open(request, timeout=timeout)

    def text(self, url, **kw):
        with self.request(url, **kw) as response:
            body = response.read()
            charset = response.headers.get_content_charset() or 'utf-8'
            return body.decode(charset, 'replace'), response

    def download(self, url, target: Path, *, data=None, headers=None, method=None, resume=False):
        """Stream to target; returns (bytes, sha256, status, content_type, disposition, final_url)."""
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.stat().st_size if resume and target.exists() else 0
        headers = dict(headers or {})
        if existing:
            headers['Range'] = f'bytes={existing}-'
        temporary = target.with_suffix(target.suffix + '.part')
        mode = 'ab' if existing else 'wb'
        if existing and not temporary.exists():
            target.replace(temporary)
        with self.request(url, data=data, headers=headers, method=method) as response, temporary.open(mode) as out:
            status = response.status
            if existing and status != 206:
                out.seek(0); out.truncate()
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                out.write(chunk)
            content_type = response.headers.get('Content-Type')
            disposition = response.headers.get('Content-Disposition')
            final_url = response.geturl()
        temporary.replace(target)
        return target.stat().st_size, sha256(target), status, content_type, disposition, final_url


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def disposition_filename(disposition, default):
    if not disposition:
        return default
    # Portals send unquoted names with spaces (filename=서울특별시 서대문구_...csv), which the
    # strict header parser truncates at the first space; take everything up to the next ';'.
    match = (re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", disposition)
             or re.search(r'filename="([^"]+)"', disposition)
             or re.search(r'filename=([^;]+)', disposition))
    if not match:
        return default
    name = urllib.parse.unquote(match.group(1).strip())
    try:
        name = name.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '_', name).strip().strip('.')
    return name or default


def csv_check(path: Path, max_bytes=400 * 1024 * 1024):
    """Strict decode + csv parse; reports encoding, header, row count. Never edits the file."""
    result = {'bytes': path.stat().st_size}
    if result['bytes'] > max_bytes:
        result['note'] = 'not parsed (over size limit); count rows during import'
        return result
    raw = path.read_bytes()
    for encoding in ('utf-8-sig', 'cp949'):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        reader = csv.reader(io.StringIO(text, newline=''))
        try:
            header = next(reader)
        except StopIteration:
            result.update(encoding=encoding, header=[], row_count=0)
            return result
        rows = 0
        widths = set()
        for row in reader:
            rows += 1
            widths.add(len(row))
        result.update(encoding=encoding, header=header[:80], column_count=len(header), row_count=rows,
                      row_widths=sorted(widths)[:10])
        return result
    result['encoding'] = 'undetermined (neither utf-8-sig nor cp949 decodes strictly)'
    result['line_count_raw'] = raw.count(b'\n')
    return result


def zip_check(path: Path):
    if not zipfile.is_zipfile(path):
        return {'is_zip': False}
    with zipfile.ZipFile(path) as archive:
        members = [{'name': m.filename, 'bytes': m.file_size} for m in archive.infolist() if not m.is_dir()]
    return {'is_zip': True, 'member_count': len(members), 'members': members[:60]}


def write_manifest(directory: Path, manifest: dict):
    manifest = {'acquired_date': ACQUIRED, 'manifest_created_at': datetime.now(timezone.utc).isoformat(),
                'acquisition_rule': 'anonymous public request only; no login, API key, proxy or captcha', **manifest}
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def file_entry(path: Path, size, digest, **extra):
    return {path.name: {'bytes': size, 'sha256': digest, **extra}}


# ----------------------------------------------------------------------------- handlers

def seoul_sheet(directory, spec):
    inf = spec['infId']
    session = Session()
    count_url = ('https://data.seoul.go.kr/dataList/dataView.do?onepagerow=1&srvType=S&infId=' + inf
                 + '&serviceKind=0&pageNo=1&ssUserId=SAMPLE_VIEW&strWhere=&strOrderby=SN%20ASC')
    count_text, _ = session.text(count_url)
    (directory / 'sheet-count-response.txt').write_text(count_text, encoding='utf-8')
    match = re.search(r'totalCount\s*[:=]\s*"?(\d+)', count_text)
    total = int(match.group(1)) if match else None
    form = {'srvType': 'S', 'infId': inf, 'serviceKind': '0', 'pageNo': '1', 'gridTotalCnt': '',
            'ssUserId': 'SAMPLE_VIEW', 'strWhere': '', 'strOrderby': 'SN ASC', 'filterCol': '필터선택', 'txtFilter': ''}
    target = directory / 'sheet.csv'
    size, digest, status, ctype, disp, _ = session.download(
        SEOUL_SHEET_CSV, target, data=urllib.parse.urlencode(form).encode('utf-8'),
        headers={'Referer': spec['portal_url'], 'Content-Type': 'application/x-www-form-urlencoded'})
    check = csv_check(target)
    files = file_entry(target, size, digest, **check)
    count_path = directory / 'sheet-count-response.txt'
    files.update(file_entry(count_path, count_path.stat().st_size, sha256(count_path)))
    return {'download_method': 'POST anonymous public Sheet CSV form', 'download_url': SEOUL_SHEET_CSV, 'form': form,
            'count_url': count_url, 'independent_count': total,
            'count_matches_csv': (check.get('row_count') == total) if total is not None and 'row_count' in check else None,
            'http_status': status, 'content_type': ctype, 'content_disposition': disp, 'files': files}


def seoul_file(directory, spec):
    session = Session()
    form = {'infId': spec['infId'], 'seq': str(spec['seq']), 'infSeq': str(spec['infSeq'])}
    probe = directory / 'attachment.bin'
    size, digest, status, ctype, disp, _ = session.download(
        SEOUL_FILE, probe, data=urllib.parse.urlencode(form).encode('utf-8'),
        headers={'Referer': spec['portal_url'], 'Content-Type': 'application/x-www-form-urlencoded'})
    target = directory / disposition_filename(disp, spec.get('filename', 'attachment.bin'))
    probe.replace(target)
    check = zip_check(target) if target.suffix.lower() == '.zip' else (csv_check(target) if target.suffix.lower() == '.csv' else {})
    return {'download_method': 'POST anonymous public attachment form (nio_download.do)', 'download_url': SEOUL_FILE,
            'form': form, 'http_status': status, 'content_type': ctype, 'content_disposition': disp,
            'files': file_entry(target, size, digest, **check)}


def datagokr_file(directory, spec):
    pk = str(spec['publicDataPk'])
    session = Session()
    page_url = f'https://www.data.go.kr/data/{pk}/fileData.do'
    page, _ = session.text(page_url)
    (directory / 'portal-page.html').write_text(page, encoding='utf-8')
    title = re.search(r'<title>(.*?)</title>', page, re.S)
    modified = re.search(r'"dateModified"\s*:\s*"([^"]+)"', page)
    license_text = re.search(r'이용허락범위</th>\s*<td[^>]*>\s*([^<]+?)\s*<', page, re.S)
    content_urls = re.findall(r'"contentUrl"\s*:\s*"([^"]+)"', page)
    detail_sn = str(spec.get('fileDetailSn', 1))
    url = None
    for candidate in content_urls:
        candidate = candidate.replace('\\/', '/')
        if f'fileDetailSn={detail_sn}' in candidate or len(content_urls) == 1:
            url = candidate
            break
    resolution = 'JSON-LD contentUrl'
    if url is None:
        detail_pk = re.search(r'name="publicDataDetailPk"\s+value="([^"]+)"', page)
        args = re.search(r"fn_fileDataDown\('(\d+)',\s*'([^']+)',\s*'[^']*',\s*'(\d+)'", page)
        detail = detail_pk.group(1) if detail_pk else (args.group(2) if args else None)
        if not detail:
            raise RuntimeError('no contentUrl or publicDataDetailPk on portal page')
        form = urllib.parse.urlencode({'publicDataPk': pk, 'publicDataDetailPk': detail, 'fileDetailSn': detail_sn,
                                       'publicDataTyCode': 'PR0051'}).encode()
        text, _ = session.text('https://www.data.go.kr/tcs/dss/selectFileDataDownload.do', data=form,
                               headers={'Referer': page_url, 'X-Requested-With': 'XMLHttpRequest',
                                        'Content-Type': 'application/x-www-form-urlencoded'})
        (directory / 'select-file-data-download.json').write_text(text, encoding='utf-8')
        payload = json.loads(text)
        if not payload.get('atchFileId'):
            raise RuntimeError('selectFileDataDownload.do returned no atchFileId: ' + text[:200])
        url = (f"https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={payload['atchFileId']}"
               f"&fileDetailSn={payload.get('fileDetailSn', detail_sn)}&insertDataPrcus=N")
        resolution = 'POST /tcs/dss/selectFileDataDownload.do -> atchFileId'
    probe = directory / 'download.bin'
    size, digest, status, ctype, disp, final = session.download(url, probe, headers={'Referer': page_url}, resume=True)
    if 'text/html' in (ctype or '') and size < 200_000:
        raise RuntimeError(f'download returned HTML ({size} bytes); likely a login or error page: {final}')
    target = directory / disposition_filename(disp, spec.get('filename', f'{pk}.bin'))
    probe.replace(target)
    suffix = target.suffix.lower()
    check = zip_check(target) if suffix == '.zip' else (csv_check(target) if suffix == '.csv' else {})
    return {'download_method': f'GET portal file link ({resolution})', 'download_url': url, 'portal_title': title.group(1).strip() if title else None,
            'portal_date_modified': modified.group(1) if modified else None,
            'portal_license_text': license_text.group(1).strip() if license_text else None,
            'http_status': status, 'content_type': ctype, 'content_disposition': disp,
            'files': file_entry(target, size, digest, **check)}


def http_get(directory, spec):
    session = Session()
    probe = directory / 'download.bin'
    size, digest, status, ctype, disp, final = session.download(spec['url'], probe, headers={'Referer': spec.get('referer', spec['portal_url'])}, resume=spec.get('resume', False))
    target = directory / disposition_filename(disp, spec.get('filename', 'download.bin'))
    probe.replace(target)
    suffix = target.suffix.lower()
    check = zip_check(target) if suffix == '.zip' else (csv_check(target) if suffix == '.csv' else {})
    return {'download_method': 'GET', 'download_url': spec['url'], 'http_status': status, 'content_type': ctype,
            'content_disposition': disp, 'final_url': final, 'files': file_entry(target, size, digest, **check)}


def kapt_session():
    session = Session()
    page, _ = session.text(f'{KAPT}/kaptinfo/openKaptLocation.do')
    token = re.search(r'name="_csrf"\s+value="([^"]+)"', page)
    if not token:
        raise RuntimeError('K-apt page did not expose a _csrf token')
    return session, token.group(1)


def kapt_json(directory, spec):
    session, token = kapt_session()
    form = {**spec['form'], '_csrf': token}
    target = directory / spec['filename']
    size, digest, status, ctype, disp, _ = session.download(
        f"{KAPT}{spec['endpoint']}", target, data=urllib.parse.urlencode(form).encode('utf-8'),
        headers={'Accept': 'application/json', 'Referer': f'{KAPT}/kaptinfo/openKaptLocation.do',
                 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'})
    payload = json.loads(target.read_text(encoding='utf-8'))
    rows = payload.get('resultList')
    if not isinstance(rows, list) or not rows:
        raise RuntimeError('K-apt response has no resultList: ' + target.read_text(encoding='utf-8')[:200])
    keys = sorted({k for row in rows for k in row})
    form_public = {k: v for k, v in form.items() if k != '_csrf'}
    return {'download_method': 'POST form after anonymous page visit (session cookie + page _csrf token)',
            'download_url': f"{KAPT}{spec['endpoint']}", 'form': {**form_public, '_csrf': '<token from page>'},
            'http_status': status, 'content_type': ctype, 'record_count': len(rows), 'record_keys': keys,
            'coordinate_note': 'x/y (or xCoord/yCoord) are metres in the projection the K-apt map script names TM_중부',
            'coordinate_projection_proj4_from_site_js': KAPT_TM_CENTRAL,
            'coordinate_projection_source': f'{KAPT}/knew/js/knew_map.js?v=2 knew_fn_coordinate()',
            'files': file_entry(target, size, digest)}


def kapt_board_xlsx(directory, spec):
    session = Session()
    list_url = f'{KAPT}/web/board/webReference/boardList.do?boardType=03&scodeT=01'
    session.text(list_url)
    with session.request(f'{KAPT}/web/board/goKaptBasicExcelDownload.do', headers={'Referer': list_url}) as response:
        view_url = response.geturl()
        view = response.read().decode('utf-8', 'replace')
    seq = urllib.parse.parse_qs(urllib.parse.urlparse(view_url).query).get('seq', [None])[0]
    if not seq:
        raise RuntimeError('goKaptBasicExcelDownload.do did not redirect to a boardView seq: ' + view_url)
    (directory / 'notice-page.html').write_text(view, encoding='utf-8')
    token = re.search(r'name="_csrf"\s+(?:content|value)="([^"]+)"', view) or re.search(r'id="_csrf"[^>]*content="([^"]+)"', view)
    if not token:
        raise RuntimeError('notice page has no _csrf token')
    posted = re.search(r'(\d{4}[-.]\d{2}[-.]\d{2})', view)
    extract = re.search(r'(\d{4})년\s*(\d{2})월\s*(\d{2})일\s*추출', view)
    body = json.dumps({'boardType': '03', 'pageNo': 1, 'seq': int(seq), 'scode': '01', '_csrf': token.group(1)}).encode()
    listing, _ = session.text(f'{KAPT}/web/board/webReference/fileListData.do?seq=BOARD_FILE', data=body,
                              headers={'Content-Type': 'application/json', 'X-CSRF-TOKEN': token.group(1), 'Referer': view_url,
                                       'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})
    (directory / 'file-list-response.json').write_text(listing, encoding='utf-8')
    payload = json.loads(listing)
    files = payload.get('data') or []
    if not files:
        raise RuntimeError('fileListData.do returned no attachments: ' + listing[:200])
    entry = files[0]
    name = entry['fileName']
    url = f"{KAPT}/cmm/file/BOARD/fileDownload.do?key={entry['seq']}&fileName={urllib.parse.quote(name)}"
    target = directory / re.sub(r'[\\/:*?"<>|]+', '_', name)
    size, digest, status, ctype, disp, _ = session.download(url, target, headers={'Referer': view_url})
    if not zipfile.is_zipfile(target):
        raise RuntimeError('downloaded attachment is not an XLSX (zip) container')
    return {'download_method': 'anonymous session: boardList -> goKaptBasicExcelDownload redirect -> fileListData (CSRF header) -> fileDownload',
            'download_url': url, 'notice_url': view_url, 'notice_seq': seq,
            'notice_extract_date': '-'.join(extract.groups()) if extract else None,
            'notice_first_date_seen': posted.group(1) if posted else None,
            'attachment_listing': files, 'http_status': status, 'content_type': ctype, 'content_disposition': disp,
            'files': file_entry(target, size, digest)}


def arcgis_layer(directory, spec):
    layer = spec['layer']
    session = Session()
    base = f'{ARCGIS}/{layer}'
    meta, _ = session.text(f'{base}?f=json')
    (directory / 'layer.json').write_text(meta, encoding='utf-8')
    legend, _ = session.text(f'{ARCGIS}/legend?f=json')
    (directory / 'legend.json').write_text(legend, encoding='utf-8')
    ids_text, _ = session.text(f'{base}/query?where=1%3D1&returnIdsOnly=true&f=json')
    ids = json.loads(ids_text).get('objectIds') or []
    if not ids:
        raise RuntimeError('layer returned no objectIds: ' + ids_text[:200])
    chunks_dir = directory / 'chunks'
    chunks_dir.mkdir(exist_ok=True)
    features, chunk_files = [], {}
    for index in range(0, len(ids), 200):
        chunk = ids[index:index + 200]
        url = (f'{base}/query?f=json&objectIds={",".join(map(str, chunk))}&outFields=*&returnGeometry=true'
               f'&outSR=4326&returnZ=false&returnM=false')
        text, _ = session.text(url)
        payload = json.loads(text)
        if payload.get('error'):
            raise RuntimeError(f'ArcGIS error on chunk {index}: {payload["error"]}')
        path = chunks_dir / f'{index // 200:04d}.json'
        path.write_text(text, encoding='utf-8')
        chunk_files[f'chunks/{path.name}'] = {'bytes': path.stat().st_size, 'sha256': sha256(path), 'features': len(payload.get('features', []))}
        features.extend(payload.get('features', []))
        time.sleep(0.2)
    merged = directory / 'features.esri.json'
    merged.write_text(json.dumps({'spatialReference': {'wkid': 4326}, 'geometryType': json.loads(meta).get('geometryType'),
                                  'fields': json.loads(meta).get('fields'), 'features': features}, ensure_ascii=False), encoding='utf-8')
    if len(features) != len(ids):
        raise RuntimeError(f'feature count {len(features)} != objectId count {len(ids)}')
    files = file_entry(merged, merged.stat().st_size, sha256(merged), feature_count=len(features))
    for name in ('layer.json', 'legend.json'):
        p = directory / name
        files.update(file_entry(p, p.stat().st_size, sha256(p)))
    files.update(chunk_files)
    return {'download_method': 'GET ArcGIS REST query in objectId chunks of 200 (pagination unsupported by service); outSR=4326 requested',
            'download_url': f'{base}/query', 'object_id_count': len(ids), 'feature_count': len(features),
            'native_spatial_reference': json.loads(meta).get('extent', {}).get('spatialReference'),
            'geometry_note': 'features.esri.json is the concatenation of chunk responses; geometry rings are EPSG:4326 as returned by outSR=4326',
            'files': files}


def hub_energy(directory, spec):
    session = Session()
    list_url = 'https://www.hub.go.kr/portal/opn/lps/idx-lgcpt-pvsn-srvc-list.do'
    page, _ = session.text(list_url)
    token = re.search(r'name="_csrf"\s+content="([^"]+)"', page)
    if not token:
        raise RuntimeError('hub.go.kr page has no _csrf meta')
    if spec['srvrFileNm'] not in page:
        raise RuntimeError('requested srvrFileNm is not listed on the current hub.go.kr page (files rotate monthly)')
    label = re.search(r'<p class="tit">([^<]*' + re.escape(spec['label_hint']) + r'[^<]*)</p>', page)
    form = urllib.parse.urlencode({'srvrFileNm': spec['srvrFileNm'], '_csrf': token.group(1)}).encode()
    probe = directory / 'download.bin'
    size, digest, status, ctype, disp, _ = session.download(
        'https://www.hub.go.kr/cmm/fms/fileOpnDown.do', probe, data=form,
        headers={'Referer': list_url, 'X-CSRF-TOKEN': token.group(1), 'Content-Type': 'application/x-www-form-urlencoded'})
    target = directory / disposition_filename(disp, spec['srvrFileNm'] + '.zip')
    probe.replace(target)
    check = zip_check(target)
    if not check.get('is_zip'):
        raise RuntimeError(f'hub.go.kr response is not a zip ({ctype}, {size} bytes)')
    return {'download_method': 'POST /cmm/fms/fileOpnDown.do with page _csrf (anonymous session)', 'download_url': 'https://www.hub.go.kr/cmm/fms/fileOpnDown.do',
            'form': {'srvrFileNm': spec['srvrFileNm'], '_csrf': '<token from page>'}, 'listed_as': label.group(1) if label else None,
            'http_status': status, 'content_type': ctype, 'content_disposition': disp, 'files': file_entry(target, size, digest, **check)}


def ish_rental_list(directory, spec):
    session = Session()
    url = spec['url']
    files, seen_first, pages = {}, set(), 0
    for page_no in range(1, 200):
        html, response = session.text(url, data=urllib.parse.urlencode({'page': str(page_no)}).encode(),
                                      headers={'Referer': url, 'Content-Type': 'application/x-www-form-urlencoded'})
        rows = re.findall(r'<tr[^>]*>\s*<td[^>]*>\s*(\d+)\s*</td>', html)
        if not rows or rows[0] in seen_first:
            break
        seen_first.add(rows[0])
        path = directory / f'page-{page_no:03d}.html'
        path.write_text(html, encoding='utf-8')
        files[path.name] = {'bytes': path.stat().st_size, 'sha256': sha256(path), 'row_numbers': [rows[0], rows[-1]]}
        pages = page_no
        time.sleep(0.3)
    if not pages:
        raise RuntimeError('no list rows parsed from the SH page')
    return {'download_method': 'POST form page=N on the public list page; one HTML file per page', 'download_url': url,
            'page_count': pages, 'http_status': 200, 'files': files}


HANDLERS = {'seoul_sheet': seoul_sheet, 'seoul_file': seoul_file, 'datagokr_file': datagokr_file, 'http_get': http_get,
            'kapt_json': kapt_json, 'kapt_board_xlsx': kapt_board_xlsx, 'arcgis_layer': arcgis_layer,
            'hub_energy': hub_energy, 'ish_rental_list': ish_rental_list}

# ----------------------------------------------------------------------------- registry

def S(slug, title, provider, portal_url, handler, license_text, relevance, note, **spec):
    return {'slug': slug, 'title': title, 'provider': provider, 'portal_url': portal_url, 'handler': handler,
            'license': license_text, 'apartment_relevance': relevance, 'note': note, **spec}

SEOUL = 'https://data.seoul.go.kr/dataList/'
DG = 'https://www.data.go.kr/data/'
SOURCES = [
    # --- complex locations / identifiers -------------------------------------------------
    S('kapt-seoul-complex-poi', 'K-apt 공동주택 단지 위치(POI) — 서울', '국토교통부·한국부동산원 공동주택관리정보시스템(K-apt)',
      f'{KAPT}/kaptinfo/openKaptLocation.do', 'kapt_json', LICENSE_UNSTATED, 'high',
      'kaptCode는 서울시 OA-15818의 k-아파트코드와 같은 체계. 좌표는 TM_중부(m).',
      endpoint='/kaptinfo/getKaptInfo_poi.do', form={'bjdCode': '11', 'searchDate': '202607'}, filename='kapt-poi-seoul.json'),
    S('kapt-seoul-complex-list', 'K-apt 공동주택 단지 목록(법정동·지번·좌표) — 서울', '국토교통부·한국부동산원 K-apt',
      f'{KAPT}/kaptinfo/openKaptLocation.do', 'kapt_json', LICENSE_UNSTATED, 'high',
      'bjdCode(10)+bun1/bun2로 필지번호(PNU) 구성 가능 — 한국부동산원 단지 식별정보와 공식 키로 연결하는 근거.',
      endpoint='/kaptinfo/getKaptList.do', form={'bjdCode': '11', 'searchDate': '202607'}, filename='kapt-list-seoul.json'),
    S('kapt-basic-info-weekly', 'K-apt 관리비공개의무단지 기본정보 (주간 xlsx, 전국)', '한국부동산원 K-apt 자료실',
      f'{DG}15073271/fileData.do', 'kapt_board_xlsx', LICENSE_UNSTATED, 'high',
      '전국 단지의 동수·세대수·분양/임대·사용승인일·주소. 서울 행은 가져오기에서 시도 열로 선별.'),
    S('reb-complex-identifier-basic', '한국부동산원 공동주택 단지 식별정보 — 기본정보', '한국부동산원 (공공데이터포털 파일)',
      f'{DG}15106861/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'high',
      '단지고유번호(14)·필지고유번호 PNU(19)·단지명 3종·단지종류·동수·세대수·사용승인일. 전국; 서울은 PNU/주소로 선별.',
      publicDataPk=15106861),
    S('reb-complex-identifier-dong', '한국부동산원 공동주택 단지 식별정보 — 동정보', '한국부동산원 (공공데이터포털 파일)',
      f'{DG}15106866/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'high',
      '단지고유번호 + 동명 3종 + 지상층수. 층수는 높이가 아니다.', publicDataPk=15106866),
    S('reb-complex-name-history', '한국부동산원 공동주택 단지 식별정보 — 단지명 이력정보', '한국부동산원 (공공데이터포털 파일)',
      f'{DG}15106867/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '단지명 변경 이력(연도·전·후).', publicDataPk=15106867),
    # --- building register / permits (Seoul sheets) --------------------------------------
    S('seoul-register-summary-oa-22423', '서울시 건축물대장 총괄표제부', '서울특별시 (서울열린데이터광장 OA-22423)',
      f'{SEOUL}OA-22423/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL1, 'high',
      '대지 단위 총괄: 세대수·가구수·호수·주건축물수·총주차수·사용승인일자 등 54열.', infId='OA-22423'),
    S('seoul-housing-permit-dong-oa-22414', '서울시 주택인허가 동별개요', '서울특별시 (서울열린데이터광장 OA-22414)',
      f'{SEOUL}OA-22414/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL1, 'high',
      '주택 인허가 동별: 동명·지상/지하층수·높이(HG)·임대/분양 세대수 열 포함. 인허가 자료이며 준공 대장과 다를 수 있다.', infId='OA-22414'),
    # --- apartment management / finance (Seoul sheets) ------------------------------------
    S('seoul-apartment-mgmt-fee-oa-15822', '서울시 공동주택 관리비 정보', '서울특별시 (서울열린데이터광장 OA-15822)',
      f'{SEOUL}OA-15822/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL1, 'medium',
      '아파트코드(K-apt 코드)별 비용명·년월·금액. 월별 첨부 csv 94개는 별도(미수집).', infId='OA-15822'),
    S('seoul-apartment-misc-income-oa-15819', '서울시 공동주택 잡수입·잡지출·장기수선충당금 정보', '서울특별시 (OA-15819)',
      f'{SEOUL}OA-15819/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL1, 'low', 'Sheet 본문만. 연도별 첨부 csv(최대 37MB)는 미수집.', infId='OA-15819'),
    S('seoul-apartment-finance-report-oa-15820', '서울시 공동주택 재무보고서 정보', '서울특별시 (OA-15820)',
      f'{SEOUL}OA-15820/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL1, 'low', 'Sheet 본문만. 월별 첨부 64개는 미수집.', infId='OA-15820'),
    S('seoul-apartment-operations-report-oa-15821', '서울시 공동주택 운영보고서 정보', '서울특별시 (OA-15821)',
      f'{SEOUL}OA-15821/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL1, 'low', 'Sheet 본문만. 월별 첨부 67개는 미수집.', infId='OA-15821'),
    # --- prices / transactions -------------------------------------------------------------
    S('seoul-realestate-sales-oa-21275', '서울시 부동산 실거래가 정보', '서울특별시 (서울열린데이터광장 OA-21275, 원본 서울부동산정보광장)',
      f'{SEOUL}OA-21275/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL1, 'high',
      '건물용도 열로 아파트 거래 선별 가능. 좌표 없음(자치구·법정동·지번·건물명).', infId='OA-21275'),
    S('seoul-rent-transactions-2025-oa-21276', '서울시 부동산 전월세가 정보 — 2025년 연간 zip', '서울특별시 (OA-21276 첨부)',
      f'{SEOUL}OA-21276/F/1/datasetView.do', 'seoul_file', LICENSE_KOGL1, 'medium',
      '전체 Sheet 260만 행 대신 최신 연도 첨부만 수집. 2011~2024 연간 zip 14개는 같은 폼(seq 26~39 추정)으로 받을 수 있음 — 미검증.',
      infId='OA-21276', seq=40, infSeq=3, filename='seoul-rent-2025.zip'),
    S('molit-apartment-price-2025', '국토교통부 주택 공시가격 정보(2025) — 공동주택가격', '국토교통부 (공공데이터포털 파일 3073746)',
      f'{DG}3073746/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'high',
      '전국 1,558만 행 zip(CSV). 서울 행은 가져오기에서 스트리밍 선별. 호 단위 공시가격과 동·호 목록.', publicDataPk=3073746),
    # --- public / rental / sale complex lists -----------------------------------------------
    S('sh-housing-management-oa-12027', '서울주택도시개발공사 주택관리현황', '서울주택도시개발공사 (OA-12027)',
      f'{SEOUL}OA-12027/S/1/datasetView.do', 'seoul_sheet', LICENSE_DATAGOKR_FREE, 'medium', 'SH 관리 단지: 구·단지명·주택유형·세대수·입주개시일·주소.', infId='OA-12027'),
    S('sh-rental-complex-list', 'SH 임대주택 단지 목록(우리 아파트 찾기)', '서울주택도시개발공사 i-sh.co.kr',
      'https://www.i-sh.co.kr/main/lay2/program/S1T305C311/www/m_491/hmng/viewRentalHouseBlockInfoList.do', 'ish_rental_list', LICENSE_UNSTATED, 'medium',
      '공개 목록 페이지 HTML 원문(유형·아파트명·구·세대수·준공일). 단지 상세 페이지는 미수집.',
      url='https://www.i-sh.co.kr/main/lay2/program/S1T305C311/www/m_491/hmng/viewRentalHouseBlockInfoList.do'),
    S('lh-apartment-complexes', '한국토지주택공사 전국 LH아파트 단지정보', '한국토지주택공사 (공공데이터포털 15080989)',
      f'{DG}15080989/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '전국; 주소 열로 서울 선별.', publicDataPk=15080989),
    S('lh-rental-complexes-built', '한국토지주택공사 임대주택단지정보(건설)', '한국토지주택공사 (15050700)',
      f'{DG}15050700/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '전국; 주소로 서울 선별.', publicDataPk=15050700),
    S('lh-rental-complexes-purchased', '한국토지주택공사 임대주택단지정보(매입)', '한국토지주택공사 (15050701)',
      f'{DG}15050701/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'low', '전국; 주소로 서울 선별.', publicDataPk=15050701),
    S('hug-seoul-sale-apartments', '주택도시보증공사 서울특별시 분양아파트 기본현황', '주택도시보증공사 (15152174)',
      f'{DG}15152174/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '사업장명·사업구분·세대수·분양개시일.', publicDataPk=15152174),
    S('hug-seoul-sale-apartments-detail', '주택도시보증공사 서울특별시 분양아파트 상세현황', '주택도시보증공사 (15152175)',
      f'{DG}15152175/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '일반분양·조합원·임대 세대수 구분.', publicDataPk=15152175),
    S('reb-new-apartments-2022', '한국부동산원 신규 아파트 단지 목록(2022 사용승인분)', '한국부동산원 (15120697)',
      f'{DG}15120697/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'low', '전국 678단지; 시군구코드로 서울 선별.', publicDataPk=15120697),
    # --- district (자치구) apartment inventories ------------------------------------------------
    S('gangbuk-apartments-oa-11614', '서울시 강북구 공동주택 현황', '강북구 (OA-11614)', f'{SEOUL}OA-11614/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL1, 'medium', '동수·층수·세대수·사용승인일.', infId='OA-11614'),
    S('gangseo-apartments-oa-21838', '서울특별시 강서구 공동주택 현황 (xlsx)', '강서구 (OA-21838)', f'{SEOUL}OA-21838/F/1/datasetView.do', 'seoul_file', LICENSE_KOGL1, 'medium', '첨부 xlsx.', infId='OA-21838', seq=2, infSeq=1, filename='gangseo-apartments.xlsx'),
    S('yangcheon-apartments-oa-22047', '서울특별시 양천구 공동주택현황 (csv)', '양천구 (OA-22047)', f'{SEOUL}OA-22047/F/1/datasetView.do', 'seoul_file', LICENSE_KOGL1, 'medium', '동수·호수·최소/최대층수.', infId='OA-22047', seq=1, infSeq=1, filename='yangcheon-apartments.csv'),
    S('seodaemun-apartments', '서울특별시 서대문구 공동주택 현황', '서대문구 (15055494)', f'{DG}15055494/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '좌표(X/Y) 열 포함 — 좌표계 미표기.', publicDataPk=15055494),
    S('gangseo-apartments', '서울특별시 강서구 공동주택 현황', '강서구 (15066129)', f'{DG}15066129/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '', publicDataPk=15066129),
    S('jungnang-apartments', '서울특별시 중랑구 공동주택 현황', '중랑구 (15006098)', f'{DG}15006098/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '', publicDataPk=15006098),
    S('yangcheon-apartments', '서울특별시 양천구 공동주택현황', '양천구 (15052389)', f'{DG}15052389/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '', publicDataPk=15052389),
    S('dongjak-apartments', '서울특별시 동작구 공동주택 현황', '동작구 (15006108)', f'{DG}15006108/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '', publicDataPk=15006108),
    S('seocho-apartments', '서울특별시 서초구 공동주택 현황', '서초구 (15134607)', f'{DG}15134607/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '', publicDataPk=15134607),
    S('seongdong-apartments', '서울특별시 성동구 공동주택현황', '성동구 (15039169)', f'{DG}15039169/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '', publicDataPk=15039169),
    S('gwangjin-apartments', '서울특별시 광진구 아파트정보', '광진구 (15046141)', f'{DG}15046141/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '', publicDataPk=15046141),
    S('geumcheon-apartments', '서울특별시 금천구 공동주택(아파트) 용도 및 면적 현황', '금천구 (15102426)', f'{DG}15102426/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'medium', '', publicDataPk=15102426),
    S('gangnam-apartment-parking', '서울특별시 강남구 공동주택 주차면수', '강남구 (15112832)', f'{DG}15112832/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'low', '', publicDataPk=15112832),
    S('seongbuk-apartment-parking', '서울특별시 성북구 공동주택 주차면수', '성북구 (15112864)', f'{DG}15112864/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'low', '', publicDataPk=15112864),
    S('gwanak-apartment-parking', '서울특별시 관악구 공동주택 주차면수', '관악구 (15112930)', f'{DG}15112930/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'low', '', publicDataPk=15112930),
    S('yangcheon-apartment-parking', '서울특별시 양천구 공동주택 주차면수', '양천구 (15112857)', f'{DG}15112857/fileData.do', 'datagokr_file', LICENSE_DATAGOKR_FREE, 'low', '', publicDataPk=15112857),
    # --- redevelopment / renewal ---------------------------------------------------------------
    S('upis-renewal-project-zones-uq120', '서울도시공간포털 UPIS_C_UQ120 정비사업 사업장 구역 도형', '서울특별시 도시공간포털 (ArcGIS 공개 조회)',
      'https://urban.seoul.go.kr/view/map/main.html', 'arcgis_layer', LICENSE_UNSTATED, 'medium',
      '신속통합기획·재개발·재건축·모아타운 등 구역 폴리곤. 공개 지도가 쓰는 조회 서비스이며 대량 재배포 허락은 미확인.', layer=12),
    S('upis-renewal-districts-uq181', '서울도시공간포털 UPIS_C_UQ181 정비구역·재정비촉진지구 도형', '서울특별시 도시공간포털 (ArcGIS 공개 조회)',
      'https://urban.seoul.go.kr/view/map/main.html', 'arcgis_layer', LICENSE_UNSTATED, 'medium', '재건축·재개발 정비구역 폴리곤.', layer=64),
    S('cleanup-seoul-project-list', '정비사업 정보몽땅 사업장 목록', '서울특별시 정비사업 정보몽땅', 'https://cleanup.seoul.go.kr/cleanup/bsnssttus/lscrMainIndx.do', 'http_get', LICENSE_UNSTATED, 'medium',
      '서울 정비사업 1,171 사업장: 자치구·사업구분·사업장명·대표지번·진행단계 (xls).',
      url='https://cleanup.seoul.go.kr/cleanup/bsnssttus/lsubBsnsSttusExcel.do', filename='project-list.xls'),
    S('seoul-redevelopment-stats-oa-22856', '서울특별시 도시정비사업 통계', '서울특별시 (OA-22856)', f'{SEOUL}OA-22856/S/1/datasetView.do', 'seoul_sheet', LICENSE_DATAGOKR_FREE, 'medium',
      '구역명·주소·사업유형·추진단계·기존/건립 세대수.', infId='OA-22856'),
    S('seoul-urban-renewal-status-oa-20281', '서울시 도시계획 정비사업 현황', '서울특별시 (OA-20281)', f'{SEOUL}OA-20281/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL4, 'low',
      '공공누리 4유형(변경금지·비상업) — 원본 보존만, 가공·지도 표시 금지.', infId='OA-20281'),
    S('seoul-renewal-promotion-oa-20286', '서울시 재정비 촉진 사업 현황', '서울특별시 (OA-20286)', f'{SEOUL}OA-20286/S/1/datasetView.do', 'seoul_sheet', LICENSE_KOGL4, 'low',
      '공공누리 4유형 — 원본 보존만.', infId='OA-20286'),
    # --- linking keys / energy -----------------------------------------------------------------
    S('juso-building-db-202608', '도로명주소 건물DB 전체분 2026-08', '행정안전부 주소기반산업지원서비스', 'https://business.juso.go.kr/jst/jstAddressDownload', 'http_get', LICENSE_UNSTATED, 'high',
      '건물관리번호(25)·도로명주소·건축물대장건물명·상세건물명(동)·공동주택여부. 서울 파일 build_seoul.txt 포함. 아파트 동을 도로명주소 건물 도형(S-MAP bd_mgt_sn)과 잇는 키.',
      url='https://business.juso.go.kr/api/jst/download?regYmd=2026&reqType=ALLRDNM&ctprvnCd=00&stdde=202608&fileName=202608_%EA%B1%B4%EB%AC%BCDB_%EC%A0%84%EC%B2%B4%EB%B6%84.zip&realFileName=202608ALLRDNM00.zip&intFileNo=0&intNum=0',
      filename='202608_building_db_all.zip', resume=True),
    S('hub-energy-gas-202605', '건축HUB 건물에너지 지번별 가스 사용량 2026.05 (200세대 이상 공동주택 등)', '국토교통부 건축HUB 대용량 제공', 'https://www.hub.go.kr/portal/opn/lps/idx-lgcpt-pvsn-srvc-list.do', 'hub_energy', LICENSE_UNSTATED, 'low',
      '', srvrFileNm='OPN202609070600171880', label_hint='가스'),
    S('hub-energy-electric-202605', '건축HUB 건물에너지 지번별 전기 사용량 2026.05 (200세대 이상 공동주택 등)', '국토교통부 건축HUB 대용량 제공', 'https://www.hub.go.kr/portal/opn/lps/idx-lgcpt-pvsn-srvc-list.do', 'hub_energy', LICENSE_UNSTATED, 'low',
      '', srvrFileNm='OPN202609070600159840', label_hint='전기'),
]

# ----------------------------------------------------------------------------- runner

def run_source(spec, force=False):
    directory = SOURCES_DIR / f"{spec['slug']}-{ACQUIRED}"
    manifest_path = directory / 'manifest.json'
    if manifest_path.exists() and not force:
        return spec['slug'], 'skipped (manifest exists)', None
    directory.mkdir(parents=True, exist_ok=True)
    started = time.time()
    try:
        result = HANDLERS[spec['handler']](directory, spec)
    except Exception as error:  # noqa: BLE001 - recorded, never hidden
        (directory / 'error.json').write_text(json.dumps({'slug': spec['slug'], 'error': repr(error),
            'traceback': traceback.format_exc(), 'at': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2), encoding='utf-8')
        return spec['slug'], f'FAILED {error!r}', None
    base = {k: spec[k] for k in ('slug', 'title', 'provider', 'portal_url', 'license', 'apartment_relevance', 'note')}
    manifest = write_manifest(directory, {**base, **result, 'elapsed_seconds': round(time.time() - started, 1)})
    (directory / 'error.json').unlink(missing_ok=True)
    total = sum(f.get('bytes', 0) for f in manifest.get('files', {}).values())
    return spec['slug'], f'ok {total:,} bytes in {manifest["elapsed_seconds"]}s', manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', help='comma-separated slugs')
    parser.add_argument('--skip', help='comma-separated slugs to skip')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--workers', type=int, default=5)
    args = parser.parse_args()
    selected = SOURCES
    if args.only:
        wanted = set(args.only.split(','))
        selected = [s for s in SOURCES if s['slug'] in wanted]
    if args.skip:
        skipped = set(args.skip.split(','))
        selected = [s for s in selected if s['slug'] not in skipped]
    if args.list:
        for s in selected:
            print(f"{s['slug']:45} {s['handler']:16} {s['apartment_relevance']:6} {s['title']}")
        return
    print(f'{len(selected)} sources -> {SOURCES_DIR} (date {ACQUIRED})', flush=True)
    failures = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_source, s, args.force): s['slug'] for s in selected}
        for future in as_completed(futures):
            slug, status, _ = future.result()
            failures += status.startswith('FAILED')
            print(f'[{datetime.now().strftime("%H:%M:%S")}] {slug}: {status}', flush=True)
    print(f'done: {len(selected) - failures} ok, {failures} failed', flush=True)
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
