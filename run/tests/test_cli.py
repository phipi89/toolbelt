from __future__ import annotations

import pathlib
import plistlib
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
