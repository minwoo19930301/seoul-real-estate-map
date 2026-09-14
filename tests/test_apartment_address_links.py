"""Address strings resolve to a PNU only through an exact, unique 도로명주소 건물DB key."""
import unittest

from scripts.build_apartment_address_links import resolve, lot_pnu


class AddressResolveTest(unittest.TestCase):
    def setUp(self):
        self.road = {('서대문구', '통일로48가길', '0', '0037', '0000'): {'1141011000100010000'},
                     ('강남구', '압구정로', '0', '0151', '0000'): {'1168011000103690001', '1168011000103690002'}}
        self.lot = {('금천구', '시흥동', '0', '0817', '0029'): {'1154510200108170029'}}

    def test_road_and_lot_addresses(self):
        self.assertEqual(resolve('서울특별시 서대문구 통일로48가길 37', None, self.road, self.lot), ('1141011000100010000', 'road_exact'))
        self.assertEqual(resolve('서울특별시 서대문구 통일로48가길 38', None, self.road, self.lot), (None, 'not_in_building_db'))
        self.assertEqual(resolve('서울특별시 금천구 시흥동 817-29', None, self.road, self.lot), ('1154510200108170029', 'lot_exact'))

    def test_district_comes_from_address_or_table(self):
        road = {('강북구', '솔샘로', '0', '0159', '0000'): {'Q'}}
        self.assertEqual(resolve('솔샘로 159', '강북구', road, {}), ('Q', 'road_exact'))
        self.assertEqual(resolve('솔샘로 159', None, road, {}), (None, 'no_district'))

    def test_ambiguous_and_empty_are_refused(self):
        self.assertEqual(resolve('서울특별시 강남구 압구정로 151', None, self.road, self.lot), (None, 'road_ambiguous'))
        self.assertEqual(resolve('', '강남구', self.road, self.lot), (None, 'empty'))
        self.assertEqual(resolve('서울특별시 강남구 압구정로 1511', None, self.road, self.lot), (None, 'not_in_building_db'))

    def test_renewal_list_address_forms(self):
        lot = {('강남구', '개포동', '0', '0138', '0000'): {'R1'}, ('양천구', '목2동', '0', '0523', '0045'): {'R2'}}
        self.assertEqual(resolve('개포동 138', None, {}, lot, '강남구'), ('R1', 'lot_exact'))
        self.assertEqual(resolve('목2동 523-45번지일대', None, {}, lot, '양천구'), ('R2', 'lot_exact'))
        self.assertEqual(resolve('-', None, {}, lot, '양천구'), (None, 'empty'))

    def test_lot_pnu_rules(self):
        self.assertEqual(lot_pnu('1111010100', '0', '108', '14'), '1111010100101080014')
        self.assertEqual(lot_pnu('1111010100', '1', '5', ''), '1111010100200050000')
        self.assertIsNone(lot_pnu('11110101', '0', '108', '14'))
        self.assertIsNone(lot_pnu('1111010100', '0', '0', '0'))


if __name__ == '__main__':
    unittest.main()
