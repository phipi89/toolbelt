#!/bin/zsh

script_dir=${0:A:h}
restart_file="${TMPDIR:-/tmp}/toolbelt-search-restart-$$"
export SEARCH_RESTART_FILE="$restart_file"
rm -f "$restart_file"
trap 'rm -f "$restart_file"' EXIT

while true; do
  clear
  echo
  if [[ -x "$script_dir/.venv/bin/search" ]]; then
    "$script_dir/.venv/bin/search" "$@"
  else
    (cd "$script_dir" && /usr/bin/env uv run search "$@")
  fi
  exit_status=$?

  if [[ ! -e "$restart_file" ]]; then
    exit "$exit_status"
  fi
  rm -f "$restart_file"
done
