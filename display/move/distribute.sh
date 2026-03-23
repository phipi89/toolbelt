#!/bin/zsh

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

hs -c "
local win = hs.window.focusedWindow()
local screen = win and win:screen() or hs.screen.mainScreen()

local function log(msg)
  print(os.date('[%Y-%m-%d %H:%M:%S] [distribute] ') .. msg)
end

if not screen then
  log('no screen found')
  return
end

local sf = screen:frame()
local screenArea = sf.w * sf.h
local tol = 12

log('focusedWindow=' .. tostring(win and win:id() or nil) .. ' screen=' .. tostring(screen:getUUID()))
log(string.format('screenFrame x=%.1f y=%.1f w=%.1f h=%.1f', sf.x, sf.y, sf.w, sf.h))

local function close(a, b)
  return math.abs(a - b) <= tol
end

local function touchesEdge(frame)
  return close(frame.x, sf.x)
    or close(frame.y, sf.y)
    or close(frame.x + frame.w, sf.x + sf.w)
    or close(frame.y + frame.h, sf.y + sf.h)
end

local function touchesLeft(frame)
  return close(frame.x, sf.x)
end

local function touchesRight(frame)
  return close(frame.x + frame.w, sf.x + sf.w)
end

local function touchesTop(frame)
  return close(frame.y, sf.y)
end

local function touchesBottom(frame)
  return close(frame.y + frame.h, sf.y + sf.h)
end

local function fillsScreen(frame)
  return close(frame.x, sf.x)
    and close(frame.y, sf.y)
    and close(frame.w, sf.w)
    and close(frame.h, sf.h)
end

local function isRightColumn(frame)
  return touchesRight(frame) and touchesTop(frame) and touchesBottom(frame)
end

local function isLeftColumn(frame)
  return touchesLeft(frame) and touchesTop(frame) and touchesBottom(frame)
end

local function clamp(value, minValue, maxValue)
  if value < minValue then
    return minValue
  end
  if value > maxValue then
    return maxValue
  end
  return value
end

local function moveWindow(targetWin, x, y)
  local frame = targetWin:frame()
  local width = math.min(frame.w, sf.w)
  local height = math.min(frame.h, sf.h)
  local maxX = sf.x + sf.w - width
  local maxY = sf.y + sf.h - height
  local nextFrame = hs.geometry.rect(
    clamp(x, sf.x, maxX),
    clamp(y, sf.y, maxY),
    width,
    height
  )
  log(string.format(
    'move id=%s title=%s from x=%.1f y=%.1f w=%.1f h=%.1f to x=%.1f y=%.1f w=%.1f h=%.1f',
    tostring(targetWin:id()),
    tostring(targetWin:title()),
    frame.x, frame.y, frame.w, frame.h,
    nextFrame.x, nextFrame.y, nextFrame.w, nextFrame.h
  ))
  targetWin:setFrame(nextFrame, 0)
end

local candidates = {}
local hasSideColumn = false
for _, orderedWin in ipairs(hs.window.orderedWindows()) do
  if orderedWin:isStandard() and orderedWin:screen() == screen then
    local frame = orderedWin:frame()
    local area = frame.w * frame.h
    local id = tostring(orderedWin:id())
    local title = tostring(orderedWin:title())
    local fills = fillsScreen(frame)
    local small = area < screenArea * 0.15
    local edge = touchesEdge(frame)
    local leftColumn = isLeftColumn(frame)
    local rightColumn = isRightColumn(frame)
    if leftColumn or rightColumn then
      hasSideColumn = true
    end
    log(string.format(
      'inspect id=%s title=%s frame x=%.1f y=%.1f w=%.1f h=%.1f fills=%s small=%s edge=%s leftColumn=%s rightColumn=%s',
      id, title, frame.x, frame.y, frame.w, frame.h, tostring(fills), tostring(small), tostring(edge), tostring(leftColumn), tostring(rightColumn)
    ))
    if not fills and not small and not leftColumn and not rightColumn then
      table.insert(candidates, orderedWin)
      log('candidate id=' .. id .. ' title=' .. title)
    else
      log('skip id=' .. id .. ' title=' .. title)
    end
  end
end

