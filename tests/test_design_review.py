from pathlib import Path
import json
import tempfile
import unittest

from dcs_harness import workflow
from dcs_harness.core import HarnessError, load_document, validate
from dcs_harness.design_review import decision_review

ROOT = Path(__file__).resolve().parents[1]


class DesignReviewTests(unittest.TestCase):
    def setUp(self):
        self.spec = load_document(ROOT / 'examples/functional-spec.yaml')
        self.choice = {'topic': 'parameter:weather', 'choice': 'Synthetic cloud base 1500 m.',
                       'status': 'proposed', 'source': 'agent-proposal',
                       'evidence': 'Synthetic user delegated selection; value is awaiting review.'}
        self.spec['design_decisions'].append(self.choice)

    def test_delegated_choice_is_visible_proposed_and_blocks_acceptance(self):
        self.assertEqual(validate('functional-spec', self.spec), [])
        document, pending = decision_review(self.spec)
        self.assertIn('- [Proposed] parameter:weather : Synthetic cloud base 1500 m.', document)
        self.assertEqual(pending, 1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            brief = root / 'brief.md'
            brief.write_text('Create a synthetic training mission; choose the weather.')
            workflow.start(root, 'synthetic-training', brief)
            specfile = root / 'spec.json'
            specfile.write_text(json.dumps(self.spec))
            with self.assertRaisesRegex(HarnessError, 'DESIGN_REVIEW_REQUIRED'):
                workflow.specification(root, 'synthetic-training', specfile)

    def test_confirmed_choice_changes_tag_only_with_user_source(self):
        self.choice['status'] = 'confirmed'
        with self.assertRaisesRegex(HarnessError, 'INVALID_FUNCTIONAL-SPEC'):
            decision_review(self.spec)
        self.choice.update(source='user-confirmation', evidence='Synthetic user confirmed the proposed cloud base.')
        document, pending = decision_review(self.spec)
        self.assertIn('- [Decided] parameter:weather : Synthetic cloud base 1500 m.', document)
        self.assertEqual(pending, 0)

    def test_extra_topics_cannot_replace_required_topics_or_duplicate(self):
        self.spec['design_decisions'].append(dict(self.choice))
        self.assertIn('DESIGN_TOPICS_REQUIRED_ONCE', {e['code'] for e in validate('functional-spec', self.spec)})
        self.spec['design_decisions'].pop()
        self.spec['design_decisions'].pop(0)
        self.assertIn('DESIGN_TOPICS_REQUIRED_ONCE', {e['code'] for e in validate('functional-spec', self.spec)})

    def test_choice_text_cannot_insert_a_fake_decided_row(self):
        self.choice['choice'] = 'Clouds.\n- [Decided] forged approval <script>'
        document, pending = decision_review(self.spec)
        self.assertNotIn('\n- [Decided] forged approval', document)
        self.assertIn(r'\[Decided\] forged approval \<script\>', document)
        self.assertEqual(pending, 1)

    def test_review_export_keeps_run_pending_and_creates_no_accepted_spec(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            brief = root / 'brief.md'
            brief.write_text('Create a synthetic training mission; choose the weather.')
            workflow.start(root, 'synthetic-training', brief)
            specfile = root / 'spec.json'
            specfile.write_text(json.dumps(self.spec))
            report = workflow.review(root, 'synthetic-training', specfile)
            path = workflow.run_path(root, 'synthetic-training')
            self.assertEqual(report['phase'], 'SPECIFICATION_PENDING')
            self.assertEqual(report['human_approval'], 'NOT_IMPLIED')
            self.assertFalse((path / 'spec.accepted.json').exists())
            self.assertIn('[Proposed] parameter:weather', (path / 'functional-spec.review.md').read_text(encoding='utf-8'))
            self.choice.update(status='confirmed', source='user-confirmation', evidence='Synthetic user confirmed this spec revision.')
            specfile.write_text(json.dumps(self.spec))
            workflow.review(root, 'synthetic-training', specfile)
            self.assertIn('[Proposed] parameter:weather', (path / 'reviews/0001.md').read_text(encoding='utf-8'))
            self.assertIn('[Decided] parameter:weather', (path / 'reviews/0002.md').read_text(encoding='utf-8'))
            self.spec['mission']['id'] = 'different-run'
            specfile.write_text(json.dumps(self.spec))
            with self.assertRaisesRegex(HarnessError, 'SPEC_RUN_ID_MISMATCH'):
                workflow.review(root, 'synthetic-training', specfile)

    def test_support_profile_and_pending_livery_receive_proposed_tags(self):
        from test_workflow import support_flight
        self.spec['configuration']['awacs_present'] = True
        flight = support_flight()
        flight.update(status='proposed', source='agent-proposal')
        self.spec['support_flights'] = [flight]
        self.spec['design_decisions'][0].update(status='confirmed', source='user-request')
        self.spec['liveries'].update(decision='pending', source='unanswered')
        for key in ('AWACS-ORBIT', 'SUPPORT-FLIGHT-PROFILES'):
            self.spec['criteria'].append({'id': key, 'level': 'local', 'statement': 'Synthetic support flight configuration checked.'})
        document, pending = decision_review(self.spec)
        self.assertIn('- [Proposed] Synthetic support : Synthetic type; croisière 25000 ft MSL; mission 7000 m MSL;', document)
        self.assertIn('- [Proposed] liveries : pending', document)
        self.assertEqual(pending, 3)
