#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [[ -n "$DISPLAY_TIMING" ]]; then
  zmodload zsh/datetime 2>/dev/null || true
  _display_timing_last=$EPOCHREALTIME
  _display_timing_mark() {
    local now=$EPOCHREALTIME
    printf 'manage %-28s %7.1fms\n' "$1" $(( (now - _display_timing_last) * 1000 )) >&2
    _display_timing_last=$now
  }
else
  _display_timing_mark() { :; }
fi

APP_NAME="$*"
CONFIG_PATH="$HOME/toolbelt/config/display/setup.yaml"

# 1. Get the action from YAML, fallback to default
export APP_NAME
ACTION=$(yq e '.apps[strenv(APP_NAME)].action // .default_action' "$CONFIG_PATH")
_display_timing_mark "yq action"
SPAWN_SCRIPT=$(yq e '.apps[strenv(APP_NAME)].spawn_script // ""' "$CONFIG_PATH")
_display_timing_mark "yq spawn_script"

if [[ "$ACTION" == "spawn_new" ]]; then
  _display_timing_mark "exec spawn_new"
  exec "$HOME/toolbelt/display/$ACTION.sh" "$APP_NAME" "$SPAWN_SCRIPT"
fi

_display_timing_mark "exec $ACTION"
exec "$HOME/toolbelt/display/$ACTION.sh" "$APP_NAME"
