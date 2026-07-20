from __future__ import annotations

import unittest
from unittest.mock import patch

from displayctl import move_here


class MoveHereTests(unittest.TestCase):
    def test_window_space_is_compared_with_space_index(self) -> None:
        win = {"id": 10, "space": 3, "is-visible": True}
        space = {"id": 500, "index": 3, "is-native-fullscreen": False}

        with (
            patch.object(move_here.goto, "matching_windows", return_value=[win]),
            patch.object(move_here.goto, "current_context", return_value=(1, 3)),
            patch.object(move_here.goto, "best_window", return_value=win),
            patch.object(move_here.goto, "focus_window") as focus_window,
            patch.object(move_here.yabai, "query_space", return_value=space),
            patch.object(move_here.yabai, "move_space") as move_space,
        ):
            move_here.run("Calendar")

        move_space.assert_not_called()
        focus_window.assert_called_once_with(win, None)

    def test_move_uses_space_index_and_updates_window_context(self) -> None:
        win = {"id": 10, "space": 2, "is-visible": False}
        space = {"id": 500, "index": 3, "is-native-fullscreen": False}

        with (
            patch.object(move_here.goto, "matching_windows", return_value=[win]),
            patch.object(move_here.goto, "current_context", return_value=(1, 3)),
            patch.object(move_here.goto, "best_window", return_value=win),
            patch.object(move_here.goto, "focus_window") as focus_window,
            patch.object(move_here.yabai, "query_space", return_value=space),
            patch.object(move_here.yabai, "move_space") as move_space,
        ):
            move_here.run("Calendar")

        move_space.assert_called_once_with(10, 3)
        focus_window.assert_called_once_with({"id": 10, "space": 3, "is-visible": True})


if __name__ == "__main__":
    unittest.main()
