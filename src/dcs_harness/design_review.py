"""Render recognizable decision labels from structured review records."""
from __future__ import annotations

import re
from .core import require_valid


def plain(value: str) -> str:
    # Keep untrusted mission text on one line and prevent Markdown label spoofing.
    return re.sub(r'([\\`*_\[\]<>])', r'\\\1', ' '.join(value.split()))


def decision_review(spec: dict) -> tuple[str, int]:
    """Private review appendix; rendering never supplies human approval."""
    require_valid('functional-spec', spec)
    rows = []

    def add(topic, choice, status, source, evidence):
        label = {'proposed': 'Proposed', 'confirmed': 'Decided',
                 'not-applicable': 'NotApplicable'}[status]
        rows.append((label, f'- [{label}] {plain(topic)} : {plain(choice)} '
                     f'(source : {plain(source)} ; preuve : {plain(evidence)}).'))

    for item in spec['design_decisions']:
        add(item['topic'], item['choice'], item['status'], item['source'], item['evidence'])
    temporal = spec['temporal']
    choice = (f"date {temporal['date']}; disponibilité des avions et armements "
              + ('limitée par l’année' if temporal['restrict_by_year'] else 'non limitée par l’année'))
    add('date et époque', choice, temporal['status'], temporal['source'], temporal['evidence'])
    nav = spec['navigation']
    from .navigation import review_choices
    for kind, choice in review_choices(nav):
        add(kind, choice, nav['status'], nav['source'], nav['evidence'])
    for flight in spec['support_flights']:
        cruise, station = flight['cruise_altitude'], flight['mission_altitude']
        choice = (f"{flight['aircraft']}; croisière {cruise['value']} {cruise['unit']} MSL; "
                  f"mission {station['value']} {station['unit']} MSL; orbite {flight['orbit']}")
        if flight['role'] == 'tanker':
            choice += f"; ravitaillement {flight['refueling_system']}; receveurs {', '.join(flight['receivers'])}"
        add(flight['group'], choice, flight['status'], flight['source'], flight['evidence'])
    for topic in ('communications', 'liveries'):
        item = spec[topic]
        choice = item['decision']
        if topic == 'communications' and 'plan' in item:
            choice += '; réseaux : ' + '; '.join(
                f"{net['id']} {net['frequency_mhz']} MHz {net['modulation']}" for net in item['plan']['nets'])
        if topic == 'liveries' and 'selections' in item:
            choice += f" : {item['selections']}"
        add(topic, choice, 'proposed' if item['decision'] == 'pending' else 'confirmed',
            item['source'], item['evidence'])
    pending = sum(label == 'Proposed' for label, _ in rows)
    document = ('# Choix de conception à relire\n\n'
                '[Proposed] : proposition en attente de validation utilisateur.\n\n'
                '[Decided] : choix explicite ou confirmé par l’utilisateur.\n\n'
                '[NotApplicable] : élément absent du scénario.\n\n'
                'Déléguer le choix ne valide pas la proposition. Ce document ne constitue pas une approbation.\n\n'
                + '\n'.join(row for _, row in rows) + '\n')
    return document, pending
