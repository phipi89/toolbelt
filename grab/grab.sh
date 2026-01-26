grab() {
  if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: grab"
    echo "Changes the current working directory to the folder currently open or selected in the frontmost Finder window."
    return 0
  fi

  local target_path
  target_path=$(osascript "$TOOLBELT/grab/get-finder-path.osa")

  if [[ -d "$target_path" ]]; then
    cd "$target_path"
  else
    echo "Error: $target_path" >&2
    return 1
  fi
}
