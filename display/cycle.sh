#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

hs -c "
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

if #wins < 2 then
  return
end

wins[2]:focus()
"
