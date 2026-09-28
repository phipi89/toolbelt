#!/bin/zsh

set -euo pipefail

root=${0:A:h}
executable="$root/Open in Obsidian.app/Contents/MacOS/OpenInObsidian"

if [[ ! -x "$executable" || "$root/App.swift" -nt "$executable" || "$root/Info.plist" -nt "$executable" ]]; then
  "$root/build.sh" >/dev/null
fi

exec "$executable" "$@"
