import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_apartment_bespoke_queue import build, canonical, digest, read, validate_snapshot, verify_asset

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'docs/model-audit'


def record(code='A10000001', count=400, classification='아파트', source='oa-15818', row=2, address='서울특별시 중구 시험로 1'):
    return dict(sourceId=source, sourceRow=row, code=code, nameKo='합성 단지', classification=classification,
                households=count, buildingCount=1, district='중구', address=address, sourceCoordinate=None)


def snapshot(records):
    return {'version': 1, 'checkedOn': '2026-09-21', 'records': records, 'locationSnapshot': {},
            'sources': {s: {'rows': sum(r['sourceId'] == s for r in records)} for s in {r['sourceId'] for r in records}}}


def run_build(records, coverage=None, assets=None, published=None, root=ROOT):
    return build(snapshot(records), coverage or {'complexes': []}, {'assets': assets or []}, published or {'sites': {}}, {'assets': []}, root)


def make_proof(root):
    def file(path, data):
        f = root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        return digest(f)
    public_hash = file('public/models/bespoke/test/model.glb', b'fixture published geometry')
    blend_hash = file('modeling/bespoke/test/source.blend', b'fixture editable source')
    mcp_hash = file('docs/model-audit/mcp/test/build.json', b'[{"tool":"execute_blender_code","isError":false,"content":[{"type":"text","text":"Code executed successfully"}]}]')
    source_hash = hashlib.sha256(b'fixture source geometry').hexdigest()
    asset = {'id': 'bespoke-test-a', 'model': 'bespoke/test/model.glb', 'sha256': public_hash,
             'footprintIds': ['fixture-footprint'], 'sourceRecord': {'siteId': 'test', 'sourceGlbSha256': source_hash,
             'blendSource': 'modeling/bespoke/test/source.blend', 'blendSha256': blend_hash}}
    published = {'sites': {'test': {'sources': [{'url': 'https://example.org/official/photo'}],
        'review': {'status': 'visually-reviewed', 'comparisons': ['Fixture explicit building comparison'], 'reviewedInputs': {'model.glb': source_hash, 'source.blend': blend_hash}},
        'assets': [{'id': asset['id'], 'sha256': public_hash, 'sourceSha256': source_hash}],
        'mcpEvidence': [{'path': 'docs/model-audit/mcp/test/build.json', 'sha256': mcp_hash, 'tool': 'execute_blender_code'}]}}}
    coverage = {'complexes': [{'code': 'A10000001', 'physicalSiteId': 'fixture-site', 'coverageApproved': True,
        'expectedResidentialBuildingCount': 1, 'photoCoverageBasis': 'Explicit test evidence',
        'buildingIdentitySource': 'https://example.org/official/plan',
        'buildings': [{'label': 'A', 'assetId': asset['id'], 'photoReviewSiteId': 'test'}]}]}
    return asset, published, coverage


