#                                  _
#   __ _  ___ _ __   ___ _ __ __ _| |
#  / _` |/ _ \ '_ \ / _ \ '__/ _` | |
# | (_| |  __/ | | |  __/ | | (_| | |
#  \__, |\___|_| |_|\___|_|  \__,_|_|
#  |___/

TOOLBELT="$HOME/toolbelt"
source ~/toolbelt/auth.sh


#
#  _ __ _   _ _ __
# | '__| | | | '_ \
# | |  | |_| | | | |
# |_|   \__,_|_| |_|
#

run() { (cd "$TOOLBELT/run" || return 1; uv run run;) }


#  ____       _____
# |  _ \ _   |_   _|__ _ __ ___  _ __
# | |_) | | | || |/ _ \ '_ ` _ \| '_ \
# |  __/| |_| || |  __/ | | | | | |_) |
# |_|    \__, ||_|\___|_| |_| |_| .__/
#        |___/                  |_|

source "$TOOLBELT/pytemp/pytemp.sh"


#                          _
#  ___  ___  __ _ _ __ ___| |__
# / __|/ _ \/ _` | '__/ __| '_ \
# \__ \  __/ (_| | | | (__| | | |
# |___/\___|\__,_|_|  \___|_| |_|
#

search() { (cd "$TOOLBELT/search" || return 1; ../display/move/center.sh; clear; uv run search;) }



#       _ _
#   ___| | | __
#  / __| | |/ /
# | (__| |   <
#  \___|_|_|\_\

# wrap in () runs the command in a subshell
clk() { (cd "$TOOLBELT/clk"; uv run clk "$@";) }



#  _     _____ ___
# | |   | ____/ _ \  ___  _ __ __ _
# | |   |  _|| | | |/ _ \| '__/ _` |
# | |___| |__| |_| | (_) | | | (_| |
# |_____|_____\___(_)___/|_|  \__, |
#                             |___/

fen() { (cd "$TOOLBELT/leo" || return 1; uv run leo -t de -f en -m 6 "$@";) }
ten() { (cd "$TOOLBELT/leo" || return 1; uv run leo -t en -f de -m 6 "$@";) }
tfr() { (cd "$TOOLBELT/leo" || return 1; uv run leo -t fr -f de -m 6 "$@";) }
ffr() { (cd "$TOOLBELT/leo" || return 1; uv run leo -t de -f fr -m 6 "$@";) }



#            _
#  _ __ ___ (_)___  ___
# | '_ ` _ \| / __|/ __|
# | | | | | | \__ \ (__
# |_| |_| |_|_|___/\___|
#

alias textitle='uv run --no-project --with pyperclip,pyfiglet $TOOLBELT/misc/textitle.py'
alias pytitle='uv run --no-project --with pyperclip,pyfiglet $TOOLBELT/misc/textitle.py --prefix "#"'

ask(){ gemini -p "$*"; }

source "$TOOLBELT/grab/grab.sh"
source "$TOOLBELT/misc/compose_mail.sh"
source "$TOOLBELT/misc/yank-to-clipboard.sh"
snippets() { (cd "$TOOLBELT/snippets" || return 1; uv run cli "$@";) }

source $TOOLBELT/misc/diskusage.sh
source $TOOLBELT/misc/eject-all.sh



#            _
#   ___ __ _| | ___
#  / __/ _` | |/ __|
# | (_| (_| | | (__
#  \___\__,_|_|\___|
#

calc() { (cd "$TOOLBELT/calc" || return 1; uv run calc;) }

buf() { "$TOOLBELT/buffer/open.sh"; }
