import json
from pathlib import Path
import tempfile
import unittest

from dcs_harness.core import HarnessError, load_document, validate
from dcs_harness.design_review import decision_review
from dcs_harness import workflow
from test_communications import fixture

ROOT = Path(__file__).resolve().parents[1]


def navigation():
    return {'schema_version': '1.0', 'status': 'confirmed', 'source': 'user-confirmation',
            'evidence': 'Synthetic user confirmed navigation and identification settings.',
            'tacan': [{'station': 'Synthetic carrier', 'platform': 'ship', 'channel': 71, 'band': 'X', 'ident': 'SYN'},
                      {'station': 'Synthetic tanker', 'platform': 'aircraft', 'channel': 43, 'band': 'Y', 'ident': 'TNK'}],
            'yardstick': [{'group': 'SYNTHETIC', 'leader': 'Synthetic leader', 'wingmen': ['Synthetic wingman'],
                          'leader_channel': 3, 'wingman_channel': 66, 'band': 'Y'}],
            'callsigns': [{'group': 'SYNTHETIC', 'aircraft': 'F-14BU', 'mode': 'dcs-default'}],
            'naval_systems': [{'unit': 'Synthetic carrier', 'icls': {'decision': 'enabled', 'channel': 11},
                              'datalink': {'decision': 'enabled', 'system': 'Synthetic frequency-based link', 'frequency_mhz': 305}}]}


class NavigationTests(unittest.TestCase):
    def test_valid_allocations_and_reverse_yardstick_pair(self):
        nav = navigation()
        self.assertEqual(validate('navigation', nav), [])
        nav['yardstick'][0].update(leader_channel=66, wingman_channel=3)
        self.assertEqual(validate('navigation', nav), [])

    def test_band_convention_and_exact_offset(self):
        for change, code in [('band', 'TACAN_BAND_CONVENTION'), ('offset', 'YARDSTICK_CHANNEL_OFFSET')]:
            nav = navigation()
            if change == 'band': nav['tacan'][0]['band'] = 'Y'
            else: nav['yardstick'][0]['wingman_channel'] = 65
            self.assertIn(code, {e['code'] for e in validate('navigation', nav)})

    def test_channel_bounds_and_icls_datalink_completeness(self):
        for change in ('tacan', 'yardstick', 'icls', 'datalink'):
            nav = navigation()
            if change == 'tacan': nav['tacan'][0]['channel'] = 127
            if change == 'yardstick': nav['yardstick'][0]['wingman_channel'] = 0
            if change == 'icls': nav['naval_systems'][0]['icls']['channel'] = 21
            if change == 'datalink': del nav['naval_systems'][0]['datalink']['frequency_mhz']
            with self.subTest(change=change):
                self.assertTrue(validate('navigation', nav))

    def test_collision_and_flight_identity(self):
        nav = navigation()
        nav['tacan'][1]['channel'] = 66
        nav['yardstick'][0]['wingmen'] = ['Synthetic leader']
        codes = {e['code'] for e in validate('navigation', nav)}
        self.assertIn('NAVIGATION_CHANNEL_COLLISION', codes)
        self.assertIn('YARDSTICK_FLIGHT_MEMBERS', codes)
        nav = navigation()
        nav['tacan'].append(dict(nav['tacan'][0]))
        self.assertIn('DUPLICATE_NAVIGATION_ALLOCATION', {e['code'] for e in validate('navigation', nav)})

    def test_callsign_defaults_and_explicit_values(self):
        nav = navigation()
        nav['callsigns'][0]['name'] = 'Invented default'
        self.assertTrue(validate('navigation', nav))
        nav['callsigns'][0].update(mode='custom', flight_number=1)
        self.assertEqual(validate('navigation', nav), [])
        del nav['callsigns'][0]['flight_number']
        self.assertTrue(validate('navigation', nav))

    def test_confirmed_plan_cannot_hide_pending_ship_settings(self):
        nav = navigation()
        nav['naval_systems'][0]['icls'] = {'decision': 'pending'}
        self.assertIn('NAVAL_SYSTEM_REVIEW_REQUIRED', {e['code'] for e in validate('navigation', nav)})
        nav['source'] = 'agent-proposal'
        self.assertIn('USER_CONFIRMATION_REQUIRED', {e['code'] for e in validate('navigation', nav)})

    def test_comm_plan_requires_identical_navigation_and_flight_coverage(self):
        spec = load_document(ROOT / 'examples/functional-spec.yaml')
        _, plan = fixture()
        spec['communications'].update(decision='enabled', plan=plan)
        self.assertIn('COMM_NAVIGATION_MISMATCH', {e['code'] for e in validate('functional-spec', spec)})
        plan['navigation']['callsigns'][0]['group'] = 'Missing flight'
        self.assertIn('COMM_CALLSIGN_COVERAGE_REQUIRED', {e['code'] for e in validate('comm-plan', plan)})

    def test_proposal_is_tagged_and_blocks_registration(self):
        spec = load_document(ROOT / 'examples/functional-spec.yaml')
        spec['navigation'] = navigation()
        spec['navigation'].update(status='proposed', source='agent-proposal')
        spec['criteria'].append({'id': 'NAVIGATION-RECEPTION', 'level': 'client', 'statement': 'Synthetic navigation reception checked in DCS.'})
        document, pending = decision_review(spec)
        self.assertIn('- [Proposed] yardstick', document)
        self.assertIn('leader Synthetic leader 3Y', document)
        self.assertIn('ailiers Synthetic wingman 66Y', document)
        self.assertIn('71X, ident SYN', document)
        self.assertIn('43Y, ident TNK', document)
        self.assertIn('ICLS 11', document)
        self.assertIn('305 MHz', document)
        self.assertGreater(pending, 0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            brief = root / 'brief.md'
            brief.write_text('Create a synthetic training mission with navigation.')
            workflow.start(root, 'synthetic-training', brief)
            specfile = root / 'spec.json'
            specfile.write_text(json.dumps(spec))
            with self.assertRaisesRegex(HarnessError, 'NAVIGATION_REVIEW_REQUIRED'):
                workflow.specification(root, 'synthetic-training', specfile)
