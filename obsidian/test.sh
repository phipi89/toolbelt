#!/bin/zsh

set -euo pipefail

root=${0:A:h}
executable="$root/Open in Obsidian.app/Contents/MacOS/OpenInObsidian"
temporary_directory=$(mktemp -d)
trap 'rm -rf "$temporary_directory"' EXIT

vault="$temporary_directory/Vault With Spaces"
note="$vault/Folder With Spaces/Note & More.md"
mkdir -p "$vault/.obsidian" "${note:h}"
touch "$note"

uri=$("$executable" --dry-run "$note")
[[ "$uri" == obsidian://open\?path=* ]]
[[ "$uri" == *"%20"* ]]
[[ "$uri" == *"%26"* ]]
[[ "$uri" != *" "* ]]

fallback="$temporary_directory/Fallback Vault"
external="$temporary_directory/Outside Folder/External Note.md"
mkdir -p "$fallback/.obsidian" "${external:h}"
touch "$external"

uri=$(OBSIDIAN_FALLBACK_VAULT="$fallback" "$executable" --dry-run "$external")
link="$fallback/temporarily linked.md"
[[ -L "$link" ]]
[[ "${link:A}" == "${external:A}" ]]
[[ "$uri" == *"Fallback%20Vault%2Ftemporarily%20linked.md" ]]

print "open-in-obsidian tests passed"
