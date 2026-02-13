#!/bin/zsh


export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

hs -c "
local win=hs.window.focusedWindow()
if not win then return end

local sf=win:screen():frame()
local target90=hs.geometry.rect(sf.x+sf.w*0.05, sf.y+sf.h*0.05, sf.w*0.90, sf.h*0.90)
local target100=sf

local cur=win:frame()
local tol=6
local function close(a,b)
  return math.abs(a-b)<=tol
end

if close(cur.x,target90.x) and close(cur.y,target90.y) and close(cur.w,target90.w) and close(cur.h,target90.h) then
  win:setFrame(target100,0)
else
  win:setFrame(target90,0)

end
"