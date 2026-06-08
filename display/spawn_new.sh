#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_NAME=$1
SPAWN_SCRIPT=${2:-}

printf '[spawn_new.sh] start app="%s"\n' "$APP_NAME"
printf '[spawn_new.sh] spawn_script_len=%s\n' "${#SPAWN_SCRIPT}"

hs -n "$HOME/toolbelt/display/lua/cli.lua" -- spawn-new "$APP_NAME" "$SPAWN_SCRIPT"
exit_code=$?

printf '[spawn_new.sh] end app="%s" exit=%s\n' "$APP_NAME" "$exit_code"
exit $exit_code
