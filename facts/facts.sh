#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

script_dir=${0:A:h}
if [[ -x "$script_dir/.venv/bin/facts" ]]; then
  exec "$script_dir/.venv/bin/facts" "$@"
fi

cd "$script_dir" || exit 1
exec uv run facts "$@"
