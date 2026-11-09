from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from search import mdfind


class MdfindTests(unittest.TestCase):
    def test_spotlight_uses_only_last_used_dates(self):
        raw = (
            "/tmp/used.pdf   kMDItemLastUsedDate = 2026-10-01 12:00:00 +0000\0"
            "/tmp/missing.pdf   kMDItemLastUsedDate = (null)\0"
        )
        with patch.object(mdfind, "_run", return_value=raw) as run:
            items = mdfind._spotlight_items(Path("/tmp"), days=10)
        self.assertEqual(
            items,
            [
                {
                    "path": "/tmp/used.pdf",
                    "last_used": dt.datetime(2026, 10, 1, 12, tzinfo=dt.UTC),
                }
            ],
        )
        self.assertEqual(
            run.call_args.args[0][-1], "kMDItemLastUsedDate > $time.now(-864000)"
        )

    def test_expansion_adds_siblings_and_one_more_directory_level(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.md"
            sibling = root / "sibling.md"
            child = root / "folder" / "child.md"
            deeper = root / "folder" / "deeper" / "too-deep.md"
            for path in (seed, sibling, child, deeper):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            timestamp = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
            items = mdfind._expand_neighbors(
                [{"path": str(seed), "last_used": timestamp}], root
            )
            by_path = {item["path"]: item for item in items}
            self.assertIn(str(sibling), by_path)
            self.assertIn(str(child), by_path)
            self.assertNotIn(str(deeper), by_path)
            self.assertEqual(by_path[str(seed)]["last_used"], timestamp)
            self.assertIsNone(by_path[str(child)]["last_used"])

    def test_expansion_excludes_hidden_generated_and_library_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.md"
            seed.touch()
            for name in (
                "Library",
                ".venv",
                ".git",
                "node_modules",
                "__pycache__",
                "build",
                "dist",
            ):
                (root / name).mkdir()
                (root / name / "hidden.txt").touch()
            (root / ".secret").touch()
            items = mdfind._expand_neighbors(
                [{"path": str(seed), "last_used": None}], root
            )
            self.assertEqual([item["path"] for item in items], [str(seed)])

    def test_expansion_deduplicates_and_preserves_seed_priority_at_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seeds = []
            for name in ("a.md", "b.md", "c.md"):
                path = root / name
                path.touch()
                if name != "c.md":
                    seeds.append({"path": str(path), "last_used": None})
            items = mdfind._expand_neighbors(seeds, root, limit=2)
            self.assertEqual(items, seeds)
            expanded = mdfind._expand_neighbors(seeds, root)
            self.assertEqual(len(expanded), 3)

    def test_expansion_does_not_follow_directory_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.md"
            seed.touch()
            target = root / ".hidden"
            target.mkdir()
            (target / "file.md").touch()
            link = root / "linked"
            link.symlink_to(target, target_is_directory=True)
            items = mdfind._expand_neighbors(
                [{"path": str(seed), "last_used": None}], root
            )
            paths = {item["path"] for item in items}
            self.assertIn(str(link), paths)
            self.assertNotIn(str(link / "file.md"), paths)

    def test_unreadable_folder_is_skipped(self):
        with patch.object(mdfind.os, "scandir", side_effect=PermissionError):
            seeds = [{"path": "/tmp/seed.md", "last_used": None}]
            self.assertEqual(mdfind._expand_neighbors(seeds, Path("/tmp")), seeds)

    def test_loaded_index_includes_neighbors_and_reports_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.md"
            sibling = root / "sibling.md"
            seed.touch()
            sibling.touch()
            timestamp = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
            with patch.object(
                mdfind,
                "_spotlight_items",
                return_value=[{"path": str(seed), "last_used": timestamp}],
            ):
                items, meta = mdfind.get_home_indexed_items(root=root, with_meta=True)
            self.assertEqual(
                {item["path"] for item in items}, {str(seed), str(sibling)}
            )
            self.assertEqual(meta["seed_count"], 1)
            self.assertEqual(meta["neighbor_count"], 1)
            self.assertEqual(meta["freshest_item_at"], timestamp)


if __name__ == "__main__":
    unittest.main()
