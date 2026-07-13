from __future__ import annotations

import json
import subprocess
from typing import Any

from . import timing


def run(*args: str) -> str:
    return timing.time_call(
        " ".join(args[:4]),
        subprocess.run,
        args,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def yabai(*args: str) -> str:
    return run("yabai", "-m", *args)


def _json_query(*args: str):
    output = yabai(*args).strip()
    return json.loads(output)


def query_window() -> dict[str, Any]:
    return _json_query("query", "--windows", "--window")


def query_windows_on_space() -> list[dict[str, Any]]:
    return _json_query("query", "--windows", "--space")


def query_windows() -> list[dict[str, Any]]:
    return _json_query("query", "--windows")


def query_display(selector: str | None = None) -> dict[str, Any]:
    args = ["query", "--displays", "--display"]
    if selector:
        args.append(selector)
    return _json_query(*args)


def query_spaces() -> list[dict[str, Any]]:
    return _json_query("query", "--spaces")


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
    timing.time_call("yabai window --grid", subprocess.run, ["yabai", "-m", "window", str(window_id), "--grid", spec], check=True)


def focus(window_id: int) -> None:
    timing.time_call("yabai window --focus", subprocess.run, ["yabai", "-m", "window", str(window_id), "--focus"], check=True)


def focus_space(space_id: int) -> None:
    timing.time_call("yabai space --focus", subprocess.run, ["yabai", "-m", "space", "--focus", str(space_id)], check=True)


def move_display(window_id: int, display_id: int) -> None:
    timing.time_call("yabai window --display", subprocess.run, ["yabai", "-m", "window", str(window_id), "--display", str(display_id)], check=True)


def move_abs(window_id: int, x: float, y: float) -> None:
    timing.time_call("yabai window --move", subprocess.run, ["yabai", "-m", "window", str(window_id), "--move", f"abs:{x:g}:{y:g}"], check=True)


def resize_abs(window_id: int, width: float, height: float) -> None:
    timing.time_call("yabai window --resize", subprocess.run, ["yabai", "-m", "window", str(window_id), "--resize", f"abs:{width:g}:{height:g}"], check=True)


def set_frame(window_id: int, frame: dict[str, float]) -> None:
    resize_abs(window_id, frame["w"], frame["h"])
    move_abs(window_id, frame["x"], frame["y"])


def close(window_id: int) -> None:
    timing.time_call("yabai window --close", subprocess.run, ["yabai", "-m", "window", str(window_id), "--close"], check=True)


def move_space(window_id: int, space_id: int) -> None:
    timing.time_call("yabai window --space", subprocess.run, ["yabai", "-m", "window", str(window_id), "--space", str(space_id)], check=True)


