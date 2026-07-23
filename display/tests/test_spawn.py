from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from displayctl import spawn


class SpawnTests(unittest.TestCase):
    def test_target_context_uses_focused_space(self) -> None:
        with (
            patch.object(
                spawn.yabai,
                "query_space",
                return_value={"id": 500, "index": 7, "display": 2},
            ),
            patch.object(spawn.yabai, "query_display") as query_display,
        ):
            self.assertEqual(spawn._target_display_and_space(), (2, 7))

        query_display.assert_not_called()

    def test_app_snapshot_includes_hidden_windows(self) -> None:
        hidden = {"id": 10, "app": "Firefox", "is-visible": False}

        with patch.object(
            spawn.goto.apps, "candidate_app_names", return_value={"Firefox"}
        ):
            self.assertEqual(spawn._app_windows("Firefox", [hidden]), [hidden])

    def test_app_snapshot_includes_exact_and_localized_names(self) -> None:
        wins = [
            {"id": 10, "app": "Calendar"},
            {"id": 20, "app": "Kalender"},
        ]

        with patch.object(
            spawn.goto.apps,
            "candidate_app_names",
            return_value={"Calendar", "Kalender"},
        ):
            self.assertEqual(spawn._app_windows("Calendar", wins), wins)

    def test_target_fallback_uses_display_index(self) -> None:
        error = subprocess.CalledProcessError(1, ["yabai"])
        with (
            patch.object(spawn.yabai, "query_space", side_effect=error),
            patch.object(
                spawn.yabai,
                "query_display",
                return_value={"id": 100, "index": 2},
            ),
        ):
            self.assertEqual(spawn._target_display_and_space(), (2, None))

    def test_move_to_target_prefers_space_index(self) -> None:
        win = {"id": 10, "display": 1, "space": 2}
        with (
            patch.object(spawn.yabai, "move_space") as move_space,
            patch.object(spawn.yabai, "move_display") as move_display,
        ):
            spawn._move_to_target(win, display_index=2, space_index=7)

        move_space.assert_called_once_with(10, 7)
        move_display.assert_not_called()

    def test_visible_window_fast_path_skips_running_check(self) -> None:
        win = {
            "id": 10,
            "app": "Firefox",
            "display": 1,
            "space": 3,
            "is-visible": True,
            "is-minimized": False,
            "is-native-fullscreen": False,
            "has-ax-reference": True,
            "can-move": True,
            "can-resize": True,
            "role": "AXWindow",
            "subrole": "AXStandardWindow",
        }
        with (
            patch.object(spawn, "_target_display_and_space", return_value=(1, 3)),
            patch.object(spawn.yabai, "query_windows", return_value=[win]),
            patch.object(spawn, "_app_is_running") as app_is_running,
            patch.object(spawn, "_focus_window") as focus_window,
        ):
            spawn.run("Firefox")

        app_is_running.assert_not_called()
        focus_window.assert_called_once_with(win)

    def test_empty_space_does_not_focus_existing_window_elsewhere(self) -> None:
        existing = {
            "id": 10,
            "app": "iTerm2",
            "display": 2,
            "space": 8,
            "is-visible": True,
            "is-minimized": False,
            "is-native-fullscreen": False,
            "has-ax-reference": True,
            "can-move": True,
            "can-resize": True,
            "role": "AXWindow",
            "subrole": "AXStandardWindow",
        }
        created = {**existing, "id": 20, "display": 1, "space": 7}

        with (
            patch.object(spawn, "_target_display_and_space", return_value=(1, 7)),
            patch.object(
                spawn.yabai,
                "query_windows",
                side_effect=[[existing], [existing, created]],
            ),
            patch.object(
                spawn.goto.apps, "candidate_app_names", return_value={"iTerm2"}
            ),
            patch.object(spawn, "_app_is_running", return_value=True),
            patch.object(spawn, "_cmd_n", return_value=True) as cmd_n,
            patch.object(spawn, "_focus_window") as focus_window,
            patch.object(spawn.move, "place"),
        ):
            spawn.run("iTerm2")

        cmd_n.assert_called_once_with("iTerm2")
        focus_window.assert_called_once_with(created)

    def test_failed_forced_spawn_exits_nonzero(self) -> None:
        with (
            patch.object(spawn, "_target_display_and_space", return_value=(1, 3)),
            patch.object(spawn.yabai, "query_windows", return_value=[]),
            patch.object(spawn, "_run_spawn_script", return_value=(False, None)),
            self.assertRaises(SystemExit),
        ):
            spawn.run("Finder", "false", force=True)

    def test_forced_spawn_fails_when_no_new_window_appears(self) -> None:
        with (
            patch.object(spawn, "_target_display_and_space", return_value=(1, 3)),
            patch.object(spawn.yabai, "query_windows", return_value=[]),
            patch.object(spawn, "_run_spawn_script", return_value=(True, None)),
            patch.object(spawn.time, "monotonic", side_effect=[0.0, 3.0]),
            self.assertRaises(SystemExit),
        ):
            spawn.run("Finder", "true", force=True)


if __name__ == "__main__":
    unittest.main()
