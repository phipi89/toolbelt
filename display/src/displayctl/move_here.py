from __future__ import annotations

from typing import Any

from . import goto, timing, yabai


def _target_space() -> dict[str, Any] | None:
    display = yabai.query_display("mouse")
    display_index = display["index"]
    for space in yabai.query_spaces():
        if (
            space["display"] == display_index
            and space["is-visible"]
            and not space["is-native-fullscreen"]
        ):
            return space
    return None


def run(app_name: str) -> None:
    with timing.timed("move-here total"):
        wins = goto.matching_windows(app_name)
        if not wins:
            return

        win = goto.best_window(wins)

        space = _target_space()
        if space is None:
            return

        if win.get("space") == space["id"] and win.get("is-visible"):
            goto.focus_window(win)
            return

        yabai.move_space(win["id"], space["index"])
        goto.focus_window({**win, "space": space["id"], "is-visible": True})
