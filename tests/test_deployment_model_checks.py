import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from deployment_model_checks import AssetVerifier


def asset(name, model, body):
    return {'id': name, 'model': model, 'sha256': hashlib.sha256(body).hexdigest()}


class DeploymentModelChecks(unittest.TestCase):
    def test_shared_instances_fetch_once_and_reuse_prior_reference_check(self):
        body = b'glTF shared representative'
        read = Mock(return_value=body)
        verifier = AssetVerifier(read)
        records = [asset(str(i), 'shared.glb', body) for i in range(1233)]
        verifier.verify('/models/shared.glb', records[0]['sha256'], 'reference', require_glb=True)
        verifier.verify_models(records, 'bespoke: ')
        read.assert_called_once_with('/models/shared.glb')

    def test_distinct_paths_are_verified_even_with_equal_hashes(self):
        body = b'glTF same contents'
        read = Mock(return_value=body)
        AssetVerifier(read).verify_models([asset('a', 'a.glb', body), asset('b', 'b.glb', body)], 'model: ')
        self.assertEqual([c.args[0] for c in read.call_args_list], ['/models/a.glb', '/models/b.glb'])

    def test_conflicting_clone_hashes_fail_before_download(self):
        read = Mock()
        with self.assertRaisesRegex(AssertionError, 'Conflicting asset hashes'):
            AssetVerifier(read).verify_models([asset('a', 'same.glb', b'a'), asset('b', 'same.glb', b'b')], 'model: ')
        read.assert_not_called()

    def test_prior_checked_path_cannot_be_redeclared_with_another_hash(self):
        read = Mock(return_value=b'a')
        verifier = AssetVerifier(read)
        verifier.verify_models([asset('a', 'same.glb', b'a')], 'model: ')
        with self.assertRaisesRegex(AssertionError, 'Conflicting asset hashes'):
            verifier.verify_models([asset('b', 'same.glb', b'b')], 'model: ')
        self.assertEqual(read.call_count, 1)

    def test_corruption_is_not_cached_and_retry_is_verified(self):
        read = Mock(side_effect=[b'bad', b'good'])
        verifier = AssetVerifier(read)
        records = [asset('a', 'a.glb', b'good')]
        with self.assertRaisesRegex(AssertionError, 'model: a'):
            verifier.verify_models(records, 'model: ')
        verifier.verify_models(records, 'model: ')
        self.assertEqual(read.call_count, 2)

    def test_cached_non_glb_still_fails_required_magic_check(self):
        read = Mock(return_value=b'not glb')
        verifier = AssetVerifier(read)
        record = asset('a', 'a.glb', b'not glb')
        verifier.verify_models([record], 'model: ')
        with self.assertRaisesRegex(AssertionError, '3D model unavailable'):
            verifier.verify('/models/a.glb', record['sha256'], 'model: a', require_glb=True)
        self.assertEqual(read.call_count, 1)


if __name__ == '__main__':
    unittest.main()
