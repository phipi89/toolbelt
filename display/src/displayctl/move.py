from __future__ import annotations

import json
import subprocess
from typing import Any

from . import geometry, yabai


def _hotkey_window(win: dict[str, Any]) -> bool:
    return bool(
        win.get("is-visible")
        and win.get("is-sticky")
        and win.get("is-floating")
        and (win.get("level") or 0) > 0
        and win.get("role") == "AXWindow"
        and win.get("subrole") == "AXSystemDialog"
        and win.get("can-move")
        and win.get("can-resize")
    )


def _target_window(space_windows: list[dict] | None = None) -> dict:
    if space_windows is None:
        try:
            space_windows = yabai.query_windows_on_space()
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
            space_windows = []
    hotkey_windows = [win for win in space_windows if _hotkey_window(win)]
    if hotkey_windows:
        return max(hotkey_windows, key=lambda win: win.get("level") or 0)
    return yabai.query_window()


def _usable_bounds_from_frames(
    *frames: dict[str, float],
) -> tuple[float, float, float, float]:
    min_x = min(frame["x"] for frame in frames)
    min_y = min(frame["y"] for frame in frames)
    max_x = max(frame["x"] + frame["w"] for frame in frames)
    max_y = max(frame["y"] + frame["h"] for frame in frames)
    return min_x, min_y, max_x - min_x, max_y - min_y


def _grid_frame(
    bounds: tuple[float, float, float, float],
    rows: float,
    cols: float,
    start_x: float,
    start_y: float,
    width: float,
    height: float,
) -> dict[str, float]:
    x, y, w, h = bounds
    return {
        "x": x + w * start_x / cols,
        "y": y + h * start_y / rows,
        "w": w * width / cols,
        "h": h * height / rows,
    }


def _framed_half_bounds(
    left_frame: dict[str, float],
) -> tuple[float, float, float, float]:
    w = left_frame["w"] * 20 / 9
    h = left_frame["h"] * 20 / 18
    return left_frame["x"] - w / 20, left_frame["y"] - h / 20, w, h


def _framed_weighted_bounds(
    left_frame: dict[str, float],
) -> tuple[float, float, float, float]:
    w = left_frame["w"] * 30 / 19
    h = left_frame["h"] * 20 / 18
    return left_frame["x"] - w / 30, left_frame["y"] - h / 20, w, h


def _overlaps(
    a: dict[str, float], b: dict[str, float], tolerance: float = 12.0
) -> bool:
    return not (
        a["x"] + a["w"] <= b["x"] + tolerance
        or b["x"] + b["w"] <= a["x"] + tolerance
        or a["y"] + a["h"] <= b["y"] + tolerance
        or b["y"] + b["h"] <= a["y"] + tolerance
    )


def _has_overlap(wins: list[dict]) -> bool:
    for index, win in enumerate(wins):
        for other in wins[index + 1 :]:
            if _overlaps(win["frame"], other["frame"]):
                return True
    return False


def _corner_position(
    frame: dict[str, float], corner: str, bounds: tuple[float, float, float, float]
) -> tuple[float, float]:
    x, y, w, h = bounds
    width = min(frame["w"], w)
    height = min(frame["h"], h)
    target_x = x if corner.endswith("left") else x + w - width
    target_y = y if corner.startswith("top") else y + h - height
    return target_x, target_y


def _move_to_corner(
    win: dict, corner: str, bounds: tuple[float, float, float, float]
) -> None:
    x, y = _corner_position(win["frame"], corner, bounds)
    yabai.move_abs(win["id"], x, y)


def _split_state(
    left_frame: dict[str, float], right_frame: dict[str, float]
) -> str | None:
    x, y, w, h = _usable_bounds_from_frames(left_frame, right_frame)
    left_half, right_half = geometry.halves(x, y, w, h)
    left_two_thirds, right_one_third = geometry.weighted_left(x, y, w, h)

    if geometry.same_frame(left_frame, left_half) and geometry.same_frame(
        right_frame, right_half
    ):
        return "half"
    if geometry.same_frame(left_frame, left_two_thirds) and geometry.same_frame(
        right_frame, right_one_third
    ):
        return "weighted"

    half_frame_bounds = _framed_half_bounds(left_frame)
    framed_left_half = _grid_frame(half_frame_bounds, 20, 20, 1, 1, 9, 18)
    framed_right_half = _grid_frame(half_frame_bounds, 20, 20, 10, 1, 9, 18)
    if geometry.same_frame(left_frame, framed_left_half) and geometry.same_frame(
        right_frame, framed_right_half
    ):
        return "framed_half"

    weighted_frame_bounds = _framed_weighted_bounds(left_frame)
    framed_left_weighted = _grid_frame(weighted_frame_bounds, 20, 30, 1, 1, 19, 18)
    framed_right_weighted = _grid_frame(weighted_frame_bounds, 20, 30, 20, 1, 9, 18)
    if geometry.same_frame(left_frame, framed_left_weighted) and geometry.same_frame(
        right_frame, framed_right_weighted
    ):
        return "framed_weighted"

    return None


