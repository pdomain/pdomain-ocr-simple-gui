on run argv
    set mode to item 1 of argv
    set messageText to item 2 of argv
    if mode is "progress" then
        display dialog messageText with title "OCR Simple GUI" buttons {"Hide"} default button "Hide" giving up after 86400
    else if mode is "done" then
        display dialog messageText with title "OCR Simple GUI" buttons {"OK"} default button "OK"
    else
        display dialog messageText with title "OCR Simple GUI" buttons {"Cancel", "GPU guide", "Continue"} default button "Continue" cancel button "Cancel"
    end if
end run
