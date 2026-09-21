import importlib.util
import json
import math
import unittest
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon, shape, mapping
from shapely.ops import transform, unary_union

path = Path(__file__).resolve().parents[1] / 'scripts/bespoke/validate_height_regions.py'
spec = importlib.util.spec_from_file_location('height_regions', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def cap(x0, x1, height, y0=0, y1=10):
    a, b, c, d = [[x0, height, -y0], [x1, height, -y0], [x1, height, -y1], [x0, height, -y1]]
    return [[a, b, c], [a, c, d]]


def region(name, x0, x1, height):
    return {'id': name, 'height_m': height, 'rings': [[[x0, 0], [x1, 0], [x1, 10], [x0, 10]]]}


class HeightRegions(unittest.TestCase):
    def test_shinbanpo7_preserves_registered_envelopes_and_full_concave_roof_caps(self):
        self.assert_registered_envelopes('shinbanpo-xi', range(101, 108), 607)

    def test_acro_riverview5_preserves_registered_envelopes_and_full_concave_roof_caps(self):
        self.assert_registered_envelopes('acro-riverview', range(101, 106), 595)

    def test_banpo_riche9_preserves_registered_envelopes_and_full_concave_roof_caps(self):
        self.assert_registered_envelopes('banpo-riche', range(101, 110), 1119, {106: 'residential-025a7bbd-1c33-4f47-90fd-1f874b5ba0d8'})

    def test_seoulforest7_preserves_registered_envelopes_and_full_concave_roof_caps(self):
        self.assert_registered_envelopes('seoulforest-riverview-xi', range(101, 108), 1034)

    def assert_registered_envelopes(self, site, numbers, households, fallback_ids=None):
        root = path.parents[2]
        assets = {a['id']: a for a in json.loads((root / 'public/models/bespoke-manifest.json').read_text())['assets']}
        sources = json.loads((root / f'docs/model-audit/{site}-source-identity.json').read_text())['towers']
        self.assertEqual([s['number'] for s in sources], list(numbers))
        self.assertEqual(sum(int(s['register']['households']) for s in sources), households)
        for source in sources:
            with self.subTest(number=source['number']):
                asset = assets[f"bespoke-{site}-{source['number']}"]
                self.assertEqual(asset['footprintIds'], [source['sourceId']])
                self.assertEqual(asset['supersedes'], [(fallback_ids or {}).get(source['number'], f"fallback-{site}-{source['number']}")])
                self.assertEqual(source['sourceChildIds'], [])
                facts = asset['sourceRecord']['buildingFacts']
                self.assertEqual(facts['heightM'], float(source['register']['height']))
                self.assertEqual(facts['floors'], int(source['register']['floors']))
                self.assertEqual(facts['sourceHeightM'], source['sourceHeightM'])
                lon, lat = asset['coordinate']['lon'], asset['coordinate']['lat']
                footprint = transform(lambda x, y: ((x-lon)*111320*math.cos(math.radians(lat)), (y-lat)*111320), shape(source['geometry']))
                triangles = module.read_triangles(root / 'public/models' / asset['model'])
                self.assertTrue(np.isfinite(triangles).all())
                self.assertAlmostEqual(float(triangles[:, :, 1].min()), 0, places=5)
                self.assertAlmostEqual(float(triangles[:, :, 1].max()), facts['heightM'], places=4)
                points = module.shapely.points((triangles[:, :, [0, 2]] * [1, -1]).reshape(-1, 2))
                self.assertLess(float(module.shapely.distance(points, footprint).max()), .5)
                recipe = (root / asset['sourceRecord']['blendSource']).parent
                regions = json.loads((recipe / 'regions.json').read_text())
                self.assertEqual(len(regions), 1)
                self.assertLess(footprint.symmetric_difference(shape(regions[0]['geometry'])).area, 1e-8)
                deck_height = regions[0]['roof_deck_height_m']
                for height in [0, deck_height]:
                    cap = triangles[np.max(np.abs(triangles[:, :, 1] - height), axis=1) < 1e-4]
                    union = unary_union([Polygon(t[:, [0, 2]] * [1, -1]) for t in cap])
                    self.assertLess(footprint.buffer(-.03).difference(union).area, .001)
                raised = triangles[np.min(triangles[:, :, 1], axis=1) > deck_height + .01]
                raised_points = module.shapely.points((raised[:, :, [0, 2]] * [1, -1]).reshape(-1, 2))
                self.assertLess(float(module.shapely.distance(raised_points, footprint).max()), 1e-5)

    def test_banpo_xi_numbered_models_keep_source_footprints_roof_decks_and_registered_maxima(self):
        root = path.parents[2]
        assets = json.loads((root / 'public/models/bespoke-manifest.json').read_text())['assets']
        sources = {s['number']: s for s in json.loads((root / 'docs/model-audit/banpo-xi-source-identity.json').read_text())['towers']}
        family = [a for a in assets if a['id'].startswith('bespoke-banpo-xi-')]
        self.assertGreaterEqual(len(family), 13)
        self.assertEqual(sum(int(s['register']['households']) for s in sources.values()), 3410)
        for asset in family:
            with self.subTest(asset=asset['id']):
                number = int(asset['id'].removeprefix('bespoke-banpo-xi-'))
                source = sources[number]
                self.assertNotIn('unresolvedHeightConflict', source)
                self.assertEqual(asset['footprintIds'], [source['sourceId']])
                facts = asset['sourceRecord']['buildingFacts']
                self.assertEqual(facts['heightM'], float(source['register']['height']))
                self.assertEqual(facts['floors'], int(source['register']['floors']))
                self.assertEqual(facts['sourceHeightM'], source['osmHeightM'])
                lon, lat = asset['coordinate']['lon'], asset['coordinate']['lat']
                footprint = transform(lambda x, y: ((x-lon)*111320*math.cos(math.radians(lat)), (y-lat)*111320), shape(source['geometry']))
                triangles = module.read_triangles(root / 'public/models' / asset['model'])
                self.assertAlmostEqual(float(triangles[:, :, 1].min()), 0, places=5)
                self.assertAlmostEqual(float(triangles[:, :, 1].max()), facts['heightM'], places=4)
                horizontal = triangles[:, :, [0, 2]] * [1, -1]
                projection = module.shapely.distance(module.shapely.points(horizontal.reshape(-1, 2)), footprint)
                self.assertLess(float(projection.max()), .65 if number in [101, 102, 104] else .35)
                ground = triangles[np.max(np.abs(triangles[:, :, 1]), axis=1) < 1e-5]
                grade = unary_union([Polygon(t[:, [0, 2]] * [1, -1]) for t in ground])
                self.assertLess(footprint.difference(grade).area, .001)
                recipe = (root / asset['sourceRecord']['blendSource']).parent
                evidence = json.loads((recipe / 'root-geometry-review.json').read_text())
                regions = evidence.get('heightRegions') or json.loads((recipe / 'regions.json').read_text())
                polygons = [shape(r['geometry']) for r in regions]
                self.assertLess(footprint.symmetric_difference(unary_union(polygons)).area, 1e-8)
                self.assertLess(polygons[0].intersection(polygons[1]).area, 1e-8)
                checks = module.inspect_regions(triangles, regions, boundary_tolerance=.65 if number in [101, 102, 104] else .35)
                for region, polygon, check, original in zip(regions, polygons, checks, evidence['checks']):
                    self.assertEqual(check['overHeightTriangles'], 0)
                    deck = region.get('body_height_m', original['deckHeightM'])
                    roof = triangles[np.max(np.abs(triangles[:, :, 1] - deck), axis=1) < 1e-4]
                    cap = unary_union([Polygon(t[:, [0, 2]] * [1, -1]) for t in roof])
                    interior = polygon.buffer(-.03)
                    self.assertLess(interior.difference(cap).area / interior.area, 1e-6)

    def test_prestige28_preserves_numbered_source_footprints_and_register_heights(self):
        root = path.parents[2]
        manifest = json.loads((root / 'public/models/bespoke-manifest.json').read_text())
        assets = {a['id']: a for a in manifest['assets']}
        sources = json.loads((root / 'docs/model-audit/raemian-prestige-source-identity.json').read_text())
        self.assertEqual([r['number'] for r in sources['towers']], list(range(101, 129)))
        self.assertEqual(sum(int(r['register']['households']) for r in sources['towers']), 2444)
        for record in sources['towers']:
            with self.subTest(number=record['number']):
                asset = assets[f'bespoke-raemian-prestige-{record["number"]}']
                self.assertEqual(asset['footprintIds'], [record['sourceId']])
                self.assertEqual(record['sourceChildIds'], [])
                facts = asset['sourceRecord']['buildingFacts']
                self.assertEqual(facts['floors'], int(record['register']['floors']))
                self.assertEqual(facts['heightM'], float(record['register']['height']))
                self.assertEqual(facts['sourceHeightM'], record['osmHeightM'])
                lon, lat = asset['coordinate']['lon'], asset['coordinate']['lat']
                footprint = transform(lambda x, y: ((x-lon)*111320*math.cos(math.radians(lat)), (y-lat)*111320), shape(record['geometry']))
                triangles = module.read_triangles(root / 'public/models' / asset['model'])
                self.assertAlmostEqual(float(triangles[:, :, 1].min()), 0, places=5)
                self.assertAlmostEqual(float(triangles[:, :, 1].max()), facts['heightM'], places=4)
                ground = triangles[np.max(np.abs(triangles[:, :, 1]), axis=1) < 1e-5]
                union = unary_union([Polygon(t[:, [0, 2]] * [1, -1]) for t in ground])
                self.assertLess(union.symmetric_difference(footprint).area, .001)
                regions = [{'id': str(record['number']), 'geometry': mapping(footprint), 'height_m': facts['heightM']}]
                inspected = module.inspect_regions(triangles, regions)[0]
                self.assertEqual(inspected['overHeightTriangles'], 0)
                self.assertGreater(inspected['roofCoverageRatio'], .999999)

    def test_empty_or_duplicated_region_specifications_are_rejected(self):
        for regions in [[], None, {}, [region('same', 0, 10, 10), region('same', 10, 20, 30)]]:
            with self.subTest(regions=regions), self.assertRaises(ValueError):
                module.inspect_regions(cap(0, 20, 30), regions)

    def test_published_acro_stepped_roofs_preserve_all_source_regions(self):
        root = path.parents[2]
        manifest = json.loads((root / 'public/models/bespoke-manifest.json').read_text())
        by_id = {a['id']: a for a in manifest['assets']}
        counts = {100: 3, 101: 2, 103: 5, 104: 3, 105: 3, 106: 2, 107: 2,
                  108: 2, 109: 5, 110: 3, 111: 3, 112: 2, 113: 2, 114: 5}
        for number, count in counts.items():
            with self.subTest(number=number):
                aid = f'bespoke-acro-riverpark-{number}' + ('-corrected' if number in [100, 109] else '')
                asset = by_id[aid]
                source = root / asset['sourceRecord']['blendSource']
                specification = json.loads(source.with_name('source-data.json').read_text())
                self.assertEqual(len(specification['regions']), count)
                result = module.validate(root / 'public/models' / asset['model'], specification, .6)
                self.assertTrue(result['passed'], result)
                self.assertEqual(result['sha256'], asset['sha256'])
                triangles = module.read_triangles(root / 'public/models' / asset['model'])
                strict = module.inspect_regions(triangles, specification['regions'], .03)
                self.assertTrue(all(r['roofCoverageRatio'] > .999999 for r in strict))
                if number == 110:
                    self.assertEqual(len(asset['footprintIds']), 2)
                    self.assertEqual(sorted(r['height_m'] for r in specification['regions']), [10.5, 70, 105])

    def test_stepped_roofs_and_shared_tall_boundary_are_valid(self):
        triangles = cap(0, 10, 10) + cap(10, 20, 30)
        triangles += [[[10, 0, 0], [10, 30, 0], [10, 30, -10]]]
        records = module.inspect_regions(triangles, [region('low', 0, 10, 10), region('high', 10, 20, 30)])
        self.assertTrue(all(r['overHeightTriangles'] == 0 and r['roofCoverageRatio'] == 1 for r in records))

    def test_full_height_body_hiding_low_wing_is_rejected(self):
        triangles = cap(0, 20, 30) + cap(0, 10, 10)
        low = module.inspect_regions(triangles, [region('low', 0, 10, 10)])[0]
        self.assertEqual(low['overHeightTriangles'], 2)

    def test_spanning_triangle_with_no_vertices_inside_region_is_rejected(self):
        triangle = [[[-100, 30, 0], [100, 30, 0], [0, 30, -100]]]
        low = module.inspect_regions(triangle, [region('low', 0, 10, 10)])[0]
        self.assertEqual(low['overHeightTriangles'], 1)

    def test_clipping_prevents_false_positive_below_sloped_edge(self):
        triangle = [[[0, 0, 0], [100, 100, 0], [100, 100, -10]]]
        low = module.inspect_regions(triangle + cap(0, 10, 11), [region('low', 0, 10, 11)])[0]
        self.assertEqual(low['overHeightTriangles'], 0)

    def test_missing_wing_and_hole_in_roof_are_detected(self):
        missing = module.inspect_regions(cap(10, 20, 30), [region('low', 0, 10, 10)])[0]
        self.assertEqual(missing['roofCoverageRatio'], 0)
        hole = module.inspect_regions(cap(0, 4, 10) + cap(6, 10, 10), [region('low', 0, 10, 10)])[0]
        self.assertLess(hole['roofCoverageRatio'], .81)

    def test_polygon_hole_is_excluded_from_envelope(self):
        courtyard = region('court', 0, 10, 10)
        courtyard['rings'].append([[3, 3], [7, 3], [7, 7], [3, 7]])
        tall_in_hole = cap(4, 6, 30, 4, 6)
        result = module.inspect_regions(cap(0, 10, 10) + tall_in_hole, [courtyard])[0]
        self.assertEqual(result['overHeightTriangles'], 0)


if __name__ == '__main__':
    unittest.main()
