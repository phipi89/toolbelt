r"""
%  _            _   _ _   _      
% | |_ _____  _| |_(_) |_| | ___ 
% | __/ _ \ \/ / __| | __| |/ _ \
% | ||  __/>  <| |_| | |_| |  __/
%  \__\___/_/\_\\__|_|\__|_|\___|
%                                

Helper to paste figlet titles as comments into latex files.
Install an alias:

```
alias textitle='uv run --no-project --with pyperclip,pyfiglet full/path/to/textitle.py'
```

then, `textitle Results` copies a commented out figlet title into your clipboard.
"""


import sys
import argparse
import pyperclip
from pyfiglet import Figlet


def main():
    parser = argparse.ArgumentParser(
        description="Helper to paste figlet titles as comments."
    )
    parser.add_argument(
        "text",
        nargs="+",
        help="The text to render into a figlet title."
    )
    parser.add_argument(
        "-c", "--prefix",
        default="%",
        help="The character(s) to use for the comment prefix (default: %%). Space is added automatically."
    )
    
    args = parser.parse_args()

    title_text = " ".join(args.text)
    title = Figlet().renderText(title_text)
    
    # Apply comment prefix
    prefix = f"{args.prefix} "
    title = "\n".join(f"{prefix}{line}" for line in title.splitlines())

    pyperclip.copy(title)

    print()
    print(title)
    print()
    print('copied to clipboard')


if __name__ == "__main__":
    main()

