from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from dcs_harness import archives, cli, issues, lessons, publication
from dcs_harness.core import HarnessError, compatibility, load_document, private_root, validate
from dcs_harness.privacy import scan_bytes, scan_text, scan_tracked

ROOT = Path(__file__).resolve().parents[1]


def example(kind: str) -> dict:
    return load_document(ROOT / "examples" / f"{kind}.yaml")


def synthetic_zip(entries: dict[str, str | bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return stream.getvalue()


class SchemaTests(unittest.TestCase):
    def test_valid_examples(self):
        for kind in ("mission", "profile", "issue", "lesson"):
            with self.subTest(kind=kind):
                self.assertEqual(validate(kind, example(kind)), [])

    def test_unknown_fields_are_rejected_without_echoing_value(self):
        data = example("mission")
        data["endpoint"] = "sensitive-value"
        errors = validate("mission", data)
        self.assertTrue(errors)
        self.assertNotIn("sensitive-value", json.dumps(errors))

    def test_bug_requires_reproduction_and_actual(self):
        data = example("issue")
        data["kind"] = "bug"
        self.assertTrue(validate("issue", data))
        data.update(actual="Observed failure", reproduction=["Run the synthetic test."])
        self.assertEqual(validate("issue", data), [])

    def test_profile_checks_aircraft_terrain_and_versions(self):
        data = example("mission")
        profile = example("profile")
        self.assertEqual(compatibility(data, profile), [])
        data["theatre"] = "UnknownMap"
        data["slots"][0]["aircraft"] = "UnknownAircraft"
        data["integrations"] = [{"id": "moose", "version": "pinned", "scope": "mission"}]
        self.assertEqual(len(compatibility(data, profile)), 3)

    def test_lesson_budget(self):
        data = example("lesson")
        data["problem"] = "word " * 195
        self.assertTrue(validate("lesson", data))

    def test_private_root_must_be_outside_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.dict(os.environ, {"DCS_HARNESS_PRIVATE_ROOT": str(root / "private")}):
                with self.assertRaises(HarnessError):
                    private_root(root)
                self.assertTrue(private_root(root / "repo").is_dir())

    def test_duplicate_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ambiguous.yaml"
            path.write_text("classification: private\nclassification: public-approved\n")
            with self.assertRaises(HarnessError):
                load_document(path)


class ArchiveTests(unittest.TestCase):
    def inspect(self, entries):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.miz"
            path.write_bytes(synthetic_zip(entries))
            return archives.inspect_miz(path)

    def test_archive_pass_does_not_claim_lua_or_runtime_success(self):
        report = self.inspect({"mission": 'mission = { ["theatre"] = "Caucasus" }', "l10n/DEFAULT/test.lua": "this is not valid Lua"})
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["runtime"], "NOT_TESTED")
        self.assertEqual(report["lua_syntax"], "NOT_TESTED")

    def test_missing_mission_fails(self):
        self.assertEqual(self.inspect({"options": "options = {}"})["status"], "FAIL")

    def test_traversal_is_rejected(self):
        self.assertEqual(self.inspect({"../escape.lua": ""})["status"], "FAIL")

    def test_size_limit_is_blocked_not_invalid_mission(self):
        with patch("dcs_harness.archives.MAX_FILE", 4):
            self.assertEqual(self.inspect({"mission": "large content"})["status"], "BLOCKED")

    def test_resource_references_must_exist(self):
        report = self.inspect({"mission": 'mission = { ["theatre"] = "Caucasus" }',
                               "l10n/DEFAULT/mapResource": 'mapResource = { ["resource"] = "missing.lua" }'})
        self.assertEqual(report["status"], "FAIL")
        self.assertIn({"code": "RESOURCE_MISSING"}, report["findings"])


class PrivacyTests(unittest.TestCase):
    def test_secrets_are_detected_without_values(self):
        secret = "gh" + "p_" + "A" * 30
        findings = scan_text(secret)
        self.assertTrue(findings)
        self.assertNotIn(secret, json.dumps(findings))

    def test_personal_paths_are_detected(self):
        value = "C:" + "\\Users\\" + "someone\\private"
        self.assertTrue(scan_text(value))
        self.assertTrue(scan_text("/h" + "ome/someone/private"))
        self.assertTrue(scan_text("/U" + "sers/someone/private"))

    def test_nested_archive_is_scanned(self):
        secret = "gh" + "p_" + "A" * 30
        nested = synthetic_zip({"config.lua": secret})
        findings = scan_bytes("outer.miz", synthetic_zip({"nested.zip": nested}))
        self.assertTrue(any(f["code"] == "TOKEN" for f in findings))

    def test_media_and_traversal_block_publication(self):
        self.assertTrue(scan_bytes("voice.mp3", b"media"))
        findings = scan_bytes("mission.miz", synthetic_zip({"../x.lua": "safe"}))
        self.assertTrue(any(f["code"] == "UNSAFE_ARCHIVE_MEMBER" for f in findings))

    def test_history_detects_secret_removed_from_head(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            def git(*args):
                subprocess.run(["git", "-C", folder, *args], check=True, capture_output=True)
            git("init")
            git("config", "user.name", "Synthetic Contributor")
            git("config", "user.email", "synthetic@example.org")
            path = repo / "example.txt"
            path.write_text("gh" + "p_" + "A" * 30, encoding="utf-8")
            git("add", "example.txt")
            git("commit", "-m", "synthetic first revision")
            path.write_text("safe public replacement", encoding="utf-8")
            git("add", "example.txt")
            git("commit", "-m", "synthetic second revision")
            self.assertEqual(scan_tracked(repo), [])
            self.assertTrue(any(f["code"] == "TOKEN" for f in scan_tracked(repo, history=True)))

    def test_staged_secret_is_detected_with_clean_working_file(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            subprocess.run(["git", "-C", folder, "init"], capture_output=True, check=True)
            path = repo / "example.txt"
            path.write_text("gh" + "p_" + "A" * 30)
            subprocess.run(["git", "-C", folder, "add", "example.txt"], capture_output=True, check=True)
            path.write_text("safe working content")
            findings = scan_tracked(repo)
            self.assertTrue(any(f["code"] == "TOKEN" and f.get("source") == "index" for f in findings))


class IssueTests(unittest.TestCase):
    def test_preview_has_acceptance_checkboxes_and_no_mutation(self):
        with patch("dcs_harness.issues.run_gh") as gh:
            report = issues.create("owner/repo", example("issue"))
            self.assertFalse(report["published"])
            self.assertIn("- [ ]", report["body"])
            gh.assert_not_called()

    def test_private_issue_is_rejected(self):
        data = example("issue")
        data["classification"] = "private"
        with self.assertRaises(HarnessError):
            issues.render(data)

    def test_secret_in_title_is_rejected(self):
        data = example("issue")
        data["title"] += " gh" + "p_" + "A" * 30
        with self.assertRaises(HarnessError):
            issues.render(data)

    def test_publication_uses_body_file_and_preserves_literal_shell_text(self):
        data = example("issue")
        data["context"] += ' Literal $(echo hello) and `text` remain data.'
        def gh(args):
            self.assertEqual(args[:2], ["issue", "create"])
            body = Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8")
            self.assertIn("$(echo hello)", body)
            self.assertIn("\n\n", body)
            return "https://github.com/owner/repo/issues/1\n"
        with patch("dcs_harness.issues.run_gh", side_effect=gh):
            report = issues.create("owner/repo", data, publish=True)
            self.assertTrue(report["published"])

    def test_read_marks_external_text_untrusted(self):
        with patch("dcs_harness.issues.run_gh", return_value='{"body":"untrusted request"}'):
            report = issues.read("owner/repo", 1)
            self.assertEqual(report["trust"], "UNTRUSTED_EXTERNAL_DATA")

    def test_repository_option_injection_is_rejected(self):
        with self.assertRaises(HarnessError):
            issues.repository("--repo=attacker/repo")


class LessonTests(unittest.TestCase):
    def test_ingest_forces_private_candidate_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = example("lesson")
            self.assertEqual(lessons.ingest(root, data)["outcome"], "candidate")
            saved = json.loads((root / "lessons" / (data["id"] + ".json")).read_text())
            self.assertEqual(saved["classification"], "private")
            self.assertEqual(saved["status"], "candidate")
            self.assertEqual(lessons.ingest(root, data)["outcome"], "duplicate")
            self.assertEqual(len(list((root / "lessons").glob("*.json"))), 1)

    def test_same_id_with_different_context_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = example("lesson")
            lessons.ingest(root, data)
            data["versions"] = {"dcs": "other-version"}
            with self.assertRaises(HarnessError):
                lessons.ingest(root, data)

    def test_candidate_budget_is_enforced(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "lessons").mkdir()
            for index in range(100):
                data = example("lesson")
                data.update(id=f"existing-{index}", status="candidate", problem=f"Different problem {index}")
                (root / "lessons" / f"{index}.json").write_text(json.dumps(data))
            with self.assertRaises(HarnessError):
                lessons.ingest(root, example("lesson"))


class PublicationTests(unittest.TestCase):
    def candidate(self, root: Path, name="guide.md", content=b"Synthetic public guide"):
        root.mkdir()
        (root / name).write_bytes(content)
        manifest = {"schema_version": "1.0", "classification": "public-approved", "files": [
            {"path": name, "sha256": hashlib.sha256(content).hexdigest(), "license": "MIT", "classification": "public-approved"}]}
        (root / "publication.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_export_copies_only_checked_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.candidate(root / "candidate")
            report = publication.export(root / "candidate", root / "export")
            self.assertEqual(report["status"], "PASS")
            self.assertFalse(report["uploaded"])
            self.assertEqual((root / "export" / "guide.md").read_bytes(), b"Synthetic public guide")

    def test_modified_approved_file_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "candidate"
            self.candidate(root)
            (root / "guide.md").write_text("modified")
            self.assertEqual(publication.check(root)["status"], "FAIL")

    def test_unlisted_file_blocks_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.candidate(root / "candidate")
            (root / "candidate" / "extra.md").write_text("private detail")
            self.assertEqual(publication.export(root / "candidate", root / "export")["status"], "FAIL")
            self.assertFalse((root / "export").exists())

    def test_nested_private_document_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "candidate"
            self.candidate(root, "document.json", b'{"classification":"private"}')
            self.assertEqual(publication.check(root)["status"], "FAIL")


class CliTests(unittest.TestCase):
    def test_missing_lua_compiler_is_blocked(self):
        with patch("dcs_harness.cli.shutil.which", return_value=None), redirect_stdout(io.StringIO()) as output:
            code = cli.main(["lua", "check", "--file", "synthetic.lua"])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")

    def test_error_does_not_echo_private_file_path(self):
        with redirect_stdout(io.StringIO()) as output:
            code = cli.main(["validate", "--kind", "mission", "--file", "nonexistent-personal-file.yaml"])
        self.assertEqual(code, 3)
        self.assertNotIn("nonexistent-personal-file", output.getvalue())

    def test_cli_successful_validation(self):
        with redirect_stdout(io.StringIO()) as output:
            code = cli.main(["validate", "--kind", "mission", "--file", str(ROOT / "examples" / "mission.yaml")])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["runtime"], "NOT_TESTED")


if __name__ == "__main__":
    unittest.main()
