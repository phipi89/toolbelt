#!/usr/bin/env bash
set -euo pipefail

osascript <<'APPLESCRIPT'
tell application "System Events"
  keystroke "c" using command down
end tell

delay 0.2
set selectedText to the clipboard as text

if selectedText is "" then
  display notification "Clipboard is empty after copy." with title "Send to ChatGPT"
  return
end if

do shell script "open -na 'Firefox' --args --new-window 'https://chatgpt.com'"
delay 2.5

set the clipboard to selectedText
tell application "System Events"
  keystroke "v" using command down
  key code 36
end tell
APPLESCRIPT
