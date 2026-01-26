hs.hotkey.bind({}, "F18", function()
    local appName = "Firefox"
    local app = hs.application.get(appName)
    local currentScreen = hs.screen.mainScreen()
    local windowFoundOnScreen = false

    if app then
        local windows = app:allWindows()
        for _, win in ipairs(windows) do
            if win:isStandard() and win:screen() == currentScreen then
                win:focus()
                windowFoundOnScreen = true
                break
            end
        end
    end

    if not windowFoundOnScreen then
        -- 1. Open the new window
        hs.task.new("/usr/bin/open", nil, { "-na", "Firefox", "--args", "-new-window" }):start()
        
        -- 2. Wait 0.3 seconds for the window to exist, then move it
        hs.timer.doAfter(0.3, function()
            local fw = hs.window.focusedWindow()
            if fw and fw:application():name() == appName then
                fw:moveToScreen(currentScreen)
                -- fw:maximize() -- Optional: ensures it fills the new screen
            end
        end)
    end
end)

local function showObsidianPicker(app, currentScreen)
    local windows = app:allWindows()
    local choices = {}

    for _, win in ipairs(windows) do
        if win:isStandard() then
            -- Create a list entry for each window
            table.insert(choices, {
                text = win:title(),
                subText = "On screen: " .. win:screen():name(),
                window = win, -- Store the window object to focus it later
                image = app:icon() -- Adds the Obsidian icon to the list
            })
        end
    end

    -- Create the chooser UI
    local chooser = hs.chooser.new(function(choice)
        if choice then
            choice.window:focus()
        end
    end)

    chooser:choices(choices)
    chooser:placeholderText("Select an Obsidian window...")
    chooser:show()
end








hs.hotkey.bind({}, "F19", function()
    local appName = "Obsidian"
    local app = hs.application.get(appName)
    local currentScreen = hs.screen.mainScreen()
    
    if not app then
        hs.application.launchOrFocus(appName)
        return
    end

    local winOnScreen = hs.fnutils.find(app:allWindows(), function(win)
        return win:isStandard() and win:screen() == currentScreen
    end)

    if winOnScreen then
        winOnScreen:focus()
    else
        -- 1. Bring the app to focus (necessary for App Exposé)
        app:activate()
        
        -- 2. Use AppleScript to trigger the NATIVE App Exposé
        -- This is the code equivalent of the trackpad gesture or Ctrl+Down
        local script = [[
            tell application "System Events"
                key code 125 using control down -- 125 is the 'Down Arrow'
            end tell
        ]]
        hs.applescript.applescript(script)
    end
end)