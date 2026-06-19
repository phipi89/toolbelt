from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

from . import timing


def _run(*args: str) -> str:
    return timing.time_call(
        " ".join(args[:2]),
        subprocess.run,
        args,
        check=False,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _add_name(names: set[str], value: str | None) -> None:
    if value:
        value = value.strip().strip('"')
        if value and value != "(null)":
            names.add(value)
            if value.endswith(".app"):
                names.add(value[:-4])


def _candidate_app_paths(name: str) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if path.suffix == ".app" and path.exists() and path not in seen:
            seen.add(path)
            paths.append(path)

    for root in (Path("/Applications"), Path("/System/Applications"), Path.home() / "Applications"):
        add(root / f"{name}.app")

    if not paths:
        for line in _run("mdfind", "-name", name).splitlines():
            path = Path(line)
            if path.suffix == ".app":
                add(path)
    return paths


def _info_plist_names(app_path: Path) -> set[str]:
    names: set[str] = set()
    info_path = app_path / "Contents" / "Info.plist"
    if not info_path.exists():
        return names
    try:
        with info_path.open("rb") as f:
            info = plistlib.load(f)
    except Exception:
        return names
    for key in ("CFBundleDisplayName", "CFBundleName", "CFBundleExecutable"):
        _add_name(names, info.get(key))
    return names


def _mdls_display_name(app_path: Path) -> str | None:
    return _run("mdls", "-raw", "-name", "kMDItemDisplayName", str(app_path)) or None


def candidate_app_names(name: str) -> set[str]:
    with timing.timed("resolve app names"):
        names = {name}
        for app_path in _candidate_app_paths(name):
            _add_name(names, app_path.stem)
            _add_name(names, _mdls_display_name(app_path))
            names.update(_info_plist_names(app_path))
        return names
