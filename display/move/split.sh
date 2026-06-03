#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

frontmost_right=false
case "$1" in
  --frontmost-right|--right|-r)
    frontmost_right=true
    ;;
esac

export FRONTMOST_RIGHT="$frontmost_right"

hs -c "
local frontmostRight = os.getenv('FRONTMOST_RIGHT') == 'true'
local focus = hs.window.focusedWindow()
local screen = (focus and focus:screen()) or hs.mouse.getCurrentScreen()
if not screen then return end

local wins = {}
for _, win in ipairs(hs.window.orderedWindows()) do
  if win:isStandard() and win:isVisible() and win:screen() == screen then
    table.insert(wins, win)
    if #wins == 2 then break end
  end
end

if #wins < 2 then return end

local sf = screen:frame()
local left = hs.geometry.rect(sf.x, sf.y, sf.w / 2, sf.h)
local right = hs.geometry.rect(sf.x + sf.w / 2, sf.y, sf.w / 2, sf.h)

if frontmostRight then
  wins[1]:setFrame(right, 0)
  wins[2]:setFrame(left, 0)
else
  wins[1]:setFrame(left, 0)
  wins[2]:setFrame(right, 0)
end
"
