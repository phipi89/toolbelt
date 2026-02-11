TOOLBELT="$HOME/toolbelt"



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

source "$TOOLBELT/pytemp/pytemp.zsh"



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
snippets() { (cd "$TOOLBELT/misc" || return 1; uv run snippets.py;) }



#            _
#   ___ __ _| | ___
#  / __/ _` | |/ __|
# | (_| (_| | | (__
#  \___\__,_|_|\___|
#

calc() { (cd "$TOOLBELT/calc" || return 1; uv run calc;) }
