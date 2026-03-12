#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

hs -c "
local wins = {}

for _, win in ipairs(hs.window.orderedWindows()) do
  if win:isStandard() and win:isVisible() then
    table.insert(wins, win)
  end
end

if #wins < 2 then
  return
end

-- Rotate front-to-back order [A, B, C] into [B, C, A]
-- by bringing windows to front from back to front.
for i = #wins, 2, -1 do
  wins[i]:focus()
end
"
