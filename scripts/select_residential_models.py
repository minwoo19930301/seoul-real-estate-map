"""Select every identifiable, not-yet-modeled residential source footprint.

No household cutoff, district quota, or invented footprint. Classification by
name is disclosed separately from source tags and official complex records.
"""
import collections
import hashlib
import json
import re
import sqlite3
import zlib
from pathlib import Path
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
VILLA = re.compile(r'빌라|빌레|연립|다세대|맨션|맨숀|타운하우스', re.I)
OFFICE = re.compile(r'오피스텔|officetel', re.I)
ANCILLARY = re.compile(r'관리사무소|경로당|경비실|경비초소|어린이집|유치원|교회|상가(?:동)?$')

def source_urls(props):
    urls = []
    for source in props.get('sources', []):
        record = source.get('record_id', '')
        match = re.fullmatch(r'([wrn])(\d+)(?:@\d+)?', record)
        if source.get('dataset') == 'OpenStreetMap' and match:
            urls.append('https://www.openstreetmap.org/' + {'w':'way','r':'relation','n':'node'}[match[1]] + '/' + match[2])
    return sorted(set(urls)) or ['https://docs.overturemaps.org/guides/buildings/']

def classify(row, props):
    name = row['name'] or ''
    if ANCILLARY.search(name): return None, 'ancillary facility name'
    if OFFICE.search(name): return 'officetel', 'source name contains officetel; legal use not independently confirmed'
    if '주상복합' in name: return 'mixed-use', 'source name contains mixed residential/commercial use; legal use not independently confirmed'
    if VILLA.search(name): return 'villa', 'source name contains villa/row-house/multifamily/mansion; legal use not independently confirmed'
    if row['is_apartment']: return 'apartment', 'explicit source apartment classification; household count may be unavailable'
    if props.get('subtype') == 'residential' and props.get('class') == 'terrace':
        return 'villa', 'source class terrace: attached row housing, not proof of Korean legal villa classification'
    return None, 'no specific requested residential class or name evidence'

