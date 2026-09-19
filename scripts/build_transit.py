"""Build rail, bus and Ttareungi points from retained original coordinates (read-only)."""
import argparse, collections, hashlib, json, math, re, sqlite3, urllib.parse, urllib.request
from pathlib import Path
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from import_apartment_sources import xlsx_rows

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
 'bus_stop': {'page':'https://data.seoul.go.kr/dataList/OA-15067/S/1/datasetView.do', 'dataset':'OA-15067', 'title':'서울시버스정류소위치정보(20260902).xlsx', 'date':'2026-09-02', 'path':'data/sources/seoul-bus-stops-20260902/stops.xlsx'},
 'bike_station': {'page':'https://data.seoul.go.kr/dataList/OA-13252/F/1/datasetView.do', 'dataset':'OA-13252', 'title':'공공자전거 대여소 정보(26.6월 기준).xlsx', 'date':'2026-06-30', 'path':'data/sources/transit-2026-09-19/bikes-202606.xlsx'},
}

def download_source(spec, path):
    html = urllib.request.urlopen(spec['page'], timeout=25).read().decode()
    seq = re.search(r'title="'+re.escape(spec['title'])+r'"\s+onclick="javascript:downloadFile\(\'(\d+)\'\)', html)
    infseq = re.search(r'name="infSeq"\s+value="(\d+)"', html)
    if not seq or not infseq: raise ValueError('Published source file or download form not found: '+spec['title'])
    fields={'infId':spec['dataset'],'seq':seq[1],'seqNo':'','infSeq':infseq[1]}
    req=urllib.request.Request('https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false', data=urllib.parse.urlencode(fields).encode(), headers={'Referer':spec['page']})
    data=urllib.request.urlopen(req,timeout=40).read()
    if not data.startswith(b'PK'): raise ValueError('Download did not return XLSX')
    path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)

def official_points(path, kind, boundary):
    rows=list(xlsx_rows(path)); spec=SOURCES[kind]; rejected=[]; features=[]; seen={}
    if kind=='bus_stop':
        expected={0:'NODE_ID',1:'ARS_ID',2:'정류소명',3:'X좌표',4:'Y좌표'}
        if any(rows[0][1].get(k)!=v for k,v in expected.items()):raise ValueError('Unexpected bus XLSX columns')
        body=rows[1:]
    else:
        if rows[0][1].get(0,'').replace('\n','')!='대여소번호' or rows[2][1].get(4)!='위도' or rows[2][1].get(5)!='경도':raise ValueError('Unexpected bike XLSX columns')
        body=rows[5:]
    for number,row in body:
        ident=row.get(0,'').strip(); name=row.get(2 if kind=='bus_stop' else 1,'').strip()
        reason=None
        try: lon=float(row[3 if kind=='bus_stop' else 5]);lat=float(row[4])
        except (ValueError,KeyError,TypeError):lon=lat=float('nan')
        if kind=='bus_stop' and row.get(5)=='한강선착장':reason='ferry landing, not road bus stop'
        elif not ident or not name or not math.isfinite(lon+lat):reason='missing identifier, name or coordinates'
        elif not boundary.covers(Point(lon,lat)):reason='outside retained Seoul boundary'
        if reason:rejected.append({'row':number,'id':ident,'name':name,'reason':reason});continue
        key=f'seoul-{kind}-{ident}'; value=(name,lon,lat)
        if key in seen:
            if seen[key]!=value:raise ValueError('Conflicting source identifier '+key)
            rejected.append({'row':number,'id':ident,'name':name,'reason':'identical duplicate identifier'});continue
        seen[key]=value
        props={'nameKo':name,'kind':kind,'ref':row.get(1,'').strip().zfill(5) if kind=='bus_stop' else ident,'sourceUrl':spec['page'],'locationMethod':'seoul_official_xlsx','sourceDate':spec['date'],'sourceRow':number}
        if kind=='bike_station':props['district']=row.get(2,'');props['address']=row.get(3,'')
        else:props['stopType']=row.get(5,'')
        features.append({'type':'Feature','id':key,'geometry':{'type':'Point','coordinates':[lon,lat]},'properties':props})
    if not features:raise ValueError('No valid official points: '+str(path))
    return features,{'file':str(path.relative_to(ROOT)),'sourceUrl':spec['page'],'sourceDate':spec['date'],'sourceTitle':spec['title'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sourceRows':len(body),'accepted':len(features),'rejected':rejected}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--official-xlsx',type=Path,default=ROOT/SOURCES['bus_stop']['path']);parser.add_argument('--official-bike-xlsx',type=Path,default=ROOT/SOURCES['bike_station']['path']);parser.add_argument('--download',action='store_true');args=parser.parse_args()
    boundary=unary_union([shape(f['geometry']) for f in json.loads((ROOT/'data/building-source/districts.geojson').read_text())['features']])
    with sqlite3.connect((ROOT/'data/places.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        rows=db.execute("select id,name,lon,lat,source_url,location_method from places where kind='station' and name is not null and trim(name)<>'' order by id").fetchall()
    features=[{'type':'Feature','id':ident,'geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{'nameKo':name,'kind':'rail_station','sourceUrl':url,'locationMethod':method}} for ident,name,lon,lat,url,method in rows]
    audits={}
    for kind,path in [('bus_stop',args.official_xlsx.resolve()),('bike_station',args.official_bike_xlsx.resolve())]:
        if args.download:download_source(SOURCES[kind],path)
        points,audits[kind]=official_points(path,kind,boundary);features.extend(points)
    assert len({f['id'] for f in features})==len(features)
    counts=dict(collections.Counter(f['properties']['kind'] for f in features))
    meta={'attribution':'버스·따릉이 위치: 서울특별시 (공공누리 제1유형), 역 위치: © OpenStreetMap contributors','counts':counts,'snapshotOnly':True,'busSourceDate':SOURCES['bus_stop']['date'],'bikeSourceDate':SOURCES['bike_station']['date']}
    (ROOT/'public/transit.json').write_text(json.dumps({'type':'FeatureCollection','metadata':meta,'features':features},ensure_ascii=False,separators=(',',':'))+'\n')
    audit={'counts':counts,'sources':audits,'checks':['unique source identifiers','original XLSX numeric coordinates without geocoding','Seoul polygon inclusion for bus and bike','road bus stops exclude ferry landings','no OSM bus/bike duplicates appended'],'scope':'Published location snapshots; neither live service status nor available bicycle counts.'}
    (ROOT/'docs/TRANSIT_VALIDATION.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');print(json.dumps(counts))
if __name__=='__main__':main()
