#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["segno"]
# ///

import argparse
import subprocess
import tempfile
from pathlib import Path

import segno


def save_qr(text: str, path: Path) -> None:
    segno.make(text, micro=False).save(
        path, kind="png", scale=10, dark="black", light=None
    )


def copy_qr(text: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "qrcode.png"
        save_qr(text, path)
        subprocess.run(
            [
                "osascript",
                "-e",
                "on run argv",
                "-e",
                "set the clipboard to (read (POSIX file (item 1 of argv)) as «class PNGf»)",
                "-e",
                "end run",
                str(path),
            ],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a transparent-background QR code."
    )
    parser.add_argument("text", nargs="+", help="text to encode")
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("-o", "--out", type=Path, help="output PNG path")
    output.add_argument(
        "--clipboard", action="store_true", help="copy the PNG to the clipboard"
    )
    args = parser.parse_args()

    text = " ".join(args.text)
    if args.clipboard:
        copy_qr(text)
        print("Copied QR code to clipboard.")
    else:
        save_qr(text, args.out)
        print(f"Saved QR code: {args.out}")


if __name__ == "__main__":
    main()