def main():
    manifest_path = ROOT/'public/models/manifest.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    matches = json.loads((ROOT/'public/models/footprint-matches.json').read_text())
    owned = {bid for ids in matches.values() for bid in ids}
    features = json.loads((ROOT/'data/building-source/districts.geojson').read_text())['features']
    districts = {f['id']:(f['properties']['names']['primary'], shape(f['geometry'])) for f in features}
    db = sqlite3.connect((ROOT/'data/buildings.sqlite').as_uri()+'?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    complexes = json.loads((ROOT/'docs/residential-expansion-complex-matched.json').read_text())
    complex_by_building = {}
    for c in complexes:
        for bid in c['buildingIds']:
            assert bid not in owned and bid not in complex_by_building
            complex_by_building[bid] = c
    official_path = ROOT/'docs/residential-expansion-official-lowrise.json'
    official_lowrise = json.loads(official_path.read_text()) if official_path.exists() else []
    if isinstance(official_lowrise, dict): official_lowrise = official_lowrise.get('candidates', official_lowrise.get('records', []))
    official_by_building = {}
    for c in official_lowrise:
        for bid in c.get('buildingIds', []): official_by_building[bid] = c
    candidates = []
    rejected = []
    stats = collections.Counter()
    district_counts = collections.defaultdict(collections.Counter)
    all_ids = set()
    for row in db.execute("SELECT * FROM buildings WHERE kind='building' ORDER BY district_id,id"):
        stats['sourceBuildings'] += 1
        props = json.loads(zlib.decompress(row['source_properties']))
        kind, basis = classify(row, props)
        c = complex_by_building.get(row['id'])
        official = official_by_building.get(row['id'])
        if c and not kind and not ANCILLARY.search(row['name'] or ''):
            kind, basis = 'apartment', 'official apartment complex candidate membership (approximate where recorded)'
        if official and not kind and not ANCILLARY.search(row['name'] or ''):
            kind, basis = 'villa', 'official multifamily/row-house record and exact named source footprint'
        if not kind:
            stats['notSpecificallyIdentified'] += 1
            continue
        stats['identifiedSourceBuildings'] += 1
        if row['id'] in owned:
            stats['alreadyModeledFootprints'] += 1
            continue
        reason = None
        geometry = shape(json.loads(row['geometry']))
        district = districts.get(row['district_id'])
        child_ids = [x[0] for x in db.execute("SELECT id FROM buildings WHERE parent_id=? AND kind='building_part'", (row['id'],))] if row['has_parts'] else []
        if props.get('is_underground'): reason = 'source marks building underground'
        elif geometry.geom_type not in ('Polygon','MultiPolygon') or geometry.is_empty or not geometry.is_valid: reason = 'invalid or empty source polygon'
        elif row['footprint_area_m2'] < 2: reason = 'source footprint below 2 square metres'
        elif not district or not district[1].covers(geometry.representative_point()): reason = 'source footprint representative point outside retained district'
        elif owned.intersection(child_ids): reason = 'existing model already owns a child footprint'
        elif row['min_height_m'] and row['min_height_m'] > 0: reason = 'elevated source base requires separate structural reconstruction'
        if reason:
            rejected.append({'buildingId':row['id'],'nameKo':row['name'],'reason':reason})
            continue
        # A name-identified officetel/villa keeps that type even when a nearby
        # apartment complex's approximate matching circle contains it.
        compatible = c and (kind == 'apartment' or kind == 'mixed-use')
        if compatible and '주상복합' in c['classification']: kind = 'mixed-use'
        point = geometry.representative_point()
        raw_name = row['name'] or ''
        name = (c['nameKo'] + (' · '+raw_name if raw_name and raw_name != c['nameKo'] else '')) if compatible else raw_name
        unnamed = not name
        if unnamed: name = district[0] + ' ' + {'villa':'연립형 주택','apartment':'아파트','mixed-use':'주상복합','officetel':'오피스텔'}[kind] + ' · ' + row['id'][:8]
        item = {'id':'residential-'+row['id'],'buildingId':row['id'],'nameKo':name,'sourceName':row['name'],'nameIsGeneratedLabel':unnamed,'kind':kind,'district':district[0],'coordinate':{'lon':point.x,'lat':point.y},'buildingIds':[row['id']]+child_ids,'classificationEvidence':basis,'sourceClass':props.get('class'),'sourceSubtype':props.get('subtype'),'sourceUrls':source_urls(props),'heightM':row['height_m'],'floors':row['num_floors'],'hasParts':bool(row['has_parts']),'sourceGeometryBounds':list(geometry.bounds)}
        if compatible:
            raw_count = c.get('householdCount')
            item['complex'] = {'id':c['id'],'code':c['apartmentCode'],'nameKo':c['nameKo'],'classification':c['classification'],'householdCount':raw_count if raw_count and raw_count>0 else None,'sourceHouseholdCount':raw_count,'householdCountScope':'whole official complex; not this individual building','membership':c.get('membership',{'method':c.get('matchingStatus'),'confidence':'exact-name or documented candidate'}),'sourceUrls':c['sourceUrls']}
        if official: item['officialLowriseRecord'] = official
        assert not all_ids.intersection(item['buildingIds'])
        all_ids.update(item['buildingIds'])
        candidates.append(item)
        district_counts[district[0]][kind] += 1
    assert not all_ids.intersection(owned)
    assert len({x['id'] for x in candidates}) == len(candidates)
    used_complexes = {c['complex']['id'] for c in candidates if c.get('complex')}
    audit = {'baselineModels':len(manifest['assets']),'baselineManifestSha256':hashlib.sha256(manifest_bytes).hexdigest(),'counts':dict(stats),'newModels':len(candidates),'newOwnedFootprints':len(all_ids),'categories':dict(collections.Counter(c['kind'] for c in candidates)),'districts':{d:dict(v) for d,v in sorted(district_counts.items())},'complexesLinked':len(used_complexes),'complexCandidatesWithoutCompatibleBuilding':[c['id'] for c in complexes if c['id'] not in used_complexes],'rejected':rejected,'scope':'Every identifiable requested residential building in the retained source snapshot after preservation and geometry checks. Not proof of complete coverage of all real Seoul villas, officetels, or <=100-household apartments. Unknown-use footprints remain unclassified. Zero household counts treated as unavailable.'}
    (ROOT/'docs/residential-model-candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'docs/RESIDENTIAL_SELECTION_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    reread = json.loads((ROOT/'docs/residential-model-candidates.json').read_text())
    assert len(reread)==audit['newModels'] and not ({b for c in reread for b in c['buildingIds']}&owned)
    print(json.dumps({k:v for k,v in audit.items() if k not in ('districts','rejected')},ensure_ascii=False))

if __name__ == '__main__': main()
