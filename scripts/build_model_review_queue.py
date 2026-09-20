#!/usr/bin/env python3
"""Inventory model records for individual likeness review; never infer fidelity from hashes."""
import collections, gzip, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/model-audit'
BUCKETS=['landmarks','apartments-400-plus','bridges-parks-heritage','civic-institutions','apartments-100-399','remaining-housing','pending-household-classification','pending-physical-type']
ORIGINAL={'sixtythree','lotte','nseoul','coex','gyeongbokgung'}
# Existing category 'cultural-site' mixes shopping malls, heritage, parks and courts.
# These named exceptions classify physical use, not visual quality.
MODERN={'central-city','ddp','galleria-west','garden-five','gimpo-airport','gocheok-skydome','jamsil-sports-complex','jangchung-arena','lotte-world-magic-island','mario-outlet','mokdong-stadium','noryangjin-market','sebitseom','sejong-center','seoul-arts-center','seoul-dragon-city','seoul-world-cup-stadium','taereung-skating','technomart','times-square','walkerhill','yoido-full-gospel','dcube-city'}
CIVIC={'national-assembly','supreme-court','chung-ang-univ','ewha-ecc','hanyang-univ','hongik-univ','korea-univ-main','kyunghee-peace-hall','sejong-univ','seoultech','snu-main-gate','univ-of-seoul','yonsei-underwood'}
def bucket(a,h):
    aid=a['id'];cat=a.get('category','');slug=aid.removeprefix('reference-flight-');name=a.get('nameKo','')
    if aid in ORIGINAL or aid=='bespoke-hyperion-department-store' or cat in {'landmark','company-office'} or slug in MODERN:return 'landmarks'
    if cat in {'city-hall','k12-school','district-public-office'} or slug in CIVIC or name.endswith('구청') or name=='국회의사당':return 'civic-institutions'
    if cat in {'bridge','park','heritage','cultural-site'}:return 'bridges-parks-heritage'
    if cat=='civic-cultural-landmark':return 'bridges-parks-heritage' if name in {'독립문','봉은사 진여문','현충관'} else 'landmarks'
    if cat in {'apartment','residential-apartment','major-apartment-complex','named-apartment-site'}:
        if h is None:return 'pending-household-classification'
        return 'apartments-400-plus' if h>=400 else 'apartments-100-399' if h>=100 else 'remaining-housing'
    if cat in {'villa','multifamily','officetel','mixed-use','residential-villa','residential-multifamily','residential-officetel','residential-mixed-use'}:return 'remaining-housing'
    return 'pending-physical-type'
