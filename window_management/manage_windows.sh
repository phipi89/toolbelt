#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


APP_NAME="$*"
CONFIG_PATH="$HOME/toolbelt/config/window_management/setup.yaml"

# 1. Get the action from YAML, fallback to default
export APP_NAME
ACTION=$(yq e '.apps[strenv(APP_NAME)].action // .default_action' "$CONFIG_PATH")
SPAWN_SCRIPT=$(yq e '.apps[strenv(APP_NAME)].spawn_script // ""' "$CONFIG_PATH")

echo "$ACTION"
echo "$SPAWN_SCRIPT"
"$HOME/toolbelt/window_management/$ACTION.sh" "$APP_NAME" "$SPAWN_SCRIPT"
