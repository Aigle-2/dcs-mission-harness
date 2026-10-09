from pathlib import Path
import json
import tempfile
import unittest
import zipfile
from dcs_harness import workflow
from dcs_harness.core import HarnessError, load_document, validate

ROOT = Path(__file__).resolve().parents[1]

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.id = 'synthetic-training'
        self.brief = self.root / 'input.md'
        self.brief.write_text('Create a synthetic cooperative navigation exercise.')
        self.spec = load_document(ROOT / 'examples/functional-spec.yaml')
        self.specfile = self.root / 'spec.json'
        self.save_spec()
        self.miz = self.root / 'input.miz'
        with zipfile.ZipFile(self.miz, 'w') as z:
            z.writestr('mission', 'mission = { ["theatre"] = "Caucasus" }')
        self.evidencefile = self.root / 'evidence.json'

    def save_spec(self):
        self.specfile.write_text(json.dumps(self.spec))

    def prepared(self):
        workflow.start(self.root, self.id, self.brief)
        workflow.specification(self.root, self.id, self.specfile)
        self.assertEqual(workflow.implementation(self.root, self.id, self.miz)['status'], 'PASS')
        path = workflow.run_path(self.root, self.id)
        state = load_document(path / 'state.json')
        evidence = {'schema_version': '1.0', 'classification': 'private',
                    'spec_sha256': state['spec_sha256'], 'artifact_sha256': state['artifact_sha256'],
                    'checks': [{'criterion': 'SLOT-COUNT', 'status': 'PASS', 'evidence': 'Synthetic count checked.'},
                               {'criterion': 'OBJECTIVE-COMPLETION', 'status': 'SKIPPED', 'evidence': 'DCS clients are unavailable.'}]}
        return path, evidence

    def verify(self, evidence):
        self.evidencefile.write_text(json.dumps(evidence))
        return workflow.verify(self.root, self.id, self.evidencefile)

    def test_start_routes_skill_and_preserves_brief(self):
        report = workflow.start(self.root, self.id, self.brief)
        self.assertEqual(report['next_skill'], 'mission-functional-spec')
        self.assertEqual((workflow.run_path(self.root, self.id) / 'brief.md').read_text(), self.brief.read_text())
        with self.assertRaises(HarnessError):
            workflow.start(self.root, self.id, self.brief)

    def test_order_open_questions_and_changed_brief_block(self):
        workflow.start(self.root, self.id, self.brief)
        with self.assertRaises(HarnessError):
            workflow.implementation(self.root, self.id, self.miz)
        self.spec['open_questions'] = ['Which departure?']
        self.save_spec()
        with self.assertRaisesRegex(HarnessError, 'SPEC_HAS_OPEN_QUESTIONS'):
            workflow.specification(self.root, self.id, self.specfile)
        self.spec['open_questions'] = []
        self.save_spec()
        (workflow.run_path(self.root, self.id) / 'brief.md').write_text('Changed request.')
        with self.assertRaisesRegex(HarnessError, 'BRIEF_CHANGED'):
            workflow.specification(self.root, self.id, self.specfile)

    def test_local_pass_is_not_runtime_validation_and_retries_are_kept(self):
        path, evidence = self.prepared()
        report = self.verify(evidence)
        self.assertEqual(report['phase'], 'LOCAL_VERIFIED')
        self.assertEqual(report['mission_validation'], 'INCONCLUSIVE')
        self.assertEqual(report['runtime'], 'NOT_TESTED')
        self.verify(evidence)
        self.assertEqual(len(list((path / 'verifications').glob('*.json'))), 2)
        self.assertEqual(load_document(path / 'spec.accepted.json')['classification'], 'private')

    def test_runtime_pass_is_rejected(self):
        _, evidence = self.prepared()
        evidence['checks'][1]['status'] = 'PASS'
        with self.assertRaisesRegex(HarnessError, 'RUNTIME_EVIDENCE_ADAPTER_NOT_AVAILABLE'):
            self.verify(evidence)

    def test_changed_spec_and_artifact_are_rejected(self):
        path, evidence = self.prepared()
        original = (path / 'spec.accepted.json').read_bytes()
        (path / 'spec.accepted.json').write_text('{}')
        with self.assertRaisesRegex(HarnessError, 'ACCEPTED_SPEC_CHANGED'):
            self.verify(evidence)
        (path / 'spec.accepted.json').write_bytes(original)
        (path / 'mission.miz').write_bytes(b'changed')
        with self.assertRaisesRegex(HarnessError, 'REGISTERED_ARTIFACT_CHANGED'):
            self.verify(evidence)

    def test_wrong_hash_missing_duplicate_and_unknown_criteria_rejected(self):
        _, evidence = self.prepared()
        original = json.loads(json.dumps(evidence))
        evidence['artifact_sha256'] = '0' * 64
        with self.assertRaisesRegex(HarnessError, 'EVIDENCE_HASH_MISMATCH'):
            self.verify(evidence)
        for checks in [original['checks'][:1], original['checks'] * 2,
                       original['checks'] + [{'criterion': 'UNKNOWN', 'status': 'PASS', 'evidence': 'Unknown check.'}]]:
            evidence = dict(original, checks=checks)
            with self.assertRaisesRegex(HarnessError, 'EVIDENCE_CRITERIA_MISMATCH'):
                self.verify(evidence)

    def test_fail_and_blocked_remain_pending(self):
        _, evidence = self.prepared()
        for status, expected in [('FAIL', 'FAIL'), ('BLOCKED', 'BLOCKED')]:
            evidence['checks'][0]['status'] = status
            report = self.verify(evidence)
            self.assertEqual(report['status'], expected)
            self.assertEqual(report['phase'], 'VERIFICATION_PENDING')

    def test_spec_nested_schema_and_duplicate_ids(self):
        self.assertEqual(validate('functional-spec', self.spec), [])
        self.spec['criteria'].append(self.spec['criteria'][0])
        self.assertTrue(validate('functional-spec', self.spec))
        self.spec['mission']['slots'][0]['count'] = 0
        self.assertTrue(validate('functional-spec', self.spec))

    def test_escape_and_symlink_are_rejected(self):
        with self.assertRaises(HarnessError):
            workflow.run_path(self.root, '../outside')
        target = self.root / 'target'
        target.mkdir()
        (self.root / 'runs').mkdir()
        try:
            (self.root / 'runs' / self.id).symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink privileges unavailable')
        with self.assertRaisesRegex(HarnessError, 'RUN_PATH_ESCAPE'):
            workflow.run_path(self.root, self.id)
