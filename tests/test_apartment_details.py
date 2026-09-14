"""Apartment detail and renewal-zone API use exact identifiers and bounded bbox queries."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from server.apartment_details import ApartmentDetailsAPI, MAX_ZONES


def build(path):
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE kapt_basic_info_weekly(row_number, 단지코드, 단지명, 동수, 세대수, 최고층수, 사용승인일, 분양형태, 난방방식, 총주차대수, 시공사);
            CREATE TABLE kapt_reb_link(kapt_code, derived_pnu, reb_complex_id, reb_name_register, reb_households, match_status);
            CREATE TABLE reb_dong_summary(reb_complex_id, dong_count, max_floors);
            CREATE TABLE seoul_apartment_mgmt_fee_oa_15822(row_number, 아파트명, 아파트코드, 비용명, 년월, 금액);
            CREATE TABLE upis_renewal_project_zones_uq120(objectid, present_sn, sclas_cl, dgm_nm, signgu_se, dgm_ar, geometry_geojson, min_lon, min_lat, max_lon, max_lat);
            CREATE TABLE upis_renewal_districts_uq181(objectid, present_sn, sclas_cl, dgm_nm, signgu_se, dgm_ar, geometry_geojson, min_lon, min_lat, max_lon, max_lat);''')
        db.execute("INSERT INTO kapt_basic_info_weekly VALUES(1,'A1','검증단지','8','1623','15','19911120','임대','지역난방','500','시공사')")
        db.execute("INSERT INTO kapt_reb_link VALUES('A1','1168010300100120000','11680200000001','검증단지','1623','pnu_exact_single')")
        db.execute("INSERT INTO kapt_reb_link VALUES('A2','1168010300100130000',NULL,NULL,NULL,'no_match')")
        db.execute("INSERT INTO reb_dong_summary VALUES('11680200000001',8,15)")
        for i,(m,n,a) in enumerate([('202606','급여','100'),('202607','급여','200'),('202607','세대전기료','1,000')]):
            db.execute('INSERT INTO seoul_apartment_mgmt_fee_oa_15822 VALUES(?,?,?,?,?,?)',(i,'검증단지','A1',n,m,a))
        ring = {'type':'Polygon','coordinates':[[[127.0,37.5],[127.01,37.5],[127.01,37.51],[127.0,37.5]]]}
        db.execute("INSERT INTO upis_renewal_project_zones_uq120 VALUES(1,'P1','BZ105','은마아파트','11680','1000',?,127.0,37.5,127.01,37.51)",(json.dumps(ring),))
        db.execute("INSERT INTO upis_renewal_districts_uq181 VALUES(2,'D1','UQ1240','먼구역','11110','10',?,126.0,36.0,126.01,36.01)",(json.dumps(ring),))


class ApartmentDetailsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.db = Path(self.temp.name) / 'a.sqlite'; build(self.db)
        self.api = ApartmentDetailsAPI(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_detail_joins_by_code_and_uses_latest_fee_month(self):
        d = self.api.detail('A1')
        self.assertEqual(d['kapt_basic']['동수'], '8')
        self.assertEqual(d['reb'][0]['dong_count'], 8)
        self.assertEqual(d['reb'][0]['max_ground_floors'], 15)
        self.assertEqual(d['management_fee']['month'], '202607')
        self.assertEqual(d['management_fee']['total_won'], 1200)

    def test_unmatched_code_returns_empty_sections_not_guesses(self):
        d = self.api.detail('A2')
        self.assertIsNone(d['kapt_basic']); self.assertEqual(d['reb'], []); self.assertIsNone(d['management_fee'])

    def test_invalid_code_and_missing_database(self):
        for bad in ('', 'A1;DROP', 'x' * 30, '가나'):
            with self.assertRaises(ValueError): self.api.detail(bad)
        self.assertFalse(ApartmentDetailsAPI(Path(self.temp.name) / 'none.sqlite').detail('A1')['available'])

    def test_zones_filter_by_bbox_and_kind(self):
        z = self.api.zones('126.99,37.49,127.02,37.52')
        self.assertEqual([f['properties']['name'] for f in z['features']], ['은마아파트'])
        self.assertEqual(z['features'][0]['geometry']['type'], 'Polygon')
        self.assertEqual(self.api.zones('125,35,128,38', 'district')['metadata']['count'], 1)
        with self.assertRaises(ValueError): self.api.zones('126,37,127,38', 'other')
        with self.assertRaises(ValueError): self.api.zones('bad')
        self.assertGreater(MAX_ZONES, 0)


if __name__ == '__main__':
    unittest.main()


class SuspectHeightTest(unittest.TestCase):
    def test_implausible_permit_heights_are_excluded_from_the_maximum(self):
        import sqlite3 as sq
        from server.apartment_details import MAX_PLAUSIBLE_HEIGHT_M
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'apartment_sources.sqlite'; build(src)
            links = Path(d) / 'apartment_parcel_links.sqlite'
            with sq.connect(links) as db:
                db.executescript('''CREATE TABLE complex_pnu(code,pnu); CREATE TABLE sales(code,pnu,contract_date,price_manwon,area_m2,floor,building_name,built_year,cancel_date,building_use);
                    CREATE TABLE rents(code,pnu,contract_date,rent_type,deposit_manwon,monthly_manwon,area_m2,floor,building_name,building_use);
                    CREATE TABLE price_summary(code,pnu,basis,unit_count,median_won,min_won,max_won,median_won_per_m2);
                    CREATE TABLE registers(code,pnu,register_serial,register_kind,main_use,households,main_buildings,parking,site_area,total_floor_area,coverage_ratio,floor_area_ratio,approval_date);
                    CREATE TABLE permit_dongs(code,pnu,housing_register_serial,building_name,dong_name,main_or_annex,main_use,ground_floors,basement_floors,height_m);''')
                db.executemany('INSERT INTO permit_dongs VALUES(?,?,?,?,?,?,?,?,?,?)', [
                    ('A1','p','1','x','101','주건축물','공동주택',18,1,50.1), ('A1','p','1','x','102','주건축물','공동주택',18,1,50101.0),
                    ('A1','p','1','x','103','주건축물','공동주택',0,0,0.0)])
            p = ApartmentDetailsAPI(src).parcel('A1')['permit_dongs']
            self.assertEqual((p['count'], p['max_height_m'], p['suspect_height_count'], p['max_ground_floors']), (3, 50.1, 1, 18))
            self.assertGreater(MAX_PLAUSIBLE_HEIGHT_M, 555)
