import copy
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publish_shared_instances as publisher


def glb(path, height=82.35, bottom=0, transform=False):
    binary = struct.pack('<9f', 0, bottom, 0, 1, bottom, 0, 0, height, 1)
    node = {'mesh': 0}
    if transform:
        node['scale'] = [1, 2, 1]
    document = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
                'nodes': [node], 'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
                'buffers': [{'byteLength': len(binary)}], 'bufferViews': [{'buffer': 0, 'byteLength': len(binary)}],
                'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3'}]}
    data = json.dumps(document).encode()
    data += b' ' * (-len(data) % 4)
    path.write_bytes(struct.pack('<4sII', b'glTF', 2, 28 + len(data) + len(binary)) +
                     struct.pack('<II', len(data), 0x4e4f534a) + data +
                     struct.pack('<II', len(binary), 0x004e4942) + binary)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PreservedFallbackHeight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        self.fallback = {'id': 'fallback-103', 'model': 'fallback.glb',
                         'sha256': glb(self.root / 'fallback.glb'),
                         'rootTransform': 'identity', 'yawDegFromEast': 0,
                         'coordinate': {'lon': .0001, 'lat': .0001}, 'footprintIds': ['103-source'],
                         # Deliberately wrong metadata: measured bytes must win.
                         'dimensions': [1, 999, 1]}
        self.patch = patch.object(publisher, 'PUB', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_actual_glb_height_wins_over_metadata_without_changing_raw_register(self):
        row = {'register': {'height': '57.7', 'floors': '27'}}
        height, proof = publisher.preserved_fallback_height(self.fallback)
        self.assertAlmostEqual(height, 82.35, places=5)
        self.assertEqual(proof['fallbackSha256'], self.fallback['sha256'])
        self.assertEqual(proof['policy'], 'preserve-existing-visible-fallback-height')
        self.assertIn('conflict unresolved, not measured', proof['heightBasis'])
        self.assertEqual(publisher.target_height(row)[0], 57.7)
        self.assertEqual(row['register']['height'], '57.7')

    def test_rejects_digest_missing_file_and_unexplained_catalog_transform(self):
        for change in [{'sha256': 'wrong'}, {'model': 'missing.glb'}, {'groundOffsetM': 1},
                       {'rootTransform': 'scaled'}, {'modelInstance': {'matrix': []}}, {'scale': [1, 2, 1]}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                publisher.preserved_fallback_height(dict(self.fallback, **change))

    def test_rejects_invalid_actual_bounds_and_node_transform(self):
        for height, bottom, transform in [(0, 0, False), (-2, 0, False), (82, 2, False),
                                           (float('nan'), 0, False), (82, 0, True)]:
            with self.subTest(height=height, bottom=bottom, transform=transform):
                self.fallback['sha256'] = glb(self.root / 'fallback.glb', height, bottom, transform)
                with self.assertRaises(ValueError):
                    publisher.preserved_fallback_height(self.fallback)

    def fixture(self, selected):
        polygon = {'type': 'Polygon', 'coordinates': [[[0, 0], [.0001, 0], [.0001, .0001], [0, .0001], [0, 0]]]}
        rows = [{'number': n, 'sourceId': f'{n}-source', 'geometry': copy.deepcopy(polygon),
                 'register': {'height': '81.3' if n == 101 else '57.7', 'floors': '29' if n == 101 else '27'},
                 'osmHeightM': None} for n in (101, 103)]
        rep_hash = glb(self.root / 'rep.glb', 81.3)
        (self.root / 'rep.blend').write_bytes(b'fixture')
        source = {'id': 'copy-101', 'model': 'rep.glb', 'sha256': rep_hash,
                  'coordinate': {'lon': 0, 'lat': 0}, 'dimensions': [1, 81.3, 1],
                  'footprintIds': ['101-source'], 'sourceRecord': {'siteId': 'reviewed',
                  'blendSource': 'rep.blend', 'blendSha256': publisher.sha(self.root / 'rep.blend'),
                  'sourceGlbSha256': rep_hash}}
        docs = {'identity': {'towers': rows}, 'bindings': {'bindings': [{'number': 103,
                'sourceFootprintId': '103-source', 'fallbackAssetId': self.fallback['id'],
                'fallbackSha256': self.fallback['sha256'], 'supersedes': [self.fallback['id']]}]},
                'bespoke-manifest.json': {'assets': [source]},
                'published-bespoke.json': {'sites': {'reviewed': {'review': {'status': 'visually-reviewed', 'comparisons': []},
                    'mcpEvidence': [], 'sources': []}}}, 'manifest.json': {'assets': [self.fallback]},
                'generic-corrections.json': {'corrections': []}, 'footprint-matches.json': {},
                'deployment-assets.json': {'files': {}}}
        for name in ('identity', 'bindings'):
            (self.root / name).write_text(json.dumps(docs[name]))
        args = SimpleNamespace(site='new', id_prefix='copy', identity=self.root / 'identity',
                               bindings=self.root / 'bindings', source_asset='copy-101', representative_number=101,
                               preserve_fallback_height_for=selected, estimated_storey_height=None,
                               name='Banpo', hidden_node=[])
        return args, docs

    def run_publish(self, selected, mutate=None):
        args, docs = self.fixture(selected)
        if mutate:
            mutate(docs)
        original_read = publisher.read
        def read(path):
            return copy.deepcopy(docs[path.name]) if path.name in docs else original_read(path)
        def measure(command, **kwargs):
            data = original_read(Path(command[-2]))
            out = [{'id': a['id'], 'min': [0, 0, 0], 'max': [1, 81.3 * a['modelInstance']['matrix'][5], 1],
                    'dimensions': [1, 81.3 * a['modelInstance']['matrix'][5], 1]} for a in data['instances']]
            Path(command[-1]).write_text(json.dumps(out))
        with patch.object(publisher, 'ROOT', self.root), patch.object(publisher, 'read', side_effect=read), \
             patch.object(publisher, 'validate_mcp_evidence'), patch.object(publisher.subprocess, 'run', side_effect=measure), \
             patch.object(publisher, 'replace_batch') as writes:
            publisher.publish(args)
            documents = writes.call_args.args[1]
            manifest = json.loads(documents[self.root / 'bespoke-manifest.json'])
            evidence = json.loads(documents[self.root / 'docs/model-audit/published-bespoke.json'])
        return manifest['assets'][-1], evidence

    def test_publish_opt_in_preserves_height_anchor_raw_facts_and_audit_proof(self):
        asset, evidence = self.run_publish([103])
        facts = asset['sourceRecord']['buildingFacts']
        self.assertAlmostEqual(asset['dimensions'][1], 82.35, places=5)
        self.assertEqual(asset['coordinate'], self.fallback['coordinate'])
        self.assertEqual(facts['registeredHeightM'], 57.7)
        self.assertIsNone(facts['sourceHeightM'])
        self.assertTrue(asset['heightEstimated'])
        self.assertTrue(facts['heightUnresolved'])
        proof = evidence['sites']['new']['assets'][0]['heightPolicy']
        self.assertEqual(proof, asset['sourceRecord']['heightPolicy'])
        self.assertEqual(proof['fallbackId'], 'fallback-103')

    def test_default_publish_still_uses_register_height(self):
        asset, evidence = self.run_publish([])
        self.assertAlmostEqual(asset['dimensions'][1], 57.7)
        self.assertNotIn('heightPolicy', asset['sourceRecord'])
        self.assertNotIn('heightPolicy', evidence['sites']['new']['assets'][0])

    def test_unknown_representative_and_missing_fallback_rejected(self):
        for selected in ([999], [101]):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                self.run_publish(selected)
        with self.assertRaisesRegex(ValueError, 'no longer active'):
            self.run_publish([103], lambda d: d['manifest.json'].update(assets=[]))


if __name__ == '__main__':
    unittest.main()
