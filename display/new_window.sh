#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_NAME="$*"
CONFIG_PATH="$HOME/toolbelt/config/display/setup.yaml"

export APP_NAME
SPAWN_SCRIPT=$(yq e -r '(.apps | with_entries(.key |= downcase))[(strenv(APP_NAME) | downcase)].spawn_script // ""' "$CONFIG_PATH")

exec "$HOME/toolbelt/display/displayctl.sh" spawn-new --force "$APP_NAME" "$SPAWN_SCRIPT"
