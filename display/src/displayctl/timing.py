from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from typing import Iterator


ENABLED = os.environ.get("DISPLAY_TIMING", "").casefold() not in {
    "",
    "0",
    "false",
    "no",
    "off",
}


def log(label: str, start: float) -> None:
    if ENABLED:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"displayctl {label:<28} {elapsed_ms:7.1f}ms", file=sys.stderr)


@contextmanager
def timed(label: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        log(label, start)


def time_call(label: str, func, *args, **kwargs):
    start = time.perf_counter()
    try:
        return func(*args, **kwargs)
    finally:
        log(label, start)
