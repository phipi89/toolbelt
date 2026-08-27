from __future__ import annotations

import os
import pathlib
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
