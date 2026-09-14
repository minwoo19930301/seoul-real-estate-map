#!/usr/bin/env python3
"""Fetch SH '우리 아파트 찾기' detail pages (anonymous public POST) and extract 단지위치 addresses.

Reads detail ids from data/apartment_sources.sqlite (sh_rental_complex_list), saves each raw HTML
page, and writes addresses.json plus manifest.json with hashes. No login, key or proxy.
"""
from datetime import date, datetime, timezone
import http.cookiejar
import hashlib, html, json, re, sqlite3, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www.i-sh.co.kr/main/lay2/program/S1T305C311/www/m_491/hmng/viewRentalHouseBlockInfoDetail.do'
LIST_URL = 'https://www.i-sh.co.kr/main/lay2/program/S1T305C311/www/m_491/hmng/viewRentalHouseBlockInfoList.do'
UA = 'Mozilla/5.0 (Macintosh) SeoulElevationLocal/0.1 (public data download)'
FIELDS = ('단지위치', '공급유형', '공급형', '세대수', '난방방식', '복도유형', '시공사')


def field(page, label):
    m = re.search(r'<th[^>]*>\s*' + re.escape(label) + r'\s*</th>\s*<td[^>]*>(.*?)</td>', page, re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1)))).strip() if m else None


def main():
    out = ROOT / 'data/sources' / f'sh-rental-complex-detail-{date.today().isoformat()}'
    pages = out / 'pages'; pages.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect((ROOT / 'data/apartment_sources.sqlite').as_uri() + '?mode=ro', uri=True)
    ids = [r[0] for r in db.execute("SELECT DISTINCT detail_id FROM sh_rental_complex_list WHERE detail_id<>'' ORDER BY CAST(detail_id AS INTEGER)")]
    records, files, failures = [], {}, []
    # Detail pages render their values only inside the session created by visiting the list page.
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.open(urllib.request.Request(LIST_URL, headers={'User-Agent': UA}), timeout=60).read()
    for i, code in enumerate(ids):
        path = pages / f'{code}.html'
        if path.exists() and not field(path.read_text(encoding='utf-8', errors='replace'), '단지위치'):
            path.unlink()
        if not path.exists():
            req = urllib.request.Request(URL + '?biznsCode=' + urllib.parse.quote(code), data=b'page=1&srchTp=0&srchWord=',  # the list form's own fields; a body biznsCode blanks the values
                                         headers={'User-Agent': UA, 'Referer': LIST_URL, 'Content-Type': 'application/x-www-form-urlencoded'})
            try:
                with opener.open(req, timeout=60) as r:
                    path.write_bytes(r.read())
            except Exception as e:
                failures.append({'detail_id': code, 'error': repr(e)}); continue
            time.sleep(0.25)
        raw = path.read_bytes(); page = raw.decode('utf-8', 'replace')
        files[f'pages/{path.name}'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        records.append({'detail_id': code, **{k: field(page, k) for k in FIELDS}})
        if i % 100 == 0: print(f'{i}/{len(ids)}', flush=True)
    (out / 'addresses.json').write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding='utf-8')
    manifest = {'slug': 'sh-rental-complex-detail', 'title': 'SH 우리 아파트 찾기 단지 상세(단지위치 주소)', 'provider': '서울주택도시개발공사 i-sh.co.kr',
                'portal_url': LIST_URL, 'download_url': URL, 'download_method': 'POST biznsCode=<detail id from list page>, one page per complex',
                'license': '페이지에 이용조건 표기 없음 (재배포 조건 미확인)', 'acquired_date': date.today().isoformat(),
                'manifest_created_at': datetime.now(timezone.utc).isoformat(), 'acquisition_rule': 'anonymous public request only',
                'detail_ids': len(ids), 'pages_saved': len(files), 'with_address': sum(1 for r in records if r['단지위치']),
                'failures': failures, 'files': files}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: manifest[k] for k in ('detail_ids', 'pages_saved', 'with_address')} | {'failures': len(failures)}, ensure_ascii=False))
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
