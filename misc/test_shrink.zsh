#!/usr/bin/env zsh

set -euo pipefail

script_dir=${0:A:h}
source "$script_dir/shrink.sh"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

input="$tmp/report.pdf"
gs -q -sDEVICE=pdfwrite -o "$input" -c showpage
shrink "$input"
[[ -f "$tmp/report_small.pdf" ]]
if shrink "$input" >/dev/null 2>&1; then
  print -u2 "shrink replaced an existing output"
  exit 1
fi

captured=()
shrink() { captured=("$@") }
_finderctl() { print "$input" }
gshrink --balanced "$tmp/finder-output.pdf"
[[ "${captured[*]}" == "$input --balanced $tmp/finder-output.pdf" ]]

print "shrink tests passed"
