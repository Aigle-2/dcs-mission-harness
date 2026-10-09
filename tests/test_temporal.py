from pathlib import Path
import json
import tempfile
import unittest

from dcs_harness import workflow
from dcs_harness.core import HarnessError, load_document, validate
from dcs_harness.design_review import decision_review

ROOT = Path(__file__).resolve().parents[1]


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.spec = load_document(ROOT / 'examples/functional-spec.yaml')

    def test_date_and_policy_are_mandatory(self):
        for field in ('date', 'start_time', 'restrict_by_year'):
            with self.subTest(field=field):
                value = self.spec['temporal'].pop(field)
                self.assertTrue(validate('functional-spec', self.spec))
                self.spec['temporal'][field] = value
        del self.spec['temporal']
        self.assertTrue(validate('functional-spec', self.spec))

    def test_real_calendar_and_leap_years(self):
        for value, valid in [('2000-02-29', True), ('1900-02-29', False),
                             ('2024-02-29', True), ('2023-02-29', False),
                             ('2024-04-31', False), ('0000-01-01', False)]:
            with self.subTest(date=value):
                self.spec['temporal']['date'] = value
                self.assertEqual(not validate('functional-spec', self.spec), valid)

    def test_policy_requires_historical_evidence_only_when_enabled(self):
        self.assertEqual(validate('functional-spec', self.spec), [])
        self.spec['temporal']['restrict_by_year'] = True
        self.assertIn('CONFIGURATION_CRITERIA_REQUIRED',
                      {e['code'] for e in validate('functional-spec', self.spec)})
        criterion = {'id': 'ERA-AVAILABILITY', 'level': 'local',
                     'statement': 'Aircraft variants and weapons match reviewed historical availability and exceptions.'}
        self.spec['criteria'].append(criterion)
        self.assertEqual(validate('functional-spec', self.spec), [])
        criterion['level'] = 'runtime'
        self.assertTrue(validate('functional-spec', self.spec))

    def test_date_criterion_is_always_local(self):
        criterion = next(c for c in self.spec['criteria'] if c['id'] == 'MISSION-DATE-TIME')
        criterion['level'] = 'client'
        self.assertIn('CONFIGURATION_CRITERIA_REQUIRED',
                      {e['code'] for e in validate('functional-spec', self.spec)})

    def test_date_and_policy_are_visible_in_review_with_provenance(self):
        self.spec['temporal'].update(status='proposed', source='agent-proposal')
        document, pending = decision_review(self.spec)
        self.assertIn('[Proposed] date et époque : date 2016-06-15;', document)
        self.assertIn('début 10:30:00 (heure locale de la carte)', document)
        self.assertIn('non limitée par l’année', document)
        self.assertEqual(pending, 1)
        self.spec['temporal'].update(status='confirmed', source='user-confirmation', restrict_by_year=True)
        self.spec['criteria'].append({'id': 'ERA-AVAILABILITY', 'level': 'local',
                                      'statement': 'Synthetic historical compatibility table checked.'})
        document, pending = decision_review(self.spec)
        self.assertIn('[Decided] date et époque', document)
        self.assertNotIn('non limitée par l’année', document)
        self.assertEqual(pending, 0)

    def test_agent_cannot_supply_own_confirmation(self):
        self.spec['temporal']['source'] = 'agent-proposal'
        self.assertIn('USER_CONFIRMATION_REQUIRED',
                      {e['code'] for e in validate('functional-spec', self.spec)})

    def test_unreviewed_temporal_choice_blocks_registration(self):
        self.spec['temporal'].update(status='proposed', source='agent-proposal')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            brief = root / 'brief.md'
            brief.write_text('Create a synthetic mission with a date proposed by the agent.')
            workflow.start(root, 'synthetic-training', brief)
            specfile = root / 'spec.json'
            specfile.write_text(json.dumps(self.spec))
            with self.assertRaisesRegex(HarnessError, 'TEMPORAL_REVIEW_REQUIRED'):
                workflow.specification(root, 'synthetic-training', specfile)
            self.assertFalse((root / 'runs/synthetic-training/spec.accepted.json').exists())

    def test_start_time_requires_a_real_local_clock_value(self):
        for value, valid in [('00:00:00', True), ('23:59:59', True),
                             ('24:00:00', False), ('12:60:00', False),
                             ('12:00:60', False), ('12:00', False), ('12:00:00Z', False)]:
            with self.subTest(time=value):
                self.spec['temporal']['start_time'] = value
                self.assertEqual(not validate('functional-spec', self.spec), valid)
