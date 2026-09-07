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

    def test_center_steps_sizes_in_both_directions(self) -> None:
        display = {
            "id": 1,
            "index": 1,
            "frame": {"x": 0, "y": 0, "w": 1000, "h": 800},
        }
        transitions = {
            False: {
                None: 90,
                **{size: min(size + 10, 100) for size in range(10, 101, 10)},
            },
            True: {
                None: 80,
                **{size: max(size - 10, 10) for size in range(10, 101, 10)},
            },
        }

        for reverse, sizes in transitions.items():
            for current, target in sizes.items():
                with self.subTest(reverse=reverse, current=current):
                    size = 73 if current is None else current
                    frame = {
                        "x": (100 - size) * 5,
                        "y": 0,
                        "w": size * 10,
                        "h": 800,
                    }
                    win = {"id": 10, "frame": frame}
                    start = (100 - target) / 2
                    expected = f"100:100:{start:g}:{start:g}:{target}:{target}"

                    with (
                        patch.object(
                            move.yabai, "query_windows_on_space", return_value=[win]
                        ),
                        patch.object(move, "_target_window", return_value=win),
                        patch.object(move.yabai, "query_display", return_value=display),
                        patch.object(move.yabai, "grid") as grid,
                    ):
                        move.center(reverse=reverse)

                    grid.assert_called_once_with(10, expected)

    def test_reduce_places_target_in_bottom_right(self) -> None:
        win = {"id": 10}

        with (
            patch.object(move, "_target_window", return_value=win),
            patch.object(move.yabai, "grid") as grid,
        ):
            move.reduce()

        grid.assert_called_once_with(10, "10:10:7:7:3:3")

    def test_place_keep_size_moves_only_the_target(self) -> None:
        win = {
            "id": 10,
            "display": 1,
            "frame": {"x": 0, "y": 0, "w": 20, "h": 20},
        }
        other = {
            "id": 20,
            "display": 1,
            "frame": {"x": 0, "y": 0, "w": 20, "h": 20},
        }
        display = {"index": 1, "frame": {"x": 0, "y": 0, "w": 100, "h": 100}}

        with (
            patch.object(move, "_target_window", return_value=win),
            patch.object(move.yabai, "query_display", return_value=display),
            patch.object(move, "_eligible_windows", return_value=[win, other]),
            patch.object(move.yabai, "move_abs") as move_abs,
            patch.object(move.yabai, "grid") as grid,
            patch.object(move.yabai, "set_frame") as set_frame,
        ):
            move.place(keep_size=True)

        move_abs.assert_called_once_with(10, 0, 80)
        grid.assert_not_called()
        set_frame.assert_not_called()

    def test_place_toggle_switches_between_cooptimal_positions(self) -> None:
        left = {"x": 0, "y": 0, "w": 20, "h": 20}
        right = {"x": 80, "y": 0, "w": 20, "h": 20}
        other = {"id": 20, "display": 1, "frame": {"x": 40, "y": 40, "w": 20, "h": 20}}
        display = {"index": 1, "frame": {"x": 0, "y": 0, "w": 100, "h": 100}}

        for current, expected in ((left, right), (right, left)):
            with self.subTest(current=current):
                win = {"id": 10, "display": 1, "frame": current}
                with (
                    patch.object(move, "_target_window", return_value=win),
                    patch.object(move.yabai, "query_display", return_value=display),
                    patch.object(move, "_eligible_windows", return_value=[win, other]),
                    patch.object(move, "_place_candidates", return_value=[left, right]),
                    patch.object(move.yabai, "move_abs") as move_abs,
                ):
                    move.place(keep_size=True, toggle=True)

                move_abs.assert_called_once_with(10, expected["x"], expected["y"])

    def test_place_toggle_switches_between_best_and_next_best(self) -> None:
        best = {"x": 0, "y": 0, "w": 20, "h": 20}
        next_best = {"x": 80, "y": 0, "w": 20, "h": 20}
        other = {"id": 20, "display": 1, "frame": next_best}
        display = {"index": 1, "frame": {"x": 0, "y": 0, "w": 100, "h": 100}}

        for current, expected in ((best, next_best), (next_best, best)):
            with self.subTest(current=current):
                win = {"id": 10, "display": 1, "frame": current}
                with (
                    patch.object(move, "_target_window", return_value=win),
                    patch.object(move.yabai, "query_display", return_value=display),
                    patch.object(move, "_eligible_windows", return_value=[win, other]),
                    patch.object(
                        move, "_place_candidates", return_value=[best, next_best]
                    ),
                    patch.object(move.yabai, "move_abs") as move_abs,
                ):
                    move.place(keep_size=True, toggle=True)

                move_abs.assert_called_once_with(10, expected["x"], expected["y"])

    def test_place_toggle_keeps_unique_optimum_in_place(self) -> None:
        current = {"x": 0, "y": 0, "w": 20, "h": 20}
        win = {"id": 10, "display": 1, "frame": current}
        other = {"id": 20, "display": 1, "frame": {"x": 50, "y": 50, "w": 20, "h": 20}}
        display = {"index": 1, "frame": {"x": 0, "y": 0, "w": 100, "h": 100}}

        with (
            patch.object(move, "_target_window", return_value=win),
            patch.object(move.yabai, "query_display", return_value=display),
            patch.object(move, "_eligible_windows", return_value=[win, other]),
            patch.object(move, "_place_candidates", return_value=[current]),
            patch.object(move.yabai, "move_abs") as move_abs,
        ):
            move.place(keep_size=True, toggle=True)

        move_abs.assert_not_called()

    def test_place_keep_size_prefers_an_optimal_display_corner(self) -> None:
        win = {
            "id": 10,
            "display": 1,
            "frame": {"x": 40, "y": 40, "w": 20, "h": 20},
        }
        corner = {"x": 0, "y": 0, "w": 20, "h": 20}
        nearby = {"x": 20, "y": 20, "w": 20, "h": 20}
        other = {"id": 20, "display": 1, "frame": win["frame"]}
        display = {"index": 1, "frame": {"x": 0, "y": 0, "w": 100, "h": 100}}

        with (
            patch.object(move, "_target_window", return_value=win),
            patch.object(move.yabai, "query_display", return_value=display),
            patch.object(move, "_eligible_windows", return_value=[win, other]),
            patch.object(move, "_place_candidates", return_value=[nearby, corner]),
            patch.object(move.yabai, "move_abs") as move_abs,
        ):
            move.place(keep_size=True)

        move_abs.assert_called_once_with(10, 0, 0)

    def test_place_toggle_falls_back_when_at_only_optimal_corner(self) -> None:
        corner = {"x": 0, "y": 0, "w": 20, "h": 20}
        nearby = {"x": 20, "y": 20, "w": 20, "h": 20}
        win = {"id": 10, "display": 1, "frame": corner}
        other = {"id": 20, "display": 1, "frame": {"x": 50, "y": 50, "w": 20, "h": 20}}
        display = {"index": 1, "frame": {"x": 0, "y": 0, "w": 100, "h": 100}}

        with (
            patch.object(move, "_target_window", return_value=win),
            patch.object(move.yabai, "query_display", return_value=display),
            patch.object(move, "_eligible_windows", return_value=[win, other]),
            patch.object(move, "_place_candidates", return_value=[corner, nearby]),
            patch.object(move.yabai, "move_abs") as move_abs,
        ):
            move.place(keep_size=True, toggle=True)

        move_abs.assert_called_once_with(10, 20, 20)

    def test_place_toggle_does_nothing_without_other_windows(self) -> None:
        win = {
            "id": 10,
            "display": 1,
            "frame": {"x": 20, "y": 20, "w": 20, "h": 20},
        }
        display = {"index": 1, "frame": {"x": 0, "y": 0, "w": 100, "h": 100}}

        with (
            patch.object(move, "_target_window", return_value=win),
            patch.object(move.yabai, "query_display", return_value=display),
            patch.object(move, "_eligible_windows", return_value=[win]),
            patch.object(move.yabai, "move_abs") as move_abs,
        ):
            move.place(keep_size=True, toggle=True)

        move_abs.assert_not_called()

    def test_place_default_resizes_with_absolute_frame(self) -> None:
        win = {
            "id": 10,
            "display": 1,
            "frame": {"x": 0, "y": 0, "w": 20, "h": 20},
        }
        display = {"index": 1, "frame": {"x": 0, "y": 0, "w": 100, "h": 100}}

        with (
            patch.object(move, "_target_window", return_value=win),
            patch.object(move.yabai, "query_display", return_value=display),
            patch.object(move, "_eligible_windows", return_value=[win]),
            patch.object(move.yabai, "set_frame") as set_frame,
            patch.object(move.yabai, "grid") as grid,
        ):
            move.place()

        set_frame.assert_called_once()
        self.assertEqual(
            set_frame.call_args.args, (10, {"x": 0, "y": 0, "w": 67, "h": 67})
        )
        grid.assert_not_called()

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
