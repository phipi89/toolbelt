#!/bin/zsh


export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

hs -c "local win=hs.window.focusedWindow(); if not win then return end; local sf=win:screen():frame(); local target=hs.geometry.rect(sf.x, sf.y+sf.h*0.70, sf.w*0.30, sf.h*0.30); win:setFrame(target,0)"
