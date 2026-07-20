#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

script_dir=${0:A:h}
clear
print

if [[ -x "$script_dir/.venv/bin/run" ]]; then
  exec "$script_dir/.venv/bin/run"
fi

cd "$script_dir" || exit 1
exec uv run run
