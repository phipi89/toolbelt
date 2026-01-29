#!/bin/zsh

APP_NAME=$1

hs -c "
local appName = '$APP_NAME'

local app = hs.application.get(appName)
-- Capture the screen where the mouse is (most intuitive "current" screen)
local targetScreen = hs.mouse.getCurrentScreen()
local windowFound = false

if app then
    local windows = app:allWindows()
    for _, win in ipairs(windows) do
        if win:isStandard() then
            win:focus()
            windowFound = true
            break
        end
    end
end

if not windowFound then
    -- 1. Bring app to front (or launch it)
    hs.application.launchOrFocus(appName)

    -- 2. Wait slightly for focus to settle, then send Cmd+N
    hs.timer.doAfter(0.1, function()
        hs.eventtap.keyStroke({'cmd'}, 'n')

        hs.timer.doAfter(0.2, function()
            local win = hs.window.focusedWindow()
            if win and win:application():name() == appName then
                -- screen, noResize, ensureInScreenBounds, duration
                win:moveToScreen(targetScreen, false, false, 0)
                win:focus()
            end
        end)
    end)
end

"
