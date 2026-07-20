from __future__ import annotations

import unittest
import subprocess
from unittest.mock import patch

from displayctl import goto


class GotoTests(unittest.TestCase):
    def test_context_fallback_uses_display_index(self) -> None:
        error = subprocess.CalledProcessError(1, ["yabai"])
        with (
            patch.object(goto.yabai, "query_window", side_effect=error),
            patch.object(
                goto.yabai,
                "query_display",
                return_value={"id": 100, "index": 2},
            ),
        ):
            self.assertEqual(goto.current_context(), (2, None))

    def test_focus_visible_window_does_not_query_context(self) -> None:
        win = {"id": 10, "space": 3, "is-visible": True}

        with (
            patch.object(goto, "current_context") as current_context,
            patch.object(goto.yabai, "focus") as focus,
        ):
            goto.focus_window(win)

        current_context.assert_not_called()
        focus.assert_called_once_with(10)

    def test_app_windows_falls_back_to_localized_names(self) -> None:
        wins = [{"id": 10, "app": "Kalender"}]

        with patch.object(
            goto.apps, "candidate_app_names", return_value={"Calendar", "Kalender"}
        ):
            self.assertEqual(goto.app_windows("Calendar", wins), wins)

    def test_focusable_matching_filters_before_exact_name_precedence(self) -> None:
        exact_but_minimized = {"id": 10, "app": "Calendar", "is-minimized": True}
        localized = {
            "id": 20,
            "app": "Kalender",
            "is-minimized": False,
            "is-native-fullscreen": False,
            "has-ax-reference": True,
            "role": "AXWindow",
            "subrole": "AXStandardWindow",
        }

        with patch.object(
            goto.apps, "candidate_app_names", return_value={"Calendar", "Kalender"}
        ):
            self.assertEqual(
                goto.focusable_app_windows(
                    "Calendar", [exact_but_minimized, localized]
                ),
                [localized],
            )


if __name__ == "__main__":
    unittest.main()
