#!/usr/bin/env python3
"""Place literal copies of one reviewed model; never author sibling GLBs or blends."""
import argparse
import copy
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

from publish_bespoke_models import ROOT, PUB, read, encoded, sha, safe_id, replace_batch, validate_mcp_evidence

METRES = 111319.49079327358
LIMITS = ('Shared copy of one representative: only placement, horizontal dimensions and overall height change. '
          'The representative shape, window/floor pattern, roof and hidden facades repeat; these are not '
          'individual photo reconstructions and do not reproduce every target footprint or floor layout.')


def local_polygon(row, anchor):
    lon, lat = anchor
    sx = METRES * math.cos(math.radians(lat))
    return Polygon([((x - lon) * sx, (y - lat) * METRES) for x, y in row['geometry']['coordinates'][0]])


def frame(polygon):
    corners = np.array(polygon.minimum_rotated_rectangle.exterior.coords)[:4]
    edges = np.roll(corners, -1, axis=0) - corners
    lengths = np.linalg.norm(edges, axis=1)
    axis = edges[int(np.argmax(lengths))] / max(lengths)
    if axis[0] < -1e-8 or (abs(axis[0]) < 1e-8 and axis[1] < 0):
        axis = -axis
    basis = np.column_stack((axis, [-axis[1], axis[0]]))
    projected = corners @ basis
    return basis, projected.max(axis=0) - projected.min(axis=0), corners.mean(axis=0)


def placement(source_row, target_row, source_asset):
    source_anchor = [source_asset['coordinate'][k] for k in ['lon', 'lat']]
    ring = target_row['geometry']['coordinates'][0]
    anchor = [(min(p[i] for p in ring) + max(p[i] for p in ring)) / 2 for i in [0, 1]]
    sb, ss, sc = frame(local_polygon(source_row, source_anchor))
    tb, ts, tc = frame(local_polygon(target_row, anchor))
    horizontal = tb @ np.diag(ts / ss) @ sb.T
    offset = tc - horizontal @ sc
    height = float(target_row['register']['height'])
    if not math.isfinite(height) or height <= 0:
        raise ValueError('Missing target height requires an explicitly reviewed estimate')
    sy = height / source_asset['dimensions'][1]
    matrix = [horizontal[0, 0], 0, -horizontal[1, 0], 0,
              0, sy, 0, 0, -horizontal[0, 1], 0, horizontal[1, 1], 0,
              offset[0], 0, -offset[1], 1]
    return anchor, [float(v) for v in matrix]


