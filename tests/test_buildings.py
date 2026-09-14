"""Original geometry/height retention, bounded read API and atomic importer tests."""
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

from scripts.build_buildings import build_database
from server.buildings import BuildingsAPI, MAX_BUILDINGS, decode_source_properties

ROOT = Path(__file__).resolve().parents[1]


def rectangle(west, south, east, north):
    return {'type': 'Polygon', 'coordinates': [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}


def feature(identifier, geometry, **overrides):
    props = {'feature_type': 'building', 'height': None, 'min_height': None,
             'sources': [{'property': '', 'dataset': 'OpenStreetMap', 'record_id': 'w123@1'}],
             '_seoul': {'district_id': 'district-test'}, **overrides}
    return {'type': 'Feature', 'id': identifier, 'properties': props, 'geometry': geometry}


def write_source(directory, features):
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for kind in ('building', 'building_part'):
        rows = [f for f in features if f['properties']['feature_type'] == kind]
        if not rows:
            continue
        path = directory / f'{kind}.ndjson.gz'
        content = ''.join(json.dumps(f) + '\n' for f in rows).encode()
        path.write_bytes(gzip.compress(content, mtime=0))
        files.append({'type': kind, 'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {'schemaVersion': 1, 'release': 'fixture-2026', 'files': files,
                'bbox': {'minLon': 126.7, 'minLat': 37.4, 'maxLon': 127.3, 'maxLat': 37.8},
                'sourceUrls': ['https://docs.overturemaps.org/guides/buildings/'],
                'license': 'ODbL-1.0', 'attribution': 'OpenStreetMap contributors, Overture Maps Foundation'}
    (directory / 'manifest.json').write_text(json.dumps(manifest))


class BuildingAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.source = cls.directory / 'source'
        cls.database = cls.directory / 'buildings.sqlite'
        courtyard = rectangle(127.06, 37.54, 127.062, 37.542)
        courtyard['coordinates'].append([[127.0605, 37.5405], [127.0605, 37.5415], [127.0615, 37.5415], [127.0615, 37.5405], [127.0605, 37.5405]])
        cls.source_features = [
            feature('reported-apt', rectangle(127.04, 37.54, 127.041, 37.541), height=52.5, num_floors=18,
                    names={'primary': '실제 태그 아파트'}, **{'class': 'apartments'}),
            feature('missing-tall', rectangle(127.042, 37.54, 127.043, 37.541), num_floors=80,
                    names={'primary': '이름에 아파트 있지만 분류 없음'}, subtype='residential'),
            feature('parent', rectangle(127.044, 37.54, 127.046, 37.542), height=50, **{'class': 'apartments'}),
            feature('child', rectangle(127.044, 37.54, 127.045, 37.541), feature_type='building_part', building_id='parent', height=35),
            feature('elevated', rectangle(127.045, 37.541, 127.046, 37.542), feature_type='building_part', building_id='parent', height=50, min_height=10),
            feature('missing-child', rectangle(127.045, 37.54, 127.046, 37.541), feature_type='building_part', building_id='parent', num_floors=12),
            feature('courtyard', courtyard, height=12),
        ]
        write_source(cls.source, cls.source_features)
        build_database(cls.source, cls.database)
        cls.api = BuildingsAPI(cls.database)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_source_height_and_missing_values_never_inherit_floor_or_parent_estimates(self):
        reported = self.api.detail('reported-apt')['properties']
        self.assertEqual(reported['height_m'], 52.5)
        self.assertEqual(reported['height_status'], 'reported')
        self.assertEqual(reported['display_top_m'], 52.5)
        self.assertEqual(reported['display_base_m'], 0)
        self.assertTrue(reported['is_apartment'])
        self.assertTrue(reported['extrude'])
        for identifier in ('missing-tall', 'missing-child'):
            with self.subTest(identifier=identifier):
                props = self.api.detail(identifier)['properties']
                self.assertIsNone(props['height_m'])
                self.assertIsNone(props['display_top_m'])
                self.assertEqual(props['height_status'], 'missing')
                self.assertFalse(props['extrude'])
                self.assertGreater(props['num_floors'], 0)
        self.assertFalse(self.api.detail('missing-tall')['properties']['is_apartment'])

    def test_parent_and_elevated_parts_remain_queryable_without_duplicate_or_guessed_extrusion(self):
        parent = self.api.detail('parent')['properties']
        child = self.api.detail('child')['properties']
        elevated = self.api.detail('elevated')['properties']
        self.assertTrue(parent['has_parts'])
        self.assertEqual(parent['height_m'], 50)
        self.assertFalse(parent['extrude'])
        self.assertEqual(parent['extrusion_reason'], 'parent_has_parts')
        self.assertTrue(child['extrude'])
        self.assertEqual(child['parent_id'], 'parent')
        self.assertTrue(child['is_apartment'])
        self.assertEqual(child['classification_source'], 'parent')
        self.assertEqual(parent['classification_source'], 'source')
        self.assertEqual(elevated['height_m'], 50)
        self.assertEqual(elevated['min_height_m'], 10)
        self.assertFalse(elevated['extrude'])
        self.assertIsNone(elevated['display_top_m'])
        self.assertEqual(elevated['extrusion_reason'], 'elevated_height_semantics_unverified')

    def test_height_outliers_preserve_source_records_but_are_excluded_from_api_extrusion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outline = rectangle(127.04, 37.54, 127.041, 37.541)
            heights = {'below-threshold': 999.99, 'at-threshold': 1000, 'source-outlier': 13438, 'missing': None}
            write_source(root / 'source', [feature(identifier, outline, height=height)
                                         for identifier, height in heights.items()])
            build_database(root / 'source', root / 'buildings.sqlite')
            api = BuildingsAPI(root / 'buildings.sqlite')
            viewport = {f['id']: f for f in api.features('127.03,37.53,127.05,37.55', '16')['features']}
            self.assertEqual(set(viewport), set(heights), 'outliers must remain visible as selectable outlines')
            for identifier, height in heights.items():
                with self.subTest(identifier=identifier):
                    detail = api.detail(identifier)
                    self.assertEqual(detail['source_properties']['height'], height)
                    self.assertEqual(detail['geometry'], outline)
                    for result in (detail, viewport[identifier]):
                        props = result['properties']
                        self.assertEqual(props['height_m'], height)
                        self.assertEqual(props['height_status'], 'missing' if height is None else 'reported')
                        review = height is not None and height >= 1000
                        self.assertEqual(props['height_review_required'], review)
                        self.assertEqual(props['extrude'], identifier == 'below-threshold')
                        if review:
                            self.assertEqual(props['extrusion_reason'], 'height_outlier_needs_review')
                            self.assertIsNone(props['display_top_m'])
                            self.assertIsNone(props['display_base_m'])
                    with api.connect() as db:
                        stored = db.execute('SELECT height_m,extrude FROM buildings WHERE id=?', (identifier,)).fetchone()
                    self.assertEqual(stored['height_m'], height)
                    self.assertEqual(bool(stored['extrude']), height is not None,
                                     'the API guard must work without rewriting an existing database')

    def test_original_outline_and_holes_survive_viewport_selection_and_detail(self):
        source = next(f for f in self.source_features if f['id'] == 'courtyard')
        detail = self.api.detail('courtyard')
        self.assertEqual(detail['geometry'], source['geometry'])
        selected = self.api.features('127.0599,37.5399,127.0601,37.5401', '16')
        self.assertEqual(len(selected['features']), 1)
        self.assertEqual(selected['features'][0]['geometry'], source['geometry'], 'source outline must not be cropped at viewport edge')
        empty_hole = self.api.features('127.0608,37.5408,127.0612,37.5412', '16')
        self.assertEqual(empty_hole['features'], [], 'RTree bbox hit inside a courtyard is not a building intersection')
        to_metric = Transformer.from_crs(4326, 5186, always_xy=True)
        expected = transform(to_metric.transform, shape(source['geometry'])).area
        self.assertAlmostEqual(detail['properties']['footprint_area_m2'], expected, places=6)
        self.assertEqual(detail['sources'], source['properties']['sources'])
        self.assertEqual(detail['source_properties'], source['properties'])
        with self.api.connect() as db:
            stored = db.execute('SELECT source_properties FROM buildings WHERE id=?', ('courtyard',)).fetchone()[0]
            self.assertIsInstance(stored, bytes)
            self.assertEqual(decode_source_properties(stored), source['properties'])
            self.assertEqual(decode_source_properties(json.dumps(source['properties'])), source['properties'], 'legacy plain-text source JSON stays readable')

    def test_low_zoom_outside_extent_and_unbuilt_database_are_explicit_empty_results(self):
        for zoom in ('0', '13', '13.99'):
            result = self.api.features('126,37,128,38', zoom)
            self.assertEqual(result['features'], [])
            self.assertTrue(result['metadata']['hidden_at_zoom'])
        self.assertEqual(self.api.features('129,35,130,36', '18')['features'], [])
        missing = BuildingsAPI(self.directory / 'not-built.sqlite')
        self.assertFalse(missing.meta()['available'])
        self.assertFalse(missing.features('126,37,128,38')['metadata']['available'])
        self.assertIsNone(missing.detail('anything'))
        self.assertFalse(missing.database.exists(), 'read-only API must not create an empty DB')

    def test_invalid_bbox_zoom_and_sql_like_identifiers_cannot_mutate_the_database(self):
        for bbox in ('1,2,3', 'NaN,37,128,38', '127,37,126,38', '-181,37,128,38', '126,37,128,91'):
            with self.assertRaises(ValueError):
                self.api.features(bbox)
        for zoom in ('nan', 'Infinity', -1, 23, True, []):
            with self.assertRaises(ValueError):
                self.api.features('126,37,128,38', zoom)
        before = self.database.stat().st_mtime_ns
        self.assertIsNone(self.api.detail("'; DROP TABLE buildings; --"))
        with self.api.connect() as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute('DELETE FROM buildings')
        self.assertEqual(self.database.stat().st_mtime_ns, before)

    def test_identical_rebuild_is_reused_and_failed_replacement_preserves_previous_database(self):
        before = self.database.read_bytes()
        result = build_database(self.source, self.database)
        self.assertTrue(result['reused'])
        self.assertEqual(self.database.read_bytes(), before)
        corrupt = self.directory / 'broken-source'
        write_source(corrupt, [feature('bad', rectangle(127, 37.5, 127.01, 37.51), height=-30)])
        with self.assertRaises(ValueError):
            build_database(corrupt, self.database)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(self.directory.glob('*.tmp')), [])
        # A truncated source file must also fail before replacing the good DB.
        (corrupt / 'building.ndjson.gz').write_bytes(b'incomplete')
        with self.assertRaises(ValueError):
            build_database(corrupt, self.database)
        self.assertEqual(self.database.read_bytes(), before)

    def test_viewport_cap_is_enforced_without_fabricated_aggregates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = [feature(f'building-{index}', rectangle(127 + index * .000001, 37.55, 127.0000005 + index * .000001, 37.5500005), height=10 if index % 2 else None)
                    for index in range(MAX_BUILDINGS + 3)]
            rows.append(feature('late-eastern-building', rectangle(127.08, 37.58, 127.0801, 37.5801), height=12))
            write_source(root / 'source', rows)
            build_database(root / 'source', root / 'buildings.sqlite')
            api = BuildingsAPI(root / 'buildings.sqlite')
            result = api.features('126.9,37.5,127.1,37.6', 18)
            self.assertEqual(len(result['features']), MAX_BUILDINGS)
            self.assertTrue(result['metadata']['truncated'])
            self.assertEqual(result['metadata']['reported'] + result['metadata']['missing'], MAX_BUILDINGS)
            self.assertEqual(len({f['id'] for f in result['features']}), MAX_BUILDINGS)
            self.assertIn('late-eastern-building', {f['id'] for f in result['features']}, 'cap must not discard another viewport area solely because its district file comes later')


class ActualSeoulBuildingTests(unittest.TestCase):
    def test_generated_database_counts_and_sample_match_retained_seoul_source(self):
        database = ROOT / 'data' / 'buildings.sqlite'
        self.assertTrue(database.is_file(), 'run scripts/build_buildings.py first')
        api = BuildingsAPI(database)
        meta = api.meta()
        self.assertEqual(meta['source_release'], '2026-08-19.0')
        self.assertEqual(meta['district_count'], 25)
        self.assertEqual(meta['total_count'], 367140)
        self.assertEqual(meta['reported_count'], 27130)
        self.assertEqual(meta['missing_count'], 340010)
        self.assertEqual(meta['apartment_count'], 27724)
        self.assertEqual(meta['source_properties_encoding'], 'zlib-json-utf8')
        self.assertEqual(meta['height_sources'], {'OpenStreetMap': 27130})
        self.assertEqual(meta['area_crs'], 'EPSG:5186')
        result = api.features('127.039,37.536,127.059,37.552', '16')
        self.assertFalse(result['metadata']['truncated'])
        self.assertGreater(len(result['features']), 2500)
        self.assertGreater(result['metadata']['reported'], 400)
        with api.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM building_index').fetchone()[0], meta['total_count'])
            self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0], 'ok')
            for row in db.execute('SELECT * FROM buildings WHERE height_m IS NOT NULL LIMIT 100'):
                original = decode_source_properties(row['source_properties'])
                self.assertEqual(row['height_m'], original['height'])
                self.assertEqual(row['min_height_m'], original.get('min_height'))
                detail = api.detail(row['id'])
                self.assertEqual(detail['geometry'], json.loads(row['geometry']))
                self.assertEqual(detail['sources'], original['sources'])


if __name__ == '__main__':
    unittest.main()
