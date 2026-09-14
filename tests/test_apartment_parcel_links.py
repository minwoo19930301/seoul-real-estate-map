"""PNU construction is exact and refuses incomplete or ambiguous inputs."""
import unittest

from scripts.build_apartment_parcel_links import make_pnu, register_pnu, digits


class ParcelLinkTest(unittest.TestCase):
    def test_pnu_from_codes(self):
        self.assertEqual(make_pnu('1171010700', '1', '913', '0'), '1171010700109130000')
        self.assertEqual(make_pnu('1171010700', '대지', '0913', ''), '1171010700109130000')
        self.assertEqual(make_pnu('1168010600', '산', '12', '3'), '1168010600200120003')

    def test_incomplete_or_other_land_types_are_refused(self):
        self.assertIsNone(make_pnu('1171010700', '3', '10', '0'))      # 블럭 is not a PNU land type
        self.assertIsNone(make_pnu('1171010700', '', '10', '0'))
        self.assertIsNone(make_pnu('11710107', '1', '10', '0'))        # short dong code
        self.assertIsNone(make_pnu('1171010700', '1', '0', '0'))       # 0-0 lot
        self.assertIsNone(make_pnu('1171010700', '1', '12a', '0'))
        self.assertIsNone(digits('12345', 4))

    def test_register_names_need_an_unambiguous_official_code(self):
        mapping = {('송파구', '가락동'): '1171010700'}
        self.assertEqual(register_pnu(mapping, '서울특별시 송파구', ' 가락동', '대지', '0913', '0000'), '1171010700109130000')
        self.assertIsNone(register_pnu(mapping, '서울특별시 강남구', '가락동', '대지', '0913', '0000'))
        self.assertIsNone(register_pnu(mapping, '서울특별시 송파구', '가락동', '블록', '0913', '0000'))


if __name__ == '__main__':
    unittest.main()
