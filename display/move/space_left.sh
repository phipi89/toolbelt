#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

hs -c "
local spaces = hs.spaces
local win = hs.window.focusedWindow()

local function log(msg)
  print(os.date('[%Y-%m-%d %H:%M:%S] [space_left] ') .. msg)
end

if not spaces or not win or not win:isStandard() then
  log('missing spaces API or focused standard window')
  return
end

local screen = win:screen()
if not screen then
  log('focused window has no screen')
  return
end

local allSpaces = spaces.allSpaces()
local screenSpaces = allSpaces[screen:getUUID()]
if not screenSpaces or #screenSpaces == 0 then
  log('no spaces found for screen ' .. tostring(screen:getUUID()))
  return
end

local currentSpace = spaces.focusedSpace()
local targetIndex = nil

log('window id=' .. tostring(win:id()) .. ' title=' .. tostring(win:title()))
log('screen=' .. tostring(screen:getUUID()) .. ' currentSpace=' .. tostring(currentSpace))
log('screenSpaces=' .. hs.inspect(screenSpaces))

for i, spaceId in ipairs(screenSpaces) do
  if spaceId == currentSpace then
    targetIndex = i - 1
    break
  end
end

if not targetIndex or targetIndex < 1 then
  log('no target space to the left')
  return
end

local targetSpace = screenSpaces[targetIndex]
local function contains(t, value)
  if not t then
    return false
  end
  for _, item in ipairs(t) do
    if item == value then
      return true
    end
  end
  return false
end

local moved = spaces.moveWindowToSpace(win, targetSpace)
log('move attempt result=' .. tostring(moved) .. ' targetSpace=' .. tostring(targetSpace))
if not moved then
  moved = spaces.moveWindowToSpace(win, targetSpace, true)
  log('forced move attempt result=' .. tostring(moved))
end

local winSpaces = nil
for _ = 1, 20 do
  hs.timer.usleep(100000)
  winSpaces = spaces.windowSpaces(win)
  if contains(winSpaces, targetSpace) then
    break
  end
end
log('windowSpaces after move=' .. hs.inspect(winSpaces))

if not contains(winSpaces, targetSpace) then
  log('window is not on target space after move; aborting gotoSpace')
  return
end

hs.timer.usleep(150000)
local switched, switchErr = spaces.gotoSpace(targetSpace)
log('gotoSpace result=' .. tostring(switched) .. ' err=' .. tostring(switchErr))
hs.timer.usleep(150000)
win:focus()
log('refocused window')
"
