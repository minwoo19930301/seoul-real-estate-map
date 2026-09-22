#!/usr/bin/env python3
"""Check shared representative body plans against source neighbors and other copies."""
import json
import math
from pathlib import Path
from shapely.geometry import Polygon
from shapely.affinity import affine_transform

ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads((ROOT/p).read_text())

def check():
    assets=read('public/models/bespoke-manifest.json')['assets'];by_id={a['id']:a for a in assets}
    published=read('docs/model-audit/published-bespoke.json')['sites'];reports=[];groups={}
    superseded={aid for a in assets for aid in a.get('supersedes',[])}
    for site,proof in published.items():
        if not proof.get('sharedRepresentative'):continue
        identity_path=proof['placementInputs'][0]['path'];identity=read(identity_path)
        key=identity.get('complex',{}).get('managementCode') or identity_path
        group=groups.setdefault(key,{'paths':[],'sites':[],'rows':{}})
        if identity_path not in group['paths']:group['paths'].append(identity_path)
        group['sites'].append(site)
        for row in identity['towers']:
            prior=group['rows'].get(row['sourceId'])
            if prior is not None and (prior['number']!=row['number'] or prior['geometry']!=row['geometry']):
                raise ValueError('Conflicting source identity across shared batches: '+row['sourceId'])
            group['rows'][row['sourceId']]=row
    for group in groups.values():
        sites=group['sites'];rows=group['rows'];identity_path=group['paths'][0]
        copies=[a for a in assets if a['sourceRecord']['siteId'] in sites and a['id'] not in superseded]
        origin=next(iter(rows.values()))['geometry']['coordinates'][0][0];sy=111319.49079327358;sx=sy*math.cos(math.radians(origin[1]))
        def world(coords):return Polygon([((x-origin[0])*sx,(y-origin[1])*sy) for x,y in coords]).buffer(0)
        originals={fid:world(r['geometry']['coordinates'][0]) for fid,r in rows.items()};plans={};hits=[]
        for a in copies:
            source=by_id[a['modelInstance']['sourceAssetId']];c=source['coordinate'];ssx=sy*math.cos(math.radians(c['lat']))
            p=Polygon([((x-c['lon'])*ssx,(y-c['lat'])*sy) for x,y in rows[source['footprintIds'][0]]['geometry']['coordinates'][0]]).buffer(0)
            m=a['modelInstance']['matrix'];plan=affine_transform(p,[m[0],-m[8],-m[2],m[10],m[12],-m[14]])
            c=a['coordinate'];plan=affine_transform(plan,[sx/(sy*math.cos(math.radians(c['lat']))),0,0,1,(c['lon']-origin[0])*sx,(c['lat']-origin[1])*sy]);plans[a['footprintIds'][0]]=plan
            for fid,poly in originals.items():
                if fid==a['footprintIds'][0]:continue
                overlap=plan.intersection(poly).area
                if overlap>.01:hits.append({'asset':a['id'],'neighbor':rows[fid]['number'],'overlapM2':overlap})
        pairs=[];keys=list(plans)
        for i,fid in enumerate(keys):
            for other in keys[i+1:]:
                area=plans[fid].intersection(plans[other]).area
                if area>.01:pairs.append({'a':rows[fid]['number'],'b':rows[other]['number'],'overlapM2':area})
        reports.append({'identity':identity_path,'identityPaths':group['paths'],'sourceBodies':len(rows),'sites':sites,'copies':len(copies),'bodyPlanNeighborOverlaps':hits,'copyToCopyOverlaps':pairs,
                        'scope':'Transformed representative source-body plans; ornamental projection and exact target-shape fidelity are not certified.'})
    return reports

if __name__=='__main__':
    reports=check();(ROOT/'docs/model-audit/shared-instance-placement-check.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(reports,ensure_ascii=False))
    if any(r['bodyPlanNeighborOverlaps'] or r['copyToCopyOverlaps'] for r in reports):raise SystemExit(1)
