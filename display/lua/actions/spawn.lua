local core = require('core')
local windows = require('windows')

local spawn = {}

local function dbg(msg)
  core.log('spawn_new', msg)
end

local function getAppWindows(appObj, includeGlobal)
  if not appObj then return {} end

  local windowsById = {}
  local result = {}

  local function addWindow(win)
    if not win then return end
    local id = win:id()
    if not id or windowsById[id] then return end
    windowsById[id] = true
    table.insert(result, win)
  end

  for _, win in ipairs(appObj:allWindows()) do
    addWindow(win)
  end

  addWindow(appObj:focusedWindow())
  addWindow(appObj:mainWindow())

  if includeGlobal then
    local pid = appObj:pid()
    for _, win in ipairs(hs.window.allWindows()) do
      local winApp = win:application()
      if winApp and winApp:pid() == pid then
        addWindow(win)
      end
    end
  end

  return result
end

local function findWindowById(appObj, wantedId, includeGlobal)
  if not wantedId then return nil end
  for _, win in ipairs(getAppWindows(appObj, includeGlobal)) do
    if win:id() == wantedId then return win end
  end
  return nil
end

local function isNewWindow(win, beforeSet)
  return win and win:id() and not beforeSet[win:id()]
end

local function windowIsOnSpace(win, spaceId, spacesApi)
  if not win or not spaceId or not spacesApi then return false end
  local winSpaces = spacesApi.windowSpaces(win)
  return core.contains(winSpaces, spaceId)
end