class QueueRulesTests(unittest.TestCase):
    def test_threshold_uses_any_credible_source_without_summing_or_erasing_zero(self):
        rows = [record(count=0), record(count=400, source='kapt-weekly'),
                record('A10000002', 399), record('A10000002', 399, source='kapt-weekly')]
        queue, summary = run_build(rows)
        self.assertEqual(summary['eligibleManagementCodes'], 1)
        self.assertEqual(queue[0]['householdValues'], [0, 400])
        self.assertTrue(queue[0]['householdDisagreement'])
        self.assertEqual(queue[0]['modelStatus'], 'not_started')

    def test_unknown_class_is_reviewed_and_explicit_non_apartment_is_retained_excluded(self):
        queue, _ = run_build([record(classification=''), record('A10000002', 762, '연립주택'), record('A10000003', 400, ''), record('A10000003', 400, '아파트', 'kapt-weekly')])
        self.assertEqual([r['eligibility'] for r in queue], ['eligibility_review', 'scope_excluded', 'eligible'])

    def test_repeated_kapt_addresses_preserve_rows_but_not_duplicate_target_or_households(self):
        records = [record(source='kapt-weekly'), record(source='kapt-weekly', row=3, address='서울특별시 중구 시험로 2')]
        queue, summary = run_build(records)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]['householdValues'], [400])
        self.assertEqual(len(queue[0]['householdEvidence']), 2)
        self.assertEqual(summary['kaptExtraAddressRows'], 1)

    def test_same_address_does_not_merge_distinct_codes_or_assign_site_identity(self):
        queue, summary = run_build([record(), record('A10000002')])
        self.assertEqual(summary['eligibleManagementCodes'], 2)
        self.assertIsNone(summary['unknownUniquePhysicalSiteCount'])
        self.assertIsNone(queue[0]['physicalSiteId'])
        self.assertEqual(queue[0]['sameAddressManagementCodes'], ['A10000002'])

    def test_duplicate_oa_codes_and_private_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate OA'):
            validate_snapshot(snapshot([record(), record(row=3)]))
        row = record(); row['관리사무소_연락처'] = 'fixture'
        with self.assertRaisesRegex(ValueError, 'public fields'):
            validate_snapshot(snapshot([row]))

    def test_missing_component_blocks_completion_even_with_approved_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset, proof, coverage = make_proof(root)
            queue, _ = run_build([record()], coverage, [asset], proof, root)
            self.assertEqual(queue[0]['modelStatus'], 'complete_residential_buildings')
            coverage['complexes'][0]['expectedResidentialBuildingCount'] = 2
            queue, _ = run_build([record()], coverage, [asset], proof, root)
            self.assertEqual(queue[0]['modelStatus'], 'partial')

    def test_changed_glb_or_missing_mcp_demotes_verified_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset, proof, coverage = make_proof(root)
            self.assertEqual(verify_asset(root, asset, proof), [])
            (root / 'public/models/bespoke/test/model.glb').write_bytes(b'changed')
            self.assertIn('published_glb_missing_or_hash_mismatch', verify_asset(root, asset, proof))
            (root / 'docs/model-audit/mcp/test/build.json').unlink()
            self.assertIn('mcp_execution_proof_missing_or_hash_mismatch', verify_asset(root, asset, proof))
            queue, summary = run_build([record()], coverage, [asset], proof, root)
            self.assertNotEqual(queue[0]['modelStatus'], 'complete_residential_buildings')
            self.assertEqual(summary['completedManagementCodes'], 0)

    def test_new_source_conflict_revokes_credit_without_deleting_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset, proof, coverage = make_proof(root)
            coverage['complexes'][0]['buildings'][0]['reviewRequiredReason'] = 'Official floors conflict with the prior authored tower.'
            queue, summary = run_build([record()], coverage, [asset], proof, root)
            self.assertEqual(summary['completedManagementCodes'], 0)
            self.assertEqual(queue[0]['verifiedBespokeBuildingCount'], 0)
            self.assertIn('building_correction_review_required', queue[0]['buildings'][0]['verificationErrors'])
            self.assertTrue((root / 'public/models/bespoke/test/model.glb').is_file())

    def test_reference_fallback_and_unbound_source_review_do_not_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset, proof, _ = make_proof(root)
            old = {**asset, 'id': 'reference-flight-test'}
            self.assertEqual(verify_asset(root, old, proof), ['not_published_bespoke'])
            proof['sites']['test']['review']['reviewedInputs']['model.glb'] = '0' * 64
            self.assertIn('review_source_geometry_hash_mismatch', verify_asset(root, asset, proof))

    def test_source_filename_may_differ_from_published_asset_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset, proof, _ = make_proof(root)
            reviewed = proof['sites']['test']['review']['reviewedInputs']
            reviewed['individual-source-name.glb'] = reviewed.pop('model.glb')
            self.assertEqual(verify_asset(root, asset, proof), [])

    def test_absent_footprint_requires_explicit_numbered_replacement_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset, proof, _ = make_proof(root)
            asset['footprintIds'] = []
            asset['supersedes'] = ['retained-numbered-tower']
            identity = {'sourceUrl': 'https://example.org/numbered-plan', 'retainedAssetId': 'retained-numbered-tower'}
            self.assertEqual(verify_asset(root, asset, proof, identity), [])
            self.assertIn('building_ownership_missing', verify_asset(root, asset, proof))
            identity['retainedAssetId'] = 'different-tower'
            self.assertIn('building_ownership_missing', verify_asset(root, asset, proof, identity))

    def test_sha_bound_mcp_must_contain_successful_execution_and_blend_must_be_reviewed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset, proof, _ = make_proof(root)
            site = proof['sites']['test']
            mcp = root / site['mcpEvidence'][0]['path']
            for calls in [[], {'tool': 'execute_blender_code'}, [{'tool': 'execute_blender_code', 'isError': False, 'content': None}],
                          [{'tool': 'execute_blender_code', 'isError': True, 'content': [{'text': 'Code executed successfully'}]}],
                          [{'tool': 'get_scene_info', 'isError': False, 'content': [{'text': 'Code executed successfully'}]}],
                          [{'tool': 'execute_blender_code', 'isError': False, 'content': [{'text': 'Execution failed'}]}]]:
                mcp.write_text(json.dumps(calls))
                site['mcpEvidence'][0]['sha256'] = digest(mcp)
                self.assertIn('mcp_execution_proof_missing_or_hash_mismatch', verify_asset(root, asset, proof))
            site['review']['reviewedInputs']['source.blend'] = '0' * 64
            self.assertIn('review_editable_blend_hash_mismatch', verify_asset(root, asset, proof))

    def test_one_model_cannot_fill_two_building_slots_or_codes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset, proof, coverage = make_proof(root)
            second = copy.deepcopy(coverage['complexes'][0]); second['code'] = 'A10000002'
            with self.assertRaisesRegex(ValueError, 'multiple management codes'):
                run_build([record(), record('A10000002')], {'complexes': [coverage['complexes'][0], second]}, [asset], proof, root)
            coverage['complexes'][0]['buildings'].append({'label': 'B', 'assetId': asset['id']})
            with self.assertRaisesRegex(ValueError, 'Duplicate building'):
                run_build([record()], coverage, [asset], proof, root)

    def test_representative_inference_is_counted_separately_and_source_changes_revoke_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); asset, proof, coverage = make_proof(root)
            source_record = asset['sourceRecord']
            source_record.update(modelingBasis='representative-photo-inference',
                          inferenceScope='Facade reused, distinct numbered footprint.',
                          inferredFrom=[{'id': 'bespoke-source', 'siteId': 'representative', 'sha256': 'c' * 64}])
            proof['sites']['test']['review']['inferenceApprovedAssets'] = [asset['id']]
            proof['sites']['representative'] = {'assets': [{'id': 'bespoke-source', 'sha256': 'c' * 64}]}
            queue, summary = run_build([record()], coverage, [asset], proof, root)
            self.assertEqual(queue[0]['modelStatus'], 'complete_residential_buildings')
            self.assertEqual(queue[0]['representativeInferredBuildingCount'], 1)
            self.assertEqual(summary['representativeInferredBuildingCount'], 1)
            proof['sites']['representative']['assets'][0]['sha256'] = 'd' * 64
            self.assertIn('representative_source_proof_mismatch', verify_asset(root, asset, proof))
            del proof['sites']['test']['review']['inferenceApprovedAssets']
            self.assertIn('representative_inference_review_missing', verify_asset(root, asset, proof))


class FrozenPublicInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = read(AUDIT / 'apartments-400-sources.json.gz')
        cls.raw = gzip.decompress((AUDIT / 'apartments-400-queue.jsonl.gz').read_bytes())
        cls.queue = [json.loads(line) for line in cls.raw.splitlines()]
        cls.summary = read(AUDIT / 'apartments-400-summary.json')

    def test_latest_source_counts_and_union_no_private_sources_required(self):
        validate_snapshot(self.snapshot)
        self.assertEqual(self.snapshot['sources']['oa-15818']['rows'], 2889)
        self.assertEqual(self.snapshot['sources']['kapt-weekly']['extractDate'], '2026-09-18')
        self.assertEqual(self.summary['eligibleManagementCodes'], 1417)
        self.assertEqual(self.summary['sourceEligibleUniqueCodes'], {'oa-15818': 1363, 'kapt-weekly': 1385})
        self.assertEqual(len(self.queue), len({r['code'] for r in self.queue}))
        self.assertEqual(self.summary['queueSha256Uncompressed'], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(self.summary['sourceSnapshotSha256'], digest(AUDIT / 'apartments-400-sources.json.gz'))

    def test_named_source_gaps_and_partial_models_are_not_reported_complete(self):
        rows = {r['code']: r for r in self.queue}
        self.assertEqual(rows['A10020557']['householdValues'], [0, 3307])
        self.assertEqual(rows['A13527017']['householdValues'], [0, 1297])
        self.assertEqual(rows['A10023043']['householdValues'], [2990])
        self.assertEqual(rows['A10023188']['householdValues'], [1152])
        self.assertEqual(rows['A10020557']['modelStatus'], 'partial')
        self.assertEqual(rows['A10020557']['expectedResidentialBuildingCount'], 29)
        self.assertEqual(rows['A10020557']['verifiedBespokeBuildingCount'], 13)
        self.assertEqual(rows['A10022556']['modelStatus'], 'complete_residential_buildings')
        self.assertEqual(rows['A10022556']['expectedResidentialBuildingCount'], 6)
        self.assertEqual(rows['A10022556']['verifiedBespokeBuildingCount'], 6)
        self.assertEqual(rows['A10023043']['verifiedBespokeBuildingCount'], 0)
        maple213 = next(b for b in rows['A10020557']['buildings'] if b['label'] == '213')
        self.assertEqual(maple213['assetId'], 'bespoke-maple-xi-213-corrected')
        self.assertEqual(maple213['verificationErrors'], [])
        self.assertEqual(rows['A15805114']['modelStatus'], 'coverage_review_needed')
        self.assertEqual(rows['A10022891']['eligibility'], 'eligibility_review')

    def test_rebuild_is_deterministic_and_completed_records_have_real_file_proofs(self):
        queue, summary = build(self.snapshot, read(AUDIT / 'apartments-400-coverage.json'), read(ROOT / 'public/models/bespoke-manifest.json'), read(AUDIT / 'published-bespoke.json'), read(ROOT / 'public/models/manifest.json'), ROOT)
        self.assertEqual(b''.join(canonical(r) for r in queue), self.raw)
        completed = {r['code'] for r in queue if r['modelStatus'] == 'complete_residential_buildings'}
        self.assertTrue({'A10023083', 'A13527017', 'A13585402', 'A13585403', 'A12174601', 'A15088614', 'A15870101', 'A15805111', 'A13822301'} <= completed)
        self.assertEqual(summary['remainingEligibleManagementCodes'], 1417 - len(completed))
        for row in queue:
            if row['modelStatus'] == 'complete_residential_buildings':
                self.assertEqual(row['verifiedBespokeBuildingCount'], row['expectedResidentialBuildingCount'])
                self.assertTrue(all(b['evidenceVerified'] for b in row['buildings']))


if __name__ == '__main__':
    unittest.main()
