from __future__ import annotations

import os
import pathlib
import plistlib
import tempfile
import unittest
from unittest.mock import patch

from run import cli
from run.cli import _app_name


class AppNameTests(unittest.TestCase):
    def _app(self, name: str, info: dict | None = None) -> pathlib.Path:
        root = pathlib.Path(self.temp_dir.name)
        app = root / f"{name}.app"
        if info is not None:
            contents = app / "Contents"
            contents.mkdir(parents=True)
            with (contents / "Info.plist").open("wb") as file:
                plistlib.dump(info, file)
        return app

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_uses_chrome_shortcut_name(self) -> None:
        app = self._app(
            "Overleaf - Projects",
            {
                "CFBundleName": "Overleaf - Projects",
                "CrAppModeShortcutName": "Overleaf",
            },
        )

        self.assertEqual(_app_name(app), "Overleaf")

    def test_uses_bundle_display_name(self) -> None:
        app = self._app("Bundle Name", {"CFBundleDisplayName": "Display Name"})

        self.assertEqual(_app_name(app), "Display Name")

    def test_falls_back_to_path_stem(self) -> None:
        app = self._app("Fallback")

        self.assertEqual(_app_name(app), "Fallback")

    def test_falls_back_for_invalid_plist(self) -> None:
        app = self._app("Broken", {})
        (app / "Contents" / "Info.plist").write_text("not a plist")

        self.assertEqual(_app_name(app), "Broken")


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
