from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from finderctl import cli


class CliTests(unittest.TestCase):
    def test_touch_defaults_to_empty_txt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli.finder, "front_path", return_value=directory):
                cli._touch([])
            self.assertTrue(Path(directory, "empty.txt").is_file())

    def test_touch_creates_folders_for_extensionless_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli.finder, "front_path", return_value=directory):
                cli._touch(["photos", "notes.txt"])

            self.assertTrue(Path(directory, "photos").is_dir())
            self.assertTrue(Path(directory, "notes.txt").is_file())

    def test_touch_can_force_an_extensionless_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli.finder, "front_path", return_value=directory):
                cli._touch(["README"], force_file=True)

            self.assertTrue(Path(directory, "README").is_file())

    def test_touch_creates_parent_folders_for_nested_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli.finder, "front_path", return_value=directory):
                created_files = cli._touch(["folder/subfolder/note.md"])

            target = Path(directory, "folder/subfolder/note.md")
            self.assertEqual(created_files, [target])
            self.assertTrue(target.is_file())

    def test_touch_creates_nested_folders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli.finder, "front_path", return_value=directory):
                created_files = cli._touch(["folder/subfolder"])

            self.assertEqual(created_files, [])
            self.assertTrue(Path(directory, "folder/subfolder").is_dir())

    def test_touch_only_reports_new_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory, "note.md")
            existing.touch()
            with patch.object(cli.finder, "front_path", return_value=directory):
                created_files = cli._touch(["note.md"])

            self.assertEqual(created_files, [])

    def test_snapshot_copies_selected_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory, "photo.jpg")
            selected.write_bytes(b"photo")
            with patch.object(cli.finder, "selected_file", return_value=str(selected)):
                target = Path(cli._snapshot())

            self.assertEqual(target.parent, Path(directory, "snapshots"))
            self.assertEqual(target.read_bytes(), b"photo")


if __name__ == "__main__":
    unittest.main()