def _split_pair(wins: list[dict]) -> tuple[dict, dict, str] | None:
    for index, first in enumerate(wins):
        for second in wins[index + 1 :]:
            left_win, right_win = sorted(
                [first, second], key=lambda win: win["frame"]["x"]
            )
            state = _split_state(left_win["frame"], right_win["frame"])
            if state:
                return left_win, right_win, state
    return None


def _frame_split_pair(left_win: dict, right_win: dict, state: str) -> None:
    if state in {"weighted", "framed_weighted"}:
        yabai.grid(left_win["id"], "20:30:1:1:19:18")
        yabai.grid(right_win["id"], "20:30:20:1:9:18")
    else:
        yabai.grid(left_win["id"], "20:20:1:1:9:18")
        yabai.grid(right_win["id"], "20:20:10:1:9:18")


def _set_split_layout(left_win: dict, right_win: dict, state: str) -> None:
    grids = {
        "half": ("1:2:0:0:1:1", "1:2:1:0:1:1"),
        "weighted": ("1:3:0:0:2:1", "1:3:2:0:1:1"),
        "framed_half": ("20:20:1:1:9:18", "20:20:10:1:9:18"),
        "framed_weighted": ("20:30:1:1:19:18", "20:30:20:1:9:18"),
    }
    left_grid, right_grid = grids[state]
    yabai.grid(left_win["id"], left_grid)
    yabai.grid(right_win["id"], right_grid)


def _eligible_windows(limit: int | None = None) -> list[dict]:
    wins = [win for win in yabai.query_windows_on_space() if yabai.eligible_window(win)]
    return wins[:limit] if limit is not None else wins


def _display_usable_bounds() -> tuple[float, float, float, float]:
    display = yabai.query_display()
    focused = yabai.query_window()
    display_frame = display["frame"]
    frame = focused["frame"]
    return display_frame["x"], frame["y"], display_frame["w"], frame["h"]


def _display_bounds() -> tuple[float, float, float, float]:
    display_frame = yabai.query_display()["frame"]
    return (
        display_frame["x"],
        display_frame["y"],
        display_frame["w"],
        display_frame["h"],
    )


def _corner_slot(
    corner: str, bounds: tuple[float, float, float, float]
) -> dict[str, float]:
    x, y, w, h = bounds
    slots = {
        "top_left": {"x": x, "y": y, "w": w / 2, "h": h / 2},
        "top_right": {"x": x + w / 2, "y": y, "w": w / 2, "h": h / 2},
        "bottom_right": {"x": x + w / 2, "y": y + h / 2, "w": w / 2, "h": h / 2},
        "bottom_left": {"x": x, "y": y + h / 2, "w": w / 2, "h": h / 2},
    }
    return slots[corner]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _place_candidate(
    x: float,
    y: float,
    width: float,
    height: float,
    bounds: tuple[float, float, float, float],
) -> dict[str, float]:
    bx, by, bw, bh = bounds
    return {
        "x": _clamp(x, bx, bx + bw - width),
        "y": _clamp(y, by, by + bh - height),
        "w": width,
        "h": height,
    }


