#!/bin/zsh

source "$HOME/toolbelt/path.sh"

APP_NAME=$1
CONFIG_PATH="$HOME/toolbelt/config/window_management/setup.yaml"

# 1. Get the action from YAML, fallback to default
export APP_NAME
ACTION=$(yq e '.apps[strenv(APP_NAME)] // .default_action' "$CONFIG_PATH")


$HOME/toolbelt/window_management/$ACTION.sh $APP_NAME
