import copy
import unittest
from dcs_harness.communications import apply_plan, check_plan
from dcs_harness.core import HarnessError, validate

def fixture():
    units = {1: {'type': 'F-14BU', 'skill': 'Client', 'unrelated': 'preserve',
                 'Radio': {r: {'channels': {1: 225, 2: 225, 3: 225}} for r in (1, 2)}}}
    table = {'coalition': {'blue': {'country': {1: {
        'plane': {'group': {1: {'name': 'SYNTHETIC', 'units': units, 'frequency': 225,
          'route': {'task': {'id': 'SetFrequency', 'params': {'frequency': 225000000, 'modulation': 0}}}}}},
        'ship': {'group': {1: {'name': 'SYNTHETIC-SHIP', 'units': {1: {'type': 'synthetic', 'frequency': 225000000}}}}}
    }}}}}
    plan = {'schema_version': '1.0', 'phases': ['launch', 'strike'],
            'nets': [{'id': 'intra', 'frequency_mhz': 307, 'modulation': 'AM'},
                     {'id': 'shared', 'frequency_mhz': 251, 'modulation': 'AM'},
                     {'id': 'ship', 'frequency_mhz': 264, 'modulation': 'AM'}],
            'assignments': [{'group': 'SYNTHETIC', 'net': 'intra'}, {'group': 'SYNTHETIC-SHIP', 'net': 'ship'}],
            'radio_inventory': [{'group': 'SYNTHETIC', 'aircraft': 'F-14BU', 'radio': r,
               'label': f'Synthetic radio {r}', 'compatible_bands': ['225-399.975 MHz AM'],
               'source': 'Synthetic fixture referencing the verified adapter subset.', 'notes': 'Other bands excluded from this synthetic test.'} for r in (1, 2)],
            'presets': [{'group': 'SYNTHETIC', 'radio': r, 'channel': ch, 'net': net}
                        for r in (1, 2) for ch, net in [(1, 'intra'), (2, 'shared'), (3, 'ship')]],
            'radio_usage': [{'group': 'SYNTHETIC', 'phase': phase, 'radio': r,
                            'net': 'intra' if r == 1 else ('ship' if phase == 'launch' else 'shared')}
                           for phase in ['launch', 'strike'] for r in (1, 2)]}
    return table, plan

class CommunicationTests(unittest.TestCase):
    def test_apply_changes_presets_group_tasks_and_ship_without_mutating_source(self):
        table, plan = fixture()
        original = copy.deepcopy(table)
        output = apply_plan(table, plan)
        country = output['coalition']['blue']['country'][1]
        group = country['plane']['group'][1]
        self.assertEqual(group['frequency'], 307)
        self.assertEqual(group['route']['task']['params']['frequency'], 307000000)
        self.assertEqual(group['units'][1]['Radio'][2]['channels'][2], 251)
        self.assertEqual(country['ship']['group'][1]['units'][1]['frequency'], 264000000)
        self.assertEqual(group['units'][1]['unrelated'], 'preserve')
        self.assertEqual(table, original)
        check_plan(output, plan)
        group['units'][1]['Radio'][2]['channels'][2] = 252
        with self.assertRaisesRegex(HarnessError, 'COMM_PLAN_NOT_APPLIED'):
            check_plan(output, plan)

    def test_unknown_aircraft_radio_channel_or_incompatible_frequency_block(self):
        for change in ('aircraft', 'radio', 'channel', 'frequency', 'step', 'mode'):
            table, plan = fixture()
            unit = table['coalition']['blue']['country'][1]['plane']['group'][1]['units'][1]
            if change == 'aircraft': unit['type'] = 'Unknown'
            if change == 'radio': del unit['Radio'][2]
            if change == 'channel': del unit['Radio'][1]['channels'][2]
            if change == 'frequency': plan['nets'][1]['frequency_mhz'] = 127.5
            if change == 'step': plan['nets'][1]['frequency_mhz'] = 251.012
            if change == 'mode': plan['nets'][1]['modulation'] = 'FM'
            with self.subTest(change=change), self.assertRaises(HarnessError):
                apply_plan(table, plan)

    def test_two_nets_on_one_radio_in_one_phase_are_rejected(self):
        _, plan = fixture()
        plan['radio_usage'].append(dict(plan['radio_usage'][0], net='shared'))
        self.assertTrue(validate('comm-plan', plan))

    def test_inventory_and_complete_timeline_required(self):
        _, plan = fixture()
        plan['radio_usage'].pop()
        self.assertTrue(validate('comm-plan', plan))
        _, plan = fixture()
        plan['radio_inventory'].pop()
        self.assertTrue(validate('comm-plan', plan))

    def test_first_preset_overwrite_conflict_is_blocked(self):
        table, plan = fixture()
        plan['presets'][0]['net'] = 'shared'
        plan['presets'].append({'group': 'SYNTHETIC', 'radio': 1, 'channel': 4, 'net': 'intra'})
        table['coalition']['blue']['country'][1]['plane']['group'][1]['units'][1]['Radio'][1]['channels'][4] = 225
        with self.assertRaisesRegex(HarnessError, 'FIRST_PRESET_FLIGHT_FREQUENCY_CONFLICT'):
            apply_plan(table, plan)

    def test_missing_client_coverage_or_unknown_group_rejected(self):
        table, plan = fixture()
        plan['assignments'] = plan['assignments'][1:]
        with self.assertRaisesRegex(HarnessError, 'COMM_CLIENT_COVERAGE_REQUIRED'):
            apply_plan(table, plan)
        _, plan = fixture()
        plan['assignments'][0]['group'] = 'UNKNOWN'
        with self.assertRaisesRegex(HarnessError, 'COMM_GROUP_NOT_FOUND'):
            apply_plan(table, plan)
