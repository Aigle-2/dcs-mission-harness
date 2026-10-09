"""Navigation allocation checks; these do not certify DCS equipment capability."""


def review_choices(plan: dict) -> list[tuple[str, str]]:
    rows = []
    for beacon in plan['tacan']:
        rows.append(('TACAN', f"{beacon['station']} : {beacon['channel']}{beacon['band']}, ident {beacon['ident']}"))
    for pair in plan['yardstick']:
        rows.append(('yardstick', f"{pair['group']} : leader {pair['leader']} {pair['leader_channel']}Y ; "
                     f"ailiers {', '.join(pair['wingmen'])} {pair['wingman_channel']}Y"))
    for flight in plan['callsigns']:
        value = 'défaut DCS' if flight['mode'] == 'dcs-default' else f"{flight['name']} {flight['flight_number']}"
        rows.append(('callsign', f"{flight['group']} ({flight['aircraft']}) : {value}"))
    for ship in plan['naval_systems']:
        icls, link = ship['icls'], ship['datalink']
        icls_value = str(icls['channel']) if icls['decision'] == 'enabled' else icls['decision']
        link_value = f"{link['system']} {link['frequency_mhz']} MHz" if link['decision'] == 'enabled' else link['decision']
        rows.append(('systèmes navals', f"{ship['unit']} : ICLS {icls_value} ; datalink {link_value}"))
    return rows


def findings(plan: dict) -> list[dict]:
    errors = []

    def fail(code, location):
        errors.append({'code': code, 'location': location})

    if plan['status'] == 'confirmed' and plan['source'] == 'agent-proposal':
        fail('USER_CONFIRMATION_REQUIRED', [])
    stations = [b['station'] for b in plan['tacan']]
    channels = [(b['channel'], b['band']) for b in plan['tacan']]
    groups = [y['group'] for y in plan['yardstick']]
    callsigns = [c['group'] for c in plan['callsigns']]
    ships = [s['unit'] for s in plan['naval_systems']]
    if any(len(set(items)) != len(items) for items in (stations, channels, groups, callsigns, ships)):
        fail('DUPLICATE_NAVIGATION_ALLOCATION', [])
    for index, beacon in enumerate(plan['tacan']):
        if beacon['band'] != ('Y' if beacon['platform'] == 'aircraft' else 'X'):
            fail('TACAN_BAND_CONVENTION', ['tacan', index, 'band'])
    used_yardstick = set()
    for index, pair in enumerate(plan['yardstick']):
        if abs(pair['leader_channel'] - pair['wingman_channel']) != 63:
            fail('YARDSTICK_CHANNEL_OFFSET', ['yardstick', index])
        if pair['leader'] in pair['wingmen'] or pair['group'] not in callsigns:
            fail('YARDSTICK_FLIGHT_MEMBERS', ['yardstick', index])
        allocated = {(pair['leader_channel'], 'Y'), (pair['wingman_channel'], 'Y')}
        if allocated.intersection(set(channels) | used_yardstick):
            fail('NAVIGATION_CHANNEL_COLLISION', ['yardstick', index])
        used_yardstick.update(allocated)
    for index, ship in enumerate(plan['naval_systems']):
        if plan['status'] == 'confirmed' and any(ship[s]['decision'] == 'pending' for s in ('icls', 'datalink')):
            fail('NAVAL_SYSTEM_REVIEW_REQUIRED', ['naval_systems', index])
    return errors
