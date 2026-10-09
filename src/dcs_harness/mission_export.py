"""Copy a verified private mission into the configured local DCS profile."""
from __future__ import annotations

from pathlib import Path
import shutil
from .archives import digest, inspect_miz
from .configuration import settings
from .core import HarnessError, load_document, require_valid, result
from .workflow import locked_run, unchanged_spec


def export(root: Path, repo: Path, run_id: str) -> dict:
    profile = settings(repo)
    destination = profile.saved_games / 'Missions'
    if not destination.resolve().is_relative_to(profile.saved_games):
        raise HarnessError('MISSION_EXPORT_PATH_ESCAPE', 'BLOCKED')
    with locked_run(root, run_id) as (path, state):
        if state['phase'] != 'LOCAL_VERIFIED':
            raise HarnessError('LOCAL_VERIFICATION_REQUIRED', 'BLOCKED')
        spec = unchanged_spec(path, state)
        if (path / 'REVISION-REQUIRED.md').exists():
            raise HarnessError('MISSION_REVISION_REQUIRED', 'BLOCKED')
        records = sorted((path / 'verifications').glob('*.json'))
        if not records:
            raise HarnessError('VERIFICATION_RECORD_REQUIRED', 'BLOCKED')
        record = load_document(records[-1])
        evidence = record['evidence']
        require_valid('verification', evidence)
        checks = {c['criterion']: c for c in evidence['checks']}
        criteria = {c['id']: c for c in spec['criteria']}
        if (record['summary']['status'] != 'PASS'
                or len(checks) != len(evidence['checks']) or set(checks) != set(criteria)
                or any(evidence[k] != state[k] for k in ('artifact_sha256', 'spec_sha256'))
                or any(checks[k]['status'] != 'PASS' for k, c in criteria.items() if c['level'] == 'local')):
            raise HarnessError('LOCAL_VERIFICATION_REQUIRED', 'BLOCKED')
        source = path / 'mission.miz'
        if digest(source) != state['artifact_sha256']:
            raise HarnessError('REGISTERED_ARTIFACT_CHANGED')
        checked = inspect_miz(source)
        if checked['status'] != 'PASS':
            raise HarnessError('EXPORT_ARCHIVE_CHECK_FAILED', 'BLOCKED')
        destination.mkdir(exist_ok=True)
        filename = f"{run_id}-{state['artifact_sha256'][:12]}.miz"
        target = destination / filename
        if target.is_symlink() or not target.resolve().is_relative_to(profile.saved_games):
            raise HarnessError('MISSION_EXPORT_PATH_ESCAPE', 'BLOCKED')
        try:
            output = target.open('xb')
        except FileExistsError:
            if digest(target) != state['artifact_sha256']:
                raise HarnessError('MISSION_EXPORT_NAME_COLLISION', 'BLOCKED') from None
            outcome = 'already-present'
        else:
            try:
                with output, source.open('rb') as incoming:
                    shutil.copyfileobj(incoming, output)
                if digest(target) != state['artifact_sha256']:
                    raise HarnessError('EXPORT_ARTIFACT_CHANGED')
            except BaseException:
                # Only this export's newly created file is removed; no overwrite.
                target.unlink(missing_ok=True)
                raise
            outcome = 'copied'
    return result('PASS', 'mission.export', run=run_id, outcome=outcome,
                  filename=filename, artifact_sha256=state['artifact_sha256'],
                  destination='configured-saved-games/Missions', runtime='NOT_TESTED',
                  next_action='Open the exported mission in DCS and run client/runtime checks.')
