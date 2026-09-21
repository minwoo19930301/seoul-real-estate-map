import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

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
