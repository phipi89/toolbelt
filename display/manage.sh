#!/bin/zsh

if [[ -z "$ZSH_VERSION" ]]; then
  exec /bin/zsh "$0" "$@"
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [[ -n "$DISPLAY_TIMING" && "$DISPLAY_TIMING" != 0 && "$DISPLAY_TIMING" != false && "$DISPLAY_TIMING" != no && "$DISPLAY_TIMING" != off ]]; then
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

export APP_NAME
if ! ACTION=$(yq e -r '.apps[strenv(APP_NAME)].action // .default_action' "$CONFIG_PATH"); then
  print -u2 "failed to read display config: $CONFIG_PATH"
  exit 2
fi
_display_timing_mark "yq action"

case "$ACTION" in
  spawn_new)
    if ! SPAWN_SCRIPT=$(yq e -r '.apps[strenv(APP_NAME)].spawn_script // ""' "$CONFIG_PATH"); then
      print -u2 "failed to read display config: $CONFIG_PATH"
      exit 2
    fi
    _display_timing_mark "yq spawn_script"
    _display_timing_mark "exec spawn_new"
    exec "$HOME/toolbelt/display/spawn_new.sh" "$APP_NAME" "$SPAWN_SCRIPT"
    ;;
  goto|select|move_here)
    _display_timing_mark "exec $ACTION"
    exec "$HOME/toolbelt/display/$ACTION.sh" "$APP_NAME"
    ;;
  *)
    print -u2 "unknown display action: $ACTION"
    exit 2
    ;;
esac
