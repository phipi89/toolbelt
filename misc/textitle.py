#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pyperclip", "pyfiglet"]
# ///


import argparse

import pyperclip
from pyfiglet import Figlet


def main():
    parser = argparse.ArgumentParser(
        description="Helper to paste figlet titles as comments."
    )
    parser.add_argument(
        "text", nargs="+", help="The text to render into a figlet title."
    )
    parser.add_argument(
        "-p",
        "--prefix",
        default="%",
        help="The character(s) to use for the comment prefix (default: %%). Space is added automatically.",
    )

    parser.add_argument(
        "-f",
        "--font",
        default="ogre",
        help="Font name, or [1, 2, 3] for a preselection.",
    )

    args = parser.parse_args()
    title_text = " ".join(args.text)

    fonts = ("cybermedium", "pagga", "future", "isometric1")
    font = args.font
    if font in ("1", "2", "3", "4"):
        font = fonts[int(font) - 1]

    if font == "list":
        for i, option in enumerate(fonts, start=1):
            title = Figlet(font=option).renderText(title_text)
            print(f"{i}: {option}")
            print(title)
            print("\n\n")
        return

    title = Figlet(font=font).renderText(title_text)

    prefix = f"{args.prefix} "
    title = "\n".join(f"{prefix}{line}" for line in title.splitlines())

    pyperclip.copy(title)

    print()
    print(title)
    print()
    print("copied to clipboard")


if __name__ == "__main__":
    main()
