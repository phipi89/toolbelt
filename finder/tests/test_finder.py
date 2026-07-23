from __future__ import annotations

import unittest
from unittest.mock import patch

from finderctl import finder


class FinderTests(unittest.TestCase):
    def test_left_right_paths_uses_two_visible_finder_windows(self) -> None:
        right = {"id": 20, "app": "Finder", "frame": {"x": 100}}
        left = {"id": 10, "app": "Finder", "frame": {"x": 0}}

        with (
            patch.object(
                finder.yabai,
                "query_windows_on_space",
                return_value=[right, {"app": "iTerm2"}, left],
            ),
            patch.object(finder.yabai, "eligible_window", return_value=True),
            patch.object(finder, "window_path", side_effect=["/left", "/right"]),
        ):
            self.assertEqual(finder.left_right_paths(), ("/left", "/right"))


if __name__ == "__main__":
    unittest.main()
