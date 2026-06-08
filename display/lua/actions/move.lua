local core = require('core')
local geometry = require('geometry')
local windows = require('windows')

local move = {}

local function placeByNearestSlot(wins, slots, tolerance)
  local placed, used = {}, {}
  for i, slot in ipairs(slots) do
    for j, win in ipairs(wins) do
      if not used[j] and geometry.sameFrame(win:frame(), slot, tolerance) then
        placed[i], used[j] = win, true
        break
      end
    end
  end

  local freeSlots, looseWins = {}, {}
  for i = 1, math.min(#wins, #slots) do
    if not placed[i] then table.insert(freeSlots, i) end
  end
  for j, win in ipairs(wins) do
    if not used[j] then table.insert(looseWins, win) end
  end

  local bestCost, bestOrder = nil, nil
  local function search(pos, cost, order, taken)
    if bestCost and cost >= bestCost then return end
    if pos > #freeSlots then
      bestCost = cost
      bestOrder = {}
      for i, win in ipairs(order) do bestOrder[i] = win end
      return
    end

    local slotIndex = freeSlots[pos]
    local slotCenter = geometry.center(slots[slotIndex])
    for i, win in ipairs(looseWins) do
      if not taken[i] then
        taken[i], order[pos] = true, win
        search(pos + 1, cost + geometry.dist2(geometry.center(win:frame()), slotCenter), order, taken)
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

  return placed
end

function move.left()
  local win = windows.focused()
  if not win then return end
  local screen = win:screen()
  if not screen then return end

  local halves = geometry.halves(screen)
  local thirds = geometry.thirds(screen)
  local cur = win:frame()
  local tolerance = 6

  if geometry.sameFrame(cur, halves.left, tolerance) then
    win:setFrame(thirds.leftTwoThirds, 0)
  elseif geometry.sameFrame(cur, thirds.leftTwoThirds, tolerance) then
    win:setFrame(halves.left, 0)
  else
    win:setFrame(halves.left, 0)
  end
end

function move.right()
  local win = windows.focused()
  if not win then return end
  local screen = win:screen()
  if not screen then return end

  local halves = geometry.halves(screen)
  local thirds = geometry.thirds(screen)
  local cur = win:frame()
  local tolerance = 6

  if geometry.sameFrame(cur, halves.right, tolerance) then
    win:setFrame(thirds.rightOneThird, 0)
  elseif geometry.sameFrame(cur, thirds.rightOneThird, tolerance) then
    win:setFrame(halves.right, 0)
  else
    win:setFrame(halves.right, 0)
  end
end

function move.center(opts)
  opts = opts or {}
  local win = windows.focused()
  if not win then return end
  local screen = win:screen()
  if not screen then return end

  local size = opts.size and tonumber(opts.size) or nil
  if size then
    if size <= 0 or size > 100 then error('center size must be between 0 and 100') end
    win:setFrame(geometry.centered(screen, size / 100), 0)
    return
  end

  local target70 = geometry.centered(screen, 0.60)
  local target90 = geometry.centered(screen, 0.90)
  local target100 = screen:frame()
  local cur = win:frame()
  local tolerance = 6

  if geometry.sameFrame(cur, target90, tolerance) then
    win:setFrame(target100, 0)
  elseif geometry.sameFrame(cur, target100, tolerance) then
    win:setFrame(target70, 0)
  elseif geometry.sameFrame(cur, target70, tolerance) then
    win:setFrame(target90, 0)
  else
    win:setFrame(target90, 0)
  end
end

function move.cycle(opts)
  opts = opts or {}
  local targetIndex = opts.targetIndex or 2
  local wins = windows.onScreen(windows.activeScreen(), {
    visible = true,
    standard = true,
    includeFocused = false,
  })
  if #wins < targetIndex then return end
  wins[targetIndex]:focus()
end

function move.split(opts)
  opts = opts or {}
  local screen = windows.activeScreen()
  if not screen then return end

  local wins = windows.onScreen(screen, {
    limit = 2,
    visible = true,
    standard = true,
    includeFocused = true,
    allowFinderFallback = true,
  })
  if #wins < 2 then return end

  local halves = geometry.halves(screen)
  local thirds = geometry.thirds(screen)
  local tolerance = opts.tolerance or 8

  local leftWin, rightWin = wins[1], wins[2]
  if opts.frontmostRight then
    leftWin, rightWin = wins[2], wins[1]
  end

  local isHalf = geometry.sameFrame(leftWin:frame(), halves.left, tolerance)
    and geometry.sameFrame(rightWin:frame(), halves.right, tolerance)
  local isWeighted = geometry.sameFrame(leftWin:frame(), thirds.leftTwoThirds, tolerance)
    and geometry.sameFrame(rightWin:frame(), thirds.rightOneThird, tolerance)

  if isHalf then
    leftWin:setFrame(thirds.leftTwoThirds, 0)
    rightWin:setFrame(thirds.rightOneThird, 0)
  elseif isWeighted then
    leftWin:setFrame(halves.left, 0)
    rightWin:setFrame(halves.right, 0)
  else
    leftWin:setFrame(halves.left, 0)
    rightWin:setFrame(halves.right, 0)
  end
end

function move.quad()
  local screen = windows.activeScreen()
  if not screen then return end

  local wins = windows.onScreen(screen, {
    limit = 4,
    visible = false,
    standard = true,
    includeFocused = false,
  })
  if #wins == 0 then return end

  local slots = geometry.quads(screen)
  local placed = placeByNearestSlot(wins, slots, 8)

  for i = 1, math.min(#wins, 4) do
    local win = placed[i]
    if win and not geometry.sameFrame(win:frame(), slots[i], 8) then
      win:setFrame(slots[i], 0)
    end
  end
end

function move.tile()
  local screen = windows.activeScreen()
  if not screen then return end

  local wins = windows.onScreen(screen, {
    limit = 4,
    visible = false,
    standard = true,
    includeFocused = false,
  })

  if #wins ~= 2 then
    return move.quad()
  end

  local halves = geometry.halves(screen)
  local slots = { halves.left, halves.right }
  local placed = placeByNearestSlot(wins, slots, 8)

  if placed[1] and not geometry.sameFrame(placed[1]:frame(), halves.left, 8) then
    placed[1]:setFrame(halves.left, 0)
  end
  if placed[2] and not geometry.sameFrame(placed[2]:frame(), halves.right, 8) then
    placed[2]:setFrame(halves.right, 0)
  end
end

function move.reduce()
  local win = windows.focused()
  if not win then return end
  local screen = win:screen()
  if not screen then return end

  local sf = screen:frame()
  win:setFrame(hs.geometry.rect(sf.x, sf.y + sf.h * 0.70, sf.w * 0.30, sf.h * 0.30), 0)
end

function move.distribute()
  local win = windows.focused()
  local screen = win and win:screen() or hs.screen.mainScreen()
  if not screen then
    core.log('distribute', 'no screen found')
    return
  end

  local sf = screen:frame()
  local screenArea = sf.w * sf.h
  local tolerance = 12

  local function close(a, b) return geometry.close(a, b, tolerance) end
  local function log(msg) core.log('distribute', msg) end
  local function touchesLeft(frame) return close(frame.x, sf.x) end
  local function touchesRight(frame) return close(frame.x + frame.w, sf.x + sf.w) end
  local function touchesTop(frame) return close(frame.y, sf.y) end
  local function touchesBottom(frame) return close(frame.y + frame.h, sf.y + sf.h) end
  local function touchesEdge(frame)
    return touchesLeft(frame) or touchesTop(frame) or touchesRight(frame) or touchesBottom(frame)
  end
  local function fillsScreen(frame)
    return close(frame.x, sf.x) and close(frame.y, sf.y) and close(frame.w, sf.w) and close(frame.h, sf.h)
  end
  local function isLeftColumn(frame)
    return touchesLeft(frame) and touchesTop(frame) and touchesBottom(frame)
  end
  local function isRightColumn(frame)
    return touchesRight(frame) and touchesTop(frame) and touchesBottom(frame)
  end
  local function moveWindow(targetWin, x, y)
    local frame = targetWin:frame()
    local width = math.min(frame.w, sf.w)
    local height = math.min(frame.h, sf.h)
    local nextFrame = hs.geometry.rect(
      geometry.clamp(x, sf.x, sf.x + sf.w - width),
      geometry.clamp(y, sf.y, sf.y + sf.h - height),
      width,
      height
    )
    log(string.format(
      'move id=%s title=%s from x=%.1f y=%.1f w=%.1f h=%.1f to x=%.1f y=%.1f w=%.1f h=%.1f',
      tostring(targetWin:id()), tostring(targetWin:title()),
      frame.x, frame.y, frame.w, frame.h,
      nextFrame.x, nextFrame.y, nextFrame.w, nextFrame.h
    ))
    targetWin:setFrame(nextFrame, 0)
  end

  log('focusedWindow=' .. tostring(win and win:id() or nil) .. ' screen=' .. tostring(screen:getUUID()))
  log(string.format('screenFrame x=%.1f y=%.1f w=%.1f h=%.1f', sf.x, sf.y, sf.w, sf.h))

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
      if leftColumn or rightColumn then hasSideColumn = true end
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
    for i = #candidates, 6, -1 do table.remove(candidates, i) end
  end

  local function matchesSlot(targetWin, slotKind)
    local frame = targetWin:frame()
    if slotKind == 'left' then return touchesLeft(frame) end
    if slotKind == 'top' then return touchesTop(frame) end
    if slotKind == 'bottom' then return touchesBottom(frame) end
    return false
  end
  local function assignBySlots(slotKinds)
    local assigned, used = {}, {}
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
    if cornerKind == 'top_left' then return touchesTop(frame) and touchesLeft(frame) end
    if cornerKind == 'top_right' then return touchesTop(frame) and touchesRight(frame) end
    if cornerKind == 'bottom_right' then return touchesBottom(frame) and touchesRight(frame) end
    if cornerKind == 'bottom_left' then return touchesBottom(frame) and touchesLeft(frame) end
    return false
  end
  local function assignByCorners(cornerKinds)
    local assigned, used = {}, {}
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
  local slotKinds = { 'top', 'bottom' }
  for _ = 1, leftCount do table.insert(slotKinds, 'left') end

  local assigned = assignBySlots(slotKinds)
  moveWindow(assigned[1], sf.x + (sf.w - assigned[1]:frame().w) / 2, sf.y)
  moveWindow(assigned[2], sf.x + (sf.w - assigned[2]:frame().w) / 2, sf.y + sf.h - assigned[2]:frame().h)

  local leftWindows = {}
  for i = 1, leftCount do table.insert(leftWindows, assigned[i + 2]) end
  table.sort(leftWindows, function(a, b) return a:frame().h < b:frame().h end)

  local orderedLeftWindows = {}
  local leftIndex, rightIndex = 1, #leftWindows
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
end

function move.space(opts)
  opts = opts or {}
  local direction = opts.direction
  local spacesApi = hs.spaces
  local win = windows.focused()
  local namespace = direction == 'left' and 'space_left' or 'space_right'
  local function log(msg) core.log(namespace, msg) end

  if not spacesApi or not win or not win:isStandard() then
    log('missing spaces API or focused standard window')
    return
  end

  local screen = win:screen()
  if not screen then
    log('focused window has no screen')
    return
  end

  local allSpaces = spacesApi.allSpaces()
  local screenSpaces = allSpaces[screen:getUUID()]
  if not screenSpaces or #screenSpaces == 0 then
    log('no spaces found for screen ' .. tostring(screen:getUUID()))
    return
  end

  local currentSpace = spacesApi.focusedSpace()
  local targetIndex = nil
  log('window id=' .. tostring(win:id()) .. ' title=' .. tostring(win:title()))
  log('screen=' .. tostring(screen:getUUID()) .. ' currentSpace=' .. tostring(currentSpace))
  log('screenSpaces=' .. hs.inspect(screenSpaces))

  for i, spaceId in ipairs(screenSpaces) do
    if spaceId == currentSpace then
      targetIndex = direction == 'left' and i - 1 or i + 1
      break
    end
  end

  if not targetIndex or targetIndex < 1 or targetIndex > #screenSpaces then
    log('no target space to the ' .. tostring(direction))
    return
  end

  local targetSpace = screenSpaces[targetIndex]
  local moved = spacesApi.moveWindowToSpace(win, targetSpace)
  log('move attempt result=' .. tostring(moved) .. ' targetSpace=' .. tostring(targetSpace))
  if not moved then
    moved = spacesApi.moveWindowToSpace(win, targetSpace, true)
    log('forced move attempt result=' .. tostring(moved))
  end

  local winSpaces = nil
  for _ = 1, 20 do
    hs.timer.usleep(100000)
    winSpaces = spacesApi.windowSpaces(win)
    if core.contains(winSpaces, targetSpace) then break end
  end
  log('windowSpaces after move=' .. hs.inspect(winSpaces))

  if not core.contains(winSpaces, targetSpace) then
    log('window is not on target space after move; aborting gotoSpace')
    return
  end

  hs.timer.usleep(150000)
  local switched, switchErr = spacesApi.gotoSpace(targetSpace)
  log('gotoSpace result=' .. tostring(switched) .. ' err=' .. tostring(switchErr))
  hs.timer.usleep(150000)
  win:focus()
  log('refocused window')
end

function move.run(action, args)
  if action == 'left' then return move.left() end
  if action == 'right' then return move.right() end
  if action == 'center' then
    return move.center({ size = core.option(args, '--size') })
  end
  if action == 'cycle' then
    local targetIndex = 2
    if core.flag(args, '--third') or core.flag(args, '-3') then targetIndex = 3 end
    return move.cycle({ targetIndex = targetIndex })
  end
  if action == 'split' then
    return move.split({
      frontmostRight = core.flag(args, '--frontmost-right')
        or core.flag(args, '--right')
        or core.flag(args, '-r'),
    })
  end
  if action == 'quad' then return move.quad() end
  if action == 'tile' then return move.tile() end
  if action == 'reduce' then return move.reduce() end
  if action == 'distribute' then return move.distribute() end
  if action == 'space-left' then return move.space({ direction = 'left' }) end
  if action == 'space-right' then return move.space({ direction = 'right' }) end

  error('unknown move action: ' .. tostring(action))
end

return move
