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
from shapely.geometry import Polygon, shape
from shapely.ops import transform

from bespoke.validate_height_regions import read_triangles

from publish_bespoke_models import ROOT, PUB, read, encoded, sha, safe_id, replace_batch, validate_mcp_evidence

METRES = 111319.49079327358
LIMITS = ('Shared copy of one representative: only placement, horizontal dimensions and overall height change. '
          'The representative shape, window/floor pattern, roof and hidden facades repeat; these are not '
          'individual photo reconstructions and do not reproduce every target footprint or floor layout.')


def local_polygon(row, anchor):
    lon, lat = anchor
    sx = METRES * math.cos(math.radians(lat))
    geometry = shape(row['geometry'])
    if geometry.geom_type not in ('Polygon', 'MultiPolygon') or geometry.is_empty or not geometry.is_valid:
        raise ValueError('Placement requires valid nonempty Polygon or MultiPolygon')
    return transform(lambda x, y, z=None: ((np.asarray(x) - lon) * sx, (np.asarray(y) - lat) * METRES), geometry)


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


def target_height(row, estimated_storey_height=None):
    registered = float(row['register']['height'] or 0)
    if math.isfinite(registered) and registered > 0:
        return registered, 'Overall cloned envelope scaled to existing registered height; not individual floor reconstruction'
    floors = int(row['register']['floors'])
    if estimated_storey_height is None or not 2 <= estimated_storey_height <= 6 or floors <= 0:
        raise ValueError('Missing target height requires an explicitly reviewed estimate')
    return floors * estimated_storey_height, f'Estimated {floors} floors x {estimated_storey_height}m; registered height missing/zero, not measured; cloned floor pattern unchanged'


def placement(source_row, target_row, source_asset, estimated_storey_height=None, *, height_override=None, anchor_override=None):
    source_anchor = [source_asset['coordinate'][k] for k in ['lon', 'lat']]
    bounds = shape(target_row['geometry']).bounds
    anchor = [(bounds[i] + bounds[i + 2]) / 2 for i in [0, 1]]
    if anchor_override is not None:
        anchor = list(anchor_override)
    sb, ss, sc = frame(local_polygon(source_row, source_anchor))
    tb, ts, tc = frame(local_polygon(target_row, anchor))
    horizontal = tb @ np.diag(ts / ss) @ sb.T
    offset = tc - horizontal @ sc
    height = height_override if height_override is not None else target_height(target_row, estimated_storey_height)[0]
    sy = height / source_asset['dimensions'][1]
    matrix = [horizontal[0, 0], 0, -horizontal[1, 0], 0,
              0, sy, 0, 0, -horizontal[0, 1], 0, horizontal[1, 1], 0,
              offset[0], 0, -offset[1], 1]
    return anchor, [float(v) for v in matrix]


def effective_fallback_assets(assets, corrections):
    current = {asset['id']: asset for asset in assets}
    for correction in corrections:
        current.pop(correction['sourceId'], None)
        current.update({asset['id']: asset for asset in correction['assets']})
    return current


PRESERVED_HEIGHT_BASIS = ('Existing visible fallback estimate preserved; registered height conflict unresolved, '
                          'not measured; cloned floor pattern unchanged')