local function findVisibleStandardWindowOnScreen(appObj, screen, spaceId, spacesApi)
  local candidates = getAppWindows(appObj)
  dbg('candidate windows count=' .. tostring(#candidates))
  for _, win in ipairs(candidates) do
    local onCurrentSpace = windowIsOnSpace(win, spaceId, spacesApi)
    dbg(
      'window id=' .. tostring(win:id()) ..
      ' standard=' .. tostring(win:isStandard()) ..
      ' visible=' .. tostring(win:isVisible()) ..
      ' screen=' .. tostring(win:screen() and win:screen():id() or 'nil') ..
      ' onCurrentSpace=' .. tostring(onCurrentSpace) ..
      ' title=' .. tostring(win:title())
    )
    if win:isStandard() and win:isVisible() and win:screen() == screen and (not spaceId or onCurrentSpace) then
      return win
    end
  end
  return nil
end

local function runFallbackCmdN(name)
  dbg('running fallback open -n -a for ' .. tostring(name))
  local app = hs.appfinder.appFromName(name)
  if app then hs.eventtap.keyStroke({ 'cmd' }, 'n', 0, app) end
end

local function runSpawnScript(script)
  dbg('running spawnScript via AppleScript')
  local output, ok, _, rc = hs.execute(script)
  dbg(tostring(output))
  if not ok then
    dbg('spawnScript failed rc=' .. tostring(rc))
    return false, nil
  end

  local spawnedWindowId = tostring(output):match('(%d+)')
  if spawnedWindowId then
    spawnedWindowId = tonumber(spawnedWindowId)
    dbg('spawnScript returned window id=' .. tostring(spawnedWindowId))
  end
  dbg('spawnScript succeeded')
  return true, spawnedWindowId
end

local function focusFinderWindowById(appName, windowId)
  if appName ~= 'Finder' or not windowId then return false end
  local cmd = string.format(
    [[osascript -e "tell application \"Finder\" to activate" -e "tell application \"Finder\" to set index of (first Finder window whose id is %d) to 1"]],
    windowId
  )
  dbg('raising Finder window by AppleScript id=' .. tostring(windowId))
  local output, ok, _, rc = hs.execute(cmd)
  if output and output ~= '' then dbg(tostring(output)) end
  dbg('Finder raise result ok=' .. tostring(ok) .. ' rc=' .. tostring(rc))
  return ok
end

local function bringToFront(win, appObj, appName)
  if not win then return end
  win:raise()
  win:focus()
  if appObj and appName == 'Finder' then
    appObj:activate(true)
  end
end

function spawn.run(appName, spawnScript)
  spawnScript = spawnScript or ''

  dbg('lua entry appName=' .. tostring(appName))
  dbg('spawnScript provided=' .. tostring(spawnScript ~= '') .. ' length=' .. tostring(#spawnScript))

  local fw = windows.focused()
  local targetScreen = (fw and fw:screen()) or hs.mouse.getCurrentScreen()
  local spacesApi = hs.spaces
  local currentSpace = spacesApi and spacesApi.focusedSpace() or nil
  dbg('focusedWindow exists=' .. tostring(fw ~= nil))
  dbg('targetScreen id=' .. tostring(targetScreen and targetScreen:id() or 'nil'))
  dbg('currentSpace id=' .. tostring(currentSpace))

  local app = hs.application.get(appName)
  dbg('app running=' .. tostring(app ~= nil))

  if app then
    dbg('checking existing windows on target screen')
    local existingWin = findVisibleStandardWindowOnScreen(app, targetScreen, currentSpace, spacesApi)
    if existingWin then
      dbg('found existing window on target screen/current space; focusing and returning')
      existingWin:focus()
      return
    end
  end

  if not app then
    dbg('app not running; launchOrFocus and return')
    hs.application.launchOrFocus(appName)
    return
  end

  local before = {}
  local snapshotWindows = getAppWindows(app)
  for _, win in ipairs(snapshotWindows) do
    before[win:id()] = true
  end
  dbg('snapshot existing windows count=' .. tostring(#snapshotWindows))

  local spawnedWindowId = nil
  if spawnScript ~= '' then
    dbg('path: spawnScript')
    local _, detectedWindowId = runSpawnScript(spawnScript)
    spawnedWindowId = detectedWindowId
    if spawnedWindowId then
      focusFinderWindowById(appName, spawnedWindowId)
    end
  else
    dbg('path: fallback open -n -a')
    runFallbackCmdN(appName)
  end

  local newWin = nil
  local deadline = hs.timer.secondsSinceEpoch() + 2.0
  dbg('waiting for new window until deadline=' .. tostring(deadline))

  while hs.timer.secondsSinceEpoch() < deadline do
    if spawnedWindowId then
      local targetedWin = findWindowById(app, spawnedWindowId)
      if targetedWin then
        newWin = targetedWin
        dbg('matched spawned window id=' .. tostring(targetedWin:id()) .. ' title=' .. tostring(targetedWin:title()))
        break
      end
    end

    for _, win in ipairs(getAppWindows(app)) do
      if win:isStandard() and win:isVisible() and not before[win:id()] then
        newWin = win
        dbg('detected new window id=' .. tostring(win:id()) .. ' title=' .. tostring(win:title()))
        break
      end
    end
    if newWin then break end
    hs.timer.usleep(100000)
  end

  if not newWin then
    dbg('no new window detected; falling back to focusedWindow/mainWindow')
    local targetedWin = findWindowById(app, spawnedWindowId, true)
    if targetedWin then
      newWin = targetedWin
    else
      local focusedWin = app:focusedWindow()
      local mainWin = app:mainWindow()
      if isNewWindow(focusedWin, before) then
        dbg('using focusedWindow because it is newly created')
        newWin = focusedWin
      elseif isNewWindow(mainWin, before) then
        dbg('using mainWindow because it is newly created')
        newWin = mainWin
      else
        dbg('focusedWindow/mainWindow are pre-existing; refusing to reuse them')
      end
    end
  end

  if newWin then
    dbg('selected window id=' .. tostring(newWin:id()) .. ' screen=' .. tostring(newWin:screen() and newWin:screen():id() or 'nil'))
    if newWin:screen() ~= targetScreen then
      dbg('window not on target screen; moving to target screen')
      newWin:moveToScreen(targetScreen, nil, true)
      hs.timer.usleep(150000)
    end
    dbg('raising and focusing selected window')
    bringToFront(newWin, app, appName)
    hs.timer.usleep(50000)
    bringToFront(newWin, app, appName)
    dbg('done')
  else
    dbg('no window available to focus after spawn path')
  end
end

return spawn
