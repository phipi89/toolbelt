from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from venvclean import cli


def make_environment(path, *, uv=False):
    path.mkdir(parents=True)
    (path / "pyvenv.cfg").write_text(
        "version = 3.13.3\n" + ("uv = 0.12.23\n" if uv else "")
    )
    (path / "bin").mkdir()
    python = path / "bin" / "python"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    return path


class CleanupTests(unittest.TestCase):
    def test_discovery_finds_custom_and_hidden_names_but_not_nested_environments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            first = make_environment(root / "project" / "custom-env")
            second = make_environment(root / "project2" / ".venv")
            make_environment(first / "nested")
            self.assertEqual(
                set(cli.discover([root, root / "project"], [])), {first, second}
            )

    def test_skip_excludes_descendants_and_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            blocked = root / "skip"
            make_environment(blocked / "env")
            (root / "link").symlink_to(blocked, target_is_directory=True)
            self.assertEqual(list(cli.discover([root], [blocked])), [])

    def test_plain_and_standalone_uv_require_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            plain = make_environment(root / "plain")
            uv = make_environment(root / "uv-env", uv=True)
            self.assertFalse(cli.inspect(plain, [root], {}).direct_delete)
            self.assertFalse(cli.inspect(uv, [root], {}).direct_delete)

    def test_locked_uv_project_allows_direct_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "project"
            path = make_environment(project / "custom-name", uv=True)
            (project / "pyproject.toml").write_text(
                '[project]\nname="demo"\nversion="0.1.0"\n'
            )
            (project / "uv.lock").write_text("version = 1\n")
            environment = cli.inspect(path, [root], {})
            self.assertTrue(environment.direct_delete)
            self.assertEqual(environment.project, project)
            self.assertIn("UV_PROJECT_ENVIRONMENT=", cli.recovery(environment))

    def test_project_source_changes_count_as_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "project" / "env")
            (path.parent / "pyproject.toml").write_text('[project]\nname="demo"\n')
            source = path.parent / "src" / "deep" / "code.py"
            source.parent.mkdir(parents=True)
            source.write_text("pass\n")
            future = 2_000_000_000
            os.utime(source, (future, future))
            self.assertGreaterEqual(cli.inspect(path, [root], {}).activity, future)

    def test_active_environment_and_outside_roots_are_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "env")
            environment = cli.inspect(path, [root], {})
            with (
                patch.dict(os.environ, {"VIRTUAL_ENV": str(path)}),
                self.assertRaisesRegex(ValueError, "active"),
            ):
                cli.validate(environment, [root], [])
            with self.assertRaisesRegex(ValueError, "scan root"):
                cli.validate(environment, [root / "elsewhere"], [])

    def test_changed_marker_is_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "env")
            environment = cli.inspect(path, [root], {})
            (path / "pyvenv.cfg").write_text("version = 3.14\n")
            with self.assertRaisesRegex(ValueError, "changed"):
                cli.validate(environment, [root], [])

    def test_export_uses_environment_interpreter_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "env")
            environment = cli.inspect(path, [root], {})
            result = subprocess.CompletedProcess([], 0, "numpy==2.4.0\n", "")
            with patch.object(cli.subprocess, "run", return_value=result) as run:
                first = cli.export_requirements(environment)
                second = cli.export_requirements(environment)
            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, path.parent)
            self.assertIn("numpy==2.4.0", first.read_text())
            self.assertEqual(run.call_args.args[0][0], str(path / "bin" / "python"))

    def test_export_failure_keeps_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "env")
            environment = cli.inspect(path, [root], {})
            answers = iter(["e"])
            with patch.object(
                cli, "export_requirements", side_effect=ValueError("failure")
            ):
                cli.review([environment], [root], [], ask=lambda _: next(answers))
            self.assertTrue(path.is_dir())

    def test_plain_environment_cannot_be_deleted_without_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "env")
            environment = cli.inspect(path, [root], {})
            answers = iter(["d", "k"])
            cli.review([environment], [root], [], ask=lambda _: next(answers))
            self.assertTrue(path.is_dir())

    def test_successful_export_and_confirmation_delete_only_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "env")
            environment = cli.inspect(path, [root], {})
            result = subprocess.CompletedProcess([], 0, "numpy==2.4.0\n", "")
            answers = iter(["e", "y"])
            with patch.object(cli.subprocess, "run", return_value=result):
                cli.review([environment], [root], [], ask=lambda _: next(answers))
            self.assertFalse(path.exists())
            self.assertEqual(len(list(root.glob("requirements-from-*.txt"))), 1)

    def test_age_formats(self):
        self.assertEqual(cli.age_days("90d"), 90)
        self.assertEqual(cli.age_days("12w"), 84)
        self.assertEqual(cli.age_days("3m"), 90)

    def test_invalid_lock_is_not_treated_as_reconstructible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "project" / "env", uv=True)
            (path.parent / "pyproject.toml").write_text('[project]\nname="demo"\n')
            (path.parent / "uv.lock").write_text("broken = [")
            self.assertFalse(cli.inspect(path, [root], {}).direct_delete)

    def test_uv_freeze_is_used_if_environment_has_no_pip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "env")
            environment = cli.inspect(path, [root], {})
            results = [
                subprocess.CompletedProcess([], 1, "", "No module named pip"),
                subprocess.CompletedProcess([], 0, "numpy==2.4.0\n", ""),
            ]
            with (
                patch.object(cli.shutil, "which", return_value="/usr/bin/uv"),
                patch.object(cli.subprocess, "run", side_effect=results) as run,
            ):
                output = cli.export_requirements(environment)
            self.assertIn("numpy==2.4.0", output.read_text())
            self.assertEqual(run.call_args.args[0][:3], ["uv", "pip", "freeze"])

    def test_dry_run_defaults_to_90_days_and_never_reviews_or_deletes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "env")
            old = cli.time.time() - 100 * 86400
            for target in [*path.rglob("*"), path]:
                os.utime(target, (old, old))
            with (
                patch.object(sys, "argv", ["venvclean", str(root), "--dry-run"]),
                patch.object(sys, "stdout", new_callable=io.StringIO) as output,
                patch.object(cli, "review") as review,
            ):
                cli.main()
            self.assertIn("age threshold: 90 days", output.getvalue())
            self.assertIn("1 eligible", output.getvalue())
            review.assert_not_called()
            self.assertTrue(path.is_dir())

    def test_declined_confirmation_keeps_environment_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = make_environment(root / "env")
            environment = cli.inspect(path, [root], {})
            result = subprocess.CompletedProcess([], 0, "numpy==2.4.0\n", "")
            answers = iter(["e", "n"])
            with patch.object(cli.subprocess, "run", return_value=result):
                cli.review([environment], [root], [], ask=lambda _: next(answers))
            self.assertTrue(path.is_dir())
            self.assertEqual(len(list(root.glob("requirements-from-*.txt"))), 1)


if __name__ == "__main__":
    unittest.main()
