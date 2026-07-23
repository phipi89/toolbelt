from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from . import check, finder


def _snapshot() -> str:
    selected = Path(finder.selected_file())
    target_dir = selected.parent / "snapshots"
    target_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"{selected.stem}-{timestamp}{selected.suffix}"
    shutil.copy2(selected, target)
    return str(target)


def _touch(names: list[str]) -> None:
    directory = Path(finder.front_path())
    for name in names or ["empty.txt"]:
        (directory / name).touch()


def main() -> None:
    parser = argparse.ArgumentParser(prog="finderctl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("path", help="print the front Finder folder")
    subparsers.add_parser("selected-file", help="print the selected Finder file")
    subparsers.add_parser("snapshot", help="snapshot the selected Finder file")

    touch_parser = subparsers.add_parser("touch", help="create files in the front Finder folder")
    touch_parser.add_argument("names", nargs="*")

    check_parser = subparsers.add_parser(
        "check-left-in-right",
        help="check that filenames in the left Finder folder exist in the right one",
    )
    check_parser.add_argument(
        "--depth", type=int, default=3, help="maximum subfolder depth (default: 3)"
    )

    args = parser.parse_args()
    try:
        if args.command == "path":
            print(finder.front_path())
        elif args.command == "selected-file":
            print(finder.selected_file())
        elif args.command == "snapshot":
            print(_snapshot())
        elif args.command == "touch":
            _touch(args.names)
        elif args.command == "check-left-in-right":
            if args.depth < 0:
                parser.error("--depth must be non-negative")
            raise SystemExit(check.run(depth=args.depth))
    except (finder.FinderError, OSError) as error:
        print(f"finderctl: {error}", file=sys.stderr)
        raise SystemExit(1) from error
