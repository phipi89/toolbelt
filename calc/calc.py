import os
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
from IPython import embed
from IPython import get_ipython
from numpy import *
from traitlets.config import Config


def closing():
    """Signal the wrapper to replace this calculator session."""
    Path(os.environ["CALC_RESTART_FILE"]).touch()
    subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            """
            tell application "iTerm2"
              tell current window
                hide hotkey window
              end tell
            end tell
            """,
        ],
        check=False,
    )
    get_ipython().ask_exit()


def main():
    print(16 * " " + "____ ____ _    ____ _  _ _    ____ ___ ____ ____")
    print(16 * " " + "|___ |--| |___ |___ |__| |___ |--|  |  [__] |--<")
    print()

    c = Config()
    c.TerminalInteractiveShell.show_banner = False  # hides the usual IPython banner
    c.InteractiveShell.enable_tip = False  # disables the “Tip:” line

    embed(config=c, banner1="", banner2="", exit_msg="")