def read(p):return json.loads(p.read_text())
def main():
    legacy=read(ROOT/'public/models/manifest.json')['assets'];refs=read(ROOT/'public/models/reference-manifest.json')
    bespoke=read(ROOT/'public/models/bespoke-manifest.json');known={a['id']:a for a in legacy}
    maple=next(p for p in refs['places'] if p['id']=='reference:maple-xi')
    rows=[];seen=set();all_assets=legacy+refs['assets']+bespoke['assets']
    reverse=collections.defaultdict(list)
    for a in all_assets:
        for old in a.get('supersedes',[]):reverse[old].append(a['id'])
    reviews=read(OUT/'published-bespoke.json')['sites'] if (OUT/'published-bespoke.json').exists() else {}
    def add(a,origin):
        if a['id'] in seen:return
        seen.add(a['id']);h=a.get('householdCount');evidence=None
        if (a['id'].startswith('maple-xi-') or a.get('sourceRecord',{}).get('siteId')=='maple-club-cloud') and a.get('category') in {'apartment','residential-apartment'}:h=maple['household_count'];evidence={'basis':'complex total, not per building','source':maple['source_url']}
        if a['id']=='reference-flight-hyperion' or a.get('sourceRecord',{}).get('siteId')=='hyperion':h=known['apt-a15805114']['householdCount'];evidence={'basis':'known apartment component of mixed-use complex; not every tower total','assetId':'apt-a15805114'}
        if a['id']=='reference-flight-tower-palace':h=max(known[x]['householdCount'] for x in ['apt-a13585402','apt-a13585403']);evidence={'basis':'one known component meets threshold; not entire compound total','assetIds':['apt-a13585402','apt-a13585403']}
        if a['id']=='reference-flight-cheongnyangni-skyl65' or a['id'].startswith('bespoke-skyl65-'):h=1425;evidence={'basis':'official complex total, not per tower','source':'https://www.lottecastle.co.kr/APT/AT00174/1449/summary/view.do'}
        site=a.get('sourceRecord',{}).get('siteId');review=reviews.get(site,{}).get('review',{})
        b=bucket(a,h);row={'id':a['id'],'nameKo':a.get('nameKo',a.get('name')),'origin':origin,'category':a.get('category'),'district':a.get('district'),'coordinate':a.get('coordinate'),'footprintIds':a.get('footprintIds',[]),'priorityRank':BUCKETS.index(b)+1,'priorityBucket':b,'needsVisualReview':review.get('status')!='visually-reviewed','visualStatus':review.get('status','unreviewed')}
        if h is not None:row['householdCountForPriority']=h
        if evidence:row['householdCountEvidence']=evidence
        if a.get('supersedes'):row['supersedes']=a['supersedes']
        if reverse[a['id']]:row['supersededBy']=sorted(reverse[a['id']])
        if site:row['siteId']=site;row['reviewLimits']=review.get('limits')
        if site=='maple-club-cloud':row['fullExteriorReviewPending']=True
        rows.append(row)
    for a in legacy:add(a,'legacy-manifest')
    for f in sorted((ROOT/'public/models/residential-survey/tiles').glob('*.json')):
        for a in read(f)['assets']:add(a,'residential-survey')
    for a in refs['assets']:add(a,'reference-manifest')
    for a in bespoke['assets']:add(a,'bespoke-manifest')
    rows.sort(key=lambda r:(r['priorityRank'],r['district'] or '',r['id']))
    raw=''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows).encode()
    OUT.mkdir(parents=True,exist_ok=True)
    with gzip.GzipFile(OUT/'rebuild-queue.jsonl.gz','wb',mtime=0) as z:z.write(raw)
    counts=collections.Counter((r['origin'],r['priorityBucket']) for r in rows)
    summary={'exactAssetRecords':len(rows),'baselineAssetRecords':sum(r['origin']!='bespoke-manifest' for r in rows),'reviewedNewAssetRecords':sum(r['visualStatus']=='visually-reviewed' for r in rows),'uniquePhysicalSiteCount':None,'status':'Model-file inventory, not physical building count; pending records have not been rebuilt.','counts':{f'{o}:{b}':n for (o,b),n in sorted(counts.items())},'priorityOrder':dict(enumerate(BUCKETS,1)),'sha256UncompressedJsonl':hashlib.sha256(raw).hexdigest(),'source':'scripts/build_model_review_queue.py','nonAssetTargets':[{'name':'서울고속버스터미널 경부·영동선','sourceFootprintId':'c313b964-022c-4f5a-9599-d69d0155d010','previousState':'raw source extrusion; no dedicated legacy asset','replacement':'bespoke-seoul-express-terminal'}]}
    (OUT/'rebuild-queue-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    table='\n'.join(f'| {i+1} | {b} | {sum(r["priorityBucket"]==b for r in rows):,} |' for i,b in enumerate(BUCKETS))
    (OUT/'rebuild-priority-summary.md').write_text('# Individual model review backlog\n\nGenerated by `scripts/build_model_review_queue.py`. Reference provenance, triangle counts, different colors and unique hashes do not establish likeness. Only published assets with a recorded photo/render comparison are marked reviewed.\n\n| Priority | Physical type | Model records |\n| --- | --- | ---: |\n'+table+'\n\nApartments without household evidence remain unclassified; known villas/officetels do not need a household count to enter priority6. City halls, courts and universities are civic; explicitly identified modern cultural-category malls/stadiums are landmarks; heritage and parks are priority3. Original five protected landmarks retain priority1. These are scheduling rules, not statements about architectural quality.\n\nA complex may contain multiple assets and legacy replacements. `supersededBy`/`supersedes` record known relationships; the number of unique physical sites is unknown. Existing models remain visible until a replacement renders. No mass facade generator was rerun.\n\nSee `rebuild-queue-summary.json` for current counts and the deterministic compressed queue for individual records.\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in {'counts','nonAssetTargets'}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
