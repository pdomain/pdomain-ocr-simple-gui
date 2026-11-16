on run argv
    set operation to item 1 of argv
    tell application "System Events"
        if not UI elements enabled then error "Accessibility access is unavailable; native GUI acceptance cannot run."
        get name of application processes
    end tell
    if operation is "preflight" then return "GUI access available"

    set buttonName to item 2 of argv
    set messageMarker to item 3 of argv
    set deadline to (current date) + (item 4 of argv as integer)
    repeat while (current date) < deadline
        try
            tell application "System Events"
                repeat with candidate in (application processes whose name is "osascript")
                    repeat with candidateWindow in windows of candidate
                        set messageText to ""
                        repeat with labelElement in static texts of candidateWindow
                            try
                                set messageText to messageText & (value of labelElement as text)
                            end try
                        end repeat
                        if messageText contains "Installation failed." then error "Native installer reported failure: " & messageText
                        if messageText contains messageMarker then
                            if exists button buttonName of candidateWindow then
                                if operation is "click" then click button buttonName of candidateWindow
                                return "Found " & buttonName & " in the expected OCR dialog"
                            end if
                        end if
                    end repeat
                end repeat
            end tell
        on error errText number errNum
            if errText contains "Native installer reported failure" then error errText number errNum
            -- The process list changes when a dialog exits. Keep waiting.
            if errNum is not -10000 and errNum is not -1712 and errNum is not -1719 and errNum is not -600 and errNum is not -609 then error errText number errNum
        end try
        delay 0.2
    end repeat
    error "Timed out waiting for " & buttonName & " in OCR dialog containing: " & messageMarker
end run
