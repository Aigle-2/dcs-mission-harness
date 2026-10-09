from pathlib import Path
import json
import tempfile
import unittest
import zipfile
from dcs_harness import workflow
from dcs_harness.core import HarnessError, load_document, validate

ROOT = Path(__file__).resolve().parents[1]

def support_flight(role='awacs'):
    flight = {'group': 'Synthetic support', 'role': role, 'aircraft': 'Synthetic type',
              'cruise_altitude': {'value': 25000, 'unit': 'ft', 'reference': 'MSL'},
              'mission_altitude': {'value': 7000, 'unit': 'm', 'reference': 'MSL'},
              'orbit': {'pattern': 'Race-Track', 'start': {'latitude': 10, 'longitude': 20},
                        'end': {'latitude': 11, 'longitude': 20}},
              'status': 'confirmed', 'source': 'user-confirmation',
              'evidence': 'Synthetic user reviewed type, altitudes and orbit.'}
    if role == 'tanker':
        flight.update(refueling_system='probe-drogue', receivers=['Synthetic receiver'])
    return flight

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
        evidence['checks'].extend(
            {'criterion': c['id'], 'status': 'PASS', 'evidence': 'Synthetic configuration checked.'}
            for c in self.spec['criteria'] if c['id'] not in {'SLOT-COUNT', 'OBJECTIVE-COMPLETION'})
        return path, evidence

    def test_carrier_choices_cannot_be_missing_or_inapplicable(self):
        self.spec['configuration']['carrier_present'] = True
        for key in ('CARRIER-GROUP', 'CARRIER-PLACEMENT'):
            self.spec['criteria'].append({'id': key, 'level': 'local', 'statement': 'Reviewed naval configuration matches saved artifact.'})
        self.assertIn('APPLICABLE_DESIGN_CHOICE_REQUIRED', {e['code'] for e in validate('functional-spec', self.spec)})
        for d in self.spec['design_decisions']:
            if d['topic'] in {'battlegroup', 'carrier-placement'}:
                d.update(status='confirmed', source='user-confirmation', evidence='Synthetic user reviewed the naval choices.')
        self.assertEqual(validate('functional-spec', self.spec), [])
        self.spec['design_decisions'].pop(3)
        self.assertTrue(validate('functional-spec', self.spec))

    def test_proposed_loadout_blocks_spec_registration(self):
        workflow.start(self.root, self.id, self.brief)
        self.spec['design_decisions'][-1].update(status='proposed', source='agent-proposal')
        self.save_spec()
        with self.assertRaisesRegex(HarnessError, 'DESIGN_REVIEW_REQUIRED'):
            workflow.specification(self.root, self.id, self.specfile)

    def test_loadouts_cannot_be_marked_inapplicable(self):
        self.spec['design_decisions'][-1]['status'] = 'not-applicable'
        self.assertIn('APPLICABLE_DESIGN_CHOICE_REQUIRED', {e['code'] for e in validate('functional-spec', self.spec)})

    def test_default_veteran_and_explicit_user_override(self):
        self.spec['configuration']['ai_skill'] = 'Average'
        self.assertIn('VETERAN_DEFAULT_REQUIRED', {e['code'] for e in validate('functional-spec', self.spec)})
        self.spec['configuration']['ai_skill_source'] = 'user-request'
        self.assertEqual(validate('functional-spec', self.spec), [])

    def test_awacs_requires_support_review_and_local_orbit_check(self):
        self.spec['configuration']['awacs_present'] = True
        self.spec['support_flights'] = [support_flight()]
        self.spec['criteria'].append({'id': 'SUPPORT-FLIGHT-PROFILES', 'level': 'local', 'statement': 'Support flight profiles match the saved mission.'})
        self.assertEqual({e['code'] for e in validate('functional-spec', self.spec)},
                         {'CONFIGURATION_CRITERIA_REQUIRED', 'APPLICABLE_DESIGN_CHOICE_REQUIRED'})
        self.spec['design_decisions'][0].update(status='confirmed', source='user-request')
        self.spec['criteria'].append({'id': 'AWACS-ORBIT', 'level': 'runtime', 'statement': 'AWACS station orbit matches reviewed configuration.'})
        self.assertIn('CONFIGURATION_CRITERIA_REQUIRED', {e['code'] for e in validate('functional-spec', self.spec)})
        self.spec['criteria'][-1]['level'] = 'local'
        self.assertEqual(validate('functional-spec', self.spec), [])

    def test_support_flight_requires_both_altitudes_type_and_orbit(self):
        self.spec['support_flights'] = [support_flight(role='tanker')]
        self.spec['design_decisions'][0].update(status='confirmed', source='user-request')
        self.spec['criteria'].append({'id': 'SUPPORT-FLIGHT-PROFILES', 'level': 'local', 'statement': 'Support flight profiles match the saved mission.'})
        self.assertEqual(validate('functional-spec', self.spec), [])
        for key in ('aircraft', 'cruise_altitude', 'mission_altitude', 'orbit', 'refueling_system', 'receivers'):
            with self.subTest(key=key):
                saved = self.spec['support_flights'][0].pop(key)
                self.assertTrue(validate('functional-spec', self.spec))
                self.spec['support_flights'][0][key] = saved

    def test_support_proposal_blocks_registration(self):
        workflow.start(self.root, self.id, self.brief)
        self.spec['support_flights'] = [support_flight(role='tanker')]
        self.spec['support_flights'][0].update(status='proposed', source='agent-proposal')
        self.spec['design_decisions'][0].update(status='confirmed', source='user-request')
        self.spec['criteria'].append({'id': 'SUPPORT-FLIGHT-PROFILES', 'level': 'local', 'statement': 'Support flight profiles match the saved mission.'})
        self.save_spec()
        with self.assertRaisesRegex(HarnessError, 'SUPPORT_FLIGHT_REVIEW_REQUIRED'):
            workflow.specification(self.root, self.id, self.specfile)

    def test_support_identity_review_and_geometry(self):
        self.spec['support_flights'] = [support_flight(role='tanker')]
        self.spec['design_decisions'][0].update(status='confirmed', source='user-request')
        self.spec['criteria'].append({'id': 'SUPPORT-FLIGHT-PROFILES', 'level': 'local', 'statement': 'Support flight profiles match the saved mission.'})
        flight = self.spec['support_flights'][0]
        flight['orbit']['end'] = dict(flight['orbit']['start'])
        flight['source'] = 'agent-proposal'
        self.spec['support_flights'].append(flight)
        self.assertEqual({e['code'] for e in validate('functional-spec', self.spec)},
                         {'DEGENERATE_SUPPORT_ORBIT', 'USER_CONFIRMATION_REQUIRED', 'DUPLICATE_SUPPORT_GROUP'})

    def test_support_altitude_units_and_coordinates_are_explicit(self):
        self.spec['support_flights'] = [support_flight(role='tanker')]
        for value in ({'value': 20000}, {'value': -1, 'unit': 'ft', 'reference': 'MSL'},
                      {'value': 20000, 'unit': 'feet', 'reference': 'MSL'}):
            self.spec['support_flights'][0]['cruise_altitude'] = value
            self.assertTrue(validate('functional-spec', self.spec))
        self.spec['support_flights'][0]['cruise_altitude'] = {'value': 6000, 'unit': 'm', 'reference': 'MSL'}
        self.spec['support_flights'][0]['orbit']['start']['latitude'] = 91
        self.assertTrue(validate('functional-spec', self.spec))

    def test_awacs_inventory_must_match_presence(self):
        self.spec['configuration']['awacs_present'] = True
        self.assertIn('AWACS_PRESENCE_MISMATCH', {e['code'] for e in validate('functional-spec', self.spec)})

    def test_circle_profile_and_required_local_check(self):
        self.spec['support_flights'] = [support_flight(role='tanker')]
        self.spec['design_decisions'][0].update(status='confirmed', source='user-request')
        self.spec['support_flights'][0]['orbit'] = {
            'pattern': 'Circle', 'center': {'latitude': 10, 'longitude': 20}, 'radius_nm': 5}
        self.assertIn('CONFIGURATION_CRITERIA_REQUIRED', {e['code'] for e in validate('functional-spec', self.spec)})
        self.spec['criteria'].append({'id': 'SUPPORT-FLIGHT-PROFILES', 'level': 'local', 'statement': 'Support flight profiles match the saved mission.'})
        self.assertEqual(validate('functional-spec', self.spec), [])
        self.spec['support_flights'][0]['orbit']['radius_nm'] = 0
        self.assertTrue(validate('functional-spec', self.spec))

    def test_unit_loadout_skill_checks_cannot_be_omitted(self):
        for key in ('UNIT-TYPES', 'AIRCRAFT-LOADOUTS', 'AI-SKILL'):
            with self.subTest(key=key):
                item = next(c for c in self.spec['criteria'] if c['id'] == key)
                self.spec['criteria'].remove(item)
                self.assertIn('CONFIGURATION_CRITERIA_REQUIRED', {e['code'] for e in validate('functional-spec', self.spec)})
                self.spec['criteria'].append(item)

    def test_historical_spec_requires_new_review(self):
        self.spec['schema_version'] = '1.1'
        self.assertTrue(validate('functional-spec', self.spec))

    def verify(self, evidence):
        self.evidencefile.write_text(json.dumps(evidence))
        return workflow.verify(self.root, self.id, self.evidencefile)

    def test_start_routes_skill_and_preserves_brief(self):
        report = workflow.start(self.root, self.id, self.brief)
        self.assertEqual(report['next_skill'], 'mission-functional-spec')
        self.assertEqual((workflow.run_path(self.root, self.id) / 'brief.md').read_text(), self.brief.read_text())
        with self.assertRaises(HarnessError):
            workflow.start(self.root, self.id, self.brief)

    def test_proposed_design_and_unanswered_comm_plan_block_implementation(self):
        workflow.start(self.root, self.id, self.brief)
        self.spec['design_decisions'][2].update(status='proposed', source='agent-proposal')
        self.save_spec()
        with self.assertRaisesRegex(HarnessError, 'DESIGN_REVIEW_REQUIRED'):
            workflow.specification(self.root, self.id, self.specfile)
        self.spec['design_decisions'][2].update(status='confirmed', source='user-confirmation')
        self.spec['communications'].update(decision='pending', source='unanswered')
        self.save_spec()
        with self.assertRaisesRegex(HarnessError, 'COMM_PLAN_DECISION_REQUIRED'):
            workflow.specification(self.root, self.id, self.specfile)

    def test_agent_proposal_cannot_be_confirmed_without_user_source(self):
        self.spec['design_decisions'][2]['source'] = 'agent-proposal'
        self.assertTrue(validate('functional-spec', self.spec))

    def test_enabled_plan_needs_application_criteria_and_archive_checks(self):
        from test_communications import fixture
        from unittest.mock import patch
        _, plan = fixture()
        self.spec['communications'].update(decision='enabled', plan=plan)
        self.assertTrue(validate('functional-spec', self.spec))
        for key in ('COMM-PRESETS', 'COMM-FREQUENCIES'):
            self.spec['criteria'].append({'id': key, 'level': 'local', 'statement': 'Communication configuration matches approved plan.'})
        self.assertEqual(validate('functional-spec', self.spec), [])
        self.save_spec()
        workflow.start(self.root, self.id, self.brief)
        workflow.specification(self.root, self.id, self.specfile)
        with patch('dcs_harness.communications.check_archive', side_effect=HarnessError('COMM_PLAN_NOT_APPLIED')) as checked:
            with self.assertRaisesRegex(HarnessError, 'COMM_PLAN_NOT_APPLIED'):
                workflow.implementation(self.root, self.id, self.miz)
            checked.assert_called_once()

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
