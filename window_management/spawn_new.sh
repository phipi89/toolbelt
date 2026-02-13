#!/bin/zsh
# APP_NAME=$1
# hs "$HOME/toolbelt/window_management/spawn_new.lua" -- $APP_NAME

#!/bin/zsh
APP_NAME=$1

hs -c "
local appName = '$APP_NAME'

-- Target screen = screen of currently focused window (fallback: mouse screen)
local fw = hs.window.focusedWindow()
local targetScreen = (fw and fw:screen()) or hs.mouse.getCurrentScreen()

local app = hs.application.get(appName)

-- 1) If there's already a normal *visible* window on the target screen, focus it
if app then
  for _, win in ipairs(app:allWindows()) do
    if win:isStandard() and win:isVisible() and win:screen() == targetScreen then
      win:focus()
      return
    end
  end
end

-- 2) If app isn't running, launch it and stop (avoid extra windows)
if not app then
  hs.application.launchOrFocus(appName)
  return
end

-- 3) App is running but no window on target screen -> create a new window (Cmd+N)
--    Snapshot current window IDs so we can detect the new one
local before = {}
for _, win in ipairs(app:allWindows()) do
  before[win:id()] = true
end

hs.osascript.applescript(([[
tell application \"System Events\"
  tell process \"%s\"
    set frontmost to true
    keystroke \"n\" using {command down}
  end tell
end tell
]]):format(appName))

-- Wait briefly for the new window to appear, then move it if it spawned on the wrong screen
local newWin = nil
local deadline = hs.timer.secondsSinceEpoch() + 2.0

while hs.timer.secondsSinceEpoch() < deadline do
  for _, win in ipairs(app:allWindows()) do
    if win:isStandard() and win:isVisible() and not before[win:id()] then
      newWin = win
      break
    end
  end
  if newWin then break end
  hs.timer.usleep(100000) -- 100ms
end

-- Fallback: some apps reuse an existing window instead of creating a new one
if not newWin then
  newWin = app:focusedWindow() or app:mainWindow()
end

if newWin then
  -- If the new/focused window is on the other screen, move it over first
  if newWin:screen() ~= targetScreen then
    newWin:moveToScreen(targetScreen, nil, true) -- ensure it stays in bounds
    hs.timer.usleep(100000)
  end
  newWin:focus()
end
"
