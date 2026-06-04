#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

target_index=2
case "$1" in
  --third|-3)
    target_index=3
    ;;
esac

hs -c "
local targetIndex = tonumber('${target_index}') or 2
local wins = {}
local focused = hs.window.focusedWindow()
local targetScreen = (focused and focused:screen()) or hs.mouse.getCurrentScreen()

if not targetScreen then
  return
end

for _, win in ipairs(hs.window.orderedWindows()) do
  if win:isStandard() and win:isVisible() and win:screen() == targetScreen then
    table.insert(wins, win)
  end
end

if #wins < targetIndex then
  return
end

wins[targetIndex]:focus()
"
