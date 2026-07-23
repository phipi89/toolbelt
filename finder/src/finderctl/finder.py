from __future__ import annotations

import os
import subprocess

from displayctl import yabai


class FinderError(Exception):
    pass


def _osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise FinderError(result.stderr.strip() or "Finder request failed")
    return result.stdout.strip()


def front_path() -> str:
    path = _osascript(
        """
tell application "Finder"
  if (count of Finder windows) is 0 then error "no Finder window open"
  set finderSelection to selection
  if finderSelection is not {} then
    set selectedItem to item 1 of finderSelection
    if class of selectedItem is folder then
      return POSIX path of (selectedItem as alias)
    end if
    return POSIX path of (container of selectedItem as alias)
  end if
  return POSIX path of (target of front Finder window as alias)
end tell
"""
    )
    if not os.path.isdir(path):
        raise FinderError(f"Finder does not point to a folder: {path}")
    return path


def selected_file() -> str:
    path = _osascript(
        """
tell application "Finder"
  set finderSelection to selection
  if finderSelection is {} then error "select a file in Finder"
  set selectedItem to item 1 of finderSelection
  if class of selectedItem is folder then error "selected item is a folder"
  return POSIX path of (selectedItem as alias)
end tell
"""
    )
    if not os.path.isfile(path):
        raise FinderError(f"selected item is not a file: {path}")
    return path


def window_path(window_id: int) -> str:
    path = _osascript(
        f"""
tell application "Finder"
  set finderWindow to first Finder window whose id is {window_id}
  return POSIX path of ((target of finderWindow) as alias)
end tell
"""
    )
    if not os.path.isdir(path):
        raise FinderError(f"Finder window {window_id} does not point to a folder: {path}")
    return path


def left_right_paths() -> tuple[str, str]:
    windows = [
        win
        for win in yabai.query_windows_on_space()
        if win.get("app") == "Finder" and yabai.eligible_window(win)
    ]
    if len(windows) != 2:
        raise FinderError(
            f"expected exactly two visible Finder windows on the current Space, found {len(windows)}"
        )

    left, right = sorted(windows, key=lambda win: win["frame"]["x"])
    if left["frame"]["x"] == right["frame"]["x"]:
        raise FinderError("could not determine which Finder window is on the left")
    return window_path(left["id"]), window_path(right["id"])
