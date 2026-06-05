#!/bin/sh
set -e

# Uninstall pdomain-ocr-simple-gui.
#
# Removes the app installed via uv tool install, and optionally removes uv
# itself (always defaulting to N -- uv removal is destructive to all other
# uv-managed tools, so it is always opt-in regardless of whether this
# installer originally bootstrapped uv).
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/uninstall.sh | sh
#
# Unattended (skip all confirmation prompts):
#   curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/uninstall.sh | sh -s -- -y
#   ASSUME_YES=1 curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/uninstall.sh | sh

ASSUME_YES="${ASSUME_YES:-0}"

# ---------------------------------------------------------------------------
# Parse flags: -y / --yes
# ---------------------------------------------------------------------------
for _arg in "$@"; do
    case "$_arg" in
        -y|--yes) ASSUME_YES=1 ;;
    esac
done

# ---------------------------------------------------------------------------
# TTY detection -- MUST use /dev/tty, not [ -t 0 ].
# Under `curl ... | sh`, fd 0 is the piped script, so [ -t 0 ] is false even
# in a real terminal. The controlling terminal is still reachable via /dev/tty.
#
# Implementation note: `if { exec 3</dev/tty; } ...` exits the script in dash
# when the redirect fails, even inside an `if` condition. The safe
# cross-shell pattern is to probe in a subshell first, then exec in the
# main shell only when the probe succeeded.
# ---------------------------------------------------------------------------
HAS_TTY=0
if sh -c "exec 3</dev/tty" 2>/dev/null; then
    exec 3</dev/tty
    HAS_TTY=1
fi

# prompt_yn "Question?" "Y"   ($2 = default: Y or N) -> returns 0 for yes
prompt_yn() {
    # auto-yes flag
    [ "$ASSUME_YES" = "1" ] && return 0
    # headless -- take the default
    if [ "$HAS_TTY" != "1" ]; then return 0; fi
    _def="$2"
    _hint="[Y/n]"
    [ "$_def" = "N" ] && _hint="[y/N]"
    printf '%s %s ' "$1" "$_hint" >/dev/tty
    read _ans <&3 || _ans=""
    [ -z "$_ans" ] && _ans="$_def"
    case "$_ans" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

# ---------------------------------------------------------------------------
# uv-installed-by-installer marker (written by install.sh when it bootstrapped uv)
# ---------------------------------------------------------------------------
_MARKER_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/pdomain-ocr-simple-gui"
_MARKER="$_MARKER_DIR/uv-installed-by-installer"

# ---------------------------------------------------------------------------
# Step 1 -- Remove desktop shortcut (best-effort)
# ---------------------------------------------------------------------------
echo "Removing desktop shortcut (best-effort)..."
if command -v pdomain-ocr-simple-gui >/dev/null 2>&1; then
    pdomain-ocr-simple-gui --remove-desktop-shortcut || true
else
    echo "  pdomain-ocr-simple-gui not on PATH; skipping shortcut removal."
fi

# ---------------------------------------------------------------------------
# Step 2 -- Unregister from suite registry (best-effort)
# ---------------------------------------------------------------------------
# The app registers itself in installed.toml via pdomain_ops.suite.register_self.
# The --unregister-suite flag calls LocalTomlSuiteRegistry().unregister().
echo "Unregistering from suite registry (best-effort)..."
if command -v pdomain-ocr-simple-gui >/dev/null 2>&1; then
    pdomain-ocr-simple-gui --unregister-suite || true
else
    echo "  pdomain-ocr-simple-gui not on PATH; suite registry not updated."
    echo "  To remove manually, edit:"
    echo "    ${XDG_DATA_HOME:-$HOME/.local/share}/pd-suite/installed.toml"
    echo "  and delete the [apps.pdomain-ocr-simple-gui] entry."
fi

# ---------------------------------------------------------------------------
# Step 3 -- Uninstall the tool
# ---------------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not on PATH -- nothing to uninstall via uv."
    echo "If you installed pdomain-ocr-simple-gui via another method, remove it manually."
    exit 0
fi

if prompt_yn "Remove pdomain-ocr-simple-gui?" "Y"; then
    echo "Uninstalling pdomain-ocr-simple-gui..."
    uv tool uninstall pdomain-ocr-simple-gui
    echo "pdomain-ocr-simple-gui removed."
else
    echo "Skipped removal of pdomain-ocr-simple-gui."
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 4 -- Offer to remove uv itself
# ---------------------------------------------------------------------------
# Default is always N -- removing uv is destructive to all other uv-managed
# tools on the system, so it must always be an explicit opt-in.
# The marker is used only to tailor the message (informing the user that uv
# was installed by this app's installer), not to change the default.
if [ -f "$_MARKER" ]; then
    _UV_PROMPT="uv was installed by this app's installer. Remove uv as well? (this affects ALL other uv-managed tools)"
    _UV_DEFAULT="N"
else
    _UV_PROMPT="Also remove uv? (this affects ALL other uv-managed tools)"
    _UV_DEFAULT="N"
fi

if prompt_yn "$_UV_PROMPT" "$_UV_DEFAULT"; then
    echo ""
    echo "WARNING: Removing uv will break all other uv-installed tools on this system."
    echo ""
    # uv self uninstall works when uv was installed via the standalone installer.
    if uv self uninstall 2>/dev/null; then
        echo "uv removed via 'uv self uninstall'."
    else
        echo "uv self uninstall not available (may have been installed via package manager)."
        echo "To remove uv manually:"
        echo "  rm -f \"\$HOME/.local/bin/uv\" \"\$HOME/.local/bin/uvx\""
        echo "  rm -rf \"\${XDG_DATA_HOME:-\$HOME/.local/share}/uv\""
        echo "  rm -rf \"\${XDG_CACHE_HOME:-\$HOME/.cache}/uv\""
    fi
    # Remove the marker regardless of which removal path ran.
    rm -f "$_MARKER"
else
    echo "Keeping uv."
fi

# ---------------------------------------------------------------------------
# Step 5 -- Final informational notes (no action taken)
# ---------------------------------------------------------------------------
echo ""
echo "Cleanup notes:"
echo ""
echo "  WebKitGTK is a system package you installed separately."
echo "  To remove it, use your system package manager, e.g.:"
echo "    Debian/Ubuntu:  sudo apt-get remove gir1.2-webkit2-4.1"
echo "    Fedora:         sudo dnf remove webkit2gtk4.1"
echo ""
echo "  OCR model weights and caches can be removed manually:"
echo "    ~/.cache/doctr/         (DocTR model weights)"
echo "    ~/.cache/torch/         (PyTorch/DocTR model cache)"
echo "    ~/.cache/huggingface/   (HuggingFace model cache, if used)"
echo ""
echo "  App data (projects, preferences) is stored at:"
echo "    \${PD_SUITE_DATA_DIR:-\${XDG_DATA_HOME:-\$HOME/.local/share}/pdomain-ocr-simple-gui/}"
echo "  Remove manually if desired."
echo ""
echo "Uninstall complete."
