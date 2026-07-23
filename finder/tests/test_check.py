from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from finderctl import check


class CheckTests(unittest.TestCase):
    def test_filenames_stops_at_requested_depth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "root.jpg").touch()
            (root / "one").mkdir()
            (root / "one" / "one.jpg").touch()
            (root / "one" / "two").mkdir()
            (root / "one" / "two" / "ignored.jpg").touch()

            filenames, too_deep, ignored_files = check.filenames(directory, 1)

        self.assertEqual(filenames, {"root.jpg", "one.jpg"})
        self.assertTrue(too_deep)
        self.assertEqual(ignored_files, 1)

    def test_display_path_compacts_volume_paths(self) -> None:
        self.assertEqual(
            check.display_path("/Volumes/ALPHA/DCIM/backup0722/"),
            "ALPHA/.../backup0722",
        )

    def test_compact_filenames_groups_numbered_sequences(self) -> None:
        filenames = {"photo001.jpg", "photo002.jpg", "photo003.jpg", "notes.txt"}
        self.assertEqual(
            check.compact_filenames(filenames),
            ["photo001.jpg-photo003.jpg", "notes.txt"],
        )

    def test_run_checks_left_is_subset_of_right(self) -> None:
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            Path(left, "present.jpg").touch()
            Path(left, "missing.jpg").touch()
            Path(right, "present.jpg").touch()

            with (
                patch.object(check.finder, "left_right_paths", return_value=(left, right)),
                redirect_stdout(StringIO()),
            ):
                result = check.run()

        self.assertEqual(result, 1)

    def test_run_prints_ignored_count_and_filename_warning(self) -> None:
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            Path(left, "present.jpg").touch()
            Path(right, "present.jpg").touch()
            Path(left, "deep").mkdir()
            Path(left, "deep", "ignored.jpg").touch()

            output = StringIO()
            with (
                patch.object(check.finder, "left_right_paths", return_value=(left, right)),
                redirect_stdout(output),
            ):
                result = check.run(depth=0)

        self.assertEqual(result, 0)
        self.assertIn("(1 file on the left)", output.getvalue())
        self.assertIn(
            "comparison uses filenames only; file contents are not checked",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
