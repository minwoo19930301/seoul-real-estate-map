"""Audit all downloaded official housing footprints against preserved city models.

Sources are opened read-only. The output is a separate, ignored modeling database;
no building or apartment source rows are patched by approximate spatial links.
"""
from __future__ import annotations
import argparse, collections, functools, hashlib, json, math, os, re, sqlite3
from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon, shape, mapping
from shapely.ops import transform
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'data/sources/residential-survey-2026-09-20'
WORK = ROOT/'data/model-source/residential-survey'
ANCILLARY = re.compile(r'관리사무소|관리사무실|관리동|경비실|경비초소|경로당|노인정|기계실|전기실|주차장|주차타워|어린이집|유치원|(?:상가동?|정자)$')
RESIDENTIAL = re.compile(r'다세대|연립|아파트|오피스텔|주상복합|공동주택|주택')
VILLA = re.compile(r'다세대|연립|빌라|빌레|맨션|맨숀|타운하우스|\bvilla\b|\bmansion\b', re.I)
MIXED = re.compile(r'주상복합')
OFFICE = re.compile(r'오피스텔|\bofficetel\b', re.I)
APARTMENT = re.compile(r'아파트|\bapartments?\b', re.I)


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def integer(value):
    try:
        n=float(str(value).strip())
        return int(n) if math.isfinite(n) and n.is_integer() else None
    except (ValueError,TypeError): return None


def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError): return None


def text(value): return str(value or '').strip()


def esri_polygon(geometry):
    """Preserve ring nesting (including holes/islands), without repairing outlines."""
    rings = geometry.get('rings', []) if isinstance(geometry,dict) else []
    if not rings: raise ValueError('missing rings')
    polygons=[]
    for ring in rings:
        if len(ring)<4 or any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in ring):
            raise ValueError('invalid ring positions')
        polygon=Polygon(ring)
        if not polygon.is_valid or polygon.is_empty or polygon.area<=0: raise ValueError('invalid ring')
        polygons.append(polygon)
    polygons.sort(key=lambda p:-p.area)
    parents=[];depths=[]
    for i,p in enumerate(polygons):
        containers=[j for j in range(i) if polygons[j].covers(p)]
        parent=max(containers,key=lambda j:-polygons[j].area) if containers else None
        parents.append(parent);depths.append(0 if parent is None else depths[parent]+1)
    shells=[]
    for i,p in enumerate(polygons):
        if depths[i]%2==0:
            holes=[list(polygons[j].exterior.coords) for j in range(i+1,len(polygons)) if parents[j]==i and depths[j]%2==1]
            shells.append(Polygon(p.exterior.coords,holes))
    result=shells[0] if len(shells)==1 else MultiPolygon(shells)
    if not result.is_valid: raise ValueError('invalid intersecting shells or holes')
    return result


def metric_area(poly):
    lat=poly.representative_point().y
    return poly.area*(111320**2)*math.cos(math.radians(lat))


def classification(main_use,other_use,name):
    specific = re.compile(r'다세대|연립|아파트|오피스텔|주상복합|도시형생활주택')
    ancillary_use = re.compile(r'주차|관리사무|경비|경로당|노인정|기계실|전기실|창고|펌프|정자|보육시설|어린이집|유치원|생활편익시설|부속|부대시설|주민공동시설')
    if ANCILLARY.search(name):return None,'excluded: ancillary building name'
    if re.search(r'아파트\s*(?:상가|부대시설|관리소)',other_use):
        return None,'excluded: apartment-complex shop or ancillary facility'
    # The apartment complex name is often copied onto its parking/office/church.
    nested = re.fullmatch(r'\s*(?:공동주택|아파트|주상복합)\s*\((.*)\)\s*',other_use)
    inner=nested.group(1) if nested else other_use
    if ancillary_use.search(inner) and not specific.search(inner):return None,'excluded: ancillary use'
    explicit=bool(specific.search(other_use))
    if not explicit and main_use not in ('공동주택','단독주택','업무시설',''):
        return None,'excluded: explicit nonresidential main use'
    if not explicit and re.search(r'종교|노유자|창고|판매|근린생활|숙박|교육|운동|공장|자동차|보육|의료',other_use):
        return None,'excluded: explicit nonresidential detailed use'
    combined=other_use+' '+name
    if OFFICE.search(combined):return 'officetel','explicit officetel use or name without conflicting official use'
    if not explicit and main_use=='업무시설':return None,'excluded: office use without confirmed officetel or housing use'
    if MIXED.search(combined):return 'mixed-use','explicit mixed-use housing'
    if VILLA.search(combined):return 'villa','explicit multifamily/row-house use or villa name'
    if APARTMENT.search(combined):
        if re.search(r'근린생활|판매시설|업무시설|상가',other_use):return 'mixed-use','apartment plus commercial use in official description'
        return 'apartment','explicit apartment use or name'
    if main_use=='공동주택' or '공동주택' in other_use:return 'multifamily','official shared housing; detailed legal subtype unavailable'
    return None,'no requested residential use confirmed'


