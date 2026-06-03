#!/bin/sh
set -eu

TOOLBELT="${TOOLBELT:-$HOME/toolbelt}"
BUFFER_DIR="$TOOLBELT/config/buffer"
BUFFER_FILE="$BUFFER_DIR/buffer.txt"
PROJECT_FILE="$BUFFER_DIR/buffer.sublime-project"
HISTORY_DIR="$HOME/.buffer_history"
MAX_AGE_SECONDS=300
MAX_HISTORY_ITEMS=10

mkdir -p "$BUFFER_DIR" "$HISTORY_DIR"
touch "$BUFFER_FILE"

now=$(date +%s)
modified=$(stat -f %m "$BUFFER_FILE")
age=$((now - modified))

if [ "$age" -gt "$MAX_AGE_SECONDS" ] && [ -s "$BUFFER_FILE" ]; then
  cp "$BUFFER_FILE" "$HISTORY_DIR/$(date +%Y%m%d-%H%M%S).txt"
  : > "$BUFFER_FILE"

  while [ "$(find "$HISTORY_DIR" -type f -name '*.txt' | wc -l | tr -d ' ')" -gt "$MAX_HISTORY_ITEMS" ]; do
    oldest=$(find "$HISTORY_DIR" -type f -name '*.txt' -print0 | xargs -0 stat -f '%m %N' | sort -n | head -n 1 | cut -d ' ' -f 2-)
    [ -n "$oldest" ] || break
    rm -- "$oldest"
  done
fi

/opt/homebrew/bin/subl --launch-or-new-window --project "$PROJECT_FILE" "$BUFFER_FILE"
sleep 0.3
"$TOOLBELT/display/move/center.sh" --size 40
