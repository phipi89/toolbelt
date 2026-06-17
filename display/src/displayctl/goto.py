from __future__ import annotations

import subprocess
import time
from typing import Any

from . import apps, yabai


def _normalized(values: set[str]) -> set[str]:
    return {value.casefold() for value in values}


def matching_windows(app_name: str) -> list[dict[str, Any]]:
    names = _normalized(apps.candidate_app_names(app_name))
    return [
        win
        for win in yabai.query_windows()
        if str(win.get("app", "")).casefold() in names
        and not win.get("is-minimized")
        and not win.get("is-native-fullscreen")
        and win.get("has-ax-reference")
        and win.get("role") == "AXWindow"
        and win.get("subrole") == "AXStandardWindow"
    ]


def current_context() -> tuple[int | None, int | None]:
    try:
        win = yabai.query_window()
        return win.get("display"), win.get("space")
    except subprocess.CalledProcessError:
        try:
            display = yabai.query_display()
            return display.get("id"), None
        except subprocess.CalledProcessError:
            return None, None


def focused_space_index(display_id: int | None) -> int | None:
    spaces = yabai.query_spaces()
    for space in spaces:
        if space.get("has-focus") and (display_id is None or space.get("display") == display_id):
            return space.get("index")
    for space in spaces:
        if space.get("is-visible") and (display_id is None or space.get("display") == display_id):
            return space.get("index")
    return None


def best_window(wins: list[dict[str, Any]]) -> dict[str, Any]:
    display_id, space_id = current_context()

    def score(win: dict[str, Any]) -> tuple[int, int, int]:
        return (
            0 if space_id is not None and win.get("space") == space_id else 1,
            0 if display_id is not None and win.get("display") == display_id else 1,
            0 if win.get("is-visible") else 1,
        )

    return sorted(wins, key=score)[0]


def activate_app(app_name: str) -> None:
    subprocess.run(["open", "-a", app_name], check=False)


def focus_window(win: dict[str, Any]) -> None:
    space_id = win.get("space")
    display_id = win.get("display")
    if space_id is not None:
        before_index = focused_space_index(display_id)
        if before_index != space_id:
            yabai.focus_space(space_id)
            time.sleep(0.1)
    yabai.focus(win["id"])


def run(app_name: str) -> None:
    wins = matching_windows(app_name)
    if not wins:
        activate_app(app_name)
        return

    focus_window(best_window(wins))
