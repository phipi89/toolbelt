from __future__ import annotations

from . import goto, timing, yabai


def run(app_name: str) -> None:
    with timing.timed("move-here total"):
        wins = goto.matching_windows(app_name)
        if not wins:
            return

        if len(wins) == 1:
            context = (None, None)
            win = wins[0]
        else:
            context = goto.current_context()
            win = goto.best_window(wins, context)

        space = yabai.query_space("mouse")
        if space["is-native-fullscreen"]:
            return

        if win.get("space") == space["index"] and win.get("is-visible"):
            goto.focus_window(win, context[1])
            return

        yabai.move_space(win["id"], space["index"])
        goto.focus_window({**win, "space": space["index"], "is-visible": True})