log('candidateCount=' .. tostring(#candidates))
log('hasSideColumn=' .. tostring(hasSideColumn))

if #candidates < 2 then
  log('fewer than two candidates, nothing to distribute')
  return
end

if #candidates > 5 then
  log('more than five candidates, keeping only the frontmost five')
  for i = #candidates, 6, -1 do
    table.remove(candidates, i)
  end
end

local function matchesSlot(targetWin, slotKind)
  local frame = targetWin:frame()
  if slotKind == 'left' then
    return touchesLeft(frame)
  end
  if slotKind == 'top' then
    return touchesTop(frame)
  end
  if slotKind == 'bottom' then
    return touchesBottom(frame)
  end
  return false
end

local function assignBySlots(slotKinds)
  local assigned = {}
  local used = {}

  for index, slotKind in ipairs(slotKinds) do
    for candidateIndex, candidate in ipairs(candidates) do
      if not used[candidateIndex] and matchesSlot(candidate, slotKind) then
        assigned[index] = candidate
        used[candidateIndex] = true
        log('slot ' .. slotKind .. ' matched edge for id=' .. tostring(candidate:id()) .. ' title=' .. tostring(candidate:title()))
        break
      end
    end
  end

  for index = 1, #slotKinds do
    if not assigned[index] then
      for candidateIndex, candidate in ipairs(candidates) do
        if not used[candidateIndex] then
          assigned[index] = candidate
          used[candidateIndex] = true
          log('slot ' .. slotKinds[index] .. ' filled by fallback id=' .. tostring(candidate:id()) .. ' title=' .. tostring(candidate:title()))
          break
        end
      end
    end
  end

  return assigned
end

local function matchesCorner(targetWin, cornerKind)
  local frame = targetWin:frame()
  if cornerKind == 'top_left' then
    return touchesTop(frame) and touchesLeft(frame)
  end
  if cornerKind == 'top_right' then
    return touchesTop(frame) and touchesRight(frame)
  end
  if cornerKind == 'bottom_right' then
    return touchesBottom(frame) and touchesRight(frame)
  end
  if cornerKind == 'bottom_left' then
    return touchesBottom(frame) and touchesLeft(frame)
  end
  return false
end

local function assignByCorners(cornerKinds)
  local assigned = {}
  local used = {}

  for index, cornerKind in ipairs(cornerKinds) do
    for candidateIndex, candidate in ipairs(candidates) do
      if not used[candidateIndex] and matchesCorner(candidate, cornerKind) then
        assigned[index] = candidate
        used[candidateIndex] = true
        log('corner ' .. cornerKind .. ' matched for id=' .. tostring(candidate:id()) .. ' title=' .. tostring(candidate:title()))
        break
      end
    end
  end

  for index = 1, #cornerKinds do
    if not assigned[index] then
      for candidateIndex, candidate in ipairs(candidates) do
        if not used[candidateIndex] then
          assigned[index] = candidate
          used[candidateIndex] = true
          log('corner ' .. cornerKinds[index] .. ' filled by fallback id=' .. tostring(candidate:id()) .. ' title=' .. tostring(candidate:title()))
          break
        end
      end
    end
  end

  return assigned
end

if not hasSideColumn and #candidates <= 4 then
  local cornerKinds = nil
  if #candidates == 2 then
    cornerKinds = { 'top_left', 'bottom_right' }
  elseif #candidates == 3 then
    cornerKinds = { 'top_left', 'top_right', 'bottom_right' }
  elseif #candidates == 4 then
    cornerKinds = { 'top_left', 'top_right', 'bottom_right', 'bottom_left' }
  end

  if cornerKinds then
    log('using corner layout')
    local assigned = assignByCorners(cornerKinds)
    for index, cornerKind in ipairs(cornerKinds) do
      local targetWin = assigned[index]
      local frame = targetWin:frame()
      if cornerKind == 'top_left' then
        moveWindow(targetWin, sf.x, sf.y)
      elseif cornerKind == 'top_right' then
        moveWindow(targetWin, sf.x + sf.w - frame.w, sf.y)
      elseif cornerKind == 'bottom_right' then
        moveWindow(targetWin, sf.x + sf.w - frame.w, sf.y + sf.h - frame.h)
      elseif cornerKind == 'bottom_left' then
        moveWindow(targetWin, sf.x, sf.y + sf.h - frame.h)
      end
    end
    return
  end
end

if #candidates == 2 then
  log('using two-window layout')
  local assigned = assignBySlots({ 'left', 'left' })
  moveWindow(assigned[1], sf.x, sf.y)
  moveWindow(assigned[2], sf.x, sf.y + sf.h - assigned[2]:frame().h)
  return
end

log('using three-to-five-window layout')
local leftCount = #candidates - 2
local bandTop = sf.y + sf.h * 0.25
local bandHeight = sf.h * 0.5

log(string.format('leftCount=%d bandTop=%.1f bandHeight=%.1f', leftCount, bandTop, bandHeight))

local slotKinds = { 'top', 'bottom' }
for _ = 1, leftCount do
  table.insert(slotKinds, 'left')
end

local assigned = assignBySlots(slotKinds)

moveWindow(assigned[1], sf.x + (sf.w - assigned[1]:frame().w) / 2, sf.y)
moveWindow(assigned[2], sf.x + (sf.w - assigned[2]:frame().w) / 2, sf.y + sf.h - assigned[2]:frame().h)

local leftWindows = {}
for i = 1, leftCount do
  table.insert(leftWindows, assigned[i + 2])
end

table.sort(leftWindows, function(a, b)
  return a:frame().h < b:frame().h
end)

local orderedLeftWindows = {}
local leftIndex = 1
local rightIndex = #leftWindows
for slotIndex = 1, #leftWindows do
  if slotIndex % 2 == 1 then
    orderedLeftWindows[slotIndex] = leftWindows[leftIndex]
    leftIndex = leftIndex + 1
  else
    orderedLeftWindows[slotIndex] = leftWindows[rightIndex]
    rightIndex = rightIndex - 1
  end
end

for i = 1, #orderedLeftWindows do
  local leftWin = orderedLeftWindows[i]
  local frame = leftWin:frame()
  local centerY = bandTop + (bandHeight * i) / (leftCount + 1)
  log('left slot ' .. tostring(i) .. ' assigned to id=' .. tostring(leftWin:id()) .. ' title=' .. tostring(leftWin:title()) .. ' height=' .. string.format('%.1f', frame.h))
  moveWindow(leftWin, sf.x, centerY - frame.h / 2)
end
"
