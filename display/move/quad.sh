#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

hs -c "
local focus = hs.window.focusedWindow()
if not focus then return end

local screen = focus:screen()
if not screen then return end

local sf = screen:frame()
local hw, hh = sf.w / 2, sf.h / 2
local tol = 8

local slots = {
  hs.geometry.rect(sf.x,      sf.y,      hw, hh),
  hs.geometry.rect(sf.x + hw, sf.y,      hw, hh),
  hs.geometry.rect(sf.x,      sf.y + hh, hw, hh),
  hs.geometry.rect(sf.x + hw, sf.y + hh, hw, hh),
}

local function close(a, b) return math.abs(a - b) <= tol end
local function same(a, b)
  return close(a.x, b.x) and close(a.y, b.y) and close(a.w, b.w) and close(a.h, b.h)
end
local function center(r)
  return { x = r.x + r.w / 2, y = r.y + r.h / 2 }
end
local function dist2(a, b)
  local dx, dy = a.x - b.x, a.y - b.y
  return dx * dx + dy * dy
end

local wins = {}
for _, win in ipairs(hs.window.orderedWindows()) do
  if win:isStandard() and win:screen() == screen then
    table.insert(wins, win)
    if #wins == 4 then break end
  end
end

local placed, used = {}, {}
for i, slot in ipairs(slots) do
  for j, win in ipairs(wins) do
    if not used[j] and same(win:frame(), slot) then
      placed[i], used[j] = win, true
      break
    end
  end
end

local freeSlots, looseWins = {}, {}
for i = 1, math.min(#wins, 4) do
  if not placed[i] then table.insert(freeSlots, i) end
end
for j, win in ipairs(wins) do
  if not used[j] then table.insert(looseWins, win) end
end

local bestCost, bestOrder = nil, nil
local function search(pos, cost, order, taken)
  if bestCost and cost >= bestCost then return end
  if pos > #freeSlots then
    bestCost, bestOrder = cost, hs.fnutils.copy(order)
    return
  end
  local slotIndex = freeSlots[pos]
  local slotCenter = center(slots[slotIndex])
  for i, win in ipairs(looseWins) do
    if not taken[i] then
      taken[i], order[pos] = true, win
      search(pos + 1, cost + dist2(center(win:frame()), slotCenter), order, taken)
      taken[i], order[pos] = nil, nil
    end
  end
end

if #freeSlots > 0 then
  search(1, 0, {}, {})
  for i, slotIndex in ipairs(freeSlots) do
    if bestOrder and bestOrder[i] then
      placed[slotIndex] = bestOrder[i]
    end
  end
end

for i = 1, math.min(#wins, 4) do
  local win = placed[i]
  if win and not same(win:frame(), slots[i]) then
    win:setFrame(slots[i], 0)
  end
end
"
