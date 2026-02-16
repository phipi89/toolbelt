import matplotlib.pyplot as plt
from IPython import embed
from numpy import *
from traitlets.config import Config


def main():
    print(16 * " " + "____ ____ _    ____ _  _ _    ____ ___ ____ ____")
    print(16 * " " + "|___ |--| |___ |___ |__| |___ |--|  |  [__] |--<")
    print()

    c = Config()
    c.TerminalInteractiveShell.show_banner = False  # hides the usual IPython banner
    c.InteractiveShell.enable_tip = False  # disables the “Tip:” line

    embed(config=c, banner1="", banner2="", exit_msg="")
