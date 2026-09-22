import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publish_shared_instances import target_height, effective_fallback_assets, publish
from check_shared_instance_placements import check as check_placements


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


class SharedFallbackCorrections(unittest.TestCase):
    def test_same_id_residual_remains_with_corrected_ownership(self):
        original = {'id': 'compound', 'footprintIds': ['a', 'b'], 'sha256': 'old'}
        residual = {'id': 'compound', 'footprintIds': ['b'], 'sha256': 'residual'}
        split = {'id': 'split-a', 'footprintIds': ['a'], 'sha256': 'split'}
        current = effective_fallback_assets([original], [
            {'sourceId': 'compound', 'assets': [residual, split]}])
        self.assertEqual(current, {'compound': residual, 'split-a': split})
        self.assertEqual(original['footprintIds'], ['a', 'b'])

    def test_later_complete_repartition_removes_earlier_asset(self):
        original = {'id': 'compound'}
        residual = {'id': 'compound', 'sha256': 'residual'}
        first = {'id': 'first'}
        last = {'id': 'last'}
        current = effective_fallback_assets([original], [
            {'sourceId': 'compound', 'assets': [residual, first]},
            {'kind': 'repartition', 'sourceId': 'compound', 'assets': [last]}])
        self.assertEqual(current, {'first': first, 'last': last})

    def test_publish_rejects_binding_to_removed_source_before_writes(self):
        source = {'id': 'rep-1', 'model': 'rep.glb', 'sha256': 'hash',
                  'footprintIds': ['source-1'], 'sourceRecord': {
                      'siteId': 'reviewed', 'blendSource': 'rep.blend', 'blendSha256': 'hash'}}
        stale = {'id': 'old', 'footprintIds': ['source-2'], 'sha256': 'old-hash'}
        args = SimpleNamespace(site='new-site', id_prefix='rep', identity=Path('identity'),
                               bindings=Path('bindings'), source_asset='rep-1', representative_number=1)
        documents = [
            {'towers': [{'number': 1, 'sourceId': 'source-1'}, {'number': 2, 'sourceId': 'source-2'}]},
            {'bindings': [{'number': 2, 'sourceFootprintId': 'source-2',
                           'fallbackAssetId': 'old', 'fallbackSha256': 'old-hash'}]},
            {'assets': [source]},
            {'sites': {'reviewed': {'review': {'status': 'visually-reviewed'}, 'mcpEvidence': []}}},
            {'assets': [stale]},
            {'corrections': [{'kind': 'repartition', 'sourceId': 'old', 'assets': [
                {'id': 'replacement', 'footprintIds': ['source-2'], 'sha256': 'new-hash'}]}]},
            {}]
        with patch('publish_shared_instances.read', side_effect=documents), \
             patch('publish_shared_instances.sha', return_value='hash'), \
             patch('publish_shared_instances.validate_mcp_evidence'), \
             patch('publish_shared_instances.placement') as placement_mock, \
             patch('publish_shared_instances.replace_batch') as writes:
            with self.assertRaisesRegex(ValueError, 'fallback is no longer active: old'):
                publish(args)
            placement_mock.assert_not_called()
            writes.assert_not_called()


class SharedPlacementBatches(unittest.TestCase):
    def fixtures(self):
        metre = 1 / 111319.49079327358
        def row(fid, number, x):
            return {'sourceId': fid, 'number': number, 'geometry': {
                'type': 'Polygon', 'coordinates': [[
                    [x * metre, 0], [(x + 1) * metre, 0],
                    [(x + 1) * metre, metre], [x * metre, metre], [x * metre, 0]]]}}
        representative = {'id': 'representative', 'coordinate': {'lon': 0, 'lat': 0},
                          'footprintIds': ['rep-source'], 'sourceRecord': {'siteId': 'reviewed'}}
        def asset(fid, site, x):
            return {'id': fid, 'coordinate': {'lon': x * metre, 'lat': 0},
                    'footprintIds': [fid], 'sourceRecord': {'siteId': site},
                    'modelInstance': {'sourceAssetId': 'representative',
                        'matrix': [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}}
        return {
            'public/models/bespoke-manifest.json': {'assets': [representative,
                asset('a', 'first', 10), asset('b', 'extension', 10.5)]},
            'docs/model-audit/published-bespoke.json': {'sites': {
                'first': {'sharedRepresentative': 'representative', 'placementInputs': [{'path': 'first.json'}]},
                'extension': {'sharedRepresentative': 'representative', 'placementInputs': [{'path': 'extension.json'}]}}},
            'first.json': {'complex': {'managementCode': 'same-complex'},
                           'towers': [row('rep-source', 1, 0), row('a', 2, 100)]},
            'extension.json': {'complex': {'managementCode': 'same-complex'},
                               'towers': [row('rep-source', 1, 0), row('b', 3, 200)]},
        }

    def test_overlap_between_separate_publication_batches_is_detected(self):
        documents = self.fixtures()
        with patch('check_shared_instance_placements.read', side_effect=documents.__getitem__):
            reports = check_placements()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]['copies'], 2)
        self.assertEqual(reports[0]['sourceBodies'], 3)
        self.assertEqual(reports[0]['bodyPlanNeighborOverlaps'], [])
        self.assertEqual(len(reports[0]['copyToCopyOverlaps']), 1)
        self.assertAlmostEqual(reports[0]['copyToCopyOverlaps'][0]['overlapM2'], .5, places=5)

    def test_conflicting_source_geometry_in_extension_is_rejected(self):
        documents = self.fixtures()
        documents['extension.json']['towers'][0]['geometry']['coordinates'][0][0][0] = .001
        with patch('check_shared_instance_placements.read', side_effect=documents.__getitem__):
            with self.assertRaisesRegex(ValueError, 'Conflicting source identity'):
                check_placements()


if __name__ == '__main__':
    unittest.main()
