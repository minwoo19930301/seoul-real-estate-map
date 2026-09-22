import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publish_shared_instances import target_height


class SharedHeight(unittest.TestCase):
    def test_missing_height_requires_explicit_estimate_and_keeps_source_missing(self):
        row = {'register': {'height': '0', 'floors': '14'}}
        with self.assertRaises(ValueError):
            target_height(row)
        height, basis = target_height(row, 3.05)
        self.assertAlmostEqual(height, 42.7)
        self.assertIn('not measured', basis)
        self.assertEqual(row['register']['height'], '0')
        for invalid in [0, -3, 10, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                target_height(row, invalid)

    def test_estimate_never_replaces_available_registered_metres(self):
        row = {'register': {'height': '81.47', 'floors': '29'}}
        height, basis = target_height(row, 3.05)
        self.assertEqual(height, 81.47)
        self.assertIn('registered', basis)


if __name__ == '__main__':
    unittest.main()
