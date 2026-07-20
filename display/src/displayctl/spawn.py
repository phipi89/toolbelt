from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from typing import Any

from . import goto, move, timing, yabai


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def _debug(message: str) -> None:
    if os.environ.get("DISPLAY_DEBUG"):
        print(message, file=sys.stderr)


def _as_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _app_is_running(app_name: str) -> bool:
    result = timing.time_call(
        "app is running",
        _run,
        "osascript",
        "-e",
        f"application {_as_string(app_name)} is running",
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _target_display_and_space(
    wins: list[dict[str, Any]] | None = None,
) -> tuple[int | None, int | None]:
    if wins is not None:
        focused = next((win for win in wins if win.get("has-focus")), None)
        if focused:
            return focused.get("display"), focused.get("space")
        try:
            return yabai.query_display().get("index"), None
        except subprocess.CalledProcessError:
            return None, None

    try:
        win = yabai.query_window()
        return win.get("display"), win.get("space")
    except subprocess.CalledProcessError:
        try:
            return yabai.query_display().get("index"), None
        except subprocess.CalledProcessError:
            return None, None


def _app_windows(
    app_name: str, wins: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    all_wins = yabai.query_windows() if wins is None else wins
    return goto.aliased_app_windows(app_name, all_wins)


def _visible_window_on_target(
    app_name: str,
    display_index: int | None,
    space_index: int | None,
    wins: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for win in goto.focusable_app_windows(app_name, wins):
        if display_index is not None and win.get("display") != display_index:
            continue
        if space_index is not None and win.get("space") != space_index:
            continue
        return win
    return None


def _focus_window(win: dict[str, Any]) -> None:
    yabai.focus(win["id"])


def _launch_or_focus(app_name: str) -> bool:
    return subprocess.run(["open", "-a", app_name], check=False).returncode == 0


def _cmd_n(app_name: str) -> bool:
    script = f"""
tell application {_as_string(app_name)} to activate
delay 0.1
tell application "System Events"
  tell process {_as_string(app_name)}
    set frontmost to true
    delay 0.1
    keystroke "n" using command down
  end tell
end tell
"""
    return subprocess.run(["osascript", "-e", script], check=False).returncode == 0


def _run_spawn_script(script: str) -> tuple[bool, int | None]:
    _debug(f"[spawn] script: {script}")
    result = subprocess.run(
        script, shell=True, text=True, capture_output=True, check=False
    )
    _debug(f"[spawn] returncode: {result.returncode}")
    if result.stdout:
        _debug(f"[spawn] stdout:\n{result.stdout}")
    if result.stderr:
        _debug(f"[spawn] stderr:\n{result.stderr}")
    if result.returncode != 0:
        return False, None
    match = re.search(r"\d+", result.stdout or "")
    return True, int(match.group(0)) if match else None


def _focus_finder_window_by_id(window_id: int | None) -> None:
    if not window_id:
        return
    script = f"""
tell application "Finder" to activate
tell application "Finder" to set index of (first Finder window whose id is {window_id}) to 1
"""
    subprocess.run(["osascript", "-e", script], check=False)


def _move_to_target(
    win: dict[str, Any], display_index: int | None, space_index: int | None
) -> None:
    if space_index is not None:
        if win.get("space") != space_index:
            yabai.move_space(win["id"], space_index)
        return
    if display_index is not None and win.get("display") != display_index:
        yabai.move_display(win["id"], display_index)


def _run_spawn(app_name: str, spawn_script: str, force: bool) -> None:
    initial_windows = yabai.query_windows()
    display_index, space_index = _target_display_and_space(initial_windows)

    if not force:
        existing_win = _visible_window_on_target(
            app_name, display_index, space_index, initial_windows
        )
        if existing_win:
            _focus_window(existing_win)
            return

    if not (force and spawn_script) and not _app_is_running(app_name):
        if not _launch_or_focus(app_name):
            raise SystemExit(f"failed to launch {app_name}")
        return

    before_ids = {win["id"] for win in _app_windows(app_name, initial_windows)}
    spawned_window_id = None
    with timing.timed("spawn command"):
        if spawn_script:
            spawn_ok, spawned_window_id = _run_spawn_script(spawn_script)
        else:
            spawn_ok = _cmd_n(app_name)
    if not spawn_ok:
        raise SystemExit(f"failed to create a new {app_name} window")

    if app_name == "Finder" and spawned_window_id:
        _focus_finder_window_by_id(spawned_window_id)

    deadline = time.monotonic() + 2.0
    selected: dict[str, Any] | None = None
    created_new = False
    latest_windows = initial_windows
    with timing.timed("wait for new window"):
        while time.monotonic() < deadline:
            latest_windows = yabai.query_windows()
            for win in goto.focusable_app_windows(app_name, latest_windows):
                if win["id"] not in before_ids:
                    selected = win
                    created_new = True
                    break
            if selected:
                break
            time.sleep(0.1)

    if not selected and not force:
        selected = _visible_window_on_target(
            app_name, display_index, space_index, latest_windows
        )
    if not selected:
        raise SystemExit(f"no new {app_name} window appeared")

    _move_to_target(selected, display_index, space_index)
    _focus_window(selected)
    if created_new:
        move.place()


def run(app_name: str, spawn_script: str = "", force: bool = False) -> None:
    with timing.timed("spawn total"):
        _run_spawn(app_name, spawn_script, force)
