"""On-demand Bright Data snapshots and provenance-bound KB facts for Turso.

Never requests a target host directly and never installs an MCP server.
"""
import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TRANSPORT = 'brightdata-web-unlocker-api'
ALLOWED = {'kbland.kr', 'www.valueupmap.com', 'doczip.kr', 'www.jaegaebal.com',
           'cleanup.seoul.go.kr', 'm.land.naver.com', 'land.naver.com'}
DETAIL = {
 '단지명': None, '구주소': None, '신주소': None, '총동수': 'buildings',
 '총세대수': 'households', '총주차대수': 'spaces', '세대당주차대수비율': 'spaces/household',
 '최고층수': 'floors', '최저층수': 'floors', '난방방식구분명': None, '난방연료구분명': None,
 '현관구조': None, '연면적내용': 'm2', '대지면적내용': 'm2', '건축면적내용': 'm2',
 '용적률내용': 'percent', '건폐율내용': 'percent', '승강기유무': None, '준공년월일': None,
}
TYPES = {
 '공급면적': 'm2', '전용면적': 'm2', '주택형타입내용': None, '방수': 'rooms', '욕실수': 'bathrooms',
 '세대수': 'households', '연평균총관리비': 'KRW', '동절기평균총관리비': 'KRW',
 '하절기평균총관리비': 'KRW', '평면도보기주소': None, '네이버단지코드': None,
}
LIMITS = ('관리비는 원문 총관리비 지표이며 공용관리비로 재분류하지 않음. '
          'KB 시세와 실거래를 실시간 호가 스프레드로 대체하지 않음. '
          '미관측 시설·베이·승강기 속도·소유자 정보는 추론하지 않음.')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def http_json(url, token, body=None, method=None):
    req = urllib.request.Request(url, data=encoded(body).encode() if body is not None else None,
                                 headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=55) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'API HTTP {error.code}') from None


