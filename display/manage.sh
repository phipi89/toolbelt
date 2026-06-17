#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


APP_NAME="$*"
CONFIG_PATH="$HOME/toolbelt/config/display/setup.yaml"

# 1. Get the action from YAML, fallback to default
export APP_NAME
ACTION=$(yq e '.apps[strenv(APP_NAME)].action // .default_action' "$CONFIG_PATH")
SPAWN_SCRIPT=$(yq e '.apps[strenv(APP_NAME)].spawn_script // ""' "$CONFIG_PATH")

if [[ "$ACTION" == "spawn_new" ]]; then
  exec "$HOME/toolbelt/display/$ACTION.sh" "$APP_NAME" "$SPAWN_SCRIPT"
fi

exec "$HOME/toolbelt/display/$ACTION.sh" "$APP_NAME"
