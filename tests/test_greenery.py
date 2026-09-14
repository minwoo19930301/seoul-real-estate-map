"""Geometry-only response, completeness metadata and bounded query contracts."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from server.greenery import GreeneryAPI


class GreeneryAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.api = GreeneryAPI(self.directory / 'buildings.sqlite', self.directory / 'roads.sqlite')
        self.bbox = '126.962,37.553,126.978,37.567'

    def test_geometry_and_completeness_survive_without_building_details(self):
        rings = [
            [[126.97, 37.56], [126.972, 37.56], [126.972, 37.562], [126.97, 37.562], [126.97, 37.56]],
            [[126.9705, 37.5605], [126.9705, 37.5615], [126.9715, 37.5615], [126.9715, 37.5605], [126.9705, 37.5605]],
        ]
        buildings = {'type': 'FeatureCollection', 'features': [{
            'type': 'Feature', 'id': 'original-building-ID',
            'geometry': {'type': 'MultiPolygon', 'coordinates': [rings]},
            'properties': {'id': 'original-building-ID', 'name': 'Example', 'height_m': 22, 'source_properties': {'unused': 'record'}},
        }], 'metadata': {'available': True, 'count': 1, 'truncated': True, 'geometry_clipped': False}}
        roads = {'type': 'FeatureCollection', 'features': [{
            'type': 'Feature', 'id': 'osm:way:1',
            'geometry': {'type': 'LineString', 'coordinates': [[126.96, 37.56], [126.98, 37.56]]},
            'properties': {'highway': 'footway', 'category': 'walkway', 'subtype': 'sidewalk', 'name': 'Example road', 'surface': 'asphalt'},
        }], 'metadata': {'available': True, 'count': 1, 'truncated': False, 'walkways_hidden_at_zoom': False}}
        originals = copy.deepcopy((buildings, roads))
        with patch.object(self.api.buildings, 'features', return_value=buildings) as building_query, patch.object(self.api.roads, 'features', return_value=roads) as road_query:
            result = self.api.features(self.bbox)
        building_query.assert_called_once_with(self.bbox, '16')
        road_query.assert_called_once_with(self.bbox, '16')
        self.assertEqual(result['buildings']['features'][0]['geometry']['coordinates'], [rings])
        self.assertEqual(result['buildings']['features'][0]['id'], 'original-building-ID')
        self.assertEqual(result['buildings']['features'][0]['properties'], {})
        self.assertEqual(result['roads']['features'][0]['geometry'], roads['features'][0]['geometry'])
        self.assertEqual(result['roads']['features'][0]['properties'], {'highway': 'footway', 'category': 'walkway', 'subtype': 'sidewalk'})
        self.assertEqual(result['buildings']['metadata'], buildings['metadata'])
        self.assertEqual(result['roads']['metadata'], roads['metadata'])
        self.assertEqual((buildings, roads), originals)
        self.assertEqual(result['metadata']['zoom'], 16)

    def test_large_or_invalid_bounds_are_rejected_before_either_database_query(self):
        with patch.object(self.api.buildings, 'features') as building_query, patch.object(self.api.roads, 'features') as road_query:
            for bbox in [None, '', 'NaN,37.5,127,37.6', '127,37.5,126,37.6', '126.9,37.55,127.1,37.56', '126.97,37.55,126.98,37.58']:
                with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                    self.api.features(bbox)
            building_query.assert_not_called()
            road_query.assert_not_called()

    def test_missing_databases_stay_unavailable_and_are_not_created(self):
        result = self.api.features(self.bbox)
        self.assertFalse(result['buildings']['metadata']['available'])
        self.assertFalse(result['roads']['metadata']['available'])
        self.assertEqual(result['buildings']['features'], [])
        self.assertEqual(result['roads']['features'], [])
        self.assertEqual(list(self.directory.iterdir()), [])
        self.assertLess(result['metadata']['width_m'], 2000)
        self.assertLess(result['metadata']['height_m'], 2000)


if __name__ == '__main__':
    unittest.main()