def safe_height(attrs,reg,overlap):
    floors=integer(attrs.get('DBJSFLOOR'))
    floors=floors if floors is not None and 0<floors<=100 else None
    year=text(attrs.get('SAYONG_YEA'))[:4]
    # Address is only a bridge: require unique record, matching floors and year.
    if reg and reg.get('identity')=='unique parcel and road record' and floors:
        h=number(reg.get('height')); rf=integer(reg.get('floors'))
        if h and 1<=h<500 and 1.8<=h/floors<=6 and rf==floors and re.fullmatch(r'(18|19|20)\d{2}',year) and year==text(reg.get('approval_year')):
            return h,floors,'register height corroborated by unique parcel+road, floors and approval year; cross-system identity is not an official key join'
    if overlap and overlap.get('strongOneToOne'):
        h=number(overlap.get('height_m'))
        if h and 1<=h<500 and (not floors or 1.8<=h/floors<=6):
            return h,floors or integer(overlap.get('num_floors')) or max(1,round(h/3.05)), 'Overture recorded height transferred through >=80% mutual footprint overlap; not independently measured'
    if floors:return floors*3.05,floors,'official source floors multiplied by estimated 3.05m'
    return None,None,'height and usable official floors unavailable'


def tile_for(lon,lat,z=16):
    n=2**z
    return f'{z}-{int((lon+180)/360*n)}-{int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)}'


