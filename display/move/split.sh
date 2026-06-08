#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

exec hs -q "$HOME/toolbelt/display/lua/cli.lua" -- move split "$@"
