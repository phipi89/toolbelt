# GENERAL

TOOLBELT="$HOME/toolbelt"
source ~/toolbelt/auth.sh


# ESSENTIALS

run() { (cd "$TOOLBELT/run" || return 1; uv run run;) }
calc() { (cd "$TOOLBELT/calc" || return 1; uv run calc;) }
snippets() { (cd "$TOOLBELT/snippets" || return 1; uv run cli "$@";) }
facts() { "$TOOLBELT/facts/facts.sh" "$@"; }
buf() { "$TOOLBELT/buffer/open.sh" "$@"; }
prose() { "$TOOLBELT/prose/open.sh" "$@"; }


# SEARCH

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


# PYTHON

source "$TOOLBELT/pytemp/pytemp.sh"


# TIME TRACKING

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


## FINDER INTERACTION

_finderctl() { (cd "$TOOLBELT/finder" || return 1; uv run finderctl "$@"); }
finderctl() { _finderctl "$@"; }

grab() {
  if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: grab"
    echo "Changes the current working directory to the folder currently open or selected in the frontmost Finder window."
    return 0
  fi

  local target_path
  target_path=$(_finderctl path) || return 1
  cd "$target_path" || return 1
}

gtouch() {
  if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    _finderctl touch --help
    return
  fi
  grab || return 1
  _finderctl touch "$@"
}

gsnap() { _finderctl snapshot "$@"; }
check_left_in_right() { _finderctl check-left-in-right "$@"; }


# LLMS

alias oc="opencode -c"
ask(){ opencode run "$*"; }


# MISCELANEOUS
timer() { clear && "$TOOLBELT/misc/timer.py"; }
alias textitle='uv run --no-project --with pyperclip,pyfiglet $TOOLBELT/misc/textitle.py'
alias pytitle='uv run --no-project --with pyperclip,pyfiglet $TOOLBELT/misc/textitle.py --prefix "#"'
source "$TOOLBELT/misc/compose_mail.sh"
source "$TOOLBELT/misc/yank-to-clipboard.sh"
source $TOOLBELT/misc/diskusage.sh
source $TOOLBELT/misc/eject-all.sh
setup() { "$TOOLBELT/setup/setup.sh" "$@"; }