def publish(args):
    site = safe_id(args.site)
    prefix = safe_id(args.id_prefix)
    identity = read(args.identity)
    bindings = {b['number']: b for b in read(args.bindings)['bindings']}
    manifest_path = PUB / 'bespoke-manifest.json'
    manifest = read(manifest_path)
    by_id = {a['id']: a for a in manifest['assets']}
    source = by_id[args.source_asset]
    if source.get('modelInstance'):
        raise ValueError('Source must be an authored representative, not another instance')
    source_record = source['sourceRecord']
    evidence_path = ROOT / 'docs/model-audit/published-bespoke.json'
    evidence = read(evidence_path)
    source_site = evidence['sites'][source_record['siteId']]
    if source_site['review']['status'] != 'visually-reviewed':
        raise ValueError('Representative has not passed visual review')
    validate_mcp_evidence(source_site['mcpEvidence'])
    if sha(PUB / source['model']) != source['sha256'] or sha(ROOT / source_record['blendSource']) != source_record['blendSha256']:
        raise ValueError('Representative changed after review')
    if site in evidence['sites']:
        raise ValueError('Publication already exists; preserve its immutable audit identity')
    rows = {r['number']: r for r in identity['towers']}
    source_row = rows[args.representative_number]
    if source['footprintIds'] != [source_row['sourceId']]:
        raise ValueError('Representative source ownership does not match inventory')
    fallback_assets = {a['id']: a for a in read(PUB / 'manifest.json')['assets']}
    fallback_assets.update({a['id']: a for c in read(PUB / 'generic-corrections.json')['corrections'] for a in c['assets']})
    matches = read(PUB / 'footprint-matches.json')
    new = []
    for number, row in sorted(rows.items()):
        aid = f'{prefix}-{number}'
        if aid in by_id:
            continue
        binding = bindings[number]
        if binding['sourceFootprintId'] != row['sourceId']:
            raise ValueError('Target fallback source identity differs')
        fallback = fallback_assets[binding['fallbackAssetId']]
        if fallback.get('footprintIds', matches.get(fallback['id'])) != [row['sourceId']] or fallback['sha256'] != binding['fallbackSha256']:
            raise ValueError('Target fallback ownership/hash differs')
        if any(row['sourceId'] in a.get('footprintIds', []) for a in by_id.values()):
            raise ValueError('Target already has a reviewed model under another identity')
        anchor, matrix = placement(source_row, row, source)
        asset = {k: copy.deepcopy(source[k]) for k in ['model', 'sha256', 'heightDatum', 'quality', 'referenceUrl', 'category', 'district', 'minZoom'] if k in source}
        asset.update(id=aid, nameKo=f'{args.name} {number}동', coordinate=dict(zip(['lon', 'lat'], anchor)),
                     yawDegFromEast=0, footprintIds=[row['sourceId']], supersedes=binding['supersedes'],
                     searchable=False, groundOffsetM=0,
                     modelInstance={'sourceAssetId': source['id'], 'sourceDimensions': source['dimensions'],
                                    'matrix': matrix, 'hiddenNodes': args.hidden_node})
        record = copy.deepcopy(source_record)
        for key in ['inferredFromPhotos', 'inferredFrom']:
            record.pop(key, None)
        record.update(provider='Shared representative instance', siteId=site, delivery='shared-instance',
                      modelingBasis='representative-photo-inference',
                      inferredFrom=[{'id': source['id'], 'sha256': source['sha256'], 'siteId': source_record['siteId']}],
                      inferenceScope=LIMITS, accuracy=LIMITS, components=['Shared representative geometry/materials', 'Inventory-based placement/size transform'],
                      uncertainties=[LIMITS, *source_record.get('uncertainties', [])],
                      buildingFacts={'floors': int(row['register']['floors']), 'floorsBasis': 'Existing register metadata; the cloned floor pattern is unchanged',
                                     'heightM': float(row['register']['height']), 'sourceHeightM': row['sourceHeightM'],
                                     'heightBasis': 'Overall cloned envelope scaled to existing registered height; not individual floor reconstruction'})
        asset['sourceRecord'] = record
        new.append(asset)
    if not new:
        raise ValueError('No new instances')
    with tempfile.TemporaryDirectory(prefix='shared-instances-', dir=ROOT / 'data') as name:
        folder = Path(name)
        (folder / 'input.json').write_bytes(encoded({'model': str(PUB / source['model']), 'sha256': source['sha256'], 'instances': new}))
        subprocess.run(['node', str(ROOT / 'scripts/bespoke/measure_instances.mjs'), str(folder / 'input.json'), str(folder / 'bounds.json')], check=True)
        measured = {a['id']: a for a in read(folder / 'bounds.json')}
    records = []
    for asset in new:
        bounds = measured[asset['id']]
        lo, hi = bounds['min'], bounds['max']
        lon, lat = (asset['coordinate'][k] for k in ['lon', 'lat'])
        sx = METRES * math.cos(math.radians(lat))
        asset.update(dimensions=bounds['dimensions'], geoBounds=[lon + lo[0] / sx, lat - hi[2] / METRES, lon + hi[0] / sx, lat - lo[2] / METRES])
        records.append({**bounds, 'sha256': source['sha256'], 'sourceSha256': source_record['sourceGlbSha256'],
                        'sharedModel': source['model'], 'modelInstance': asset['modelInstance']})
    review = copy.deepcopy(source_site['review'])
    review.update(siteId=site, reviewScope='One representative visually reviewed; batch placement checks and sample map review for shared copies',
                  inferenceApprovedAssets=[a['id'] for a in new],
                  comparisons=[*review['comparisons'], LIMITS, 'All copy transforms, bounds, source identities and independent fallback bindings checked automatically.'],
                  limits=[LIMITS, 'Representative number hidden on all copies. Existing authored assets remain unchanged.'])
    evidence['sites'][site] = {'sources': source_site['sources'], 'review': review, 'assets': records,
                             'mcpEvidence': source_site['mcpEvidence'], 'recipeInputs': [],
                             'sharedRepresentative': source['id'], 'newGlbFiles': 0, 'newBlendFiles': 0,
                             'placementInputs': [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for p in [args.identity, args.bindings]],
                             'placementMethod': 'Long-axis oriented rectangle mapping with positive plan scales and registered overall height; actual concave target shapes are not reconstructed.'}
    manifest['assets'].extend(new)
    deployment_path = ROOT / 'public/data/deployment-assets.json'
    deployment = read(deployment_path)
    data = encoded(manifest)
    deployment['files']['public/models/bespoke-manifest.json'] = hashlib.sha256(data).hexdigest()
    replace_batch([], {manifest_path: data, evidence_path: encoded(evidence), deployment_path: encoded(deployment)})
    print(json.dumps({'site': site, 'instances': len(new), 'sharedModel': source['model'], 'newGlbFiles': 0, 'newBlendFiles': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ['identity', 'bindings']:
        parser.add_argument('--' + option, type=lambda p: Path(p).resolve(), required=True)
    for option in ['source-asset', 'site', 'id-prefix', 'name']:
        parser.add_argument('--' + option, required=True)
    parser.add_argument('--representative-number', type=int, required=True)
    parser.add_argument('--hidden-node', action='append', required=True)
    publish(parser.parse_args())
