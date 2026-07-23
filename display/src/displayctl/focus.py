from __future__ import annotations

import subprocess
import time
from typing import Any

from . import yabai


def _app_windows(app_name: str) -> list[dict[str, Any]]:
    try:
        return [win for win in yabai.query_windows() if win.get("app") == app_name]
    except subprocess.CalledProcessError:
        return []


def _best_window(wins: list[dict[str, Any]]) -> dict[str, Any] | None:
    focusable = [win for win in wins if yabai.focusable_window(win)]
    visible = [win for win in focusable if win.get("is-visible")]
    if visible:
        return visible[0]
    if focusable:
        return focusable[0]
    return wins[0] if wins else None


def goto(app_name: str) -> None:
    win = _best_window(_app_windows(app_name))
    if win and win.get("id") is not None:
        try:
            yabai.focus(win["id"])
            return
        except subprocess.CalledProcessError:
            pass

    subprocess.run(["open", "-a", app_name], check=False)


def _trigger_app_expose() -> None:
    script = 'tell application "System Events" to key code 125 using control down'
    subprocess.run(["osascript", "-e", script], check=False)


def select(app_name: str) -> None:
    wins = _app_windows(app_name)
    focusable_wins = [win for win in wins if yabai.focusable_window(win)]
    win = _best_window(wins)
    if not win or win.get("id") is None:
        subprocess.run(["open", "-a", app_name], check=False)
        return

    try:
        yabai.focus(win["id"])
    except subprocess.CalledProcessError:
        subprocess.run(["open", "-a", app_name], check=False)
        return

    if len(focusable_wins) <= 1:
        return

    time.sleep(0.15)
    _trigger_app_expose()
