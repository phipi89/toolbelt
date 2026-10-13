from __future__ import annotations

import os
import pathlib
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from snippets import cli


class HotkeyLifecycleTests(unittest.TestCase):
    def test_hides_and_requests_restart_in_hotkey_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            restart_file = pathlib.Path(temp_dir) / "restart"
            with (
                patch.dict(os.environ, {cli.RESTART_ENV: str(restart_file)}),
                patch.object(cli.subprocess, "run") as run,
            ):
                cli._hide_hotkey_window()
                cli._request_restart()

            self.assertTrue(restart_file.exists())

        run.assert_called_once_with(
            ["/usr/bin/osascript", "-e", cli.HIDE_HOTKEY_WINDOW], check=False
        )

    def test_regular_cli_session_is_unchanged(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(cli.subprocess, "run") as run,
        ):
            cli._hide_hotkey_window()
            cli._request_restart()

        run.assert_not_called()

    def test_paste_uses_temporary_clipboard_until_target_has_received_text(
        self,
    ) -> None:
        args = type("Args", (), {"close": False})()

        @contextmanager
        def temporary_clipboard(content):
            self.assertEqual(content, "snippet")
            yield

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(cli, "temporary_clipboard", temporary_clipboard),
            patch.object(cli.subprocess, "run") as run,
            patch.object(cli.time, "sleep") as sleep,
        ):
            cli._paste_snippet("snippet", args)

        self.assertEqual(sleep.call_args_list[0].args, (0.15,))
        self.assertEqual(sleep.call_args_list[1].args, (cli.PASTE_SETTLE_DELAY,))
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
