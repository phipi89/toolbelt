from __future__ import annotations

import unittest
from unittest.mock import patch

from snippets import clipboard


class FakeItem:
    def __init__(self, data):
        self.data = data

    def types(self):
        return list(self.data)

    def dataForType_(self, pasteboard_type):
        return self.data[pasteboard_type]


class FakePasteboard:
    def __init__(self):
        self.change_count = 0

    def changeCount(self):
        return self.change_count


class ClipboardTests(unittest.TestCase):
    def test_snapshot_preserves_every_item_type_and_payload(self) -> None:
        pasteboard = FakePasteboard()
        pasteboard.pasteboardItems = lambda: [
            FakeItem({"public.utf8-plain-text": b"text", "public.rtf": b"rich"}),
            FakeItem({"public.tiff": b"image"}),
        ]

        snapshot = clipboard._snapshot(pasteboard)

        self.assertEqual(
            snapshot,
            (
                (("public.utf8-plain-text", b"text"), ("public.rtf", b"rich")),
                (("public.tiff", b"image"),),
            ),
        )

    def test_restores_original_clipboard_when_unchanged(self) -> None:
        pasteboard = FakePasteboard()
        restored = []
        snapshot = ((("public.utf8-plain-text", b"original"),),)

        def write_text(_pasteboard, _text):
            pasteboard.change_count += 1

        def write_snapshot(_, value):
            restored.append(value)

        with (
            patch.object(clipboard, "_snapshot", return_value=snapshot),
            patch.object(clipboard, "_write_text", side_effect=write_text),
            patch.object(clipboard, "_write_snapshot", side_effect=write_snapshot),
            clipboard.temporary_clipboard("snippet", pasteboard),
        ):
            pass

        self.assertEqual(restored, [snapshot])

    def test_keeps_clipboard_changed_during_paste(self) -> None:
        pasteboard = FakePasteboard()

        def write_text(_pasteboard, _text):
            pasteboard.change_count += 1

        with (
            patch.object(clipboard, "_snapshot", return_value=()),
            patch.object(clipboard, "_write_text", side_effect=write_text),
            patch.object(clipboard, "_write_snapshot") as restore,
            clipboard.temporary_clipboard("snippet", pasteboard),
        ):
            pasteboard.change_count += 1

        restore.assert_not_called()

    def test_restores_empty_clipboard(self) -> None:
        pasteboard = FakePasteboard()
        restored = []

        def write_text(_pasteboard, _text):
            pasteboard.change_count += 1

        def write_snapshot(_, value):
            restored.append(value)

        with (
            patch.object(clipboard, "_snapshot", return_value=()),
            patch.object(clipboard, "_write_text", side_effect=write_text),
            patch.object(clipboard, "_write_snapshot", side_effect=write_snapshot),
            clipboard.temporary_clipboard("snippet", pasteboard),
        ):
            pass

        self.assertEqual(restored, [()])

    def test_restores_clipboard_if_writing_the_snippet_fails(self) -> None:
        pasteboard = FakePasteboard()
        snapshot = ((("public.utf8-plain-text", b"original"),),)

        def write_text(_pasteboard, _text):
            pasteboard.change_count += 1
            raise clipboard.ClipboardError("write failed")

        with (
            patch.object(clipboard, "_snapshot", return_value=snapshot),
            patch.object(clipboard, "_write_text", side_effect=write_text),
            patch.object(clipboard, "_write_snapshot") as restore,
            self.assertRaisesRegex(clipboard.ClipboardError, "write failed"),
            clipboard.temporary_clipboard("snippet", pasteboard),
        ):
            pass

        restore.assert_called_once_with(pasteboard, snapshot)


if __name__ == "__main__":
    unittest.main()
