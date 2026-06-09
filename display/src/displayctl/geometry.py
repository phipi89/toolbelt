from __future__ import annotations


TOLERANCE = 8.0


def close(a: float, b: float, tolerance: float = TOLERANCE) -> bool:
    return abs(a - b) <= tolerance


def same_frame(a: dict[str, float], b: dict[str, float], tolerance: float = TOLERANCE) -> bool:
    return (
        close(a["x"], b["x"], tolerance)
        and close(a["y"], b["y"], tolerance)
        and close(a["w"], b["w"], tolerance)
        and close(a["h"], b["h"], tolerance)
    )


def halves(x: float, y: float, w: float, h: float) -> tuple[dict[str, float], dict[str, float]]:
    return (
        {"x": x, "y": y, "w": w / 2, "h": h},
        {"x": x + w / 2, "y": y, "w": w / 2, "h": h},
    )


def weighted_left(x: float, y: float, w: float, h: float) -> tuple[dict[str, float], dict[str, float]]:
    return (
        {"x": x, "y": y, "w": w * 2 / 3, "h": h},
        {"x": x + w * 2 / 3, "y": y, "w": w / 3, "h": h},
    )


def center(frame: dict[str, float]) -> dict[str, float]:
    return {"x": frame["x"] + frame["w"] / 2, "y": frame["y"] + frame["h"] / 2}


def dist2(a: dict[str, float], b: dict[str, float]) -> float:
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    return dx * dx + dy * dy


def quads(x: float, y: float, w: float, h: float) -> list[dict[str, float]]:
    return [
        {"x": x, "y": y, "w": w / 2, "h": h / 2},
        {"x": x + w / 2, "y": y, "w": w / 2, "h": h / 2},
        {"x": x, "y": y + h / 2, "w": w / 2, "h": h / 2},
        {"x": x + w / 2, "y": y + h / 2, "w": w / 2, "h": h / 2},
    ]
