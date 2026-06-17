#!/bin/zsh

APP_NAME=$1

hs -c "
local appName = [==[$APP_NAME]==]
local app = hs.application.get(appName)
local spaces = hs.spaces
local screen = hs.mouse.getCurrentScreen()
local targetSpace = spaces and screen and spaces.activeSpaces()[screen:getUUID()] or nil

if not app or not spaces or not targetSpace then
  return
end

local win = app:focusedWindow() or app:mainWindow() or app:allWindows()[1]
if not win then
  return
end

spaces.moveWindowToSpace(win, targetSpace)
"
