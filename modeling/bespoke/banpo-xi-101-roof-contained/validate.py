import importlib.util
import json
import hashlib
import math
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform, unary_union

ROOT = Path('/Users/hyemini/Documents/Codex/2026-09-21/seoul-real-estate-map')
spec = importlib.util.spec_from_file_location('regions', ROOT / 'scripts/bespoke/validate_height_regions.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
stage = ROOT / 'data/model-source/bespoke/banpo-xi-101-roof-contained'
sources = {x['number']: x for x in json.loads((ROOT / 'docs/model-audit/banpo-xi-source-identity.json').read_text())['towers']}

for number in [101]:
    local = stage
    data = json.loads((local / 'source-data.json').read_text())
    source = sources[number]
    assert source['sourceId'] == data['id'] and source['geometry'] == data['geometry']
    assert source['register']['height'] == '81.3' and source['register']['floors'] == '29'
    lon, lat = data['anchor_lonlat']
    footprint = transform(lambda x, y: ((x-lon)*111320*math.cos(math.radians(lat)), (y-lat)*111320), shape(source['geometry']))
    ring = np.asarray(data['ring_m'])
    assert footprint.symmetric_difference(Polygon(ring)).area < 1e-8
    if number == 101:
        theta = math.atan2(ring[5, 1]-ring[4, 1], ring[5, 0]-ring[4, 0])
        normal = np.array([math.cos(theta), math.sin(theta)])
        threshold = -5.5
    else:
        theta = data['facade_axis_rad_inferred']
        normal = np.array([math.sin(theta), -math.cos(theta)])
        threshold = 7.2
    tangent = np.array([-normal[1], normal[0]])
    halfplane = Polygon([normal*u+tangent*v for u, v in [(threshold,-1000),(1000,-1000),(1000,1000),(threshold,1000)]])
    upper = footprint.intersection(halfplane)
    lower = footprint.difference(upper)
    assert upper.is_valid and lower.is_valid and upper.area > 100 and lower.area > 100
    scaled = 81.3/81
    decks = [78/29*24*scaled, 78*scaled]
    ceilings = [(78/29*24+3)*scaled, 81.3]
    regions = [{'id': label, 'geometry': mapping(poly), 'height_m': ceiling}
               for label, poly, ceiling in zip(['inferred-lower','inferred-upper'], [lower,upper], ceilings)]
    glb = local / f'banpo-xi-{number}.glb'
    triangles = module.read_triangles(glb)
    horizontal = triangles[:, :, [0, 2]] * [1, -1]
    assert abs(triangles[:, :, 1].min()) < 1e-5
    assert abs(triangles[:, :, 1].max()-81.3) < 1e-4
    checks = module.inspect_regions(triangles, regions, boundary_tolerance=.65)
    for report, polygon, deck in zip(checks, [lower,upper], decks):
        # Open pergolas rise3m above the deck: check the actual roof plane,
        # separately from the maximum ornament envelope.
        roof_triangles = triangles[np.max(np.abs(triangles[:, :, 1]-deck), axis=1) < 1e-4]
        cap = unary_union([Polygon(t[:, [0, 2]] * [1,-1]) for t in roof_triangles])
        interior = polygon.buffer(-.03)
        report['deckHeightM'] = deck
        report['deckCoverageRatio'] = 1-interior.difference(cap).area/interior.area
        assert report['overHeightTriangles'] == 0, (number, report)
        assert report['deckCoverageRatio'] > .999999, (number, report)
    ground = triangles[np.max(np.abs(triangles[:, :, 1]), axis=1) < 1e-5]
    grade = unary_union([Polygon(t[:, [0, 2]] * [1,-1]) for t in ground])
    missing = footprint.difference(grade).area
    projection = float(np.max(shapely.distance(shapely.points(horizontal.reshape(-1,2)), footprint)))
    assert missing < .001, (number, missing, projection)
    result = {'number': number, 'passed': projection < .65, 'glbSha256': hashlib.sha256(glb.read_bytes()).hexdigest(),
              'heightM':81.3, 'floors':29, 'missingGradeAreaM2':missing,
              'extraGradeDecorationAreaM2': grade.difference(footprint).area,
              'maximumProjectionBeyondSourceM':projection, 'heightRegions':regions,
              'checks':checks, 'limitation':'Both wing geometry and24/29-floor stepping are explicitly complex-photo inference, not sourced child heights. Roof deck and3m ornament envelope are checked separately.'}
    (local / 'independent-geometry-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print(number, 'projection', projection, 'roof checks', [(c['id'], c['overHeightTriangles'], c['deckCoverageRatio']) for c in checks])
