import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_roads import build_database, classify
from server.roads import RoadsAPI


def way(identifier, tags, coordinates=None):
    points = coordinates or [[126.97, 37.56], [126.971, 37.561], [126.973, 37.562]]
    return {'type': 'way', 'id': identifier, 'tags': tags,
            'geometry': [{'lon': x, 'lat': y} for x, y in points]}


class RoadsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'overpass.json'
        self.database = self.root / 'roads.sqlite'
        self.api = RoadsAPI(self.database)

    def build(self, elements):
        self.source.write_text(json.dumps({'osm3s': {'timestamp_osm_base': '2026-09-08T00:00:00Z'}, 'elements': elements}))
        return build_database(self.source, self.database)

    def test_separate_geometry_required_for_sidewalk_and_raw_coordinates_preserved(self):
        road = way(1, {'highway': 'residential', 'sidewalk': 'both'})
        sidewalk = way(2, {'highway': 'footway', 'footway': 'sidewalk'})
        crossing = way(3, {'highway': 'footway', 'footway': 'crossing'})
        path = way(4, {'highway': 'path', 'access': 'private'})
        steps = way(5, {'highway': 'steps', 'incline': 'up'})
        # POI output repeats id=1 without geometry; it must not erase the line.
        self.build([road, sidewalk, crossing, path, steps,
                    {'type': 'way', 'id': 1, 'tags': road['tags'], 'center': {'lon': 127, 'lat': 37}}])
        result = self.api.features('126.969,37.559,126.974,37.563', '15')
        self.assertEqual(result['metadata']['counts'], {'roadway': 1, 'walkway': 3, 'steps': 1})
        features = {f['id']: f for f in result['features']}
        self.assertEqual(features['osm:way:1']['geometry']['coordinates'], [[126.97, 37.56], [126.971, 37.561], [126.973, 37.562]])
        self.assertFalse(features['osm:way:1']['properties']['separate_sidewalk'])
        self.assertEqual(features['osm:way:1']['properties']['sidewalk'], 'both')
        self.assertTrue(features['osm:way:2']['properties']['separate_sidewalk'])
        self.assertEqual(features['osm:way:3']['properties']['subtype'], 'crossing')
        self.assertTrue(features['osm:way:4']['properties']['restricted'])
        self.assertEqual(self.api.meta()['total_count'], 5)

    def test_zoom_visibility_and_exact_viewport_intersection(self):
        self.build([way(1, {'highway': 'primary'}), way(2, {'highway': 'residential'}), way(3, {'highway': 'footway'}),
                    way(4, {'highway': 'primary'}, [[126.90, 37.50], [126.90, 37.65], [127.1, 37.65]])])
        viewport = '126.969,37.559,126.974,37.563'
        self.assertEqual(len(self.api.features(viewport, '10')['features']), 0)
        self.assertEqual(len(self.api.features(viewport, '12')['features']), 1)
        self.assertEqual(len(self.api.features(viewport, '13')['features']), 2)
        self.assertEqual(len(self.api.features(viewport, '14')['features']), 3)
        self.assertEqual(self.api.features('128,38,128.1,38.1', '18')['features'], [])

    def test_caps_are_explicit_and_do_not_crop_or_simplify_geometry(self):
        self.build([way(i, {'highway': 'residential'}, [[126.97+i*.0001, 37.56], [126.97005+i*.0001, 37.5601]]) for i in range(1, 8)])
        with patch('server.roads.MAX_FEATURES', 3):
            result = self.api.features('126.96,37.55,126.98,37.57', '15')
            self.assertEqual(len(result['features']), 3)
            self.assertTrue(result['metadata']['truncated'])
        with patch('server.roads.MAX_VERTICES', 5):
            result = self.api.features('126.96,37.55,126.98,37.57', '15')
            self.assertEqual(result['metadata']['vertices'], 4)
            self.assertTrue(result['metadata']['truncated'])
            self.assertTrue(all(len(f['geometry']['coordinates']) == 2 for f in result['features']))

    def test_failed_download_or_incomplete_geometry_retains_previous_database(self):
        self.build([way(1, {'highway': 'primary'})])
        before = self.database.read_bytes()
        self.source.write_text(json.dumps({'remark': 'runtime error: Query timed out', 'elements': [way(2, {'highway': 'primary'})]}))
        with self.assertRaises(ValueError):
            build_database(self.source, self.database)
        self.assertEqual(self.database.read_bytes(), before)
        with self.assertRaises(ValueError):
            self.build([{'type': 'way', 'id': 2, 'tags': {'highway': 'residential'}}])
        self.assertEqual(self.database.read_bytes(), before)

    def test_pedestrian_area_and_unbuilt_roads_are_not_drawn_as_paths(self):
        self.assertIsNone(classify({'highway': 'pedestrian', 'area': 'yes'}))
        self.assertIsNone(classify({'highway': 'construction', 'construction': 'residential'}))
        self.assertIsNone(classify({'highway': 'cycleway', 'foot': 'no'}))
        self.assertEqual(classify({'highway': 'cycleway', 'foot': 'designated'}), ('walkway', 'shared_cycleway'))

    def test_boundary_filters_external_ways_without_clipping_crossing_way(self):
        coordinates = [[126.90, 37.56], [126.97, 37.56], [127.05, 37.56]]
        self.build([way(1, {'highway': 'primary'}, coordinates),
                    way(2, {'highway': 'residential'}, [[127.2, 37.6], [127.21, 37.6]])])
        boundary = self.root / 'boundary.geojson'
        boundary.write_text(json.dumps({'type': 'Polygon', 'coordinates': [[[126.96,37.55],[126.98,37.55],[126.98,37.57],[126.96,37.57],[126.96,37.55]]]}))
        metadata = build_database(self.source, self.database, boundary)
        self.assertEqual(metadata['skipped']['outside_seoul'], 1)
        self.assertEqual(metadata['total_count'], 1)
        feature = self.api.features('126.96,37.55,126.98,37.57', '15')['features'][0]
        self.assertEqual(feature['geometry']['coordinates'], coordinates)

    def test_missing_database_does_not_create_file_and_invalid_queries_rejected(self):
        self.assertFalse(self.api.meta()['available'])
        self.assertEqual(self.api.features('126,37,127,38')['features'], [])
        self.assertFalse(self.database.exists())
        for bbox in ('nan,37,127,38', '127,37,126,38', '126,37,181,38', '1,2,3'):
            with self.assertRaises(ValueError):
                self.api.features(bbox)
        for zoom in ('nan', 'inf', '23', True, None):
            with self.assertRaises(ValueError):
                self.api.features('126,37,127,38', zoom)


if __name__ == '__main__':
    unittest.main()
