#!/bin/sh
set -eu

# Launch Services can start this script-only app under Rosetta. Switch before
# any temp files or downloads. install.sh repeats the check for a direct run.
if [ "$(uname -s)" = "Darwin" ]; then
    _translated=$(/usr/sbin/sysctl -n sysctl.proc_translated 2>/dev/null || true)
    if [ "$_translated" = "1" ]; then
        if [ "${PD_OCR_NATIVE_ARM64:-}" = "1" ]; then
            echo "Could not switch this Apple Silicon Mac out of Rosetta." >&2
            exit 1
        fi
        PD_OCR_NATIVE_ARM64=1
        export PD_OCR_NATIVE_ARM64
        if [ -f "$0" ]; then
            exec /usr/bin/arch -arm64 /bin/sh "$0" "$@"
        fi
        echo "This terminal is running under Rosetta. Open Terminal and run the installer again." >&2
        exit 1
    fi
fi

PAYLOAD=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
DIALOG="$PAYLOAD/dialog.applescript"
GPU_SETUP_GUIDE_URL="https://github.com/pdomain/pdomain-ocr-simple-gui/blob/master/docs/usage/nvidia-gpu-setup.md"
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

# Return 0 when the person chooses Continue. A GPU guide click opens the
# driver page and shows the same dialog again. Cancel and other osascript
# failures return that status so the caller can keep its existing exit.
confirm_install() {
    message=$1
    while :; do
        CONFIRM_STATUS=0
        /usr/bin/osascript "$DIALOG" confirm "$message" >"$INSTALL_LOG" 2>&1 || CONFIRM_STATUS=$?
        if [ "$CONFIRM_STATUS" -ne 0 ]; then
            return "$CONFIRM_STATUS"
        fi
        if grep -Fq 'button returned:GPU guide' "$INSTALL_LOG"; then
            open_status=0
            /usr/bin/open "$GPU_SETUP_GUIDE_URL" || open_status=$?
            if [ "$open_status" -ne 0 ]; then
                return "$open_status"
            fi
            continue
        fi
        return 0
    done
}

CONFIRM_STATUS=0
confirm_install "Install OCR Simple GUI and required Python packages in your user account? This installer does not install an NVIDIA driver. OCR works on the CPU until you install driver 525 or newer and run the installer again. The GPU guide button opens the steps." || CONFIRM_STATUS=$?
if [ "$CONFIRM_STATUS" -ne 0 ]; then
    if [ "$CONFIRM_STATUS" -eq 1 ] && grep -Fq '(-128)' "$INSTALL_LOG"; then
        exit 0
    fi
    cat "$INSTALL_LOG" >&2
    exit "$CONFIRM_STATUS"
fi

while :; do
    /usr/bin/osascript "$DIALOG" progress "Installing OCR Simple GUI. Downloads can take several minutes. You can close this window. Installation continues until a later window says it is complete." >/dev/null 2>&1 &
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
    if ! confirm_install "Installation failed. Choose Continue to retry.

$DETAILS"; then
        exit 1
    fi
done
