#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

frontmost_right=false
case "$1" in
  --frontmost-right|--right|-r)
    frontmost_right=true
    ;;
esac

hs -c "
local frontmostRight = ${frontmost_right}
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
local tol = 8
local leftHalf = hs.geometry.rect(sf.x, sf.y, sf.w / 2, sf.h)
local rightHalf = hs.geometry.rect(sf.x + sf.w / 2, sf.y, sf.w / 2, sf.h)
local leftTwoThirds = hs.geometry.rect(sf.x, sf.y, sf.w * 2 / 3, sf.h)
local rightOneThird = hs.geometry.rect(sf.x + sf.w * 2 / 3, sf.y, sf.w / 3, sf.h)
local leftOneThird = hs.geometry.rect(sf.x, sf.y, sf.w / 3, sf.h)
local rightTwoThirds = hs.geometry.rect(sf.x + sf.w / 3, sf.y, sf.w * 2 / 3, sf.h)

local function close(a, b) return math.abs(a - b) <= tol end
local function same(a, b)
  return close(a.x, b.x) and close(a.y, b.y) and close(a.w, b.w) and close(a.h, b.h)
end

local leftWin, rightWin = wins[1], wins[2]
if frontmostRight then
  leftWin, rightWin = wins[2], wins[1]
end

local isHalf = same(leftWin:frame(), leftHalf) and same(rightWin:frame(), rightHalf)
local isWeighted = nil
if frontmostRight then
  isWeighted = same(leftWin:frame(), leftOneThird) and same(rightWin:frame(), rightTwoThirds)
else
  isWeighted = same(leftWin:frame(), leftTwoThirds) and same(rightWin:frame(), rightOneThird)
end

if isHalf then
  if frontmostRight then
    leftWin:setFrame(leftOneThird, 0)
    rightWin:setFrame(rightTwoThirds, 0)
  else
    leftWin:setFrame(leftTwoThirds, 0)
    rightWin:setFrame(rightOneThird, 0)
  end
elseif isWeighted then
  leftWin:setFrame(leftHalf, 0)
  rightWin:setFrame(rightHalf, 0)
else
  leftWin:setFrame(leftHalf, 0)
  rightWin:setFrame(rightHalf, 0)
end
"
