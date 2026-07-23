from __future__ import annotations

import os
import re
import sys

from . import finder


def _raise_walk_error(error: OSError) -> None:
    raise error


def filenames(folder: str, max_depth: int) -> tuple[set[str], bool, int]:
    found: set[str] = set()
    too_deep = False
    ignored_files = 0

    for root, dirnames, names in os.walk(folder, onerror=_raise_walk_error):
        relative_root = os.path.relpath(root, folder)
        current_depth = 0 if relative_root == "." else relative_root.count(os.sep) + 1
        if current_depth <= max_depth:
            found.update(names)
        else:
            too_deep = True
            ignored_files += len(names)
        if current_depth == max_depth:
            too_deep = too_deep or bool(dirnames)

    return found, too_deep, ignored_files


def display_path(path: str) -> str:
    parts = [part for part in os.path.normpath(path).split(os.sep) if part]
    if parts[:1] == ["Volumes"]:
        parts = parts[1:]
    if len(parts) <= 2:
        return "/".join(parts) or os.sep
    return f"{parts[0]}/.../{parts[-1]}"


def _filename_key(filename: str) -> tuple:
    stem, extension = os.path.splitext(filename)
    match = re.match(r"^(.*?)(\d+)$", stem)
    if match:
        return 0, match.group(1), int(match.group(2)), extension
    return 1, stem, extension


def compact_filenames(filenames: set[str]) -> list[str]:
    ordered = sorted(filenames, key=_filename_key)
    compacted: list[str] = []
    index = 0

    while index < len(ordered):
        stem, extension = os.path.splitext(ordered[index])
        match = re.match(r"^(.*?)(\d+)$", stem)
        if not match:
            compacted.append(ordered[index])
            index += 1
            continue

        prefix = match.group(1)
        width = len(match.group(2))
        start = end = int(match.group(2))
        index += 1

        while index < len(ordered):
            next_stem, next_extension = os.path.splitext(ordered[index])
            next_match = re.match(r"^(.*?)(\d+)$", next_stem)
            if not (
                next_match
                and next_match.group(1) == prefix
                and next_extension == extension
                and int(next_match.group(2)) == end + 1
            ):
                break
            end = int(next_match.group(2))
            index += 1

        def formatted(number: int) -> str:
            return f"{prefix}{number:0{width}d}{extension}"

        compacted.append(
            f"{formatted(start)}-{formatted(end)}"
            if start != end
            else formatted(start)
        )

    return compacted


def run(depth: int = 3) -> int:
    try:
        left_path, right_path = finder.left_right_paths()
        left_files, left_too_deep, left_ignored = filenames(left_path, depth)
        right_files, right_too_deep, _ = filenames(right_path, depth)
    except (finder.FinderError, OSError) as error:
        print(f"check_left_in_right: {error}", file=sys.stderr)
        return 2

    missing = left_files - right_files
    print(f"Left:  {left_path}")
    print(f"Right: {right_path}")
    print(f"Files through depth {depth}: {len(left_files)} left, {len(right_files)} right")

    if left_too_deep or right_too_deep:
        file_label = "file" if left_ignored == 1 else "files"
        print(
            f"Warning: folders below depth {depth} were ignored "
            f"({left_ignored} {file_label} on the left)."
        )
    print("Warning: comparison uses filenames only; file contents are not checked.")

    if missing:
        print(f"\nMissing on the right ({len(missing)}):")
        for filename in compact_filenames(missing):
            print(filename)
        return 1

    print(
        f"\nEvery file in {display_path(left_path)} is present in "
        f"{display_path(right_path)}."
    )
    return 0