def _unique_frames(frames: list[dict[str, float]]) -> list[dict[str, float]]:
    seen: set[tuple[int, int, int, int]] = set()
    unique = []
    for frame in frames:
        key = tuple(round(frame[item]) for item in ("x", "y", "w", "h"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(frame)
    return unique


def _place_candidates(
    target: dict[str, float],
    others: list[dict],
    bounds: tuple[float, float, float, float],
) -> list[dict[str, float]]:
    bx, by, bw, bh = bounds
    width = bw * 0.67
    height = bh * 0.67
    max_x = bx + bw - width
    max_y = by + bh - height
    current_center = geometry.center(target)
    candidates = [
        _place_candidate(bx, by, width, height, bounds),
        _place_candidate(max_x, by, width, height, bounds),
        _place_candidate(bx, max_y, width, height, bounds),
        _place_candidate(max_x, max_y, width, height, bounds),
        _place_candidate(
            bx + (bw - width) / 2, by + (bh - height) / 2, width, height, bounds
        ),
        _place_candidate(
            current_center["x"] - width / 2,
            current_center["y"] - height / 2,
            width,
            height,
            bounds,
        ),
    ]

    for row in range(4):
        for col in range(4):
            x = bx + (bw - width) * col / 3
            y = by + (bh - height) * row / 3
            candidates.append(_place_candidate(x, y, width, height, bounds))

    x_positions = [candidate["x"] for candidate in candidates]
    y_positions = [candidate["y"] for candidate in candidates]
    for other in others:
        frame = other["frame"]
        x_positions.extend(
            [
                frame["x"],
                frame["x"] + frame["w"] - width,
                frame["x"] - width,
                frame["x"] + frame["w"],
                frame["x"] + frame["w"] / 2 - width / 2,
            ]
        )
        y_positions.extend(
            [
                frame["y"],
                frame["y"] + frame["h"] - height,
                frame["y"] - height,
                frame["y"] + frame["h"],
                frame["y"] + frame["h"] / 2 - height / 2,
            ]
        )
    for x in x_positions:
        for y in y_positions:
            candidates.append(_place_candidate(x, y, width, height, bounds))

    return _unique_frames(candidates)


def _same_display(win: dict, display: dict) -> bool:
    return win.get("display") == display.get("index")


def _corner_order(count: int) -> list[str]:
    if count == 2:
        return ["top_left", "bottom_right"]
    if count == 3:
        return ["top_left", "top_right", "bottom_right"]
    return ["top_left", "top_right", "bottom_right", "bottom_left"][:count]


def _place_by_nearest_slot(
    wins: list[dict], slots: list[dict[str, float]]
) -> list[dict | None]:
    placed: list[dict | None] = [None] * min(len(wins), len(slots))
    used: set[int] = set()

    for slot_index, slot in enumerate(slots[: len(placed)]):
        for win_index, win in enumerate(wins):
            if win_index not in used and geometry.same_frame(win["frame"], slot):
                placed[slot_index] = win
                used.add(win_index)
                break

    free_slots = [index for index, win in enumerate(placed) if win is None]
    loose_windows = [
        (index, win) for index, win in enumerate(wins) if index not in used
    ]

    best_cost: float | None = None
    best_order: list[dict] | None = None

    def search(pos: int, cost: float, order: list[dict], taken: set[int]) -> None:
        nonlocal best_cost, best_order
        if best_cost is not None and cost >= best_cost:
            return
        if pos >= len(free_slots):
            best_cost = cost
            best_order = order.copy()
            return

        slot = slots[free_slots[pos]]
        slot_center = geometry.center(slot)
        for loose_index, win in loose_windows:
            if loose_index in taken:
                continue
            taken.add(loose_index)
            order.append(win)
            search(
                pos + 1,
                cost + geometry.dist2(geometry.center(win["frame"]), slot_center),
                order,
                taken,
            )
            order.pop()
            taken.remove(loose_index)

    if free_slots:
        search(0, 0, [], set())
        if best_order:
            for index, slot_index in enumerate(free_slots):
                placed[slot_index] = best_order[index]

    return placed


def left() -> None:
    win = _target_window()
    display = yabai.query_display()
    display_frame = display["frame"]
    frame = win["frame"]

    x = display_frame["x"]
    y = frame["y"]
    w = display_frame["w"]
    h = frame["h"]
    left_half, _ = geometry.halves(x, y, w, h)

    if geometry.same_frame(frame, left_half):
        yabai.grid(win["id"], "1:3:0:0:2:1")
    else:
        yabai.grid(win["id"], "1:2:0:0:1:1")


def right() -> None:
    win = _target_window()
    display = yabai.query_display()
    display_frame = display["frame"]
    frame = win["frame"]

    x = display_frame["x"]
    y = frame["y"]
    w = display_frame["w"]
    h = frame["h"]
    _, right_half = geometry.halves(x, y, w, h)

    if geometry.same_frame(frame, right_half):
        yabai.grid(win["id"], "1:3:2:0:1:1")
    else:
        yabai.grid(win["id"], "1:2:1:0:1:1")


def reduce() -> None:
    win = _target_window()
    yabai.grid(win["id"], "10:10:7:7:3:3")


def _same_horizontal_percent(
    frame: dict[str, float], display_frame: dict[str, float], start: float, width: float
) -> bool:
    expected_x = display_frame["x"] + display_frame["w"] * start
    expected_w = display_frame["w"] * width
    return geometry.close(frame["x"], expected_x, 8) and geometry.close(
        frame["w"], expected_w, 8
    )


def center(size: float | None = None, reverse: bool = False) -> None:
    try:
        space_windows = yabai.query_windows_on_space()
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        space_windows = []

    win = _target_window(space_windows)
    display = yabai.query_display()
    display_frame = display["frame"]
    frame = win["frame"]

    if size is not None:
        if size <= 0 or size > 100:
            raise ValueError("center size must be between 0 and 100")
        start = (100 - size) / 2
        yabai.grid(win["id"], f"100:100:{start:g}:{start:g}:{size:g}:{size:g}")
        return

    sizes = tuple(range(10, 101, 10))
    current = next(
        (
            candidate
            for candidate in sizes
            if _same_horizontal_percent(
                frame,
                display_frame,
                (100 - candidate) / 200,
                candidate / 100,
            )
        ),
        None,
    )
    if current is None:
        target = 80 if reverse else 90
    else:
        step = -1 if reverse else 1
        target_index = max(0, min(sizes.index(current) + step, len(sizes) - 1))
        target = sizes[target_index]

    start = (100 - target) / 2
    yabai.grid(win["id"], f"100:100:{start:g}:{start:g}:{target}:{target}")


def place() -> None:
    win = _target_window()
    display = yabai.query_display()
    display_frame = display["frame"]
    bounds = (
        display_frame["x"],
        display_frame["y"],
        display_frame["w"],
        display_frame["h"],
    )
    others = [
        other
        for other in _eligible_windows()
        if other["id"] != win["id"] and _same_display(other, display)
    ]
    candidates = _place_candidates(win["frame"], others, bounds)
    current_center = geometry.center(win["frame"])

    def score(frame: dict[str, float]) -> tuple[float, float]:
        overlap = sum(geometry.overlap_area(frame, other["frame"]) for other in others)
        movement = geometry.dist2(geometry.center(frame), current_center)
        return overlap, movement

    best = min(candidates, key=score)
    bx, by, bw, bh = bounds
    start_x = (best["x"] - bx) * 100 / bw
    start_y = (best["y"] - by) * 100 / bh
    yabai.grid(win["id"], f"100:100:{start_x:g}:{start_y:g}:67:67")


def cycle(target_index: int = 2) -> None:
    wins = _eligible_windows()
    if len(wins) < target_index:
        return
    yabai.focus(wins[target_index - 1]["id"])


def _quad(wins: list[dict]) -> None:
    if not wins:
        return

    x, y, w, h = _display_usable_bounds()
    slots = geometry.quads(x, y, w, h)
    placed = _place_by_nearest_slot(wins, slots)
    grids = ["2:2:0:0:1:1", "2:2:1:0:1:1", "2:2:0:1:1:1", "2:2:1:1:1:1"]
    for win, grid in zip(placed, grids, strict=False):
        if win:
            yabai.grid(win["id"], grid)


def quad() -> None:
    _quad(_eligible_windows(limit=4))


def tile() -> None:
    wins = _eligible_windows(limit=4)
    if len(wins) != 2:
        _quad(wins)
        return

    x, y, w, h = _display_usable_bounds()
    slots = list(geometry.halves(x, y, w, h))
    placed = _place_by_nearest_slot(wins, slots)
    grids = ["1:2:0:0:1:1", "1:2:1:0:1:1"]
    for win, grid in zip(placed, grids, strict=False):
        if win:
            yabai.grid(win["id"], grid)


def distribute() -> None:
    wins = _eligible_windows(limit=6)
    if len(wins) < 2 or not _has_overlap(wins):
        return

    bounds = _display_bounds()
    split_pair = _split_pair(wins)

    if split_pair:
        left_win, right_win, state = split_pair
        _frame_split_pair(left_win, right_win, state)
        split_ids = {left_win["id"], right_win["id"]}
        remaining = [win for win in wins if win["id"] not in split_ids][:4]
    else:
        remaining = wins[:4]

    corner_names = _corner_order(len(remaining))
    corner_slots = [_corner_slot(corner, bounds) for corner in corner_names]
    placed = _place_by_nearest_slot(remaining, corner_slots)
    for win, corner in zip(placed, corner_names, strict=False):
        if win:
            _move_to_corner(win, corner, bounds)


def split(frontmost_right: bool = False, frame: bool = False) -> None:
    wins = _eligible_windows()
    if len(wins) < 2:
        return

    first, second = wins[0], wins[1]
    left_win, right_win = (second, first) if frontmost_right else (first, second)
    state = _split_state(left_win["frame"], right_win["frame"])

    if frame:
        target = (
            "framed_weighted" if state in {"half", "framed_half"} else "framed_half"
        )
        _set_split_layout(left_win, right_win, target)
        return

    target = {
        "half": "weighted",
        "weighted": "half",
        "framed_half": "framed_weighted",
        "framed_weighted": "half",
    }.get(state, "half")
    _set_split_layout(left_win, right_win, target)
