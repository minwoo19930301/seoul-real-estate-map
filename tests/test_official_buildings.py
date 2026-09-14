"""Generated AL_D010 fixtures only; these are not downloaded Seoul records."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from zipfile import ZipFile
import zlib

from pyproj import CRS, Transformer
import shapefile
from shapely.geometry import shape

from scripts.import_official_buildings import import_database, positive_number
from server.buildings import BuildingsAPI


def make_archive(directory, name='fixture', heights=(51.25, 0, None, -2), *, prj=True, delta=False, legal_code='1168010100'):
    base = directory / name
    with shapefile.Writer(str(base), shapeType=shapefile.POLYGON, encoding='cp949') as writer:
        for index in range(31 if delta else 29):
            field = f'A{index}'
            if index in (12, 14, 15, 16, 17, 18):
                writer.field(field, 'F', size=20, decimal=3)
            elif index in (0, 26, 27):
                writer.field(field, 'N', size=9)
            else:
                writer.field(field, 'C', size=80)
        project = Transformer.from_crs(4326, 5174, always_xy=True)
        for index, height in enumerate(heights):
            x, y = project.transform(127.05 + index * .001, 37.5)
            # Clockwise outer ring, counterclockwise hole, second outer part.
            # Rings survive import without an inferred rectangle or lost hole.
            rings = [
                [(x, y), (x, y+20), (x+20, y+20), (x+20, y), (x, y)],
                [(x+5, y+5), (x+15, y+5), (x+15, y+15), (x+5, y+15), (x+5, y+5)],
                [(x+30, y), (x+30, y+10), (x+40, y+10), (x+40, y), (x+30, y)],
            ]
            writer.poly(rings)
            values = [''] * (31 if delta else 29)
            values[0] = index+1
            values[1] = '1234567890123456789012345678'
            values[2] = '1168010100101230001'
            values[3] = legal_code
            values[4] = '서울특별시 강남구 역삼동'
            values[5] = '123-1'
            values[8] = ('2001', '02000', '02003', '02001')[index % 4]
            values[9] = '아파트' if index in (0, 3) else '공동주택'
            values[12] = 455.5  # Deliberately differs from geometry area.
            values[13] = '2001-01-01'
            values[14] = 6000
            values[15] = 800
            values[16] = height
            values[17] = 35
            values[18] = 300
            values[19] = '9999999999999999999999999999'
            values[22] = '2026-08-09'
            values[23] = '11680'
            values[24] = '검증용아파트'
            values[25] = f'{index+101}동'
            values[26] = 17
            values[27] = 2
            values[28] = '2026-08-01'
            writer.record(*values)
    base.with_suffix('.cpg').write_text('949', encoding='ascii')
    if prj:
        base.with_suffix('.prj').write_text(CRS.from_epsg(5174).to_wkt(version='WKT1_ESRI'), encoding='utf-8')
    archive_path = directory / (name + '.zip')
    with ZipFile(archive_path, 'w') as archive:
        for extension in ('.shp', '.shx', '.dbf', '.cpg', '.prj'):
            path = base.with_suffix(extension)
            if path.exists():
                archive.write(path, 'AL_D010_11' + extension)
    return archive_path


class OfficialImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.database = self.directory / 'data' / 'buildings.sqlite'

    def tearDown(self):
        self.temp.cleanup()

    def test_real_schema_fixture_preserves_ids_holes_and_registered_height(self):
        source = make_archive(self.directory)
        metadata = import_database(source, self.database, '2026-08-09')
        self.assertEqual(metadata['source_kind'], 'official_gis_buildings')
        self.assertFalse(metadata['source_height_verified'])
        self.assertEqual((metadata['total_count'], metadata['reported_count'], metadata['missing_count']), (4, 1, 3))
        self.assertEqual(metadata['apartment_count'], 2)
        self.assertEqual(metadata['raw_height_counts'], {'positive': 1, 'nonpositive': 2, 'empty': 1})
        self.assertTrue((self.database.parent / metadata['retained_source']).is_file())
        api = BuildingsAPI(self.database)
        result = api.features('127.049,37.499,127.06,37.502', 16)
        self.assertEqual(len(result['features']), 4)
        by_shape_id = {item['id'].split(':')[-1]: item for item in result['features']}
        feature = by_shape_id['1']
        self.assertEqual(feature['properties']['height_m'], 51.25)
        self.assertEqual(feature['properties']['height_status'], 'reported')
        self.assertEqual(feature['properties']['height_source'], '국토부 건축물대장')
        self.assertTrue(feature['properties']['extrude'])
        self.assertTrue(feature['properties']['is_apartment'])
        self.assertEqual(feature['id'], 'official:1234567890123456789012345678:1')
        geometry = shape(feature['geometry'])
        self.assertEqual(geometry.geom_type, 'MultiPolygon')
        self.assertEqual(len(geometry.geoms), 2)
        self.assertEqual(sum(len(poly.interiors) for poly in geometry.geoms), 1)
        self.assertAlmostEqual(feature['properties']['footprint_area_m2'], 400, delta=1)
        self.assertAlmostEqual(geometry.bounds[0], 127.05, places=5)
        self.assertAlmostEqual(geometry.bounds[1], 37.5, places=5)
        for missing in (by_shape_id[str(index)] for index in (2, 3, 4)):
            self.assertIsNone(missing['properties']['height_m'])
            self.assertFalse(missing['properties']['extrude'])
            self.assertEqual(missing['properties']['num_floors'], 17)
        self.assertFalse(by_shape_id['2']['properties']['is_apartment'])
        detail = api.detail(feature['id'])
        self.assertEqual(detail['source_properties']['A19'], '9999999999999999999999999999')
        self.assertEqual(detail['provenance']['release'], '2026-08-09')
        with sqlite3.connect(self.database) as db:
            raw = db.execute('SELECT source_properties FROM buildings ORDER BY rowid').fetchone()[0]
            self.assertIsInstance(raw, bytes)
            props = json.loads(zlib.decompress(raw))
            self.assertEqual(props['A19'], '9999999999999999999999999999')
            self.assertEqual(props['A12'], 455.5)
            self.assertEqual(props['_official']['source_use_code'], '02001')
            self.assertFalse(props['_official']['source_height_verified'])

    def test_reimport_reuses_and_changed_archive_preserves_previous_database(self):
        first = make_archive(self.directory, 'first', heights=(51.25,))
        initial = import_database(first, self.database, '2026-08-09')
        identity = self.database.stat().st_ino
        repeat = import_database(first, self.database, '2026-08-09')
        self.assertTrue(repeat['reused'])
        self.assertEqual(self.database.stat().st_ino, identity)
        second = make_archive(self.directory, 'second', heights=(62.5,))
        updated = import_database(second, self.database, '2026-08-10')
        self.assertFalse(updated['reused'])
        backup = Path(updated['previous_database_backup'])
        with sqlite3.connect(backup) as db:
            self.assertEqual(db.execute('SELECT height_m FROM buildings').fetchone()[0], 51.25)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT height_m FROM buildings').fetchone()[0], 62.5)
        self.assertTrue((self.database.parent / initial['retained_source']).exists())
        self.assertTrue((self.database.parent / updated['retained_source']).exists())

    def test_missing_prj_and_delta_input_never_replace_existing_database(self):
        valid = make_archive(self.directory, 'valid', heights=(51.25,))
        import_database(valid, self.database, '2026-08-09')
        before = self.database.read_bytes()
        for name, options, error in [
            ('no-prj', {'prj': False}, 'PRJ is mandatory'),
            ('delta', {'delta': True}, 'change/delta'),
            ('not-seoul', {'legal_code': '2611012000'}, 'not a Seoul'),
        ]:
            with self.subTest(name=name):
                archive = make_archive(self.directory, name, heights=(15,), **options)
                with self.assertRaisesRegex(ValueError, error):
                    import_database(archive, self.database, '2026-08-09')
                self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(self.database.parent.glob('*.sqlite.tmp')), [])
        self.assertEqual(list(self.database.parent.glob('*.previous-*')), [])

    def test_nonfinite_and_fractional_source_values_fail_instead_of_fabricating(self):
        for value in (float('nan'), float('inf'), True, 'unknown'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                positive_number(value, 'height')
        with self.assertRaises(ValueError):
            positive_number('3.5', 'floor count', integer=True)
        self.assertIsNone(positive_number(-2, 'height'))
        self.assertIsNone(positive_number('', 'height'))


if __name__ == '__main__':
    unittest.main()
