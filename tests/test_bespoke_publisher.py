import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).resolve().parents[1] / 'scripts/publish_bespoke_models.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class McpEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / 'docs/model-audit/mcp/site/build.json'
        self.path.parent.mkdir(parents=True)

    def evidence(self, calls):
        self.path.write_text(json.dumps(calls))
        return [{'path': str(self.path.relative_to(self.root)), 'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest()}]

    def test_successful_execution_is_accepted(self):
        records = self.evidence([{'tool': 'execute_blender_code', 'isError': False, 'content': [{'text': 'Code executed successfully: exported model.glb'}]}])
        publisher.validate_mcp_evidence(records, self.root)

    def test_empty_evidence_and_failed_or_unrelated_calls_are_rejected(self):
        for records in [None, []]:
            with self.subTest(records=records), self.assertRaises(ValueError):
                publisher.validate_mcp_evidence(records, self.root)
        for tool, error in [('execute_blender_code', True), ('get_scene_info', False)]:
            records = self.evidence([{'tool': tool, 'isError': error, 'content': [{'text': 'Code executed successfully'}]}])
            with self.subTest(tool=tool, error=error), self.assertRaisesRegex(ValueError, 'no successful'):
                publisher.validate_mcp_evidence(records, self.root)

    def test_modified_proof_is_rejected_even_when_the_call_succeeded(self):
        records = self.evidence([{'tool': 'execute_blender_code', 'isError': False, 'content': [{'text': 'Code executed successfully'}]}])
        self.path.write_text(self.path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            publisher.validate_mcp_evidence(records, self.root)

    def test_evidence_cannot_escape_the_committed_audit_directory(self):
        records = self.evidence([])
        outside = self.root / 'outside.json'
        self.path.rename(outside)
        records[0]['path'] = 'docs/model-audit/mcp/../../../outside.json'
        with self.assertRaisesRegex(ValueError, 'local audit'):
            publisher.validate_mcp_evidence(records, self.root)


if __name__ == '__main__':
    unittest.main()
