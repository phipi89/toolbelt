#!/usr/bin/env zsh

eject-all() {
  if [ "${1-}" = "-h" ] || [ "${1-}" = "--help" ]; then
    echo "usage: eject-all"
    echo "  eject all connected external physical disks so they can be unplugged."
    return 0
  fi

  local -a disks
  disks=("${(@f)$(
    diskutil list external physical 2>/dev/null |
      awk '/^\/dev\/disk[0-9]+/ { print $1 }'
  )}")


  if [ "${#disks[@]}" -eq 0 ]; then
    echo "No external physical disks found."
    return 0
  fi

  local failed=0
  local total="${#disks[@]}"
  local i=1
  local disk
  for disk in "${disks[@]}"; do
    echo "Ejecting disk ${i} / ${total}: ${disk}..."
    if ! diskutil eject "$disk"; then
      failed=1
    fi
    ((i++))
  done

  return "$failed"
}

if [[ "$ZSH_EVAL_CONTEXT" == toplevel ]]; then
  eject-all "$@"
fi
