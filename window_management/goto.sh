#!/bin/zsh

APP_NAME=$1

hs -c "
local appName = '$APP_NAME'
local app = hs.application.get(appName)

-- 1. Try to find any standard window belonging to the app
local win = nil
if app then
    win = app:mainWindow() or app:allWindows()[1]
end

if win then
    -- 2. If found, focus it. Hammerspoon will switch Spaces/Screens automatically.
    win:focus()
else
    -- 3. If not found or app not running, launch/focus the app
    -- This handles starting the app if it's closed.
    hs.application.launchOrFocus(appName)
end
"
