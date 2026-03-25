#!/bin/zsh

APP_NAME=$1

hs -c "
local appName = '$APP_NAME'
local app = hs.application.get(appName)

local function safeCall(obj, methodName)
    if not obj then return nil end
    local method = obj[methodName]
    if type(method) ~= 'function' then return nil end
    local ok, result = pcall(method, obj)
    if ok then return result end
    return nil
end

-- 1. Try to find any standard window belonging to the app
local win = nil
if app then
    local windows = safeCall(app, 'allWindows') or {}
    win = safeCall(app, 'focusedWindow') or safeCall(app, 'mainWindow') or windows[1]
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
