#!/bin/sh
set -eu

TOOLBELT="${TOOLBELT:-$HOME/toolbelt}"
TOOLBELT_LOCAL="${TOOLBELT_LOCAL:-$HOME/.toolbelt-local}"
BUFFER_DIR="$TOOLBELT_LOCAL/buffer"
BUFFER_FILE="$BUFFER_DIR/buffer.txt"
STATE_FILE="$BUFFER_DIR/buffer.state"
HISTORY_DIR="$BUFFER_DIR/history"
OLD_BUFFER_FILE="$TOOLBELT/config/buffer/buffer.txt"
OLD_HISTORY_DIR="$HOME/.buffer_history"
MAX_AGE_SECONDS=300
MAX_HISTORY_ITEMS=10
clear_now=false
open_last=false
open_history=false

usage() {
  cat <<'EOF'
usage: buf [--clear|-c] [--last] [--history] [-h|--help]

Options:
  -c, --clear    Archive and clear the current buffer before opening it
  --last         Open the newest archived buffer
  --history      Open the buffer history directory
  -h, --help     Show this help
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --clear|-c)
      clear_now=true
      ;;
    --last)
      open_last=true
      ;;
    --history)
      open_history=true
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
  shift
done

mkdir -p "$BUFFER_DIR" "$HISTORY_DIR"

if [ ! -e "$BUFFER_FILE" ] && [ -e "$OLD_BUFFER_FILE" ]; then
  cp "$OLD_BUFFER_FILE" "$BUFFER_FILE"
fi

if [ -d "$OLD_HISTORY_DIR" ] && [ -z "$(find "$HISTORY_DIR" -type f -name '*.txt' -print -quit)" ]; then
  find "$OLD_HISTORY_DIR" -type f -name '*.txt' -exec cp -n {} "$HISTORY_DIR" \;
fi

if [ "$open_history" = true ]; then
  open "$HISTORY_DIR"
  exit 0
fi

if [ "$open_last" = true ]; then
  last=$(find "$HISTORY_DIR" -type f -name '*.txt' -print0 | xargs -0 stat -f '%m %N' | sort -nr | head -n 1 | cut -d ' ' -f 2-)
  if [ -z "$last" ]; then
    echo "No buffer history found." >&2
    exit 1
  fi
  open -a CotEditor "$last"
  sleep 0.3
  "$TOOLBELT/display/move/center.sh" --size 40 || true
  exit 0
fi

touch "$BUFFER_FILE"

hash=$(shasum -a 256 "$BUFFER_FILE" | cut -d ' ' -f 1)
changed_at=0
stored_hash=

if [ -f "$STATE_FILE" ]; then
  while IFS='=' read -r key value; do
    case "$key" in
      stored_hash) stored_hash=$value ;;
      changed_at) changed_at=$value ;;
    esac
  done < "$STATE_FILE"
fi

now=$(date +%s)
if [ "$hash" != "${stored_hash:-}" ]; then
  changed_at=$now
fi
case "$changed_at" in
  ''|*[!0-9]*) changed_at=$now ;;
esac
age=$((now - changed_at))

if { [ "$clear_now" = true ] || [ "$age" -gt "$MAX_AGE_SECONDS" ]; } && [ -s "$BUFFER_FILE" ]; then
  cp "$BUFFER_FILE" "$HISTORY_DIR/$(date +%Y%m%d-%H%M%S).txt"
  : > "$BUFFER_FILE"
  hash=$(shasum -a 256 "$BUFFER_FILE" | cut -d ' ' -f 1)
  changed_at=$now

  while [ "$(find "$HISTORY_DIR" -type f -name '*.txt' | wc -l | tr -d ' ')" -gt "$MAX_HISTORY_ITEMS" ]; do
    oldest=$(find "$HISTORY_DIR" -type f -name '*.txt' -print0 | xargs -0 stat -f '%m %N' | sort -n | head -n 1 | cut -d ' ' -f 2-)
    [ -n "$oldest" ] || break
    rm -- "$oldest"
  done
fi

{
  printf 'stored_hash=%s\n' "$hash"
  printf 'changed_at=%s\n' "$changed_at"
} > "$STATE_FILE"

open -a CotEditor "$BUFFER_FILE"
sleep 0.3
"$TOOLBELT/display/move/center.sh" --size 40 || true
