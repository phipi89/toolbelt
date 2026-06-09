from __future__ import annotations

import json
import subprocess
from typing import Any


def run(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def yabai(*args: str) -> str:
    return run("yabai", "-m", *args)


def query_window() -> dict[str, Any]:
    return json.loads(yabai("query", "--windows", "--window"))


def query_windows_on_space() -> list[dict[str, Any]]:
    return json.loads(yabai("query", "--windows", "--space"))


def query_windows() -> list[dict[str, Any]]:
    return json.loads(yabai("query", "--windows"))


def query_display() -> dict[str, Any]:
    return json.loads(yabai("query", "--displays", "--display"))


def eligible_window(win: dict[str, Any]) -> bool:
    return bool(
        win.get("is-visible")
        and not win.get("is-minimized")
        and not win.get("is-native-fullscreen")
        and win.get("has-ax-reference")
        and win.get("can-move")
        and win.get("can-resize")
        and win.get("role") == "AXWindow"
        and win.get("subrole") == "AXStandardWindow"
    )


def grid(window_id: int, spec: str) -> None:
    subprocess.run(["yabai", "-m", "window", str(window_id), "--grid", spec], check=True)


def focus(window_id: int) -> None:
    subprocess.run(["yabai", "-m", "window", str(window_id), "--focus"], check=True)


def move_display(window_id: int, display_id: int) -> None:
    subprocess.run(["yabai", "-m", "window", str(window_id), "--display", str(display_id)], check=True)


def move_abs(window_id: int, x: float, y: float) -> None:
    subprocess.run(["yabai", "-m", "window", str(window_id), "--move", f"abs:{x:g}:{y:g}"], check=True)
