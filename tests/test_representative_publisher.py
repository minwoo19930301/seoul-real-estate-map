import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('representative', Path(__file__).resolve().parents[1]/'scripts/publish_representative_models.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)

class RepresentativeValidationTest(unittest.TestCase):
    def test_anchor_axes_and_metres(self):
        bounds = publisher.geometry_bounds({'lon': 127, 'lat': 37.5}, {'min': [-100, 0, -200], 'max': [100, 120, 200]})
        self.assertLess(bounds[0], 127)
        self.assertLess(bounds[1], 37.5)
        self.assertAlmostEqual(bounds[2]-127, 127-bounds[0])
        self.assertAlmostEqual(bounds[3]-37.5, 200/111319.49079327358)
        for coordinate, geometry in [({'lon': 37.5, 'lat': 127}, {'min': [-1,0,-1], 'max':[1,20,1]}),
                ({'lon': 127, 'lat': 37.5}, {'min': [100000,0,100000], 'max':[100010,20,100010]}),
                ({'lon': 127, 'lat': float('nan')}, {'min': [-1,0,-1], 'max':[1,20,1]})]:
            with self.assertRaises(ValueError): publisher.geometry_bounds(coordinate, geometry)

    def test_duplicate_and_protected_ownership(self):
        asset = {'id':'representative-one', 'footprintIds':['a'], 'supersedes':[]}
        publisher.validate_ownership([asset], [{'id':'bespoke', 'footprintIds':['b']}], [])
        for assets, protected, existing in [([asset,asset], [], []), ([asset], [{'id':'bespoke','footprintIds':['a']}], []),
                ([asset], [], [{'id':'old','footprintIds':['a']}]), ([{**asset,'supersedes':['bespoke']}], [], []),
                ([{**asset,'footprintIds':['a','a']}], [], [])]:
            with self.assertRaises(ValueError): publisher.validate_ownership(assets, protected, existing)

if __name__ == '__main__': unittest.main()
