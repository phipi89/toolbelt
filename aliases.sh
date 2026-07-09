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

search() { (cd "$TOOLBELT/search" || return 1; clear; uv run search "$@";) }
goto() {
  local tmp target exit_status
  tmp="$(mktemp)" || return 1
  "$TOOLBELT/search/goto.sh" --result-file "$tmp"
  exit_status=$?
  if [[ $exit_status -ne 0 ]]; then
    rm -f "$tmp"
    return $exit_status
  fi
  target="$(<"$tmp")"
  rm -f "$tmp"
  [[ -n "$target" ]] && cd "$target"
}



#       _ _
#   ___| | | __
#  / __| | |/ /
# | (__| |   <
#  \___|_|_|\_\

# wrap in () runs the command in a subshell
_clk() { (cd "$TOOLBELT/clk"; uv run clk "$@";) }
alias clk='noglob _clk'



# TRANSLATION

translate() { (cd "$TOOLBELT/translate" || return 1; uv run translate "$@";) }
fen() { (cd "$TOOLBELT/translate" || return 1; uv run translate fen "$@";) }
ten() { (cd "$TOOLBELT/translate" || return 1; uv run translate ten "$@";) }
tfr() { (cd "$TOOLBELT/translate" || return 1; uv run translate tfr "$@";) }
ffr() { (cd "$TOOLBELT/translate" || return 1; uv run translate ffr "$@";) }
tit() { (cd "$TOOLBELT/translate" || return 1; uv run translate tit "$@";) }
fit() { (cd "$TOOLBELT/translate" || return 1; uv run translate fit "$@";) }



#            _
#  _ __ ___ (_)___  ___
# | '_ ` _ \| / __|/ __|
# | | | | | | \__ \ (__
# |_| |_| |_|_|___/\___|
#

alias textitle='uv run --no-project --with pyperclip,pyfiglet $TOOLBELT/misc/textitle.py'
alias pytitle='uv run --no-project --with pyperclip,pyfiglet $TOOLBELT/misc/textitle.py --prefix "#"'

ask(){ opencode run "$*"; }

source "$TOOLBELT/grab/grab.sh"
source "$TOOLBELT/misc/compose_mail.sh"
source "$TOOLBELT/misc/yank-to-clipboard.sh"
snippets() { (cd "$TOOLBELT/snippets" || return 1; uv run cli "$@";) }

source $TOOLBELT/misc/diskusage.sh
source $TOOLBELT/misc/eject-all.sh
alias oc="opencode -c"



#            _
#   ___ __ _| | ___
#  / __/ _` | |/ __|
# | (_| (_| | | (__
#  \___\__,_|_|\___|
#

calc() { (cd "$TOOLBELT/calc" || return 1; uv run calc;) }

timer() { clear && "$TOOLBELT/misc/timer.py"; }

buf() { "$TOOLBELT/buffer/open.sh" "$@"; }
