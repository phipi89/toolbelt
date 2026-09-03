#!/bin/sh
set -eu

TOOLBELT="${TOOLBELT:-$HOME/toolbelt}"
TOOLBELT_LOCAL="${TOOLBELT_LOCAL:-$HOME/.toolbelt-local}"
PROSE_DIR="$TOOLBELT_LOCAL/prose"
DOCUMENTS_DIR="$PROSE_DIR/documents"
RECENT_DIR="$PROSE_DIR/recent"
BACKUP_DIR="$PROSE_DIR/.backup"
MIGRATION_MARKER="$PROSE_DIR/.recents-v3"
APP="$PROSE_DIR/Prose.app"
SOURCE="$TOOLBELT/prose/App.swift"
INFO_PLIST="$TOOLBELT/prose/Info.plist"
BINARY="$APP/Contents/MacOS/Prose"

usage() {
  cat <<'EOF'
usage: prose [--recent] [-h|--help]

Options:
  --recent      Select and reopen a recently closed document
  -h, --help    Show this help
EOF
}

build_app() {
  if [ ! -x "$BINARY" ] || [ "$SOURCE" -nt "$BINARY" ] || [ "$INFO_PLIST" -nt "$APP/Contents/Info.plist" ]; then
    mkdir -p "$APP/Contents/MacOS"
    swiftc -O -framework AppKit "$SOURCE" -o "$BINARY.new"
    mv "$BINARY.new" "$BINARY"
    cp "$INFO_PLIST" "$APP/Contents/Info.plist"
  fi
}

open_document() {
  build_app
  open -n "$APP" --args "$1"
}

open_recent() {
  set -- "$RECENT_DIR"/*.txt
  if [ ! -e "$1" ]; then
    printf 'No recent prose documents.\n' >&2
    exit 1
  fi

  listing=$(mktemp)
  choices=$(mktemp)
  trap 'rm -f "$listing" "$choices"' EXIT HUP INT TERM

  for file do
    printf '%s\t%s\n' "$(stat -f '%m' "$file")" "$file"
  done | sort -rn > "$listing"

  index=0
  while IFS="$(printf '\t')" read -r modified file; do
    index=$((index + 1))
    preview=$(tr '\n' ' ' < "$file" | cut -c 1-72)
    [ -n "$preview" ] || preview='(empty)'
    printf '%2d  %s  %s\n' "$index" "$(date -r "$modified" '+%Y-%m-%d %H:%M')" "$preview"
    printf '%s\n' "$file" >> "$choices"
  done < "$listing"

  printf 'Open document: '
  IFS= read -r selection
  case "$selection" in
    ''|*[!0-9]*) printf 'Invalid selection.\n' >&2; exit 2 ;;
  esac
  selected=$(sed -n "${selection}p" "$choices")
  if [ -z "$selected" ]; then
    printf 'Invalid selection.\n' >&2
    exit 2
  fi
  active="$DOCUMENTS_DIR/$(basename "$selected")"
  mv "$selected" "$active"
  open_document "$active"
}

maintain_history() {
  now=$(date +%s)
  recent_cutoff=$((now - 7 * 24 * 60 * 60))
  backup_cutoff=$((now - 30 * 24 * 60 * 60))

  set -- "$RECENT_DIR"/*.txt
  if [ -e "$1" ]; then
    for file do
      if [ "$(stat -f '%m' "$file")" -le "$recent_cutoff" ]; then
        mv "$file" "$BACKUP_DIR/$(basename "$file")"
      fi
    done
  fi

  set -- "$BACKUP_DIR"/*.txt
  if [ -e "$1" ]; then
    for file do
      if [ "$(stat -f '%m' "$file")" -le "$backup_cutoff" ]; then
        rm "$file"
      fi
    done
  fi
}

case "${1:-}" in
  --recent)
    [ "$#" -eq 1 ] || { usage >&2; exit 2; }
    mode=recent
    ;;
  --help|-h)
    usage
    exit 0
    ;;
  '')
    mode=new
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

mkdir -p "$DOCUMENTS_DIR" "$RECENT_DIR" "$BACKUP_DIR"

if [ ! -e "$MIGRATION_MARKER" ]; then
  set -- "$DOCUMENTS_DIR"/*.txt
  if [ -e "$1" ]; then
    for file do
      mv "$file" "$RECENT_DIR/$(basename "$file")"
    done
  fi

  migration_cutoff=$(($(date +%s) - 7 * 24 * 60 * 60))
  set -- "$BACKUP_DIR"/*.txt
  if [ -e "$1" ]; then
    for file do
      if [ "$(stat -f '%m' "$file")" -gt "$migration_cutoff" ]; then
        mv "$file" "$RECENT_DIR/$(basename "$file")"
      fi
    done
  fi
  touch "$MIGRATION_MARKER"
fi

maintain_history

if [ "$mode" = recent ]; then
  open_recent
else
  document="$DOCUMENTS_DIR/$(uuidgen | tr '[:upper:]' '[:lower:]').txt"
  : > "$document"
  open_document "$document"
fi
