"""Build a private address index without changing the official source files."""
import csv, hashlib, json, os, re, sqlite3, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/model-source/residential-survey/register.sqlite'
CSV=ROOT/'data/sources/seoul-building-register-2026-09-08.csv'


def number(v, *, main=False):
    s=str(v or '').strip()
    if not s and not main:return 0  # An omitted address sub-number denotes no sub-lot.
    if not re.fullmatch(r'\d{1,4}',s):return None
    n=int(s)
    return n if not main or n>0 else None


def district(v):return re.sub(r'^서울특별시\s*','',v or '').strip()


def keyland(gu,dong,kind,main,sub):
    m,s=number(main,main=True),number(sub)
    if not gu or not dong or kind not in ('land','mountain') or m is None or s is None:return None
    return f'{gu}|{dong}|{kind}|{m}|{s}'


def keyroad(gu,road,main,sub,underground):
    m,s=number(main,main=True),number(sub)
    if not gu or not road or underground not in ('지상','지하') or m is None or s is None:return None
    return f'{gu}|{road}|{m}|{s}|{underground}'


def safe(v):
    # Indexed text must be valid UTF-8; raw_json below preserves original bytes
    # through JSON surrogate escapes instead of silently replacing source text.
    return (v or '').encode('utf-8','backslashreplace').decode('utf-8')


def parcel_id(code,mountain,main,sub):
    code=str(code or '').strip();m,s=number(main,main=True),number(sub)
    if not re.fullmatch(r'11\d{8}',code) or mountain not in ('0','1') or m is None or s is None:return None
    return code+('2' if mountain=='1' else '1')+f'{m:04d}{s:04d}'


def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='register-',suffix='.sqlite',dir=OUT.parent);os.close(fd)
    db=sqlite3.connect(tmp)
    try:
        db.executescript('CREATE TABLE reg(row_number INTEGER PRIMARY KEY,id TEXT,district TEXT,dong TEXT,parcel_key TEXT,road_key TEXT,building_dong TEXT,main_aux TEXT,main_use TEXT,other_use TEXT,floors TEXT,basement TEXT,height TEXT,households TEXT,approval_year TEXT,roof TEXT,structure TEXT,source_hash TEXT,raw_json TEXT); CREATE TABLE juso(row_number INTEGER PRIMARY KEY,building_manager_id TEXT,parcel_id TEXT,parcel_key TEXT,road_key TEXT,name TEXT,detail_name TEXT,district TEXT,source_hash TEXT,raw_json TEXT);')
        with CSV.open(encoding='cp949',errors='surrogateescape',newline='') as f:
            for i,row in enumerate(csv.DictReader(f),1):
                raw=json.dumps(row,ensure_ascii=True,separators=(',',':'));digest=hashlib.sha256(raw.encode()).hexdigest()
                r={k:safe(v).strip() for k,v in row.items()};gu=district(r['시군구코드명']);dong=r['법정동코드명']
                land={'산':'mountain','대지':'land'}.get(r['대지구분코드명'])
                db.execute('INSERT INTO reg VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(i,r['건축물대장일련번호'],gu,dong,keyland(gu,dong,land,r['주지번'],r['부지번']),keyroad(gu,r['새주소도로코드명'],r['새주소주지번'],r['새주소부지번'],r['새주소지상지하구분코드명']),r['동명'],r['주부속구분코드명'],r['주용도코드명'],r['기타용도내용'],r['지상층수'],r['지하층수'],r['높이'],r['세대수'],r['사용승인일자'][:4],r['지붕코드명'],r['구조코드명'],digest,raw))
        source=sqlite3.connect((ROOT/'data/apartment_sources.sqlite').as_uri()+'?mode=ro',uri=True);source.row_factory=sqlite3.Row
        for r in source.execute('SELECT row_number,법정동코드,법정읍면동명,산여부,지하여부,지번본번,지번부번,도로명,건물본번,건물부번,건축물대장건물명,상세건물명,건물관리번호,시군구명,raw_json FROM juso_building_db_202608'):
            gu=district(r['시군구명']);land={'0':'land','1':'mountain'}.get(r['산여부']);level={'0':'지상','1':'지하'}.get(r['지하여부']);raw=r['raw_json'];digest=hashlib.sha256(raw.encode()).hexdigest()
            db.execute('INSERT INTO juso VALUES (?,?,?,?,?,?,?,?,?,?)',(r['row_number'],r['건물관리번호'],parcel_id(r['법정동코드'],r['산여부'],r['지번본번'],r['지번부번']),keyland(gu,r['법정읍면동명'],land,r['지번본번'],r['지번부번']),keyroad(gu,r['도로명'],r['건물본번'],r['건물부번'],level),r['건축물대장건물명'],r['상세건물명'],gu,digest,raw))
        for table,cols in [('reg',['parcel_key','road_key','id']),('juso',['parcel_key','road_key','building_manager_id','parcel_id'])]:
            for col in cols:db.execute(f'CREATE INDEX {table}_{col} ON {table}({col})')
        counts={t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ['reg','juso']}
        assert counts=={'reg':585194,'juso':593178},counts
        assert db.execute("SELECT parcel_key,road_key FROM reg WHERE row_number=1").fetchone()==('강서구|방화동|land|246|66','강서구|방화대로|309|4|지상')
        audit={'tables':counts,'registerInputSha256':hashlib.sha256(CSV.read_bytes()).hexdigest(),'keyPolicy':'explicit district+legal dong+land kind+numeric lot / district+road+number+underground; missing or invalid fields remain null; no management-ID prefix inference','nullKeys':{t:{k:db.execute(f'SELECT COUNT(*) FROM {t} WHERE {k} IS NULL').fetchone()[0] for k in ['parcel_key','road_key']} for t in counts}}
        db.commit();db.close();os.replace(tmp,OUT)
        (OUT.parent/'register-index-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(audit,ensure_ascii=False))
    finally:
        db.close()
        if Path(tmp).exists():Path(tmp).unlink()


if __name__=='__main__':main()