def preserved_fallback_height(fallback):
    """Measure baked GLB triangles, rather than trusting catalog height metadata."""
    if (fallback.get('rootTransform') not in (None, 'identity') or fallback.get('modelInstance')
            or fallback.get('yawDegFromEast', 0) != 0 or fallback.get('groundOffsetM', 0) != 0
            or any(k in fallback for k in ('matrix', 'scale', 'rotation', 'translation'))):
        raise ValueError('Fallback height preservation requires an untransformed grounded model')
    path = (PUB / fallback['model']).resolve()
    if not path.is_relative_to(PUB.resolve()) or not path.is_file():
        raise ValueError('Fallback GLB is missing or outside the model directory')
    digest = sha(path)
    if digest != fallback['sha256']:
        raise ValueError('Fallback GLB hash differs from binding')
    # The existing decoder rejects scene/node transforms, skins, morphs and non-finite vertices.
    triangles = read_triangles(path)
    if not triangles.size or not np.isfinite(triangles).all():
        raise ValueError('Fallback geometry has no finite bounds')
    lo, hi = triangles.reshape(-1, 3).min(axis=0), triangles.reshape(-1, 3).max(axis=0)
    height = float(hi[1] - lo[1])
    if not math.isfinite(height) or height <= 0 or abs(float(lo[1])) > .01:
        raise ValueError('Fallback height must be finite, positive and grounded at local Y zero')
    coordinate = fallback.get('coordinate', {})
    anchor = [coordinate.get(k) for k in ('lon', 'lat')]
    if (not all(isinstance(v, (int, float)) and math.isfinite(v) for v in anchor)
            or not -180 <= anchor[0] <= 180 or not -90 <= anchor[1] <= 90):
        raise ValueError('Fallback anchor must be finite geographic coordinates')
    proof = {'policy': 'preserve-existing-visible-fallback-height', 'fallbackId': fallback['id'],
             'fallbackSha256': digest, 'fallbackModel': fallback['model'], 'heightM': height,
             'localBounds': {'min': lo.tolist(), 'max': hi.tolist()}, 'anchor': anchor,
             'heightBasis': PRESERVED_HEIGHT_BASIS}
    return height, proof


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
    preserve_numbers = set(getattr(args, 'preserve_fallback_height_for', []) or [])
    if preserve_numbers - rows.keys():
        raise ValueError('Unknown height-preservation target number')
    if args.representative_number in preserve_numbers:
        raise ValueError('Cannot preserve fallback height for the representative')
    if any(f'{prefix}-{number}' in by_id for number in preserve_numbers):
        raise ValueError('Height-preservation target already exists')
    source_row = rows[args.representative_number]
    if source['footprintIds'] != [source_row['sourceId']]:
        raise ValueError('Representative source ownership does not match inventory')
    fallback_assets = effective_fallback_assets(
        read(PUB / 'manifest.json')['assets'],
        read(PUB / 'generic-corrections.json')['corrections'])
    matches = read(PUB / 'footprint-matches.json')
    new = []
    for number, row in sorted(rows.items()):
        aid = f'{prefix}-{number}'
        if aid in by_id:
            continue
        binding = bindings[number]
        if binding['sourceFootprintId'] != row['sourceId']:
            raise ValueError('Target fallback source identity differs')
        fallback = fallback_assets.get(binding['fallbackAssetId'])
        if fallback is None:
            raise ValueError('Target fallback is no longer active: ' + binding['fallbackAssetId'])
        if fallback.get('footprintIds', matches.get(fallback['id'])) != [row['sourceId']] or fallback['sha256'] != binding['fallbackSha256']:
            raise ValueError('Target fallback ownership/hash differs')
        if any(row['sourceId'] in a.get('footprintIds', []) for a in by_id.values()):
            raise ValueError('Target already has a reviewed model under another identity')
        height_policy = None
        if number in preserve_numbers:
            height, height_policy = preserved_fallback_height(fallback)
            height_basis = PRESERVED_HEIGHT_BASIS
            anchor, matrix = placement(source_row, row, source, args.estimated_storey_height,
                                       height_override=height, anchor_override=height_policy['anchor'])
        else:
            anchor, matrix = placement(source_row, row, source, args.estimated_storey_height)
            height, height_basis = target_height(row, args.estimated_storey_height)
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
                                     'heightM': height, 'registeredHeightM': float(row['register']['height'] or 0), 'sourceHeightM': row.get('sourceHeightM', row.get('osmHeightM')),
                                     'heightBasis': height_basis})
        if height_policy is not None:
            asset['heightEstimated'] = True
            record['heightPolicy'] = height_policy
            record['buildingFacts']['heightUnresolved'] = True
            record['uncertainties'].append(PRESERVED_HEIGHT_BASIS)
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
                        'sharedModel': source['model'], 'modelInstance': asset['modelInstance'],
                        **({'heightPolicy': asset['sourceRecord']['heightPolicy']}
                           if 'heightPolicy' in asset['sourceRecord'] else {})})
    review = copy.deepcopy(source_site['review'])
    review.update(siteId=site, reviewScope='One representative visually reviewed; batch placement checks and sample map review for shared copies',
                  inferenceApprovedAssets=[a['id'] for a in new],
                  comparisons=[*review['comparisons'], LIMITS, 'All copy transforms, bounds, source identities and independent fallback bindings checked automatically.'],
                  limits=[LIMITS, 'Representative number hidden on all copies.' if args.hidden_node else 'Representative has no number label; no node needs hiding.', 'Existing authored assets remain unchanged.'])
    evidence['sites'][site] = {'sources': source_site['sources'], 'review': review, 'assets': records,
                             'mcpEvidence': source_site['mcpEvidence'], 'recipeInputs': [],
                             'sharedRepresentative': source['id'], 'newGlbFiles': 0, 'newBlendFiles': 0,
                             'placementInputs': [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for p in [args.identity, args.bindings]],
                             'placementMethod': 'Long-axis oriented rectangle mapping with positive plan scales and explicit per-target height basis; actual concave target shapes are not reconstructed.'}
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
    parser.add_argument('--hidden-node', action='append', default=[], help='Repeat for representative number-label nodes; omit when the representative is unlabeled')
    parser.add_argument('--estimated-storey-height', type=float, help='Explicit estimate used only where the register height is missing/zero')
    parser.add_argument('--preserve-fallback-height-for', type=int, action='append', default=[], metavar='NUMBER',
                        help='Explicitly preserve this target current fallback GLB height; repeat for each reviewed unresolved-height exception')
    publish(parser.parse_args())
