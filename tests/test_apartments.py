"""Synthetic OA-15818 fixtures verify thresholds, identity and location evidence."""
import csv
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zlib

from shapely.geometry import box,mapping

from scripts.import_apartments import FIELDS,import_database
from scripts.build_places import build_database
from server.places import PlacesAPI


class ApartmentsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.directory=Path(self.temp.name)
        self.csv=self.directory/'apartments.csv'
        self.database=self.directory/'apartments.sqlite'
        self.districts=self.directory/'districts.json'
        self.districts.write_text(json.dumps({'type':'FeatureCollection','features':[
            {'type':'Feature','id':'district-fixture','geometry':mapping(box(126.9,37.4,127.2,37.7)),
             'properties':{'names':{'primary':'검증구'}}}]}))
        def row(code,name,count,lon='127.01',lat='37.51',classification='아파트',address='서울 검증로 1'):
            values={'code':code,'name':name,'classification':classification,'households':count,
                'district':'검증구','city':'서울','address':address,'lon':lon,'lat':lat,
                'updated':'2026-09-08 01:02:03','status':'Y'}
            return {FIELDS[k]:v for k,v in values.items()}
        self.rows=[
            row('A399','검증399','399',lon='127.011'),
            row('A400','검증400','400',lon='127.012'),
            row('AZERO','검증0','0',lon='127.013'),
            row('AMISSING','검증미등록','',lon='127.014'),
            row('AROW','검증연립','500',lon='127.015',classification='연립주택'),
            row('ARECOVER','위치보완 아파트','800',lon='',lat=''),
            row('AOUT','서울밖','900',lon='129'),
            row('ACOLLISION1','중복위치1','1000',lon='127.04',address='서울 검증로 10'),
            row('ACOLLISION2','중복위치2','1001',lon='127.04',address='서울 검증로 20'),
            row('AFUZZY','새로운단지A','2000',lon='',lat=''),
        ]
        self.osm=self.directory/'osm.json'
        self.elements=[
            {'type':'node','id':1,'lon':127.02,'lat':37.52,'tags':{'name':'검증역','railway':'station'}},
            {'type':'way','id':2,'center':{'lon':127.03,'lat':37.53},'tags':{'name':'위치보완','landuse':'residential'}},
            {'type':'way','id':3,'center':{'lon':127.05,'lat':37.53},'tags':{'name':'중복위치1','landuse':'residential'}},
            {'type':'way','id':4,'center':{'lon':127.06,'lat':37.53},'tags':{'name':'중복위치2','landuse':'residential'}},
            {'type':'way','id':5,'center':{'lon':127.07,'lat':37.53},'tags':{'name':'새로운단지B','landuse':'residential'}},
        ]
        self.write_sources()

    def write_sources(self):
        with self.csv.open('w',encoding='cp949',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(FIELDS.values()))
            writer.writeheader();writer.writerows(self.rows)
        self.osm.write_text(json.dumps({'elements':self.elements}))

    def import_data(self):
        return import_database(self.csv,self.database,self.districts,'2026-09-08',osm_path=self.osm,expected_count=len(self.rows))

    def tearDown(self):
        self.temp.cleanup()

    def test_threshold_is_complex_total_and_missing_zero_and_class_stay_distinct(self):
        meta=self.import_data()
        self.assertEqual(meta['source_row_count'],10)
        self.assertEqual(meta['official_complex_count_ge400'],6)
        self.assertEqual(meta['mapped_complex_count_ge400'],4)
        self.assertEqual(meta['household_missing_count'],1)
        self.assertEqual(meta['household_zero_count'],1)
        with sqlite3.connect(self.database) as db:
            rows={r[0]:(r[1],r[2]) for r in db.execute('SELECT code,household_count,target_400 FROM apartments')}
            self.assertEqual(rows['A399'],(399,0))
            self.assertEqual(rows['A400'],(400,1))
            self.assertEqual(rows['AZERO'],(0,0))
            self.assertEqual(rows['AMISSING'],(None,0))
            self.assertEqual(rows['AROW'],(500,0))
            raw=json.loads(zlib.decompress(db.execute("SELECT source_properties FROM apartments WHERE code='A400'").fetchone()[0]))
            self.assertEqual(raw,self.rows[1])

    def test_missing_and_duplicate_coordinates_use_unique_exact_name_in_same_district(self):
        self.import_data()
        with sqlite3.connect(self.database) as db:
            db.row_factory=sqlite3.Row
            recovery=db.execute("SELECT * FROM apartments WHERE code='ARECOVER'").fetchone()
            self.assertEqual(recovery['official_lon'],'')
            self.assertEqual((recovery['lon'],recovery['lat']),(127.03,37.53))
            self.assertEqual(recovery['coordinate_status'],'osm_exact_name_and_district')
            self.assertEqual(recovery['household_count'],800)
            a=db.execute("SELECT * FROM apartments WHERE code='ACOLLISION1'").fetchone()
            b=db.execute("SELECT * FROM apartments WHERE code='ACOLLISION2'").fetchone()
            self.assertEqual(a['official_lon'],b['official_lon'])
            self.assertNotEqual(a['lon'],b['lon'])
            self.assertIsNone(db.execute("SELECT lon FROM apartments WHERE code='AFUZZY'").fetchone()[0])
            self.assertIsNone(db.execute("SELECT lon FROM apartments WHERE code='AOUT'").fetchone()[0])

    def test_ambiguous_exact_names_do_not_supply_a_coordinate(self):
        self.elements.append({'type':'way','id':20,'center':{'lon':127.08,'lat':37.53},
                              'tags':{'name':'위치보완아파트','landuse':'residential'}})
        self.write_sources();self.import_data()
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT lon,osm_candidate_count FROM apartments WHERE code='ARECOVER'").fetchone(),(None,2))

    def test_bad_count_duplicate_identity_and_partial_count_preserve_previous_db(self):
        self.import_data();before=self.database.read_bytes()
        self.rows[1][FIELDS['households']]='400.5';self.write_sources()
        with self.assertRaises(ValueError):self.import_data()
        self.assertEqual(self.database.read_bytes(),before)
        self.rows[1][FIELDS['households']]='400';self.rows[1][FIELDS['code']]='A399';self.write_sources()
        with self.assertRaises(ValueError):self.import_data()
        self.assertEqual(self.database.read_bytes(),before)
        self.rows[1][FIELDS['code']]='A400';self.write_sources()
        with self.assertRaises(ValueError):
            import_database(self.csv,self.database,self.districts,'2026-09-08',expected_count=11)
        self.assertEqual(self.database.read_bytes(),before)

    def test_places_household_filter_preserves_other_landmark_categories(self):
        self.import_data()
        buildings=self.directory/'buildings.sqlite'
        with sqlite3.connect(buildings) as db:
            db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT);
                CREATE TABLE buildings(id TEXT,name TEXT,kind TEXT,geometry TEXT,
                    source_properties TEXT,district_id TEXT,is_apartment INTEGER);''')
        places=self.directory/'places.sqlite'
        build_database(places,buildings,self.districts,self.districts,[self.osm],apartments=self.database)
        api=PlacesAPI(places)
        result=api.features('126.9,37.4,127.2,37.7',16,'station,residential',400)
        self.assertEqual(len(result['features']),5)
        self.assertEqual({f['properties']['kind'] for f in result['features']},{'station','residential'})
        residential=[f['properties'] for f in result['features'] if f['properties']['kind']=='residential']
        self.assertTrue(all(p['household_count']>=400 and p['apartment_class']=='아파트' for p in residential))
        self.assertEqual(api.search('검증399')['results'][0]['household_count'],399)
        self.assertEqual(api.search('검증399',min_households=400)['results'],[])
        self.assertEqual(api.search('위치보완')['results'][0]['official_complex_code'],'ARECOVER')
        self.assertEqual(api.meta()['mapped_complex_count_ge400'],4)
        for value in (-1,400.5,'nan',True):
            with self.subTest(value=value),self.assertRaises(ValueError):
                api.features('126.9,37.4,127.2,37.7',16,min_households=value)


if __name__=='__main__':
    unittest.main()


class KaptSupplementTest(unittest.TestCase):
    """K-apt POI joins only on the identical complex code and never outranks a valid official coordinate."""

    def setUp(self):
        # Reuse the official-dataset fixture without inheriting its official-only test methods.
        self.fixture = ApartmentsTest('test_threshold_is_complex_total_and_missing_zero_and_class_stay_distinct')
        self.fixture.setUp()
        for name in ('temp', 'directory', 'csv', 'database', 'districts', 'rows', 'osm', 'elements'):
            setattr(self, name, getattr(self.fixture, name))
        from pyproj import Transformer
        self.to_tm = Transformer.from_crs('EPSG:4326', 'EPSG:5174', always_xy=True)
        self.kapt = self.directory / 'kapt-poi.json'
        def poi(code, lon, lat, name='단지'):
            if lon is None:
                return {'kaptCode': code, 'kaptName': name, 'kaptUsedate': '20200101', 'xCoord': None, 'yCoord': None}
            x, y = self.to_tm.transform(lon, lat)
            return {'kaptCode': code, 'kaptName': name, 'kaptUsedate': '20200101', 'xCoord': x, 'yCoord': y}
        self.poi_rows = [
            poi('ARECOVER', 127.0301, 37.5301),            # single point, agrees with the OSM area (~10 m)
            poi('AFUZZY', 127.0700, 37.5300), poi('AFUZZY', 127.0702, 37.5300),   # two points ~18 m apart
            poi('AOUT', 127.0500, 37.5000), poi('AOUT', 127.0900, 37.5000),        # points 3.5 km apart
            poi('ACOLLISION1', 127.1000, 37.6000), poi('ZOTHER', 127.1000, 37.6000),  # coordinate shared by two codes
            poi('ACOLLISION2', 127.0800, 37.5500),          # valid, but 2 km from the OSM '중복위치2' area at 127.06
            poi('A400', 127.0600, 37.5120),                 # ~4 km from the valid official coordinate
            poi('A399', None, None),                        # coordinate missing in K-apt
            poi('AMISSING', 127.3000, 37.5300),             # outside the Seoul fixture
            poi('테스트', 127.0000, 37.5000, name='테슽002'),  # code absent from the official dataset
        ]
        self.kapt.write_text(json.dumps({'resultList': self.poi_rows}, ensure_ascii=False))

    def import_data(self):
        return import_database(self.csv, self.database, self.districts, '2026-09-08', osm_path=self.osm,
                               expected_count=len(self.rows), kapt_path=self.kapt)

    def tearDown(self):
        self.fixture.tearDown()

    def rows_by_code(self):
        with sqlite3.connect(self.database) as db:
            db.row_factory = sqlite3.Row
            return {r['code']: dict(r) for r in db.execute('SELECT * FROM apartments')}

    def test_kapt_code_match_outranks_osm_name_match_and_records_agreement(self):
        meta = self.import_data()
        rows = self.rows_by_code()
        recovery = rows['ARECOVER']
        self.assertEqual(recovery['coordinate_status'], 'kapt_official_code_poi')
        self.assertEqual(recovery['location_method'], 'kapt_poi')
        self.assertAlmostEqual(recovery['lon'], 127.0301, places=5)
        self.assertAlmostEqual(recovery['lat'], 37.5301, places=5)
        self.assertLess(recovery['kapt_osm_distance_m'], 100)
        self.assertNotIn('kapt_osm_location_disagreement_over_750m', json.loads(recovery['coordinate_issues']))
        matched = json.loads(recovery['matched_kapt'])
        self.assertEqual((matched['point_count'], matched['spread_m']), (1, 0.0))
        self.assertEqual(meta['kapt_located_count'], 3)          # ARECOVER, AFUZZY, ACOLLISION2
        self.assertEqual(meta['kapt_poi_record_count'], len(self.poi_rows))
        self.assertEqual(meta['kapt_coordinates_shared_between_codes'], 1)
        self.assertEqual(meta['coordinate_status_counts']['kapt_official_code_poi'], 3)

    def test_tight_cluster_uses_mean_but_disagreeing_points_are_ambiguous(self):
        self.import_data()
        rows = self.rows_by_code()
        cluster = rows['AFUZZY']
        self.assertEqual(cluster['location_method'], 'kapt_poi_cluster_mean')
        self.assertAlmostEqual(cluster['lon'], 127.0701, places=4)
        self.assertLess(json.loads(cluster['matched_kapt'])['spread_m'], 100)
        spread = rows['AOUT']
        self.assertIsNone(spread['lon'])
        self.assertEqual(spread['coordinate_status'], 'unresolved')
        self.assertIn('kapt_poi_points_disagree', json.loads(spread['coordinate_issues']))

    def test_shared_kapt_coordinate_is_not_a_location_and_osm_fallback_still_applies(self):
        self.import_data()
        rows = self.rows_by_code()
        shared = rows['ACOLLISION1']
        self.assertIn('kapt_coordinate_shared_with_other_complex', json.loads(shared['coordinate_issues']))
        self.assertEqual(shared['coordinate_status'], 'osm_exact_name_and_district')
        self.assertEqual((shared['lon'], shared['lat']), (127.05, 37.53))

    def test_kapt_osm_disagreement_is_recorded_and_kapt_wins_by_official_code(self):
        meta = self.import_data()
        rows = self.rows_by_code()
        disagree = rows['ACOLLISION2']
        self.assertEqual(disagree['coordinate_status'], 'kapt_official_code_poi')
        self.assertAlmostEqual(disagree['lon'], 127.08, places=5)
        self.assertGreater(disagree['kapt_osm_distance_m'], 750)
        self.assertIn('kapt_osm_location_disagreement_over_750m', json.loads(disagree['coordinate_issues']))
        self.assertEqual([d['code'] for d in meta['kapt_osm_disagreements_over_750m']], ['ACOLLISION2'])

    def test_valid_official_coordinate_is_never_replaced_by_kapt(self):
        meta = self.import_data()
        rows = self.rows_by_code()
        official = rows['A400']
        self.assertEqual(official['coordinate_status'], 'official_reported')
        self.assertEqual((official['lon'], official['lat']), (127.012, 37.51))
        self.assertGreater(official['official_kapt_distance_m'], 750)
        self.assertIn('official_kapt_location_disagreement_over_750m', json.loads(official['coordinate_issues']))
        self.assertEqual([d['code'] for d in meta['official_kapt_disagreements_over_750m']], ['A400'])
        self.assertIsNone(rows['A399']['official_kapt_distance_m'])
        self.assertIn('kapt_coordinate_missing', json.loads(rows['A399']['coordinate_issues']))
        outside = rows['AMISSING']
        self.assertEqual(outside['coordinate_status'], 'official_reported')
        self.assertIn('kapt_coordinate_outside_seoul', json.loads(outside['coordinate_issues']))
        self.assertEqual(meta['kapt_codes_in_source_dataset'], 8)   # 테스트 row has no official record

    def test_without_kapt_supplement_behaviour_is_unchanged(self):
        meta = import_database(self.csv, self.database, self.districts, '2026-09-08', osm_path=self.osm, expected_count=len(self.rows))
        self.assertEqual(meta['kapt_located_count'], 0)
        self.assertIsNone(meta['kapt_source_sha256'])
        rows = self.rows_by_code()
        self.assertEqual(rows['ARECOVER']['coordinate_status'], 'osm_exact_name_and_district')
        self.assertIsNone(rows['ARECOVER']['matched_kapt'])
