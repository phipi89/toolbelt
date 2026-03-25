#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

script_dir=${0:A:h}

count=$(hs -c "
local focus = hs.window.focusedWindow()
if not focus then print(0) return end
local screen = focus:screen()
if not screen then print(0) return end
local n = 0
for _, win in ipairs(hs.window.orderedWindows()) do
  if win:isStandard() and win:screen() == screen then
    n = n + 1
    if n == 4 then break end
  end
end
print(n)
")

if [[ \"$count\" -eq 2 ]]; then
  hs -c "
  local focus = hs.window.focusedWindow()
  if not focus then return end

  local screen = focus:screen()
  if not screen then return end

  local sf = screen:frame()
  local tol = 8
  local left = hs.geometry.rect(sf.x, sf.y, sf.w / 2, sf.h)
  local right = hs.geometry.rect(sf.x + sf.w / 2, sf.y, sf.w / 2, sf.h)

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
      if #wins == 2 then break end
    end
  end

  local slots = { left, right }
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
  for i = 1, 2 do
    if not placed[i] then table.insert(freeSlots, i) end
  end
  for j, win in ipairs(wins) do
    if not used[j] then table.insert(looseWins, win) end
  end

  if #freeSlots == 2 then
    local leftCost = dist2(center(looseWins[1]:frame()), center(left)) + dist2(center(looseWins[2]:frame()), center(right))
    local rightCost = dist2(center(looseWins[1]:frame()), center(right)) + dist2(center(looseWins[2]:frame()), center(left))
    if leftCost <= rightCost then
      placed[1], placed[2] = looseWins[1], looseWins[2]
    else
      placed[1], placed[2] = looseWins[2], looseWins[1]
    end
  elseif #freeSlots == 1 then
    placed[freeSlots[1]] = looseWins[1]
  end

  if not same(placed[1]:frame(), left) then placed[1]:setFrame(left, 0) end
  if not same(placed[2]:frame(), right) then placed[2]:setFrame(right, 0) end
  "
else
  "$script_dir/quad.sh"
fi
