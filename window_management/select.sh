#!/bin/zsh

APP_NAME=$1

osascript <<EOT
tell application "System Events"
    if not (exists process "$APP_NAME") then
        -- App isn't running? We have to launch it (this will move screens)
        tell application "$APP_NAME" to activate
    else
        tell process "$APP_NAME"
            set windowCount to count (windows whose role is "AXWindow")

            -- Setting frontmost to true via System Events is "quieter"
            -- than the 'activate' command.
            set frontmost to true

            if windowCount is 0 then
                -- Trigger App Exposé for the current app only
                -- 125 is Down Arrow
                key code 125 using control down
            else
                -- If windows exist, they will now pop over to your current space
                -- or just focus if they are already here.
            end if
        end tell
    end if
end tell
EOT
