"""Freeze retained source footprints for photo-informed apartment drafts.

Run with an explicit read-only source database and a reviewed target list.
This preserves existing geometry; it does not verify current tower identities.
"""
import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path


def prepare(targets, database, manifest):
    assets = {a['id']: a for a in manifest['assets']}
    result = []
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        for target in targets:
            asset = assets[target['assetId']]
            anchor = asset['coordinate']
            scale = 111319.49079327358
            coslat = math.cos(math.radians(anchor['lat']))
            north0 = math.log(math.tan(math.pi / 4 + math.radians(anchor['lat']) / 2))
            towers, issues = [], []
            for source_id in asset['footprintIds']:
                row = db.execute('SELECT * FROM buildings WHERE id=?', (source_id,)).fetchone()
                if row is None:
                    issues.append(f'Missing source building: {source_id}')
                    continue
                geometry = json.loads(row['geometry'])
                if geometry['type'] != 'Polygon' or len(geometry['coordinates']) != 1:
                    issues.append(f'Non-simple polygon needs manual review: {source_id}')
                    continue
                ring = [[(lon-anchor['lon'])*scale*coslat,
                         (math.log(math.tan(math.pi/4+math.radians(lat)/2))-north0)
                         *6378137*coslat]
                        for lon, lat, *_ in geometry['coordinates'][0]]
                if not row['height_m'] and not row['num_floors']:
                    issues.append(f'Missing height and floors: {source_id}')
                towers.append({key: row[key] for key in
                    ['id', 'name', 'height_m', 'num_floors', 'geometry_source', 'height_source']}
                    | {'ringEastNorthM': ring,
                       'heightNote': 'Existing source, not newly surveyed; missing heights require explicit estimates.'})
            result.append({**target, 'officialBuildingCount': target['buildings'],
                           'legacyAssetIds': [asset['id']], 'sourceModel': asset['model'],
                           'sourceSha256': asset['sha256'], 'anchor': anchor,
                           'towers': towers, 'sourceIssues': issues,
                           'status': 'source_review_needed' if issues else 'candidate_not_modeled'})
    return {'method': 'Retained source polygons, Mercator differences scaled at anchor latitude',
            'sourceIdentityVerified': False, 'sites': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', type=Path)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=Path('public/models/manifest.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = prepare(json.loads(args.targets.read_text()), args.database,
                   json.loads(args.manifest.read_text()))
    data['targetSha256'] = hashlib.sha256(args.targets.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'sites': len(data['sites']),
                      'buildings': sum(len(s['towers']) for s in data['sites']),
                      'sitesWithIssues': sum(bool(s['sourceIssues']) for s in data['sites'])}))
