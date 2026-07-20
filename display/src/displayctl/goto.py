from __future__ import annotations

import subprocess
import time
from typing import Any

from . import apps, timing, yabai


def _normalized(values: set[str]) -> set[str]:
    return {value.casefold() for value in values}


def _eligible(wins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        win
        for win in wins
        if not win.get("is-minimized")
        and not win.get("is-native-fullscreen")
        and win.get("has-ax-reference")
        and win.get("role") == "AXWindow"
        and win.get("subrole") == "AXStandardWindow"
    ]


def app_windows(app_name: str, wins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    app_name_cf = app_name.casefold()
    direct = [win for win in wins if str(win.get("app", "")).casefold() == app_name_cf]
    if direct:
        return direct

    return aliased_app_windows(app_name, wins)


def aliased_app_windows(
    app_name: str, wins: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    names = _normalized(apps.candidate_app_names(app_name) | {app_name})
    return [win for win in wins if str(win.get("app", "")).casefold() in names]


def focusable_app_windows(
    app_name: str, wins: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return app_windows(app_name, _eligible(wins))


def matching_windows(
    app_name: str, wins: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    with timing.timed("matching windows"):
        all_wins = yabai.query_windows() if wins is None else wins
        return focusable_app_windows(app_name, all_wins)


def current_context() -> tuple[int | None, int | None]:
    try:
        win = yabai.query_window()
        return win.get("display"), win.get("space")
    except subprocess.CalledProcessError:
        try:
            display = yabai.query_display()
            return display.get("index"), None
        except subprocess.CalledProcessError:
            return None, None


def best_window(
    wins: list[dict[str, Any]],
    context: tuple[int | None, int | None] | None = None,
) -> dict[str, Any]:
    with timing.timed("choose best window"):
        display_index, space_index = context or current_context()

        def score(win: dict[str, Any]) -> tuple[int, int, int]:
            return (
                0 if space_index is not None and win.get("space") == space_index else 1,
                0
                if display_index is not None and win.get("display") == display_index
                else 1,
                0 if win.get("is-visible") else 1,
            )

        return sorted(wins, key=score)[0]


def activate_app(app_name: str) -> None:
    result = subprocess.run(["open", "-a", app_name], check=False)
    if result.returncode:
        raise SystemExit(f"failed to open {app_name}")


def focus_window(win: dict[str, Any], current_space_index: int | None = None) -> None:
    with timing.timed("focus window"):
        space_index = win.get("space")
        if space_index is not None and not win.get("is-visible"):
            if current_space_index is None:
                _, current_space_index = current_context()
            if current_space_index != space_index:
                yabai.focus_space(space_index)
                time.sleep(0.1)
        yabai.focus(win["id"])


def run(app_name: str) -> None:
    with timing.timed("goto total"):
        wins = matching_windows(app_name)
        if not wins:
            activate_app(app_name)
            return

        if len(wins) == 1:
            focus_window(wins[0])
            return

        context = current_context()
        focus_window(best_window(wins, context), context[1])
