#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

script_dir=${0:A:h}
restart_file="${TMPDIR:-/tmp}/toolbelt-run-restart-$$"
export RUN_RESTART_FILE="$restart_file"
rm -f "$restart_file"
trap 'rm -f "$restart_file"' EXIT

while true; do
  clear
  print
  if [[ -x "$script_dir/.venv/bin/run" ]]; then
    "$script_dir/.venv/bin/run"
  else
    (cd "$script_dir" && uv run run)
  fi
  exit_status=$?

  if [[ ! -e "$restart_file" ]]; then
    exit "$exit_status"
  fi
  rm -f "$restart_file"
done
