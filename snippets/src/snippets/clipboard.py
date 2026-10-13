from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from AppKit import NSPasteboard, NSPasteboardItem, NSPasteboardTypeString
from Foundation import NSData


class ClipboardError(RuntimeError):
    pass


def _snapshot(pasteboard) -> tuple[tuple[tuple[str, bytes], ...], ...]:
    return tuple(
        tuple(
            (str(pasteboard_type), bytes(data))
            for pasteboard_type in item.types()
            if (data := item.dataForType_(pasteboard_type)) is not None
        )
        for item in (pasteboard.pasteboardItems() or [])
    )


def _write_snapshot(pasteboard, snapshot) -> None:
    pasteboard.clearContents()
    if not snapshot:
        return

    items = []
    for snapshot_item in snapshot:
        item = NSPasteboardItem.alloc().init()
        for pasteboard_type, data in snapshot_item:
            native_data = NSData.dataWithBytes_length_(data, len(data))
            item.setData_forType_(native_data, pasteboard_type)
        items.append(item)

    if not pasteboard.writeObjects_(items):
        raise ClipboardError("could not restore the clipboard")


def _write_text(pasteboard, text: str) -> None:
    item = NSPasteboardItem.alloc().init()
    if not item.setString_forType_(text, NSPasteboardTypeString):
        raise ClipboardError("could not prepare the snippet for pasting")

    pasteboard.clearContents()
    if not pasteboard.writeObjects_([item]):
        raise ClipboardError("could not write the snippet to the clipboard")


@contextmanager
def temporary_clipboard(text: str, pasteboard=None) -> Iterator[None]:
    """Temporarily place text on the pasteboard and restore its prior contents."""
    pasteboard = pasteboard or NSPasteboard.generalPasteboard()
    snapshot = _snapshot(pasteboard)
    original_change_count = pasteboard.changeCount()
    try:
        _write_text(pasteboard, text)
    except Exception:
        if pasteboard.changeCount() != original_change_count:
            _write_snapshot(pasteboard, snapshot)
        raise
    owned_change_count = pasteboard.changeCount()

    try:
        yield
    finally:
        if pasteboard.changeCount() == owned_change_count:
            _write_snapshot(pasteboard, snapshot)
