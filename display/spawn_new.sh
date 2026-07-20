#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_NAME=$1
SPAWN_SCRIPT=${2:-}

exec "$HOME/toolbelt/display/displayctl.sh" spawn-new "$APP_NAME" "$SPAWN_SCRIPT"
