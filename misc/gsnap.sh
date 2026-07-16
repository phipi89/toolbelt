gsnap() {
  if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: gsnap"
    echo "Copies the selected Finder file into a snapshots/ subdirectory with a timestamped name."
    return 0
  fi

  local selected dir filename stem ext timestamp target
  selected=$(osascript "$TOOLBELT/grab/get-finder-selected-file.osa") || return 1

  if [[ ! -f "$selected" ]]; then
    echo "gsnap: selected item is not a file: $selected" >&2
    return 1
  fi

  dir=${selected:h}
  filename=${selected:t}
  timestamp=$(date +%Y%m%d-%H%M%S)

  if [[ "$filename" == *.* && "$filename" != .* ]]; then
    stem=${filename:r}
    ext=.${filename:e}
  else
    stem=$filename
    ext=
  fi

  mkdir -p "$dir/snapshots" || return 1
  target="$dir/snapshots/$stem-$timestamp$ext"
  cp -p "$selected" "$target" || return 1
  echo "$target"
}
