"""Small synthetic source fixtures test semantics, not a claim about real POI coverage."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from shapely.geometry import Point, box, mapping, shape

from scripts.build_places import build_database, osm_place
from server.places import PlacesAPI


class PlacesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.buildings = self.directory / 'buildings.sqlite'
        polygon = box(127, 37.5, 127.001, 37.501)
        with sqlite3.connect(self.buildings) as db:
            db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT);
                CREATE TABLE buildings(id TEXT,name TEXT,kind TEXT,geometry TEXT,
                    source_properties TEXT,district_id TEXT,is_apartment INTEGER);''')
            db.execute('INSERT INTO metadata VALUES(?,?)', ('source_kind', '"overture_buildings"'))
            # Same name for a part must not create a second search result.
            for identifier, kind in [('source-building', 'building'), ('source-part', 'building_part')]:
                db.execute('INSERT INTO buildings VALUES(?,?,?,?,?,?,?)',
                    (identifier, '검증단지 101동', kind, json.dumps(mapping(polygon)),
                     json.dumps({'names': {'primary': '검증단지 101동'}}), 'district-test', 1))
        region = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'id': 'district-test',
            'geometry': mapping(box(126.9, 37.4, 127.2, 37.7)),
            'properties': {'names': {'primary': '검증구'}}}]}
        self.boundary = self.directory / 'boundary.json'
        self.boundary.write_text(json.dumps(region))
        self.osm = self.directory / 'osm.json'
        elements = [
            {'type': 'node', 'id': 1, 'lon': 127.01, 'lat': 37.51, 'tags': {'railway': 'station', 'name': '검증', 'name:en': 'Test Station'}},
            {'type': 'node', 'id': 2, 'lon': 127.01001, 'lat': 37.51, 'tags': {'railway': 'station', 'name': '검증'}},
            {'type': 'node', 'id': 3, 'lon': 129, 'lat': 35, 'tags': {'railway': 'station', 'name': '서울밖'}},
            {'type': 'way', 'id': 4, 'center': {'lon': 127.02, 'lat': 37.52}, 'tags': {'landuse': 'residential', 'name': '서울검증단지'}},
            {'type': 'node', 'id': 5, 'lon': 127.03, 'lat': 37.53, 'tags': {'highway': 'traffic_signals', 'name': '검증사거리'}},
        ]
        self.osm.write_text(json.dumps({'elements': elements}))
        self.database = self.directory / 'places.sqlite'
        self.rebuild()
        self.api = PlacesAPI(self.database)

    def rebuild(self):
        return build_database(self.database, self.buildings, self.boundary, self.boundary, [self.osm])

    def tearDown(self):
        self.temp.cleanup()

    def test_search_suffix_alias_source_identity_and_scope(self):
        station = self.api.search('검증 역')['results']
        self.assertEqual(len(station), 1)
        self.assertEqual(station[0]['name'], '검증')
        self.assertEqual(station[0]['center'], [127.01, 37.51])
        self.assertEqual(station[0]['source_url'], 'https://www.openstreetmap.org/node/1')
        self.assertEqual(self.api.search('test station')['results'][0]['id'], station[0]['id'])
        self.assertEqual(self.api.search('서울밖')['results'], [])
        with sqlite3.connect(self.database) as db:
            ids = json.loads(db.execute("SELECT source_ids FROM places WHERE id='osm:node/1'").fetchone()[0])
        self.assertEqual(ids, ['osm:node/1', 'osm:node/2'])

    def test_building_is_not_a_complex_and_point_is_inside_source(self):
        results = self.api.search('검증단지101동')['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['kind'], 'building')
        self.assertEqual(results[0]['building_id'], 'source-building')
        self.assertTrue(box(127, 37.5, 127.001, 37.501).covers(Point(results[0]['center'])))
        viewport = self.api.features('126.9,37.4,127.2,37.7', 15)
        self.assertEqual({f['properties']['kind'] for f in viewport['features']}, {'station', 'junction', 'residential'})
        self.assertEqual(len(self.api.features('126.9,37.4,127.2,37.7', 15, 'building')['features']), 0)
        self.assertEqual(len(self.api.features('126.9,37.4,127.2,37.7', 16, 'building')['features']), 1)

    def test_complex_substring_ranks_above_a_building_prefix_but_exact_name_wins(self):
        # Regression: 헬리오시티 경로당 used to precede 송파헬리오시티.
        self.assertEqual(self.api.search('검증단지')['results'][0]['kind'], 'residential')
        self.assertEqual(self.api.search('검증단지101동')['results'][0]['building_id'], 'source-building')

    def test_empty_invalid_queries_and_viewport_outside(self):
        self.assertEqual(self.api.search('   ')['results'], [])
        for limit in (0, 51, 'nan', True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.api.search('검증', limit)
        for q in (None, '가' * 101):
            with self.assertRaises(ValueError):
                self.api.search(q)
        for bbox in ('1,2,0,3', 'nan,2,3,4', '1,2,3', None):
            with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                self.api.features(bbox)
        for zoom in ('nan', -1, 25, True):
            with self.assertRaises(ValueError):
                self.api.features('126,37,127,38', zoom)
        with self.assertRaises(ValueError):
            self.api.features('126,37,127,38', 15, 'station,unknown')
        self.assertEqual(self.api.features('0,0,1,1')['features'], [])
        self.assertEqual(self.api.search("%' OR 1=1 --")['results'], [])

    def test_failed_partial_source_preserves_previous_database(self):
        previous = self.database.read_bytes()
        self.osm.write_text(json.dumps({'elements': [], 'remark': 'runtime error: timed out'}))
        with self.assertRaises(ValueError):
            self.rebuild()
        self.assertEqual(self.database.read_bytes(), previous)

    def test_response_limit_and_rebuild_unique(self):
        for _ in range(2):
            meta = self.rebuild()
        self.assertEqual(meta['total_count'], 5)
        self.assertEqual(meta['osm_outside_seoul_excluded'], 1)
        self.assertEqual(len(self.api.search('검증', 2)['results']), 2)
        self.assertTrue(self.api.search('검증', 2)['metadata']['truncated'])
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT COUNT(DISTINCT id) FROM places').fetchone()[0], 5)

    def test_bridge_name_does_not_turn_generic_named_road_into_bridge(self):
        generic = {'type': 'way', 'id': 9, 'tags': {'highway': 'primary', 'bridge': 'yes', 'name': '검증대로'},
                   'geometry': [{'lon': 127, 'lat': 37.5}, {'lon': 127.01, 'lat': 37.51}]}
        self.assertIsNone(osm_place(generic))
        generic['tags']['bridge:name'] = '검증대교'
        bridge = osm_place(generic)
        self.assertEqual(bridge['name'], '검증대교')
        self.assertEqual(bridge['location_method'], 'osm_line_midpoint')

    def test_bus_stop_named_after_junction_is_not_the_junction(self):
        for tags in ({'highway': 'bus_stop', 'public_transport': 'platform'},
                     {'public_transport': 'stop_position'}):
            self.assertIsNone(osm_place({'type': 'node', 'id': 10, 'lon': 127, 'lat': 37.5,
                                        'tags': {**tags, 'name': '검증사거리'}}))

    def test_viewport_cap_is_explicit_and_returned_points_are_in_bounds(self):
        with sqlite3.connect(self.database) as db:
            for index in range(305):
                cursor = db.execute('''INSERT INTO places(id,name,kind,lon,lat,subtitle,source_url,location_method,
                    priority,min_zoom,zoom,building_id,district_name,source_ids)
                    SELECT ?,name,kind,lon,lat,subtitle,source_url,location_method,
                    priority,min_zoom,zoom,building_id,district_name,source_ids FROM places WHERE id='osm:node/1'
                ''', (f'fixture-cap-{index}',))
                db.execute('INSERT INTO place_index VALUES(?,?,?,?,?)', (cursor.lastrowid,127.01,127.01,37.51,37.51))
        result = self.api.features('127,37.5,127.02,37.52', 15, 'station')
        self.assertEqual(len(result['features']), 300)
        self.assertTrue(result['metadata']['truncated'])
        self.assertEqual(len({f['id'] for f in result['features']}), 300)
        for feature in result['features']:
            self.assertTrue(box(127,37.5,127.02,37.52).covers(shape(feature['geometry'])))


if __name__ == '__main__':
    unittest.main()
