[[ -o interactive ]] || return 0

autoload -Uz add-zsh-hook

typeset -gi _toolbelt_tab_family=0
typeset -gi _toolbelt_tab_variant=0
typeset -gi _toolbelt_tab_preserve_state=0
typeset -gi _toolbelt_tab_skip_history=0
typeset -g _toolbelt_tab_git=${commands[git]:-/usr/bin/git}

_toolbelt_tab_reset() {
  if (( _toolbelt_tab_preserve_state )); then
    _toolbelt_tab_preserve_state=0
    return
  fi
  _toolbelt_tab_family=0
  _toolbelt_tab_variant=0
}

_toolbelt_tab_history() {
  if (( _toolbelt_tab_skip_history )); then
    _toolbelt_tab_skip_history=0
    return 1
  fi
  return 0
}

_toolbelt_tab_submit() {
  _toolbelt_tab_preserve_state=1
  _toolbelt_tab_skip_history=1
  BUFFER="_toolbelt_tab_execute ${(q)1}"
  CURSOR=${#BUFFER}
  zle accept-line
}

_toolbelt_tab_fit_line() {
  emulate -L zsh
  local rest=$1
  local -i maximum=$2 width=0
  local result="" sequence

  while [[ -n $rest ]] && (( width < maximum )); do
    if [[ $rest =~ $'^\e\\[[0-9;?]*[ -/]*[@-~]' ]]; then
      sequence=$MATCH
      result+=$sequence
      rest=${rest[$(( ${#sequence} + 1 )),-1]}
    else
      result+=${rest[1]}
      rest=${rest[2,-1]}
      (( width++ ))
    fi
  done

  REPLY="${result}"$'\e[0m'
}

_toolbelt_tab_execute() {
  local preset=$1
  local rows=$LINES
  local columns=$COLUMNS
  (( rows > 0 )) || rows=${terminfo[lines]:-24}
  (( columns > 0 )) || columns=${terminfo[cols]:-80}
  (( rows >= 8 )) || rows=8
  (( columns >= 20 )) || columns=20

  local prompt_without_newlines=${PROMPT//$'\n'/}
  local prompt_rows=$(( ${#PROMPT} - ${#prompt_without_newlines} + 1 ))
  local page_rows=$(( rows - prompt_rows ))
  (( page_rows >= 2 )) || page_rows=2
  local output_rows=$(( page_rows - 1 ))
  local label output

  case $preset in
    ls)
      label="ls"
      output=$(CLICOLOR_FORCE=1 COLUMNS=$columns /bin/ls -CG 2>&1 |
        /usr/bin/head -n $(( output_rows + 1 )))
      ;;
    ls-all)
      label="ls -la"
      output=$(CLICOLOR_FORCE=1 /bin/ls -laG 2>&1 |
        /usr/bin/head -n $(( output_rows + 1 )))
      ;;
    pwd)
      label="pwd"
      output=$(/bin/pwd 2>&1)
      ;;
    git-status)
      label="git status"
      if [[ -x $_toolbelt_tab_git ]]; then
        output=$("$_toolbelt_tab_git" --no-pager \
          -c color.ui=always -c core.fsmonitor=false status 2>&1 |
          /usr/bin/head -n $(( output_rows + 1 )))
      else
        output="git not found"
      fi
      ;;
    git-log)
      label="git log --oneline -10"
      if [[ -x $_toolbelt_tab_git ]]; then
        output=$("$_toolbelt_tab_git" --no-pager \
          -c color.ui=always -c core.fsmonitor=false log --oneline -10 2>&1 |
          /usr/bin/head -n $(( output_rows + 1 )))
      else
        output="git not found"
      fi
      ;;
    *)
      label=$preset
      output="unknown preset"
      ;;
  esac

  local -a output_lines
  output_lines=("${(@f)output}")
  local line_count=${#output_lines}
  local limit=$line_count
  local truncated=0
  if (( line_count > output_rows )); then
    truncated=1
    limit=$(( output_rows - 1 ))
  fi

  print -n -- "${terminfo[clear]:-$'\e[H\e[2J'}"
  print -r -- $'\e[2;36m'"$ $label"$'\e[0m'

  local index printed=0
  for (( index = 1; index <= limit; index++ )); do
    _toolbelt_tab_fit_line "${output_lines[index]}" "$columns"
    print -r -- "$REPLY"
    (( printed++ ))
  done
  if (( truncated )); then
    print -r -- $'\e[2m... output truncated ...\e[0m'
    (( printed++ ))
  fi
  while (( printed < output_rows )); do
    print
    (( printed++ ))
  done
}

_toolbelt_tab_run_ls_variant() {
  case $_toolbelt_tab_variant in
    1) _toolbelt_tab_submit ls ;;
    2) _toolbelt_tab_submit ls-all ;;
  esac
}

_toolbelt_tab_run_git_variant() {
  case $_toolbelt_tab_variant in
    1) _toolbelt_tab_submit git-status ;;
    2) _toolbelt_tab_submit git-log ;;
  esac
}

_toolbelt_tab_forward() {
  if [[ -n $BUFFER ]]; then
    zle expand-or-complete
    return
  fi

  case $_toolbelt_tab_family in
    1)
      _toolbelt_tab_family=2
      _toolbelt_tab_variant=1
      _toolbelt_tab_run_git_variant
      ;;
    2)
      _toolbelt_tab_family=3
      _toolbelt_tab_variant=1
      _toolbelt_tab_submit pwd
      ;;
    *)
      _toolbelt_tab_family=1
      _toolbelt_tab_variant=1
      _toolbelt_tab_run_ls_variant
      ;;
  esac
}

_toolbelt_tab_next_variant() {
  if [[ -n $BUFFER ]]; then
    zle reverse-menu-complete
    return
  fi

  case $_toolbelt_tab_family in
    1)
      (( _toolbelt_tab_variant = _toolbelt_tab_variant % 2 + 1 ))
      _toolbelt_tab_run_ls_variant
      ;;
    2)
      (( _toolbelt_tab_variant = _toolbelt_tab_variant % 2 + 1 ))
      _toolbelt_tab_run_git_variant
      ;;
  esac
}

add-zsh-hook precmd _toolbelt_tab_reset
add-zsh-hook zshaddhistory _toolbelt_tab_history
zle -N _toolbelt_tab_forward
zle -N _toolbelt_tab_next_variant
bindkey -M emacs '^I' _toolbelt_tab_forward
bindkey -M emacs "${terminfo[kcbt]:-$'\e[Z'}" _toolbelt_tab_next_variant
