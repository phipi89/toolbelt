#!/bin/zsh

set -euo pipefail

root=${0:A:h}
app="$root/Open in Obsidian.app"
contents="$app/Contents"
executable="$contents/MacOS/OpenInObsidian"
lsregister="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

mkdir -p "$contents/MacOS"
cp "$root/Info.plist" "$contents/Info.plist"
swiftc "$root/App.swift" -o "$executable" -framework AppKit -framework UniformTypeIdentifiers
codesign --force --deep --sign - "$app"
"$lsregister" -f "$app"

if [[ ${1:-} == "--associate" ]]; then
  "$executable" --associate "$app"
fi

print -r -- "$app"
