#!/bin/zsh


export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

hs -c "local win=hs.window.focusedWindow(); if not win then return end; local sf=win:screen():frame(); local half=hs.geometry.rect(sf.x, sf.y, sf.w/2, sf.h); local twothirds=hs.geometry.rect(sf.x, sf.y, sf.w*2/3, sf.h); local cur=win:frame(); local tol=6; local function close(a,b) return math.abs(a-b)<=tol end; local function same(r1,r2) return close(r1.x,r2.x) and close(r1.y,r2.y) and close(r1.w,r2.w) and close(r1.h,r2.h) end; if same(cur,half) then win:setFrame(twothirds,0) elseif same(cur,twothirds) then win:setFrame(half,0) else win:setFrame(half,0) end"
