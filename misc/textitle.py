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

    args = parser.parse_args()

    title_text = " ".join(args.text)
    title = Figlet().renderText(title_text)

    prefix = f"{args.prefix} "
    title = "\n".join(f"{prefix}{line}" for line in title.splitlines())

    pyperclip.copy(title)

    print()
    print(title)
    print()
    print("copied to clipboard")


if __name__ == "__main__":
    main()
