#!/bin/zsh
APP_NAME=$1
SPAWN_SCRIPT=$2

printf '[spawn_new.sh] start app="%s"\n' "$APP_NAME"
printf '[spawn_new.sh] spawn_script_len=%s\n' "${#SPAWN_SCRIPT}"

hs -c '
local appName = [==['"$APP_NAME"']==]
local spawnScript = [==['"$SPAWN_SCRIPT"']==]

local function dbg(msg)
  print(os.date("[%Y-%m-%d %H:%M:%S] [spawn_new] ") .. msg)
end

dbg("lua entry appName=" .. tostring(appName))
dbg("spawnScript provided=" .. tostring(spawnScript ~= "") .. " length=" .. tostring(#spawnScript))

-- Target screen = screen of currently focused window (fallback: mouse screen)
local fw = hs.window.focusedWindow()
local targetScreen = (fw and fw:screen()) or hs.mouse.getCurrentScreen()
local spaces = hs.spaces
local currentSpace = spaces and spaces.focusedSpace() or nil
dbg("focusedWindow exists=" .. tostring(fw ~= nil))
dbg("targetScreen id=" .. tostring(targetScreen and targetScreen:id() or "nil"))
dbg("currentSpace id=" .. tostring(currentSpace))

local app = hs.application.get(appName)
dbg("app running=" .. tostring(app ~= nil))

local function getAppWindows(appObj)
  if not appObj then return {} end

  local windowsById = {}
  local windows = {}

  local function addWindow(win, source)
    if not win then return end
    local id = win:id()
    if not id or windowsById[id] then return end
    windowsById[id] = true
    table.insert(windows, win)
  end

  for _, win in ipairs(appObj:allWindows()) do
    addWindow(win, "app:allWindows")
  end

  addWindow(appObj:focusedWindow(), "app:focusedWindow")
  addWindow(appObj:mainWindow(), "app:mainWindow")

  local pid = appObj:pid()
  for _, win in ipairs(hs.window.allWindows()) do
    local winApp = win:application()
    if winApp and winApp:pid() == pid then
      addWindow(win, "hs.window.allWindows")
    end
  end

  return windows
end

local function findWindowById(appObj, wantedId)
  if not wantedId then return nil end
  for _, win in ipairs(getAppWindows(appObj)) do
    if win:id() == wantedId then
      return win
    end
  end
  return nil
end

local function isNewWindow(win, beforeSet)
  return win and win:id() and not beforeSet[win:id()]
end

local function windowIsOnSpace(win, spaceId)
  if not win or not spaceId or not spaces then return false end
  local winSpaces = spaces.windowSpaces(win)
  if not winSpaces then return false end
  for _, winSpaceId in ipairs(winSpaces) do
    if winSpaceId == spaceId then
      return true
    end
  end
  return false
end

local function findVisibleStandardWindowOnScreen(appObj, screen, spaceId)
  local windows = getAppWindows(appObj)
  dbg("candidate windows count=" .. tostring(#windows))
  for _, win in ipairs(windows) do
    local onCurrentSpace = windowIsOnSpace(win, spaceId)
    dbg(
      "window id=" .. tostring(win:id()) ..
      " standard=" .. tostring(win:isStandard()) ..
      " visible=" .. tostring(win:isVisible()) ..
      " screen=" .. tostring(win:screen() and win:screen():id() or "nil") ..
      " onCurrentSpace=" .. tostring(onCurrentSpace) ..
      " title=" .. tostring(win:title())
    )
    if win:isStandard() and win:isVisible() and win:screen() == screen and (not spaceId or onCurrentSpace) then
      return win
    end
  end
  return nil
end

-- 1) If there is already a normal visible window on the target screen, focus it
if app then
  dbg("checking existing windows on target screen")
  local existingWin = findVisibleStandardWindowOnScreen(app, targetScreen, currentSpace)
  if existingWin then
    dbg("found existing window on target screen/current space; focusing and returning")
    existingWin:focus()
    return
  end
end

-- 2) If app is not running, launch it and stop (avoid extra windows)
if not app then
  dbg("app not running; launchOrFocus and return")
  hs.application.launchOrFocus(appName)
  return
end

-- 3) App is running but no window on target screen -> create a new window
--    Snapshot current window IDs so we can detect the new one
local before = {}
for _, win in ipairs(getAppWindows(app)) do
  before[win:id()] = true
end
dbg("snapshot existing windows count=" .. tostring(#getAppWindows(app)))

local function runFallbackCmdN(name)
  -- NOTE: this can switch spaces if Mission Control setting is enabled
  -- “When switching to an application, switch to a Space with open windows”
  dbg("running fallback open -n -a for " .. tostring(name))
  -- hs.execute(("/usr/bin/open -n -a %q"):format(name), true)
  local app=hs.appfinder.appFromName(name)
  if app then hs.eventtap.keyStroke({"cmd"},"n",0,app) end
end

local function runSpawnScript(script)
  -- Run user-provided AppleScript
  -- script can be multiline
  dbg("running spawnScript via AppleScript")
  local output, ok, _, rc = hs.execute(script)
  dbg(tostring(output))
  if not ok then
    dbg("spawnScript failed rc=" .. tostring(rc))
    return false, nil
  end
  local spawnedWindowId = tostring(output):match("(%d+)")
  if spawnedWindowId then
    spawnedWindowId = tonumber(spawnedWindowId)
    dbg("spawnScript returned window id=" .. tostring(spawnedWindowId))
  end
  dbg("spawnScript succeeded")
  return true, spawnedWindowId
end

local function focusFinderWindowById(windowId)
  if appName ~= "Finder" or not windowId then return false end
  local cmd = string.format(
    [[osascript -e "tell application \"Finder\" to activate" -e "tell application \"Finder\" to set index of (first Finder window whose id is %d) to 1"]],
    windowId
  )
  dbg("raising Finder window by AppleScript id=" .. tostring(windowId))
  local output, ok, _, rc = hs.execute(cmd)
  if output and output ~= "" then
    dbg(tostring(output))
  end
  dbg("Finder raise result ok=" .. tostring(ok) .. " rc=" .. tostring(rc))
  return ok
end

local function bringToFront(win, appObj)
  if not win then return end
  win:raise()
  win:focus()
  if appObj and appName == "Finder" then
    appObj:activate(true)
  end
end

-- If config provided a spawn_script, use it; else fallback to Cmd+N
local spawnedWindowId = nil
if spawnScript ~= "" then
  dbg("path: spawnScript")
  local _, detectedWindowId = runSpawnScript(spawnScript)
  spawnedWindowId = detectedWindowId
  if spawnedWindowId then
    focusFinderWindowById(spawnedWindowId)
  end
else
  dbg("path: fallback open -n -a")
  runFallbackCmdN(appName)
end

-- Wait briefly for the new window to appear
local newWin = nil
local deadline = hs.timer.secondsSinceEpoch() + 2.0
dbg("waiting for new window until deadline=" .. tostring(deadline))

while hs.timer.secondsSinceEpoch() < deadline do
  if spawnedWindowId then
    local targetedWin = findWindowById(app, spawnedWindowId)
    if targetedWin then
      newWin = targetedWin
      dbg("matched spawned window id=" .. tostring(targetedWin:id()) .. " title=" .. tostring(targetedWin:title()))
      break
    end
  end

  for _, win in ipairs(getAppWindows(app)) do
    if win:isStandard() and win:isVisible() and not before[win:id()] then
      newWin = win
      dbg("detected new window id=" .. tostring(win:id()) .. " title=" .. tostring(win:title()))
      break
    end
  end
  if newWin then break end
  hs.timer.usleep(100000) -- 100ms
end

-- Fallback: some apps reuse an existing window instead of creating a new one
if not newWin then
  dbg("no new window detected; falling back to focusedWindow/mainWindow")
  local targetedWin = findWindowById(app, spawnedWindowId)
  if targetedWin then
    newWin = targetedWin
  else
    local focusedWin = app:focusedWindow()
    local mainWin = app:mainWindow()

    if isNewWindow(focusedWin, before) then
      dbg("using focusedWindow because it is newly created")
      newWin = focusedWin
    elseif isNewWindow(mainWin, before) then
      dbg("using mainWindow because it is newly created")
      newWin = mainWin
    else
      dbg("focusedWindow/mainWindow are pre-existing; refusing to reuse them")
    end
  end
end

if newWin then
  dbg("selected window id=" .. tostring(newWin:id()) .. " screen=" .. tostring(newWin:screen() and newWin:screen():id() or "nil"))
  -- If the new/focused window is on the other screen, move it over first
  if newWin:screen() ~= targetScreen then
    dbg("window not on target screen; moving to target screen")
    newWin:moveToScreen(targetScreen, nil, true)
    hs.timer.usleep(150000)
  end
  dbg("raising and focusing selected window")
  bringToFront(newWin, app)
  hs.timer.usleep(50000)
  bringToFront(newWin, app)
  dbg("done")
else
  dbg("no window available to focus after spawn path")
end
'

exit_code=$?
printf '[spawn_new.sh] end app="%s" exit=%s\n' "$APP_NAME" "$exit_code"
exit $exit_code
