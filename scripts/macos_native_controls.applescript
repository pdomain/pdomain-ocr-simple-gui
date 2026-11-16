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
        -- Copy the ids first. A live "whose" list throws -1719 when a dialog exits mid-scan.
        set procIds to {}
        try
            tell application "System Events"
                set procIds to (unix id of every application process whose name is "osascript") as list
            end tell
        end try
        repeat with procId in procIds
            set oneId to contents of procId
            try
                tell application "System Events"
                    set candidate to first application process whose unix id is oneId
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
                end tell
            on error errText number errNum
                if errText contains "Native installer reported failure" then error errText number errNum
            end try
        end repeat
        delay 0.2
    end repeat
    error "Timed out waiting for " & buttonName & " in OCR dialog containing: " & messageMarker
end run
