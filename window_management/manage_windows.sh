#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_NAME=$1
CONFIG_PATH="$HOME/toolbelt/config/window_management/setup.yaml"

# 1. Get the action from YAML, fallback to default

ACTION=$(yq ".apps.\"$APP_NAME\" // .default_action" "$CONFIG_PATH")

$HOME/toolbelt/window_management/$ACTION.sh $APP_NAME
