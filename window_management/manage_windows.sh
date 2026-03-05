#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_NAME="$*"
CONFIG_PATH="$HOME/toolbelt/config/window_management/setup.yaml"

export APP_NAME

# Support both config styles:
# apps:
#   AppName: spawn_new
# OR
# apps:
#   AppName:
#     action: spawn_new
ACTION=$(yq e '.apps[strenv(APP_NAME)].action // .apps[strenv(APP_NAME)] // .default_action' "$CONFIG_PATH")

# Optional per-app spawn script (used by spawn_new.sh)
SPAWN_SCRIPT=$(yq e -r '.apps[strenv(APP_NAME)].spawn_script // ""' "$CONFIG_PATH")
export SPAWN_SCRIPT

"$HOME/toolbelt/window_management/$ACTION.sh" "$APP_NAME"
