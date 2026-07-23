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
