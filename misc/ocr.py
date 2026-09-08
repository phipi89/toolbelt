#!/usr/bin/env python3

import shutil
import subprocess
import tempfile
from pathlib import Path


def find_tesseract() -> str:
    executable = shutil.which("tesseract")
    if executable:
        return executable

    for candidate in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if Path(candidate).is_file():
            return candidate

    raise SystemExit("tesseract not found; install it with Homebrew")


def main() -> None:
    tesseract = find_tesseract()

    with tempfile.TemporaryDirectory() as temporary_directory:
        image = Path(temporary_directory) / "capture.png"
        capture = subprocess.run(
            ["/usr/sbin/screencapture", "-i", "-s", "-x", str(image)],
            check=False,
        )
        if capture.returncode != 0 or not image.exists() or image.stat().st_size == 0:
            return

        result = subprocess.run(
            [tesseract, str(image), "stdout", "-l", "eng+deu"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        text = result.stdout.strip()
        if text:
            subprocess.run(
                ["/usr/bin/pbcopy"], input=text, check=True, text=True
            )
            subprocess.run(
                [
                    "/usr/bin/osascript",
                    "-e",
                    "on run argv",
                    "-e",
                    'display notification (item 1 of argv) with title "OCR copied"',
                    "-e",
                    "end run",
                    text,
                ],
                check=False,
            )


if __name__ == "__main__":
    main()
