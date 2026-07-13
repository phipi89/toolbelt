from __future__ import annotations

import argparse
import os
import plistlib
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from displayctl import yabai


LOCAL_ROOT = Path(os.environ.get("TOOLBELT_LOCAL", Path.home() / ".toolbelt-local"))
TOOLBELT_ROOT = Path(os.environ.get("TOOLBELT", Path.home() / "toolbelt"))
LOCAL_PATH = LOCAL_ROOT / "setup" / "setups.yaml"
GLOBAL_PATH = TOOLBELT_ROOT / "config" / "setup" / "setups.yaml"
APP_ROOTS = (Path("/Applications"), Path("/System/Applications"), Path.home() / "Applications")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def _osascript(script: str) -> str:
    return _run("osascript", "-e", script).stdout.strip()


def _as_applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _normalized_app_name(value: str) -> str:
    return value.strip().removesuffix(".app").casefold()


def _mdls_display_name(app_path: Path) -> str | None:
    result = _run("mdls", "-raw", "-name", "kMDItemDisplayName", str(app_path))
    value = result.stdout.strip().strip('"')
    if result.returncode != 0 or not value or value == "(null)":
        return None
    return value


def _app_metadata(app_path: Path) -> dict[str, Any]:
    names = {app_path.name, app_path.stem}
    bundle_id = None
    info_path = app_path / "Contents" / "Info.plist"
    if info_path.exists():
        try:
            with info_path.open("rb") as f:
                info = plistlib.load(f)
        except Exception:
            info = {}
        bundle_id = info.get("CFBundleIdentifier")
        for key in ("CFBundleDisplayName", "CFBundleName", "CFBundleExecutable"):
            value = info.get(key)
            if value:
                names.add(str(value))
    display_name = _mdls_display_name(app_path)
    if display_name:
        names.add(display_name)
    return {"path": str(app_path), "bundle_id": bundle_id, "names": names}


def _known_apps() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in APP_ROOTS:
        if not root.exists():
            continue
        for app_path in sorted(root.glob("*.app")):
            if app_path in seen:
                continue
            seen.add(app_path)
            found.append(_app_metadata(app_path))
    return found


def _resolve_app(app_name: str, known_apps: list[dict[str, Any]]) -> dict[str, str]:
    wanted = _normalized_app_name(app_name)
    for app in known_apps:
        names = {_normalized_app_name(name) for name in app["names"]}
        if wanted not in names:
            continue
        resolved = {"app_path": app["path"]}
        if app.get("bundle_id"):
            resolved["bundle_id"] = app["bundle_id"]
        return resolved
    return {}


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"setups": {}}
    with path.open() as f:
        return yaml.safe_load(f) or {"setups": {}}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _storage_path(global_: bool) -> Path:
    return GLOBAL_PATH if global_ else LOCAL_PATH


def _confirm_overwrite(name: str, path: Path) -> bool:
    try:
        answer = input(f"setup '{name}' already exists in {path}. Overwrite? [y/N] ")
    except EOFError:
        return False
    return answer.strip().casefold() in {"y", "yes"}


def _current_context() -> tuple[int | None, int | None, int | None]:
    try:
        win = yabai.query_window()
        return win.get("id"), win.get("display"), win.get("space")
    except subprocess.CalledProcessError:
        try:
            display = yabai.query_display()
            return None, display.get("id"), None
        except subprocess.CalledProcessError:
            return None, None, None


def _is_launcher_window(win: dict[str, Any], launcher_id: int | None) -> bool:
    return bool(launcher_id and win.get("id") == launcher_id and win.get("app") == "iTerm2")


def _scope_windows(launcher_id: int | None, display_id: int | None, space_id: int | None) -> list[dict[str, Any]]:
    wins = []
    for win in yabai.query_windows():
        if not yabai.eligible_window(win):
            continue
        if _is_launcher_window(win, launcher_id):
            continue
        if display_id is not None and win.get("display") != display_id:
            continue
        if space_id is not None and win.get("space") != space_id:
            continue
        wins.append(win)
    return wins


def _frame(win: dict[str, Any]) -> dict[str, float]:
    frame = win["frame"]
    return {key: frame[key] for key in ("x", "y", "w", "h")}


def _front_finder_cwd() -> str | None:
    script = 'tell application "Finder" to if (count of Finder windows) > 0 then POSIX path of (target of front Finder window as alias)'
    return _osascript(script) or None


def _front_iterm_cwd() -> str | None:
    script = 'tell application "iTerm2" to tell current session of current window to get variable named "session.path"'
    return _osascript(script) or None


