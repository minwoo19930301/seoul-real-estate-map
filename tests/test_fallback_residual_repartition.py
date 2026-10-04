import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import split_godeok_laclassy_fallbacks as split
from split_caelitus_fallback import encode, decode, sha
from split_prestige_fallbacks import triangle_signatures


class ResidualRepartition(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'public/models'
        (self.folder / 'generic-corrections').mkdir(parents=True)
        (self.root / 'data').mkdir()
        db = sqlite3.connect(self.root / 'data/buildings.sqlite')
        db.execute('create table buildings (id text, geometry text)')
        polygon = {'type': 'Polygon', 'coordinates': [[[-.01, -.01], [.01, -.01], [.01, .01], [-.01, .01], [-.01, -.01]]]}
        db.executemany('insert into buildings values (?,?)', [(fid, json.dumps(polygon)) for fid in 'abcd'])
        db.commit(); db.close()
        self.root_patch = patch.object(split, 'ROOT', self.root)
        self.root_patch.start(); self.addCleanup(self.root_patch.stop)
        document = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
                    'nodes': [{'mesh': 0, 'name': 'base'}], 'meshes': [{'primitives': []}],
                    'materials': [{'name': 'first'}, {'name': 'second'}],
                    'accessors': [{'componentType': 5126, 'type': 'VEC3'},
                                  {'componentType': 5126, 'type': 'VEC4'},
                                  {'componentType': 5125, 'type': 'SCALAR'}]}
        primitives = []
        for material in range(2):
            positions = np.array([[i, material, 0] for i in range(12)], dtype='<f4')
            positions[1::3, 2] = 1
            positions[2::3, 1] += 2
            colors = np.array([[i/12, .25, material/2, 1] for i in range(12)], dtype='<f4')
            primitives.append(({'material': material, 'attributes': {'POSITION': 0, 'COLOR_0': 1}, 'indices': 2},
                               {'POSITION': positions, 'COLOR_0': colors}, np.arange(12, dtype='<u4').reshape(-1, 3)))
        self.original, stats = encode(document, primitives, [np.ones(4, dtype=bool)] * 2, 'base')
        self.base = dict(stats, id='base', model='base.glb', coordinate={'lon': 0, 'lat': 0},
                         footprintIds=list('abcd'), name='base', yawDegFromEast=0)
        (self.folder / 'base.glb').write_bytes(self.original)
        g, parts = decode(self.original)
        self.current_bytes, stats = encode(g, parts, [np.array([False, True, True, True])] * 2, 'base')
        self.current = dict(self.base, **stats)
        self.current.update(model='generic-corrections/base.glb', footprintIds=list('bcd'),
                            genericCorrection={'sourceId': 'base'}, buildingCount=3)
        (self.folder / self.current['model']).write_bytes(self.current_bytes)
        self.frozen = {'currentResidual': True, 'ancestorAssetId': 'base', 'sha256': self.current['sha256'],
                       'provenance': 'original-provenance.json'}
        self.owners = [list('abcd'), list('abcd')]

    def replay(self, frozen=None, ids=None):
        proof = {'byteExact': True, 'sha256': sha(self.original)}
        with patch.object(split, 'replay', return_value=(self.owners, proof)) as original_replay:
            result = split.replay_current_residual(frozen or self.frozen, self.folder, self.current,
                ids or list('bcd'), {'base': self.base}, {'base': list('abcd')}, 'base')
            original_replay.assert_called_once_with(self.base, self.original, list('abcd'), 'original-provenance.json')
            return result

    def test_base_residual_new_parts_preserve_attributes_owners_and_old_bytes(self):
        owners, authoring = self.replay()
        self.assertEqual(owners, {0: list('bcd'), 1: list('bcd')})
        self.assertTrue(authoring['ancestorAuthoringReplay']['byteExact'])
        self.assertTrue(authoring['currentResidualReplay']['byteExact'])
        self.assertEqual(authoring['sha256'], sha(self.current_bytes))
        ranges = authoring['triangleRangesBySource']
        self.assertEqual(ranges, [
            {'sourceId': fid, 'triangleRangesByMaterial': {0: [i, i + 1], 1: [i, i + 1]}}
            for i, fid in enumerate('bcd')])
        for material, tags in owners.items():
            reconstructed = [None] * len(tags)
            for row in ranges:
                start, end = row['triangleRangesByMaterial'][material]
                self.assertTrue(all(value is None for value in reconstructed[start:end]))
                reconstructed[start:end] = [row['sourceId']] * (end - start)
            self.assertEqual(reconstructed, tags)

        cfg = {'parts': [('new-b', 'B', 'b')], 'remainingName': 'Remaining',
               'sha': self.current['sha256'], 'limits': []}
        correction, documents, proof = split.partition_by_replayed_source(
            cfg, self.folder, self.current, list('bcd'), owners, authoring, remainingId='residual-v2')
        self.assertEqual(correction['kind'], 'repartition')
        self.assertEqual({a['id'] for a in correction['assets']}, {'new-b', 'residual-v2'})
        self.assertEqual(proof['groupFootprints'], {'residual-v2': ['c', 'd'], 'new-b': ['b']})
        combined = Counter()
        g, parts = decode(self.original)
        for asset in correction['assets']:
            generated = documents[self.folder / asset['model']]
            masks = [np.array([fid in asset['footprintIds'] for fid in tags]) for tags in self.owners]
            expected, _ = encode(g, parts, masks, asset['id'])
            self.assertEqual(triangle_signatures(generated), triangle_signatures(expected))
            combined.update(triangle_signatures(generated))
            self.assertEqual(asset['searchable'], asset['id'] == 'residual-v2')
        self.assertEqual(combined, triangle_signatures(self.current_bytes))
        self.assertEqual((self.folder / self.current['model']).read_bytes(), self.current_bytes)
        self.assertEqual((self.folder / 'base.glb').read_bytes(), self.original)
        self.assertFalse((self.folder / 'generic-corrections/residual-v2.glb').exists())

    def test_stale_hash_invalid_subset_and_ancestor_rejected(self):
        for changes, ids in [({'sha256': 'stale'}, None), ({'ancestorAssetId': 'other'}, None),
                             ({}, ['b', 'b', 'c']), ({}, ['b', 'missing'])]:
            with self.subTest(changes=changes, ids=ids), self.assertRaises(AssertionError):
                self.replay(dict(self.frozen, **changes), ids)

    def test_non_byte_exact_current_model_rejected_even_with_updated_hash(self):
        g, parts = decode(self.current_bytes)
        parts[0][1]['COLOR_0'][0, 0] = .99
        changed, stats = encode(g, parts, [np.ones(3, dtype=bool)] * 2, 'base')
        (self.folder / self.current['model']).write_bytes(changed)
        self.current.update(stats)
        self.frozen['sha256'] = stats['sha256']
        with self.assertRaisesRegex(AssertionError, 'byte-exact replay differs'):
            self.replay()

    def test_repartition_rejects_old_id_or_duplicate_output_ids(self):
        owners, authoring = self.replay()
        cfg = {'parts': [('new-b', 'B', 'b')], 'remainingName': 'Remaining', 'sha': self.current['sha256'], 'limits': []}
        for residual in ['base', 'new-b']:
            with self.subTest(residual=residual), self.assertRaises(AssertionError):
                split.partition_by_replayed_source(cfg, self.folder, self.current, list('bcd'), owners, authoring, remainingId=residual)

    def test_effective_order_removes_old_residual_and_preserves_prior_metadata(self):
        first = {'sourceId': 'base', 'sourceSha256': self.base['sha256'], 'sourceFootprintIds': list('abcd'),
                 'assets': [self.current, {'id': 'part-a', 'sha256': 'a', 'footprintIds': ['a']}]}
        second = {'kind': 'repartition', 'sourceId': 'base', 'sourceSha256': self.current['sha256'],
                  'sourceFootprintIds': list('bcd'), 'assets': [
                      {'id': 'new-b', 'sha256': 'b', 'footprintIds': ['b']},
                      {'id': 'residual-v2', 'sha256': 'cd', 'footprintIds': ['c', 'd']}]}
        corrections = [first, second]
        before = copy.deepcopy(corrections)
        assets, matches, ancestors, touched = split.effective_sources([self.base], {'base': list('abcd')}, corrections)
        self.assertNotIn('base', assets)
        self.assertEqual(matches['residual-v2'], ['c', 'd'])
        self.assertEqual(ancestors['residual-v2'], 'base')
        self.assertEqual(corrections, before)
        self.assertIn('base', touched)
        second['assets'][1]['id'] = 'new-b'
        with self.assertRaisesRegex(AssertionError, 'Duplicate'):
            split.effective_sources([self.base], {'base': list('abcd')}, corrections)


if __name__ == '__main__':
    unittest.main()
