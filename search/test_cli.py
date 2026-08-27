from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from search import cli


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

    def test_closing_does_not_open_a_selection(self) -> None:
        with (
            patch.object(sys, "argv", ["search"]),
            patch.object(cli, "_select_path", return_value=(cli.CLOSING, False)),
            patch.object(cli, "_hide_hotkey_window") as hide,
            patch.object(cli, "_request_restart") as restart,
            patch.object(cli, "_open_in_finder") as open_path,
            patch.object(cli, "_reveal_in_finder") as reveal_path,
        ):
            cli.main()

        hide.assert_called_once_with()
        restart.assert_called_once_with()
        open_path.assert_not_called()
        reveal_path.assert_not_called()

    def test_selection_hides_opens_then_restarts(self) -> None:
        events = []
        with (
            patch.object(sys, "argv", ["search"]),
            patch.object(cli, "_select_path", return_value=("/tmp/result", False)),
            patch.object(
                cli, "_hide_hotkey_window", side_effect=lambda: events.append("hide")
            ),
            patch.object(
                cli,
                "_open_in_finder",
                side_effect=lambda _path: events.append("open"),
            ),
            patch.object(
                cli, "_request_restart", side_effect=lambda: events.append("restart")
            ),
        ):
            cli.main()

        self.assertEqual(events, ["hide", "open", "restart"])


if __name__ == "__main__":
    unittest.main()
