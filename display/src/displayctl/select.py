from __future__ import annotations

import subprocess
import time

from . import goto


def _app_expose() -> None:
    subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to key code 125 using control down'],
        check=False,
    )


def run(app_name: str) -> None:
    wins = goto.matching_windows(app_name)
    if not wins:
        goto.activate_app(app_name)
        return

    if len(wins) == 1:
        goto.focus_window(wins[0])
        return

    visible_wins = [win for win in wins if win.get("is-visible")]
    if visible_wins:
        goto.focus_window(goto.best_window(visible_wins))
        return

    goto.activate_app(app_name)
    time.sleep(0.15)
    _app_expose()
