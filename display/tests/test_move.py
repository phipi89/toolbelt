from __future__ import annotations

import unittest
from unittest.mock import patch

from displayctl import move


class MoveTests(unittest.TestCase):
    def _hotkey(self, window_id: int = 10, level: int = 25) -> dict:
        return {
            "id": window_id,
            "app": "iTerm2",
            "role": "AXWindow",
            "subrole": "AXSystemDialog",
            "level": level,
            "is-visible": True,
            "is-floating": True,
            "is-sticky": True,
            "can-move": True,
            "can-resize": True,
        }

    def test_target_prefers_hotkey_window_over_focused_finder(self) -> None:
        hotkey = self._hotkey()
        finder = {"id": 20, "app": "Finder", "has-focus": True}

        with patch.object(move.yabai, "query_window") as query_window:
            self.assertEqual(move._target_window([hotkey, finder]), hotkey)

        query_window.assert_not_called()

    def test_target_prefers_hotkey_window_over_regular_iterm(self) -> None:
        hotkey = self._hotkey()
        regular = {"id": 20, "app": "iTerm2", "has-focus": True}

        self.assertEqual(move._target_window([regular, hotkey]), hotkey)

    def test_target_ignores_ordinary_sticky_window(self) -> None:
        sticky = {
            **self._hotkey(),
            "subrole": "AXStandardWindow",
        }
        focused = {"id": 20, "app": "Finder", "has-focus": True}

        with patch.object(move.yabai, "query_window", return_value=focused):
            self.assertEqual(move._target_window([sticky, focused]), focused)

    def test_target_uses_highest_hotkey_window(self) -> None:
        lower = self._hotkey(window_id=10, level=20)
        higher = self._hotkey(window_id=11, level=30)

        self.assertEqual(move._target_window([lower, higher]), higher)

    def test_target_falls_back_to_current_window(self) -> None:
        focused = {"id": 20, "app": "Finder", "has-focus": True}

        with patch.object(move.yabai, "query_window", return_value=focused):
            self.assertEqual(move._target_window([]), focused)

    def test_center_resizes_hotkey_instead_of_focused_finder(self) -> None:
        hotkey = {
            **self._hotkey(window_id=10),
            "frame": {"x": 100, "y": 100, "w": 700, "h": 300},
        }
        finder = {
            "id": 20,
            "app": "Finder",
            "frame": {"x": 0, "y": 31, "w": 1000, "h": 700},
            "has-focus": True,
        }
        display = {
            "id": 1,
            "index": 1,
            "frame": {"x": 0, "y": 0, "w": 1000, "h": 800},
        }

        with (
            patch.object(
                move.yabai, "query_windows_on_space", return_value=[hotkey, finder]
            ),
            patch.object(move.yabai, "query_display", return_value=display),
            patch.object(move.yabai, "query_window") as query_window,
            patch.object(move.yabai, "grid") as grid,
        ):
            move.center()

        query_window.assert_not_called()
        grid.assert_called_once_with(10, "100:100:5:5:90:90")

    def test_split_uses_shared_state_transition(self) -> None:
        left = {"id": 10, "frame": {"x": 0}}
        right = {"id": 20, "frame": {"x": 100}}

        with (
            patch.object(move, "_eligible_windows", return_value=[left, right]),
            patch.object(move, "_split_state", return_value="half"),
            patch.object(move, "_set_split_layout") as set_layout,
        ):
            move.split()

        set_layout.assert_called_once_with(left, right, "weighted")

    def test_framed_split_preserves_existing_cycle(self) -> None:
        left = {"id": 10, "frame": {"x": 0}}
        right = {"id": 20, "frame": {"x": 100}}

        with (
            patch.object(move, "_eligible_windows", return_value=[left, right]),
            patch.object(move, "_split_state", return_value="framed_weighted"),
            patch.object(move, "_set_split_layout") as set_layout,
        ):
            move.split(frame=True)

        set_layout.assert_called_once_with(left, right, "framed_half")

    def test_tile_reuses_window_query_when_falling_back_to_quad(self) -> None:
        wins = [{"id": 10}]
        with (
            patch.object(move, "_eligible_windows", return_value=wins) as eligible,
            patch.object(move, "_quad") as quad,
        ):
            move.tile()

        eligible.assert_called_once_with(limit=4)
        quad.assert_called_once_with(wins)


if __name__ == "__main__":
    unittest.main()