def _cwd_for_window(win: dict[str, Any]) -> str | None:
    app = win.get("app")
    if app not in {"Finder", "iTerm2"}:
        return None
    try:
        yabai.focus(win["id"])
        time.sleep(0.1)
    except subprocess.CalledProcessError:
        return None
    if app == "Finder":
        return _front_finder_cwd()
    return _front_iterm_cwd()


def _entry_for_window(win: dict[str, Any], known_apps: list[dict[str, Any]]) -> dict[str, Any]:
    entry: dict[str, Any] = {"app": win["app"], "frame": _frame(win)}
    entry.update(_resolve_app(win["app"], known_apps))
    cwd = _cwd_for_window(win)
    if cwd:
        entry["cwd"] = cwd
    return entry


def save_setup(name: str, global_: bool) -> None:
    path = _storage_path(global_)
    data = _load(path)
    if name in data.get("setups", {}) and not _confirm_overwrite(name, path):
        print("not overwritten")
        return

    launcher_id, display_id, space_id = _current_context()
    wins = _scope_windows(launcher_id, display_id, space_id)
    known_apps = _known_apps()
    entries = [_entry_for_window(win, known_apps) for win in wins]
    if launcher_id:
        try:
            yabai.focus(launcher_id)
        except subprocess.CalledProcessError:
            pass

    data.setdefault("setups", {})[name] = {"windows": entries}
    _save(path, data)
    print(f"saved {name} to {path}")


def _setup(name: str) -> tuple[dict[str, Any], Path]:
    local = _load(LOCAL_PATH).get("setups", {})
    if name in local:
        return local[name], LOCAL_PATH
    global_setups = _load(GLOBAL_PATH).get("setups", {})
    if name in global_setups:
        return global_setups[name], GLOBAL_PATH
    raise SystemExit(f"unknown setup: {name}")


def _app_matches(win: dict[str, Any], app_name: str) -> bool:
    win_app = str(win.get("app", ""))
    return win_app.casefold() == app_name.casefold()


def _window_matches_entry(win: dict[str, Any], entry: dict[str, Any], cwd_cache: dict[int, str | None]) -> bool:
    if not _app_matches(win, entry["app"]):
        return False
    wanted_cwd = entry.get("cwd")
    if not wanted_cwd or entry["app"] not in {"Finder", "iTerm2"}:
        return True
    win_id = win["id"]
    if win_id not in cwd_cache:
        cwd_cache[win_id] = _cwd_for_window(win)
    return cwd_cache[win_id] == wanted_cwd


def _match_windows(entries: list[dict[str, Any]], wins: list[dict[str, Any]]) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    remaining = wins.copy()
    cwd_cache: dict[int, str | None] = {}
    matched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    missing: list[dict[str, Any]] = []
    for entry in entries:
        match = next((win for win in remaining if _window_matches_entry(win, entry, cwd_cache)), None)
        if match is None:
            missing.append(entry)
            continue
        remaining.remove(match)
        matched.append((entry, match))
    return matched, missing, remaining


def _open_entry(entry: dict[str, Any]) -> None:
    app = entry["app"]
    cwd = entry.get("cwd")
    if app == "Finder" and cwd:
        subprocess.run(["open", cwd], check=False)
        return
    if app == "iTerm2":
        if cwd:
            command = "cd " + shlex.quote(cwd)
            script = f'''
tell application "iTerm2"
  set newWindow to (create window with default profile)
  tell current session of newWindow to write text {_as_applescript_string(command)}
end tell
'''
        else:
            script = 'tell application "iTerm2" to create window with default profile'
        subprocess.run(["osascript", "-e", script], check=False)
        return
    if entry.get("bundle_id"):
        subprocess.run(["open", "-b", entry["bundle_id"]], check=False)
        return
    if entry.get("app_path"):
        subprocess.run(["open", entry["app_path"]], check=False)
        return
    subprocess.run(["open", "-a", app], check=False)


def _wait_for_entry(entry: dict[str, Any], launcher_id: int | None, display_id: int | None, space_id: int | None, used_ids: set[int]) -> dict[str, Any] | None:
    deadline = time.monotonic() + 4.0
    cwd_cache: dict[int, str | None] = {}
    while time.monotonic() < deadline:
        for win in _scope_windows(launcher_id, display_id, space_id):
            if win["id"] in used_ids:
                continue
            if _window_matches_entry(win, entry, cwd_cache):
                return win
        time.sleep(0.15)
    return None


