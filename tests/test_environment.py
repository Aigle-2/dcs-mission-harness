from pathlib import Path
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from dcs_harness import cli, configuration, mission_export, workflow
from dcs_harness.core import HarnessError, load_document

ROOT = Path(__file__).resolve().parents[1]


class EnvironmentFixture:
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.repo = self.base / 'checkout'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True, capture_output=True)
        (self.repo / '.gitignore').write_text('.env\n.env.*\n')
        self.dcs = self.base / 'installation'
        (self.dcs / 'bin').mkdir(parents=True)
        (self.dcs / 'bin/DCS.exe').write_bytes(b'')
        self.saved = self.base / 'profiles/DCS'
        (self.saved / 'Config').mkdir(parents=True)
        self.refs = self.base / 'references'
        self.refs.mkdir()
        self.private = self.base / 'private'
        clean = {k: v for k, v in os.environ.items() if k not in configuration.KEYS}
        env = patch.dict(os.environ, clean, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def configure(self):
        return configuration.initialize(self.repo, self.dcs, self.saved, [self.refs], self.private)


class LocalEnvironmentTests(EnvironmentFixture, unittest.TestCase):
    def test_missing_setup_routes_agent_without_writing(self):
        report = configuration.initialize(self.repo, None, None, None, None)
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertEqual(report['next_skill'], 'environment-setup')
        self.assertFalse((self.repo / '.env').exists())

    def test_roundtrip_ignored_paths_and_environment_override(self):
        report = self.configure()
        self.assertEqual(report['status'], 'PASS')
        self.assertNotIn(str(self.base), json.dumps(report))
        configuration.ignored_env(self.repo)
        config = configuration.settings(self.repo)
        self.assertEqual(config.dcs, self.dcs)
        self.assertEqual(config.saved_games, self.saved)
        self.assertEqual(config.references, (self.refs,))
        second = self.base / 'DCS-second'
        second.mkdir()
        with patch.dict(os.environ, {configuration.KEYS[1]: str(second)}):
            configuration.load_env(self.repo)
            self.assertEqual(configuration.settings(self.repo).saved_games, second)

    def test_updates_preserve_unrelated_values_without_execution(self):
        (self.repo / '.env').write_text('OTHER_SETTING=$(literal)\n')
        self.configure()
        configuration.initialize(self.repo, None, None, None, None)
        content = (self.repo / '.env').read_text()
        self.assertIn('OTHER_SETTING=$(literal)', content)
        self.assertEqual(content.count('DCS_HARNESS_DCS_PATH='), 1)
        self.assertNotIn('OTHER_SETTING', configuration.read_env(self.repo))

    def test_tracked_env_is_rejected_without_modification(self):
        self.configure()
        path = self.repo / '.env'
        before = path.read_bytes()
        subprocess.run(['git', 'add', '-f', '.env'], cwd=self.repo, check=True, capture_output=True)
        with self.assertRaisesRegex(HarnessError, 'LOCAL_ENV_MUST_BE_GITIGNORED'):
            self.configure()
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_install_and_duplicate_reference_are_rejected(self):
        (self.dcs / 'bin/DCS.exe').unlink()
        with self.assertRaisesRegex(HarnessError, 'DCS_INSTALLATION_NOT_FOUND'):
            self.configure()
        (self.dcs / 'bin/DCS.exe').write_bytes(b'')
        with self.assertRaisesRegex(HarnessError, 'DUPLICATE_REFERENCE_ROOT'):
            configuration.initialize(self.repo, self.dcs, self.saved, [self.refs, self.refs], self.private)
        self.assertFalse((self.repo / '.env').exists())

    def test_duplicate_dotenv_setting_is_rejected(self):
        (self.repo / '.env').write_text('DCS_HARNESS_DCS_PATH=a\nDCS_HARNESS_DCS_PATH=b\n')
        with self.assertRaisesRegex(HarnessError, 'DUPLICATE_LOCAL_SETTING'):
            configuration.read_env(self.repo)

    def test_placeholder_template_uses_default_private_storage(self):
        (self.repo / '.env').write_bytes((ROOT / '.env.example').read_bytes())
        report = configuration.initialize(self.repo, self.dcs, self.saved, None, None)
        self.assertEqual(report['status'], 'PASS')
        values = configuration.read_env(self.repo)
        self.assertEqual(Path(values[configuration.KEYS[3]]), self.base / 'checkout-private')

    def test_profile_inside_checkout_is_rejected(self):
        profile = self.repo / 'DCS'
        profile.mkdir()
        with self.assertRaisesRegex(HarnessError, 'SAVED_GAMES_INSIDE_CHECKOUT'):
            configuration.initialize(self.repo, self.dcs, profile, None, self.private)

    def test_first_doctor_returns_setup_skill_without_private_output(self):
        output = io.StringIO()
        with patch('dcs_harness.cli.Path.cwd', return_value=self.repo), contextlib.redirect_stdout(output):
            code = cli.main(['doctor'])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 3)
        self.assertEqual(report['next_skill'], 'environment-setup')
        self.assertNotIn(str(self.base), output.getvalue())


