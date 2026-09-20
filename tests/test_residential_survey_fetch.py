import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import fetch_residential_survey as fetch


class SurveyFetchTests(unittest.TestCase):
    def collect(self, root, get, supplemental=False):
        argv = ['fetch', '--root', str(root)] + (['--supplemental'] if supplemental else [])
        with patch.object(sys, 'argv', argv), patch.object(fetch, 'get', side_effect=get), contextlib.redirect_stdout(io.StringIO()):
            fetch.main()

    @staticmethod
    def response(params):
        if 'returnCountOnly' in params:
            return 'https://source/count', {'count': 2}
        if 'returnIdsOnly' in params:
            return 'https://source/ids', {'objectIds': [1, 2]}
        return 'https://source/geometry', {'features': [{'attributes': {'OBJECTID': int(i)}} for i in params['objectIds'].split(',')]}

    def test_resume_verifies_local_geometry_before_network_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.collect(root, self.response)
            first = json.loads((root / 'metadata.json').read_text())['collectedAt']
            def resume(params):
                self.assertNotIn('returnGeometry', params)
                return self.response(params)
            self.collect(root, resume)
            self.assertEqual(json.loads((root / 'metadata.json').read_text())['collectedAt'], first)

    def test_custom_root_supplemental_subtracts_its_own_base_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'objectids.json').write_text(json.dumps({'objectIds': [1]}))
            self.collect(root, self.response, supplemental=True)
            self.assertEqual(json.loads((root / 'supplemental/objectids.json').read_text())['objectIds'], [2])

    def test_duplicate_feature_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            def duplicate(params):
                url, result = self.response(params)
                if 'features' in result:
                    result['features'].append(result['features'][0])
                return url, result
            with self.assertRaisesRegex(RuntimeError, 'duplicate ids'):
                self.collect(Path(folder), duplicate)
            self.assertFalse((Path(folder) / 'metadata.json').exists())


if __name__ == '__main__':
    unittest.main()
