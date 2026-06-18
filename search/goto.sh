#!/bin/zsh

script_dir=${0:A:h}
if [[ -x "$script_dir/.venv/bin/goto-picker" ]]; then
  exec "$script_dir/.venv/bin/goto-picker" "$@"
fi

cd "$script_dir" || exit 1
exec uv run goto-picker "$@"