class MissionExportTests(EnvironmentFixture, unittest.TestCase):
    def prepare(self, verify=True):
        self.configure()
        self.run_id = 'synthetic-export'
        brief = self.base / 'brief.md'
        brief.write_text('Create a synthetic cooperative navigation exercise.')
        spec = load_document(ROOT / 'examples/functional-spec.yaml')
        spec['mission']['id'] = self.run_id
        specfile = self.base / 'spec.json'
        specfile.write_text(json.dumps(spec))
        artifact = self.base / 'input.miz'
        with zipfile.ZipFile(artifact, 'w') as archive:
            archive.writestr('mission', 'mission = { ["theatre"] = "Caucasus" }')
        workflow.start(self.private, self.run_id, brief)
        workflow.specification(self.private, self.run_id, specfile)
        workflow.implementation(self.private, self.run_id, artifact)
        self.run = workflow.run_path(self.private, self.run_id)
        state = load_document(self.run / 'state.json')
        evidence = {'schema_version': '1.0', 'classification': 'private',
                    'spec_sha256': state['spec_sha256'], 'artifact_sha256': state['artifact_sha256'],
                    'checks': [{'criterion': c['id'], 'status': 'PASS' if c['level'] == 'local' else 'SKIPPED',
                                'evidence': 'Synthetic local check; DCS runtime is unavailable.'}
                               for c in spec['criteria']]}
        evidencefile = self.base / 'evidence.json'
        evidencefile.write_text(json.dumps(evidence))
        if verify:
            workflow.verify(self.private, self.run_id, evidencefile)

    def test_export_is_identical_idempotent_and_does_not_certify_runtime(self):
        self.prepare()
        report = mission_export.export(self.private, self.repo, self.run_id)
        target = self.saved / 'Missions' / report['filename']
        self.assertEqual(target.read_bytes(), (self.run / 'mission.miz').read_bytes())
        self.assertEqual(report['runtime'], 'NOT_TESTED')
        self.assertEqual(mission_export.export(self.private, self.repo, self.run_id)['outcome'], 'already-present')
        self.assertNotIn(str(self.base), json.dumps(report))

    def test_export_never_overwrites_existing_file(self):
        self.prepare()
        report = mission_export.export(self.private, self.repo, self.run_id)
        target = self.saved / 'Missions' / report['filename']
        target.write_bytes(b'Existing user content')
        with self.assertRaisesRegex(HarnessError, 'MISSION_EXPORT_NAME_COLLISION'):
            mission_export.export(self.private, self.repo, self.run_id)
        self.assertEqual(target.read_bytes(), b'Existing user content')

    def test_unverified_or_revision_required_mission_cannot_be_exported(self):
        self.prepare(verify=False)
        with self.assertRaisesRegex(HarnessError, 'LOCAL_VERIFICATION_REQUIRED'):
            mission_export.export(self.private, self.repo, self.run_id)
        self.assertFalse((self.saved / 'Missions').exists())

    def test_revision_required_blocks_export(self):
        self.prepare()
        (self.run / 'REVISION-REQUIRED.md').write_text('Synthetic changes require another review.')
        with self.assertRaisesRegex(HarnessError, 'MISSION_REVISION_REQUIRED'):
            mission_export.export(self.private, self.repo, self.run_id)

    def test_changed_artifact_blocks_export(self):
        self.prepare()
        (self.run / 'mission.miz').write_bytes(b'Changed after verification')
        with self.assertRaisesRegex(HarnessError, 'REGISTERED_ARTIFACT_CHANGED'):
            mission_export.export(self.private, self.repo, self.run_id)

    def test_changed_verification_hash_blocks_export(self):
        self.prepare()
        recordfile = sorted((self.run / 'verifications').glob('*.json'))[-1]
        record = load_document(recordfile)
        record['evidence']['artifact_sha256'] = '0' * 64
        recordfile.write_text(json.dumps(record))
        with self.assertRaisesRegex(HarnessError, 'LOCAL_VERIFICATION_REQUIRED'):
            mission_export.export(self.private, self.repo, self.run_id)

    def test_missions_directory_cannot_redirect_outside_profile(self):
        self.prepare()
        other = self.base / 'other-destination'
        other.mkdir()
        try:
            (self.saved / 'Missions').symlink_to(other, target_is_directory=True)
        except OSError:
            self.skipTest('Creating directory symlinks is unavailable on this system.')
        with self.assertRaisesRegex(HarnessError, 'MISSION_EXPORT_PATH_ESCAPE'):
            mission_export.export(self.private, self.repo, self.run_id)
        self.assertEqual(list(other.iterdir()), [])