def fetch(url, folder, credentials):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED or parsed.username or parsed.password:
        raise ValueError('Target must be an approved public HTTPS source')
    conf = json.loads(credentials.read_text())
    token = conf['accounts'][conf.get('active', 1) - 1]['token']
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    req = urllib.request.Request('https://api.brightdata.com/request',
        data=encoded({'zone': 'web_unlocker1', 'url': url, 'format': 'raw'}).encode(),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=55) as response:
            raw = response.read(20_000_001)
            if len(raw) > 20_000_000:
                raise ValueError('Response too large')
            status, content_type = response.status, response.headers.get('Content-Type')
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'Bright Data HTTP {error.code}; no direct fallback') from None
    receipt = {'url': url, 'transport': TRANSPORT, 'retrievedAt': started,
               'completedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'httpStatus': status,
               'contentType': content_type, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    folder.mkdir(parents=True, exist_ok=True)
    stem = hashlib.sha256((url + started).encode()).hexdigest()
    path = folder / (stem + '.html')
    path.write_bytes(raw)
    path.with_suffix('.receipt.json').write_text(encoded(receipt))
    return path, receipt


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.parts = []
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.active, self.parts = True, []
    def handle_data(self, data):
        if self.active:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.scripts.append(''.join(self.parts))
            self.active = False


def find_payload(node, complex_id):
    if isinstance(node, dict):
        if str(node.get('complexId')) == complex_id and isinstance(node.get('data'), dict):
            yield node['data']
        for value in node.values():
            yield from find_payload(value, complex_id)
    elif isinstance(node, list):
        for value in node:
            yield from find_payload(value, complex_id)


def extract_kb(raw, receipt):
    if receipt.get('transport') != TRANSPORT or receipt.get('httpStatus') != 200:
        raise ValueError('Successful Bright Data receipt required')
    if hashlib.sha256(raw).hexdigest() != receipt.get('sha256'):
        raise ValueError('Raw payload checksum mismatch')
    url = urllib.parse.urlsplit(receipt['url'])
    match = re.fullmatch(r'/se/c/(\d+)', url.path)
    if url.scheme != 'https' or url.hostname != 'kbland.kr' or not match:
        raise ValueError('Unsupported detail URL; no guessed extraction')
    complex_id = match[1]
    parser = Scripts()
    parser.feed(raw.decode('utf-8'))
    chunks = []
    for script in parser.scripts:
        for m in re.finditer(r'self\.__next_f\.push\((.*)\)\s*;?$', script, re.S):
            try:
                envelope = json.loads(m[1])
                if envelope[0] == 1 and isinstance(envelope[1], str):
                    chunks.append(envelope[1])
            except (ValueError, IndexError, TypeError):
                continue
    payloads = []
    for line in ''.join(chunks).splitlines():
        try:
            payloads.extend(find_payload(json.loads(line.split(':', 1)[1]), complex_id))
        except (ValueError, IndexError):
            continue
    if not payloads:
        raise ValueError('No KB detail payload; shell/login/blocked response is not data')
    data = payloads[0]
    detail = data.get('detail', {})
    if str(detail.get('단지기본일련번호')) != complex_id or not detail.get('단지명'):
        raise ValueError('Complex identity mismatch')
    facts = []
    def add(scope, values, fields, pointer):
        for field, unit in fields.items():
            value = values.get(field)
            facts.append({'scope': scope, 'field': field, 'value': value, 'unit': unit,
                          'status': 'not_observed' if value is None or value == '' else 'observed',
                          'sourcePointer': pointer + '/' + field})
    add('complex', detail, DETAIL, '/data/detail')
    seen = set()
    for i, row in enumerate(data.get('typeList', [])):
        if str(row.get('단지기본일련번호')) != complex_id:
            raise ValueError('Area type belongs to another complex')
        area_id = row.get('면적일련번호')
        if area_id is None or area_id in seen:
            raise ValueError('Ambiguous area identity')
        seen.add(area_id)
        add('area:' + str(area_id), row, TYPES, f'/data/typeList/{i}')
    return {'provider': 'kbland', 'providerComplexId': complex_id, 'name': detail['단지명'],
            'facts': facts, 'limits': LIMITS}


def extract_naver_gallery(raw, receipt):
    if (receipt.get('transport') != TRANSPORT or receipt.get('httpStatus') != 200
            or hashlib.sha256(raw).hexdigest() != receipt.get('sha256')):
        raise ValueError('Verified successful Bright Data snapshot required')
    url = urllib.parse.urlsplit(receipt['url'])
    params = urllib.parse.parse_qs(url.query)
    ids = params.get('rletNo', [])
    if (url.scheme != 'https' or url.hostname != 'land.naver.com'
            or url.path != '/info/groundPlanGallery.naver' or len(ids) != 1 or not ids[0].isdigit()):
        raise ValueError('Unsupported public gallery URL')
    parser = Scripts()
    parser.feed(raw.decode('utf-8'))
    script = '\n'.join(parser.scripts)
    def payload(name):
        matches = re.findall(name + r"\s*:\s*'([^'\n]*)'", script)
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous embedded gallery data')
        return json.loads(matches[0])
    identity = payload('complexDongHo')
    buildings = payload('complexDongList')
    if str(identity.get('hscpNo')) != ids[0] or not identity.get('hscpNm'):
        raise ValueError('Gallery complex mismatch')
    rows = buildings.get('bildList', [])
    if buildings.get('bildCount') != len(rows) or not rows:
        raise ValueError('Incomplete building list')
    facts = []
    def add(scope, key, value, unit, pointer):
        facts.append({'scope': scope, 'field': key, 'value': value, 'unit': unit,
                      'status': 'not_observed' if value is None else 'observed', 'sourcePointer': pointer})
    for key, unit in [('hscpNm', None), ('highFlr', 'floors'), ('lowFlr', 'floors')]:
        add('complex', key, identity.get(key), unit, '/jsonPageData/complexDongHo/' + key)
    add('complex', 'bildCount', len(rows), 'buildings', '/jsonPageData/complexDongList/bildCount')
    seen = set()
    for i, row in enumerate(rows):
        number = row.get('dongNo')
        if number is None or number in seen or not row.get('bildNm'):
            raise ValueError('Ambiguous building identity')
        seen.add(number)
        for key, unit in [('bildNm', None), ('highFlr', 'floors'), ('lowFlr', 'floors')]:
            add('building:' + str(number), key, row.get(key), unit,
                f'/jsonPageData/complexDongList/bildList/{i}/' + key)
    return {'provider': 'naver-gallery', 'providerComplexId': ids[0], 'name': identity['hscpNm'],
            'facts': facts, 'limits': '공개 갤러리 단지·동별 층수 자료. 호가·집주인확인·급매·실시간 매물 자료가 아님. '
            'lowFlr는 원천 최저층 표기이며 지하층수로 해석하지 않음. 세대 호수·소유주 정보는 적재하지 않음.'}


def extract(raw, receipt):
    host = urllib.parse.urlsplit(receipt['url']).hostname
    if host == 'kbland.kr':
        return extract_kb(raw, receipt)
    if host == 'land.naver.com':
        return extract_naver_gallery(raw, receipt)
    raise ValueError('No reviewed parser for this provider; nothing uploaded')


def sql(hostname, token, statements):
    endpoint = 'https://' + hostname + '/v2/pipeline'
    def send(items, baton=None, close=False):
        body = {'requests': [{'type': 'execute', 'stmt': {'sql': query, 'args':
                [{'type': 'text', 'value': str(arg)} for arg in args], 'want_rows': True}}
                for query, args in items]}
        if baton is not None:
            body['baton'] = baton
        if close:
            body['requests'].append({'type': 'close'})
        return http_json(endpoint, token, body)
    def results(response):
        out = []
        for result in response['results']:
            if result['type'] == 'error':
                raise RuntimeError('Turso statement failed')
            if result['response']['type'] == 'execute':
                out.append(result['response']['result'])
        return out
    commit = next((i for i, (query, _) in enumerate(statements) if query == 'COMMIT'), None)
    if commit is None:
        return results(send(statements, close=True))
    # Check every write result before COMMIT. Errors roll back the same connection.
    response = send(statements[:commit])
    baton = response.get('baton')
    if not baton:
        raise RuntimeError('Missing transaction connection baton; transaction not committed')
    try:
        written = results(response)
    except Exception:
        send([('ROLLBACK', [])], baton=baton, close=True)
        raise
    return written + results(send(statements[commit:], baton=baton, close=True))


def upload(document, receipt):
    config = Path.home() / '.config/seoul-map-turso'
    state = json.loads((config / 'upload-state.json').read_text())['seoul-service.sqlite']
    accounts = json.loads((config / 'accounts.json').read_text())['accounts']
    account = next(a for a in accounts if a['organization'] == state['organization'])
    platform_token = (config / account['token_file']).read_text().strip()
    endpoint = ('https://api.turso.tech/v1/organizations/' + state['organization'] + '/databases/'
                + state['name'] + '/auth/tokens?authorization=full-access&expiration=1h')
    write_token = http_json(endpoint, platform_token, method='POST')['jwt']
    snapshot_id = hashlib.sha256(encoded(receipt).encode()).hexdigest()
    queries = [
        ('BEGIN IMMEDIATE', []),
        ('''CREATE TABLE IF NOT EXISTS proptech_bd_snapshots (
          id TEXT PRIMARY KEY, provider TEXT NOT NULL, provider_complex_id TEXT NOT NULL,
          source_url TEXT NOT NULL, retrieved_at TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
          transport TEXT NOT NULL CHECK(transport='brightdata-web-unlocker-api'),
          receipt_json TEXT NOT NULL, limits TEXT NOT NULL)''', []),
        ('''CREATE TABLE IF NOT EXISTS proptech_bd_facts (
          snapshot_id TEXT NOT NULL REFERENCES proptech_bd_snapshots(id), scope TEXT NOT NULL,
          field TEXT NOT NULL, value_json TEXT NOT NULL, unit TEXT, status TEXT NOT NULL,
          source_pointer TEXT NOT NULL, PRIMARY KEY(snapshot_id,scope,field))''', []),
        ('INSERT INTO proptech_bd_snapshots VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
         [snapshot_id, document['provider'], document['providerComplexId'], receipt['url'],
          receipt['retrievedAt'], receipt['sha256'], TRANSPORT, encoded(receipt), document['limits']]),
    ]
    for fact in document['facts']:
        queries.append(('INSERT INTO proptech_bd_facts VALUES (?,?,?,?,?,?,?) ON CONFLICT DO NOTHING',
                        [snapshot_id, fact['scope'], fact['field'], encoded(fact['value']),
                         fact['unit'] or '', fact['status'], fact['sourcePointer']]))
    queries.extend([('COMMIT', []), ('SELECT COUNT(*) FROM proptech_bd_facts WHERE snapshot_id=?', [snapshot_id])])
    result = sql(state['hostname'], write_token, queries)
    count = int(result[-1]['rows'][0][0]['value'])
    if count != len(document['facts']):
        raise ValueError('Remote fact count mismatch')
    return {'snapshotId': snapshot_id, 'factsVerified': count, 'database': state['name']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--url')
    source.add_argument('--receipt', type=Path, help='Replay only a verified BD raw snapshot')
    p.add_argument('--credentials', type=Path, default=Path.home()/'.config/brightdata/mcp-accounts.json')
    p.add_argument('--folder', type=Path, default=ROOT/'data/proptech-brightdata')
    p.add_argument('--upload', action='store_true')
    args = p.parse_args()
    if args.url:
        path, receipt = fetch(args.url, args.folder, args.credentials)
    else:
        receipt = json.loads(args.receipt.read_text())
        path = args.receipt.with_name(args.receipt.name.replace('.receipt.json', '.html'))
    document = extract(path.read_bytes(), receipt)
    output = path.with_suffix('.facts.json')
    output.write_text(encoded(document))
    result = {'providerComplexId': document['providerComplexId'], 'name': document['name'],
              'facts': len(document['facts']), 'transport': TRANSPORT}
    if args.upload:
        result.update(upload(document, receipt))
    print(encoded(result))

if __name__ == '__main__':
    main()