class Registry:
    def __init__(self,path):
        self.db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);self.db.row_factory=sqlite3.Row
        self.shared_records=set()
    @functools.lru_cache(maxsize=8192)
    def by_manager(self,manager):
        return [dict(r) for r in self.db.execute('select * from juso where building_manager_id=?',(manager,))]
    @functools.lru_cache(maxsize=8192)
    def reg_for(self,parcel):
        return [dict(r) for r in self.db.execute('select * from reg where parcel_key=?',(parcel,))]
    def link(self,attrs,district):
        pnu=text(attrs.get('ADDRESS'));manager=text(attrs.get('BLDG_MGRNU'))
        rows=[r for r in self.by_manager(manager) if r['district']==district and r['parcel_id']==pnu]
        variants={(r['parcel_key'],r['road_key'],r['name'],r['detail_name']) for r in rows}
        if not rows or len(variants)!=1:return None,None,'manager ID absent, ambiguous, or current parcel differs'
        j=rows[0]; rs=self.reg_for(j['parcel_key'])
        rs=[r for r in rs if r['main_aux']=='주건축물' and r['district']==district]
        exact=[r for r in rs if r['road_key'] and r['road_key']==j['road_key']]
        # Requiring one whole parcel record prevents choosing a conveniently tall
        # building among several structures on the same lot.
        if len(rs)==1 and len(exact)==1:
            r=exact[0];r['identity']='unique parcel and road record'
            if r['id'] in self.shared_records:
                return j,None,'register record shared by multiple official footprints; height and subtype not transferred'
            return j,r,'unique parcel and road record'
        return j,None,'address-linked building; register identity ambiguous or road differs'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sample',type=int);args=parser.parse_args()
    WORK.mkdir(parents=True,exist_ok=True)
    target=WORK/('selection-sample.sqlite' if args.sample else 'selection.sqlite')
    tmp=target.with_suffix('.tmp.sqlite')
    if tmp.exists():tmp.unlink()
    output=sqlite3.connect(tmp)
    output.executescript('CREATE TABLE candidates(id TEXT PRIMARY KEY,tile TEXT,district TEXT,kind TEXT,name TEXT,geometry TEXT,height REAL,floors INTEGER,footprints TEXT,evidence TEXT); CREATE INDEX candidate_tile ON candidates(tile); CREATE TABLE dispositions(object_id INTEGER PRIMARY KEY,reason TEXT,detail TEXT); CREATE VIRTUAL TABLE selected_index USING rtree(rowid,minx,maxx,miny,maxy);')
    legacy=json.loads((ROOT/'public/models/manifest.json').read_text())
    if legacy.get('catalogIndex'):raise ValueError('Survey already published; refuse to resurvey against its own output')
    owned={bid for ids in json.loads((ROOT/'public/models/footprint-matches.json').read_text()).values() for bid in ids}
    db=sqlite3.connect((ROOT/'data/buildings.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    @functools.lru_cache(maxsize=8192)
    def poly_for(bid,raw):return shape(json.loads(raw))
    registry=Registry(WORK/'register.sqlite')
    districts=[(f['properties']['names']['primary'],shape(f['geometry'])) for f in json.loads((ROOT/'data/building-source/districts.geojson').read_text())['features']]
    tree=STRtree([p for _,p in districts]);counts=collections.Counter();kinds=collections.Counter();by_district=collections.defaultdict(collections.Counter);height_basis=collections.Counter();claimed=set();selected={};seen=set();inputs=[]
    paths=sorted(SOURCE.glob('batch-*.json'))+sorted((SOURCE/'supplemental').glob('batch-*.json'))
    paths=[p for p in paths if not p.name.endswith('.meta.json')]
    source_ids=set()
    for folder in [SOURCE,SOURCE/'supplemental']:
        if not (folder/'objectids.json').exists():continue
        source_ids.update(json.loads((folder/'objectids.json').read_text())['objectIds'])
        if not args.sample and not (folder/'metadata.json').exists():raise ValueError('Collection not completed: '+str(folder))
    # A unique address record can still describe several disjoint map buildings.
    # Count across the entire acquired snapshot before selecting any one of them.
    register_targets=collections.defaultdict(set)
    for path in paths:
        for feature in json.loads(path.read_text()).get('features',[]):
            attrs=feature.get('attributes',{})
            possible=registry.by_manager(text(attrs.get('BLDG_MGRNU')))
            for district_name in {j['district'] for j in possible}:
                _,record,_=registry.link(attrs,district_name)
                if record:register_targets[record['id']].add(attrs['OBJECTID'])
    registry.shared_records={key for key,ids in register_targets.items() if len(ids)>1}
    print(f'Register ambiguity guard: {len(registry.shared_records)} shared record IDs',flush=True)
    for path in paths:
        batch=json.loads(path.read_text());meta=json.loads(path.with_suffix('.meta.json').read_text())
        expected=meta.get('sha256')
        if expected and sha(path)!=expected:raise ValueError('Changed source batch '+str(path))
        inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)})
        for feature in batch.get('features',[]):
            attrs=feature.get('attributes',{});oid=attrs['OBJECTID']
            if oid in seen:raise ValueError('Duplicate source object ID '+str(oid))
            if args.sample and len(seen)>=args.sample:break
            seen.add(oid);counts['sourceFeatures']+=1
            def skip(reason,detail=None):
                counts[reason]+=1;output.execute('insert into dispositions values (?,?,?)',(oid,reason,json.dumps(detail,ensure_ascii=False) if detail is not None else None))
            try:poly=esri_polygon(feature.get('geometry'))
            except (ValueError,TypeError) as e:skip('invalid_geometry',str(e));continue
            point=poly.representative_point();inside=[int(i) for i in tree.query(point) if districts[int(i)][1].covers(point)]
            if len(inside)!=1:skip('outside_or_ambiguous_district');continue
            district=districts[inside[0]][0]
            area=metric_area(poly)
            if not 8<=area<=1_000_000:skip('unusable_footprint_area');continue
            j,reg,link_basis=registry.link(attrs,district)
            official_name=text(attrs.get('BLDG_NAME'))
            name=official_name
            if j and (not name or re.fullmatch(r'(?:제)?\d+[A-Za-z가-힣]?동?',name)):
                name=' '.join(dict.fromkeys(x for x in [text(j['name']),text(j['detail_name']),official_name] if x))
            main_use=text(attrs.get('DBJYDCD'));other=text(attrs.get('DBYDETC'))
            kind,classification_basis=classification(main_use,other,name)
            if reg and not classification_basis.startswith('excluded:'):
                rk,rb=classification(text(reg['main_use']),text(reg['other_use']),name)
                if rk and (kind is None or kind=='multifamily'):
                    kind=rk;classification_basis='unique parcel+road register use: '+rb
            if kind is None:skip('not_requested_or_ancillary',{'mainUse':main_use,'otherUse':other,'reason':classification_basis});continue
            w,s,e,n=poly.bounds
            rows=[dict(r) for r in db.execute('SELECT b.id,b.kind,b.parent_id,b.geometry,b.height_m,b.min_height_m,b.num_floors,b.extrude,b.has_parts FROM building_index i JOIN buildings b ON b.rowid=i.rowid WHERE i.minx<=? AND i.maxx>=? AND i.miny<=? AND i.maxy>=?',(e,w,n,s))]
            overlaps=[];legacy_hits=[]
            for row in rows:
                op=poly_for(row['id'],row['geometry'])
                if not op.is_valid or op.is_empty:continue
                intersect=poly.intersection(op).area
                if intersect<=0:continue
                source_ratio=intersect/poly.area;ovt_ratio=intersect/op.area
                overlap={**{k:v for k,v in row.items() if k!='geometry'},'officialRatio':source_ratio,'overtureRatio':ovt_ratio,'overlapAreaM2':intersect*(111320**2)*math.cos(math.radians(point.y))}
                overlaps.append(overlap)
                if row['id'] in owned and overlap['overlapAreaM2']>2 and max(source_ratio,ovt_ratio)>.1:legacy_hits.append(row['id'])
            if legacy_hits:skip('preserved_model_overlap',legacy_hits);continue
            # Exclude a conflicting official polygon rather than doubling it.
            conflicts=[]
            for idx, in output.execute('select rowid from selected_index where minx<=? and maxx>=? and miny<=? and maxy>=?',(e,w,n,s)):
                op=selected[idx];intersection=poly.intersection(op).area
                if intersection>0 and intersection/min(poly.area,op.area)>.1 and metric_area(poly.intersection(op))>2:conflicts.append(idx)
            if conflicts:skip('other_official_footprint_overlap',conflicts);continue
            takeover=[o for o in overlaps if o['kind']=='building' and o['overtureRatio']>=.65 and o['officialRatio']>=.5]
            footprints=[]
            uncovered_parts=[]
            for o in takeover:
                footprints.append(o['id'])
                if o['has_parts']:
                    for child in db.execute('select id,geometry from buildings where parent_id=?',(o['id'],)):
                        cp=poly_for(child['id'],child['geometry'])
                        if not cp.is_valid or cp.is_empty or poly.intersection(cp).area/cp.area<.9:
                            uncovered_parts.append(child['id'])
                        else:footprints.append(child['id'])
            if uncovered_parts:skip('incomplete_coverage_of_source_parts',uncovered_parts);continue
            footprints=sorted(set(footprints))
            if owned.intersection(footprints) or claimed.intersection(footprints):skip('already_owned_source_footprint');continue
            ambiguous=[o for o in overlaps if o['extrude'] and o['id'] not in footprints and o['overlapAreaM2']>2 and max(o['officialRatio'],o['overtureRatio'])>.1]
            if ambiguous:skip('ambiguous_overlap_with_visible_original',[o['id'] for o in ambiguous]);continue
            strong=takeover[0] if len(takeover)==1 and takeover[0]['officialRatio']>=.8 and takeover[0]['overtureRatio']>=.8 else None
            if strong:strong={**strong,'strongOneToOne':True}
            height,floors,basis=safe_height(attrs,reg,strong)
            if height is None:
                floors={'villa':4,'apartment':5,'multifamily':4,'mixed-use':8,'officetel':10}[kind];height=floors*3.05;basis=f'illustrative {floors}-storey fallback; usable source height/floors unavailable'
            if not name:name=f'{district} '+{'villa':'빌라·연립형 주택','apartment':'아파트','multifamily':'공동주택','mixed-use':'주상복합','officetel':'오피스텔'}[kind]+' · '+str(oid)
            tile=tile_for(point.x,point.y);ident='survey-upis-'+str(oid)
            evidence={'officialObjectId':oid,'buildingManagerId':text(attrs.get('BLDG_MGRNU')),'parcelId':text(attrs.get('ADDRESS')),'mainUse':main_use,'otherUse':other,'officialName':official_name,'roadAddress':text(attrs.get('ROAD_NAME')),'sourceFloors':attrs.get('DBJSFLOOR'),'sourceApprovalYear':attrs.get('SAYONG_YEA'),'classificationBasis':classification_basis,'heightBasis':basis,'registerLinkBasis':link_basis,'register':{k:reg[k] for k in ['id','floors','height','main_use','other_use','households','approval_year','roof','structure','source_hash']} if reg else None,'jusoName':j['name'] if j else None,'overtureMatches':[{k:v for k,v in o.items() if k in ['id','officialRatio','overtureRatio','height_m','num_floors']} for o in takeover],'geometrySource':'Seoul UPIS layer 86 public query; snapshot vintage not specified','geometryAreaM2':round(area,3),'sourceBatch':path.name}
            cursor=output.execute('insert into candidates values (?,?,?,?,?,?,?,?,?,?)',(ident,tile,district,kind,name,json.dumps(mapping(poly),separators=(',',':')),height,floors,json.dumps(footprints),json.dumps(evidence,ensure_ascii=False,separators=(',',':'))))
            rid=cursor.lastrowid;output.execute('insert into selected_index values (?,?,?,?,?)',(rid,w,e,s,n));selected[rid]=poly;claimed.update(footprints)
            counts['selected']+=1;kinds[kind]+=1;by_district[district][kind]+=1;height_basis[basis]+=1
            output.execute('insert into dispositions values (?,?,?)',(oid,'selected',ident))
        if len(seen)%5000==0:print(f"audited {len(seen)} / selected {counts['selected']}",flush=True);output.commit()
        if args.sample and len(seen)>=args.sample:break
    if not args.sample and seen!=source_ids:raise ValueError(f'Source ID coverage mismatch: expected {len(source_ids)} got {len(seen)}')
    output.commit();output.close();os.replace(tmp,target)
    result={'baselineModels':len(legacy['assets']),'baselineManifestSha256':sha(ROOT/'public/models/manifest.json'),'retrievedDate':'2026-09-20','counts':dict(counts),'categories':dict(kinds),'districts':{k:dict(v) for k,v in sorted(by_district.items())},'heightBasis':dict(height_basis),'ownedOvertureFootprints':len(claimed),'sourceBatches':inputs,'registerIndexSha256':sha(WORK/'register.sqlite'),'sharedRegisterRecordsNotTransferred':len(registry.shared_records),'selectorSha256':sha(Path(__file__)),'sourceIdsExactlyAccounted':seen==source_ids,'scope':'All downloaded targeted official records accounted for. Excluded conflicts are not fabricated. Source publication/vintage is unspecified; acquisition date is not a construction or survey date.'}
    destination=WORK/('selection-sample-audit.json' if args.sample else 'selection-audit.json');destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sourceBatches','districts','heightBasis')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
