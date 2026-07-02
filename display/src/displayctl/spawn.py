from __future__ import annotations

import re
import subprocess
import sys
import time
from typing import Any

from . import move, yabai


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def _as_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _app_is_running(app_name: str) -> bool:
    result = _run(
        "osascript",
        "-e",
        f'tell application "System Events" to exists process {_as_string(app_name)}',
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _target_display_and_space() -> tuple[int | None, int | None]:
    try:
        win = yabai.query_window()
        return win.get("display"), win.get("space")
    except subprocess.CalledProcessError:
        try:
            return yabai.query_display().get("id"), None
        except subprocess.CalledProcessError:
            return None, None


def _app_windows(app_name: str) -> list[dict[str, Any]]:
    return [
        win
        for win in yabai.query_windows()
        if win.get("app") == app_name and yabai.eligible_window(win)
    ]


def _visible_window_on_target(
    app_name: str, display_id: int | None, space_id: int | None
) -> dict[str, Any] | None:
    for win in _app_windows(app_name):
        if display_id is not None and win.get("display") != display_id:
            continue
        if space_id is not None and win.get("space") != space_id:
            continue
        return win
    return None


def _focus_window(win: dict[str, Any]) -> None:
    yabai.focus(win["id"])


def _launch_or_focus(app_name: str) -> None:
    subprocess.run(["open", "-a", app_name], check=False)


def _cmd_n(app_name: str) -> None:
    script = f"""
tell application {_as_string(app_name)} to activate
delay 0.1
tell application "System Events"
  tell process {_as_string(app_name)}
    set frontmost to true
    delay 0.3
    keystroke "n" using command down
  end tell
end tell
delay 0.25
"""
    subprocess.run(["osascript", "-e", script], check=False)


def _run_spawn_script(script: str) -> int | None:
    print(f"[spawn] script: {script}", file=sys.stderr)
    result = subprocess.run(
        script, shell=True, text=True, capture_output=True, check=False
    )
    print(f"[spawn] returncode: {result.returncode}", file=sys.stderr)
    if result.stdout:
        print(f"[spawn] stdout:\n{result.stdout}", file=sys.stderr)
    if result.stderr:
        print(f"[spawn] stderr:\n{result.stderr}", file=sys.stderr)
    if result.returncode != 0:
        return None
    match = re.search(r"\d+", result.stdout or "")
    return int(match.group(0)) if match else None


def _focus_finder_window_by_id(window_id: int | None) -> None:
    if not window_id:
        return
    script = f"""
tell application "Finder" to activate
tell application "Finder" to set index of (first Finder window whose id is {window_id}) to 1
"""
    subprocess.run(["osascript", "-e", script], check=False)


def _move_to_display(win: dict[str, Any], display_id: int | None) -> None:
    if display_id is None or win.get("display") == display_id:
        return
    yabai.move_display(win["id"], display_id)


def run(app_name: str, spawn_script: str = "", force: bool = False) -> None:
    display_id, space_id = _target_display_and_space()

    if force and spawn_script:
        pass
    elif _app_is_running(app_name):
        existing_win = _visible_window_on_target(app_name, display_id, space_id)
        if existing_win and not force:
            _focus_window(existing_win)
            return
    else:
        _launch_or_focus(app_name)
        return

    before_ids = {win["id"] for win in _app_windows(app_name)}
    spawned_window_id = _run_spawn_script(spawn_script) if spawn_script else None
    if app_name == "Finder" and spawned_window_id:
        _focus_finder_window_by_id(spawned_window_id)
    elif not spawn_script:
        _cmd_n(app_name)

    deadline = time.monotonic() + 2.0
    selected: dict[str, Any] | None = None
    created_new = False
    while time.monotonic() < deadline:
        for win in _app_windows(app_name):
            if win["id"] not in before_ids:
                selected = win
                created_new = True
                break
        if selected:
            break
        time.sleep(0.1)

    if not selected:
        if spawn_script:
            print("[spawn] no new window detected after spawn_script", file=sys.stderr)
        selected = _visible_window_on_target(app_name, display_id, space_id)
    if not selected:
        return

    _move_to_display(selected, display_id)
    _focus_window(selected)
    if created_new:
        move.place()
