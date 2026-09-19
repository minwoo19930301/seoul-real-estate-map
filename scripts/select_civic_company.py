"""Exact named civic/company footprints; current models are reserved before selection."""
import collections,json,sqlite3
from pathlib import Path
from shapely.geometry import shape
ROOT=Path(__file__).resolve().parents[1]
TERMS=['서울특별시청','서울도서관','숭례문','흥인지문','경복궁 건춘문','창경궁 함인정','창경궁 선인문','덕수궁 중명전','국립현대미술관 덕수궁관','조계사 일주문','조계사 대설법전','봉은사 대웅전','봉은사 판전','봉은사 진여문','서울역사박물관','현대자동차그룹 본사','현대건설 본사','아모레퍼시픽 본사','LG유플러스본사','대한항공 본사','중앙일보 본사','CJ 본사','KB손해보험 본사','LG서울역빌딩','포스코피엔에스타워','SK서린빌딩','SK텔레콤 본사','금호아시아나 본관','한화생명 본사','교보생명빌딩','미래에셋센터원','두산타워']

def main():
    places=sqlite3.connect((ROOT/'data/places.sqlite').as_uri()+'?mode=ro',uri=True);places.row_factory=sqlite3.Row
    buildings=sqlite3.connect((ROOT/'data/buildings.sqlite').as_uri()+'?mode=ro',uri=True);buildings.row_factory=sqlite3.Row
    districts={f['properties']['names']['primary']:shape(f['geometry']) for f in json.loads((ROOT/'data/building-source/districts.geojson').read_text())['features']}
    matches=json.loads((ROOT/'public/models/footprint-matches.json').read_text());owners={bid:model for model,ids in matches.items() for bid in ids};out=[];upgrades=[];rejected=[]
    for term in TERMS:
        rows=list(places.execute('select * from places where name=? and building_id is not null order by id',(term,)))
        if len(rows)!=1:rejected.append({'nameKo':term,'reason':'no single exact retained named building'});continue
        r=rows[0];b=buildings.execute("select * from buildings where id=? and kind='building'",(r['building_id'],)).fetchone();d=r['district_name']
        if not b or d not in districts:rejected.append({'nameKo':term,'reason':'no supported source footprint/district'});continue
        g=shape(json.loads(b['geometry']))
        if not g.is_valid or not districts[d].covers(g.representative_point()):rejected.append({'nameKo':term,'reason':'invalid source geometry or outside recorded district'});continue
        owner=owners.get(b['id'])
        if owner and term!='서울특별시청':rejected.append({'nameKo':term,'reason':'existing model retained','existingModel':owner});continue
        kind='city-hall' if term in ('서울특별시청','서울도서관') else 'company-office' if term in TERMS[15:] else 'cultural-site'
        candidate={'id':owner or 'civic-'+b['id'],'nameKo':term,'district':d,'kind':kind,'coordinate':{'lon':g.centroid.x,'lat':g.centroid.y,'basis':'retained named source footprint centroid'},'buildingIds':[b['id']],'sourceUrls':[r['source_url']],'evidence':{'sourcePlaceId':r['id'],'sourceHeightM':b['height_m'],'sourceFloors':b['num_floors']},'scope':'Named source building only. Cultural category is not a legal heritage designation; company name follows retained map record, not a current tenancy audit.'}
        if owner:upgrades.append(candidate)
        else:out.append(candidate);owners[b['id']]=candidate['id']
    for name,value in [('civic-company-candidates.json',out),('city-hall-upgrade.json',upgrades),('civic-company-audit.json',{'newCount':len(out),'upgradeCount':len(upgrades),'categories':dict(collections.Counter(x['kind'] for x in out)),'rejected':rejected})]:
        (ROOT/'docs'/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('new',len(out),'upgrades',len(upgrades))
if __name__=='__main__':main()
