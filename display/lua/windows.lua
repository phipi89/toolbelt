local windows = {}

function windows.activeScreen()
  local focused = hs.window.focusedWindow()
  return (focused and focused:screen()) or hs.mouse.getCurrentScreen()
end

function windows.focused()
  return hs.window.focusedWindow()
end

function windows.isFinderWindow(win)
  local app = win and win:application()
  return app and app:name() == 'Finder'
end

function windows.isEligible(win, screen, opts)
  opts = opts or {}
  if not win or not screen then return false end
  if opts.visible ~= false and not win:isVisible() then return false end
  if win:screen() ~= screen then return false end
  if opts.standard == false or win:isStandard() then return true end
  return opts.allowFinderFallback and windows.isFinderWindow(win) and tostring(win:title()) ~= ''
end

function windows.addUnique(list, seen, win, screen, opts)
  if not windows.isEligible(win, screen, opts) then return end
  local id = win:id()
  if not id or seen[id] then return end
  seen[id] = true
  table.insert(list, win)
end

function windows.onScreen(screen, opts)
  opts = opts or {}
  local result = {}
  local seen = {}
  local limit = opts.limit
  local focused = hs.window.focusedWindow()

  if opts.includeFocused ~= false then
    windows.addUnique(result, seen, focused, screen, opts)
  end

  for _, win in ipairs(hs.window.orderedWindows()) do
    windows.addUnique(result, seen, win, screen, opts)
    if limit and #result >= limit then return result end
  end

  local frontApp = hs.application.frontmostApplication()
  if opts.allowFinderFallback and frontApp and frontApp:name() == 'Finder' then
    windows.addUnique(result, seen, frontApp:focusedWindow(), screen, opts)
    windows.addUnique(result, seen, frontApp:mainWindow(), screen, opts)
    for _, win in ipairs(frontApp:allWindows()) do
      windows.addUnique(result, seen, win, screen, opts)
      if limit and #result >= limit then return result end
    end
  end

  return result
end

function windows.focusedOnScreenWindows(opts)
  local screen = windows.activeScreen()
  if not screen then return {}, nil end
  return windows.onScreen(screen, opts), screen
end

return windows
