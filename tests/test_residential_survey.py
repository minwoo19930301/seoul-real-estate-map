"""Source interpretation and preservation boundaries for the housing census."""
import importlib.util
import sys
import unittest
from pathlib import Path
from shapely.geometry import Polygon
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from select_residential_survey import Registry, classification, esri_polygon, safe_height, tile_for
from index_residential_register import keyland,keyroad,parcel_id,number


class SurveySourceTests(unittest.TestCase):
    def test_complex_name_cannot_turn_ancillary_structures_into_apartments(self):
        cases=[('공동주택','공동주택(주차장)','엘지한강 자이아파트'),('제1종근린생활시설','생활편익시설','면목동삼호아파트 상가동'),('종교시설','종교시설','관악 우성아파트'),('노유자시설','보육시설','무악현대아파트'),('자동차관련시설','기계식주차타워','미가오피스텔'),('공동주택','아파트상가','현대아파트'),('공동주택','아파트 부대시설','현대아파트'),('공동주택','아파트관리소','현대아파트')]
        for case in cases:
            with self.subTest(case=case):self.assertIsNone(classification(*case)[0])

    def test_explicit_residential_types_and_unknown_subtype_stay_distinct(self):
        self.assertEqual(classification('공동주택','공동주택(다세대주택)','')[0],'villa')
        self.assertEqual(classification('공동주택','연립주택','')[0],'villa')
        self.assertEqual(classification('업무시설','업무시설(오피스텔)','')[0],'officetel')
        self.assertEqual(classification('공동주택','아파트 및 근린생활시설','')[0],'mixed-use')
        self.assertEqual(classification('공동주택','주택','')[0],'multifamily')
        self.assertIsNone(classification('업무시설','일반업무시설','건물')[0])

    def test_esri_ring_order_direction_holes_and_islands(self):
        rings=[[(0,0),(10,0),(10,10),(0,10),(0,0)],[(2,2),(2,8),(8,8),(8,2),(2,2)],[(4,4),(6,4),(6,6),(4,6),(4,4)],[(20,20),(21,20),(21,21),(20,21),(20,20)]]
        expected=69
        for ordered in [rings,[list(reversed(r)) for r in rings[::-1]]]:
            geom=esri_polygon({'rings':ordered});self.assertTrue(geom.is_valid);self.assertEqual(geom.area,expected)
            self.assertEqual(len(geom.geoms),3)
        with self.assertRaises(ValueError):esri_polygon({'rings':[[(0,0),(1,1),(0,1),(1,0),(0,0)]]})

    def test_register_height_needs_identity_floors_year_and_plausible_scale(self):
        attrs={'DBJSFLOOR':'4','SAYONG_YEA':'1995'}
        reg={'identity':'unique parcel and road record','height':'12','floors':'4','approval_year':'1995'}
        self.assertEqual(safe_height(attrs,reg,None)[0],12)
        for changes in [{'identity':'ambiguous'},{'floors':'3'},{'approval_year':'2010'},{'height':'9999'}]:
            self.assertEqual(safe_height(attrs,{**reg,**changes},None)[0],12.2)
        self.assertIsNone(safe_height({'DBJSFLOOR':'0'},None,None)[0])

    def test_lot_and_road_keys_preserve_district_mountain_and_underground(self):
        self.assertNotEqual(keyland('중구','중동','land','1','0'),keyland('마포구','중동','land','1','0'))
        self.assertNotEqual(keyland('중구','중동','land','1','0'),keyland('중구','중동','mountain','1','0'))
        self.assertNotEqual(keyroad('중구','중앙로','1','0','지상'),keyroad('중구','중앙로','1','0','지하'))
        self.assertEqual(number(''),0);self.assertIsNone(number('',main=True));self.assertIsNone(number('0',main=True))
        self.assertEqual(parcel_id('1111017300','0','1','1068'),'1111017300100011068')
        self.assertIsNone(parcel_id('4111017300','0','1','1068'))
        self.assertIsNone(parcel_id('1111017300','unknown','1','0'))

    def test_tiles_use_stable_numeric_seoul_location(self):
        self.assertRegex(tile_for(126.978,37.566),r'^16-\d+-\d+$')

    def test_one_register_record_cannot_supply_several_official_buildings(self):
        registry = Registry.__new__(Registry)
        registry.shared_records = set()
        address = {'district':'종로구','parcel_id':'1111017300100010000','parcel_key':'parcel','road_key':'road','name':'주택','detail_name':''}
        record = {'id':'same-register','district':'종로구','main_aux':'주건축물','road_key':'road'}
        registry.by_manager = lambda manager: [address]
        registry.reg_for = lambda parcel: [record.copy()]
        attrs = {'ADDRESS':address['parcel_id'],'BLDG_MGRNU':'manager'}
        self.assertEqual(registry.link(attrs,'종로구')[1]['id'],'same-register')
        registry.shared_records.add('same-register')
        linked, height_source, reason = registry.link(attrs,'종로구')
        self.assertEqual(linked,address)
        self.assertIsNone(height_source)
        self.assertIn('not transferred',reason)


if __name__=='__main__':unittest.main()