def _restore_frame(win: dict[str, Any], entry: dict[str, Any]) -> None:
    frame = entry.get("frame")
    if not frame:
        return
    try:
        yabai.set_frame(win["id"], frame)
    except subprocess.CalledProcessError as exc:
        print(f"setup: failed to restore {entry['app']}: {exc}", file=sys.stderr)


def open_setup(name: str) -> None:
    setup, path = _setup(name)
    entries = setup.get("windows", [])
    launcher_id, display_id, space_id = _current_context()
    wins = _scope_windows(launcher_id, display_id, space_id)
    matched, missing, extra = _match_windows(entries, wins)

    for win in extra:
        try:
            yabai.close(win["id"])
        except subprocess.CalledProcessError as exc:
            print(f"setup: failed to close {win.get('app')}: {exc}", file=sys.stderr)

    used_ids = {win["id"] for _, win in matched}
    for entry in missing:
        _open_entry(entry)
        win = _wait_for_entry(entry, launcher_id, display_id, space_id, used_ids)
        if win is None:
            print(f"setup: opened {entry['app']} but did not find a matching window", file=sys.stderr)
            continue
        used_ids.add(win["id"])
        matched.append((entry, win))

    for entry, win in matched:
        _restore_frame(win, entry)

    if launcher_id:
        try:
            yabai.focus(launcher_id)
        except subprocess.CalledProcessError:
            pass
    print(f"opened {name} from {path}")


def list_setups() -> None:
    local = _load(LOCAL_PATH).get("setups", {})
    global_setups = _load(GLOBAL_PATH).get("setups", {})
    names = sorted(set(local) | set(global_setups))
    for name in names:
        if name in local:
            source = "local"
        else:
            source = "global"
        print(f"{name}\t{source}")


def _existing_setup_names() -> list[str]:
    local = _load(LOCAL_PATH).get("setups", {})
    global_setups = _load(GLOBAL_PATH).get("setups", {})
    return sorted(set(local) | set(global_setups))


def _scoped_app_names() -> list[str]:
    launcher_id, display_id, space_id = _current_context()
    seen: set[str] = set()
    names: list[str] = []
    for win in _scope_windows(launcher_id, display_id, space_id):
        app = str(win.get("app", "")).strip()
        key = app.casefold()
        if not app or key in seen:
            continue
        seen.add(key)
        names.append(app)
    return names


def suggest_name() -> None:
    app_names = _scoped_app_names()
    if not app_names:
        print("no windows found on current screen/space", file=sys.stderr)
        return

    existing_names = _existing_setup_names()
    prompt = """
Suggest 8 concise names for a saved desktop/window setup.

Rules:
- Output only the names, one per line.
- Use lowercase kebab-case or a single short lowercase word.
- Prefer names that describe the activity or context, not just the app names.
- Avoid existing setup names.

Current apps:
{apps}

Existing setup names:
{existing}
""".strip().format(
        apps="\n".join(f"- {name}" for name in app_names),
        existing="\n".join(f"- {name}" for name in existing_names) if existing_names else "- none",
    )

    try:
        print("asking opencode for setup name suggestions...", file=sys.stderr)
        result = subprocess.run(
            ["opencode", "run", prompt],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError:
        raise SystemExit("opencode not found")
    except subprocess.TimeoutExpired:
        raise SystemExit("opencode timed out")

    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    print(result.stdout.strip())


def edit_setups(global_: bool) -> None:
    path = _storage_path(global_)
    if not path.exists():
        _save(path, {"setups": {}})
    subprocess.run(["open", "-t", str(path)], check=False)


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--suggest-name"]:
        argv = ["suggest-name"]
    if argv == ["--edit"]:
        argv = ["edit"]
    if argv and argv[0] not in {"save", "open", "list", "suggest", "suggest-name", "edit", "-h", "--help"}:
        argv = ["open", *argv]

    parser = argparse.ArgumentParser(prog="setup")
    subparsers = parser.add_subparsers(dest="command", required=True)

    save_parser = subparsers.add_parser("save")
    save_parser.add_argument("--global", dest="global_", action="store_true")
    save_parser.add_argument("name")

    open_parser = subparsers.add_parser("open")
    open_parser.add_argument("name")

    subparsers.add_parser("list")
    subparsers.add_parser("suggest-name", aliases=["suggest"])

    edit_parser = subparsers.add_parser("edit")
    edit_parser.add_argument("--global", dest="global_", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "save":
        save_setup(args.name, args.global_)
    elif args.command == "open":
        open_setup(args.name)
    elif args.command == "list":
        list_setups()
    elif args.command in {"suggest-name", "suggest"}:
        suggest_name()
    elif args.command == "edit":
        edit_setups(args.global_)


if __name__ == "__main__":
    main()
