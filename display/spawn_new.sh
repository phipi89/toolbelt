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
dbg("focusedWindow exists=" .. tostring(fw ~= nil))
dbg("targetScreen id=" .. tostring(targetScreen and targetScreen:id() or "nil"))

local app = hs.application.get(appName)
dbg("app running=" .. tostring(app ~= nil))

-- 1) If there is already a normal visible window on the target screen, focus it
if app then
  dbg("checking existing windows on target screen")
  for _, win in ipairs(app:allWindows()) do
    dbg(
      "window id=" .. tostring(win:id()) ..
      " standard=" .. tostring(win:isStandard()) ..
      " visible=" .. tostring(win:isVisible()) ..
      " screen=" .. tostring(win:screen() and win:screen():id() or "nil") ..
      " title=" .. tostring(win:title())
    )
    if win:isStandard() and win:isVisible() and win:screen() == targetScreen then
      dbg("found existing window on target screen; focusing and returning")
      win:focus()
      return
    end
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
for _, win in ipairs(app:allWindows()) do
  before[win:id()] = true
end
dbg("snapshot existing windows count=" .. tostring(#app:allWindows()))

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
  -- local ok, result, desc = hs.osascript.applescript(script)
  -- if not ok then
  --   hs.printf("spawn_script failed for %s: %s", appName, tostring(desc or result))
  --   dbg("spawnScript failed: " .. tostring(desc or result))
  --   return false
  -- end
  dbg(hs.execute(script))
  dbg("spawnScript succeeded")
  return true
end

-- If config provided a spawn_script, use it; else fallback to Cmd+N
if spawnScript ~= "" then
  dbg("path: spawnScript")
  runSpawnScript(spawnScript)
else
  dbg("path: fallback open -n -a")
  runFallbackCmdN(appName)
end

-- Wait briefly for the new window to appear
local newWin = nil
local deadline = hs.timer.secondsSinceEpoch() + 2.0
dbg("waiting for new window until deadline=" .. tostring(deadline))

while hs.timer.secondsSinceEpoch() < deadline do
  for _, win in ipairs(app:allWindows()) do
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
  newWin = app:focusedWindow() or app:mainWindow()
end

if newWin then
  dbg("selected window id=" .. tostring(newWin:id()) .. " screen=" .. tostring(newWin:screen() and newWin:screen():id() or "nil"))
  -- If the new/focused window is on the other screen, move it over first
  if newWin:screen() ~= targetScreen then
    dbg("window not on target screen; moving to target screen")
    newWin:moveToScreen(targetScreen, nil, true)
    hs.timer.usleep(100000)
  end
  dbg("focusing selected window")
  newWin:focus()
  dbg("done")
else
  dbg("no window available to focus after spawn path")
end
'

exit_code=$?
printf '[spawn_new.sh] end app="%s" exit=%s\n' "$APP_NAME" "$exit_code"
exit $exit_code
