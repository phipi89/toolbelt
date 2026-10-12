#!/usr/bin/env zsh

eject-all() {
  if [ "${1-}" = "-h" ] || [ "${1-}" = "--help" ]; then
    echo "usage: eject-all"
    echo "  eject all connected external physical disks so they can be unplugged."
    return 0
  fi

  ( __eject_all_run ) >/dev/null 2>&1 &!
  echo "Started ejecting external disks in the background."
}

__eject_all_run() {
  local -a disks
  disks=("${(@f)$(
    diskutil list external physical 2>/dev/null |
      awk '/^\/dev\/disk[0-9]+/ { print $1 }'
  )}")


  if [ "${#disks[@]}" -eq 0 ]; then
    osascript -e 'display notification "No external physical disks found." with title "eject-all"' 2>/dev/null
    return 0
  fi

  local failed=0
  local -a failed_disks
  failed_disks=()
  local total="${#disks[@]}"
  local i=1
  local disk
  for disk in "${disks[@]}"; do
    echo "Ejecting disk ${i} / ${total}: ${disk}..."
    if ! diskutil eject "$disk"; then
      failed=1
      failed_disks+=("$disk")
    fi
    ((i++))
  done

  local message
  if [ "$failed" -eq 0 ]; then
    message="Ejected all ${total} external disk(s)."
  else
    message="Ejected with errors: ${failed_disks[*]}"
  fi
  osascript -e "display notification \"${message}\" with title \"eject-all\"" 2>/dev/null

  return "$failed"
}

if [[ "$ZSH_EVAL_CONTEXT" == toplevel ]]; then
  eject-all "$@"
fi
