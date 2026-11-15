#!/bin/sh
set -eu

PAYLOAD=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
DIALOG="$PAYLOAD/dialog.applescript"
UV_BIN_DIR="${UV_UNMANAGED_INSTALL:-${UV_INSTALL_DIR:-${XDG_BIN_HOME:-${XDG_DATA_HOME:+$XDG_DATA_HOME/../bin}}}}"
UV_BIN_DIR="${UV_BIN_DIR:-$HOME/.local/bin}"
export PATH="$UV_BIN_DIR:$PATH"

INSTALL_LOG_DIR=$(mktemp -d)
touch "$INSTALL_LOG_DIR/.nobackup"
INSTALL_LOG="$INSTALL_LOG_DIR/install.log"
PROGRESS_PID=''
cleanup() {
    if [ -n "$PROGRESS_PID" ]; then
        kill "$PROGRESS_PID" 2>/dev/null || :
        wait "$PROGRESS_PID" 2>/dev/null || :
    fi
    rm -rf "$INSTALL_LOG_DIR"
}
trap cleanup EXIT HUP INT TERM

CONFIRM_STATUS=0
/usr/bin/osascript "$DIALOG" confirm "Install OCR Simple GUI and required Python packages in your user account?" >"$INSTALL_LOG" 2>&1 || CONFIRM_STATUS=$?
if [ "$CONFIRM_STATUS" -ne 0 ]; then
    if [ "$CONFIRM_STATUS" -eq 1 ] && grep -Fq '(-128)' "$INSTALL_LOG"; then
        exit 0
    fi
    cat "$INSTALL_LOG" >&2
    exit "$CONFIRM_STATUS"
fi

while :; do
    /usr/bin/osascript "$DIALOG" progress "Installing OCR Simple GUI. Downloads can take several minutes. This window closes when installation finishes." >/dev/null 2>&1 &
    PROGRESS_PID=$!
    INSTALL_STATUS=0
    if [ -f "$PAYLOAD/bundled-wheel.path" ]; then
        PD_SIMPLE_GUI_INSTALL_WHEEL="$PAYLOAD/$(cat "$PAYLOAD/bundled-wheel.path")"
        export PD_SIMPLE_GUI_INSTALL_WHEEL
    fi
    /bin/sh "$PAYLOAD/install.sh" --no-appimage -y >"$INSTALL_LOG" 2>&1 || INSTALL_STATUS=$?
    if [ "$INSTALL_STATUS" = 0 ]; then
        TOOL_ROOT=$(uv tool dir) || INSTALL_STATUS=$?
        if [ "$INSTALL_STATUS" = 0 ]; then
            "$TOOL_ROOT/pdomain-ocr-simple-gui/bin/python" "$PAYLOAD/native.py" --integrate-only >>"$INSTALL_LOG" 2>&1 || INSTALL_STATUS=$?
        fi
    fi
    kill "$PROGRESS_PID" 2>/dev/null || :
    wait "$PROGRESS_PID" 2>/dev/null || :
    PROGRESS_PID=''
    if [ "$INSTALL_STATUS" = 0 ]; then
        /usr/bin/osascript "$DIALOG" "done" "Installation complete. Open OCR Simple GUI in your Applications folder."
        exit 0
    fi
    DETAILS=$(tail -c 5000 "$INSTALL_LOG")
    if ! /usr/bin/osascript "$DIALOG" confirm "Installation failed. Choose Continue to retry.

$DETAILS"; then
        exit 1
    fi
done
