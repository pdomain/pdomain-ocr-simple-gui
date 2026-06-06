#!/bin/sh
set -e

# Install pdomain-ocr-simple-gui as a standalone tool using uv.
#
# Pulls the wheel from the latest non-prerelease GitHub Release of
# pdomain/pdomain-ocr-simple-gui and installs it via `uv tool install`.
# Uses `gh` if available (and authenticated); otherwise falls back to the
# public GitHub Releases API via curl.
#
# Desktop mode:
#   Always pulls pdomain-ops[desktop] (pywebview>=5 + pystray>=0.19) so
#   the native window works out of the box. After install the script
#   checks for WebKitGTK and prints per-distro install hints if absent.
#
# GPU auto-enable:
#   The CUDA >= 12.4 branch below passes `--with pdomain-book-tools[gpu]`
#   to pull in the optional CuPy + opencv-cuda extras. That extra exists
#   only in pdomain-book-tools >= v0.11.0. pdomain-book-tools is published
#   on the self-hosted pdomain-index-pip PEP 503 index, so the wheel's
#   Requires-Dist entry resolves automatically when we pass
#   --extra-index-url to uv — no manual git-pin fetch needed.
#
# Confirmation gates:
#   The script prompts before auto-installing uv and before `uv tool install`.
#   Gates read from /dev/tty (not stdin), so they work correctly under
#   `curl ... | sh`. In headless environments (CI, cron, docker without -t),
#   gates auto-proceed. Pass -y / --yes or set ASSUME_YES=1 to skip all
#   prompts unconditionally.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/install.sh | sh
#
# Unattended (skip all confirmation prompts):
#   curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/install.sh | sh -s -- -y
#   ASSUME_YES=1 curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/install.sh | sh

REPO="pdomain/pdomain-ocr-simple-gui"
PYTHON_VERSION="${PD_SIMPLE_GUI_INSTALL_PYTHON:-3.13}"
ASSUME_YES="${ASSUME_YES:-0}"
# Minimum uv version required by this project (matches pyproject.toml
# [tool.uv] required-version). Update here whenever pyproject.toml changes.
MIN_UV_VERSION="0.11.16"

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
    # headless -- take the default (which for install gates is "proceed")
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
# Marker file: records that WE bootstrapped uv, so uninstall.sh can offer to
# remove it with the correct default.
# ---------------------------------------------------------------------------
_MARKER_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/pdomain-ocr-simple-gui"
_MARKER="$_MARKER_DIR/uv-installed-by-installer"

# ---------------------------------------------------------------------------
# Install uv if not already present -- with a confirmation gate.
# ---------------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    if prompt_yn "uv is not installed. Install it now via astral.sh/uv/install.sh?" "Y"; then
        echo "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
        # Record that this installer bootstrapped uv
        mkdir -p "$_MARKER_DIR"
        touch "$_MARKER"
    else
        echo ""
        echo "uv is required to install pdomain-ocr-simple-gui."
        echo "Install it manually:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo "Then re-run this installer."
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Version guard: ensure the installed uv is >= MIN_UV_VERSION.
# Bootstrapped uv is always current; this check matters only when the user
# already had an old uv installed before running this script.
# Uses field-by-field numeric compare (POSIX sh -- no `sort -V` assumed).
# ---------------------------------------------------------------------------
_UV_VER_RAW=$(uv --version 2>/dev/null | head -1)
# Format: "uv X.Y.Z (...)" -- extract the X.Y.Z part
_UV_VER=$(printf '%s' "$_UV_VER_RAW" | sed 's/^uv \([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/')
if [ -n "$_UV_VER" ] && [ "$_UV_VER" != "$_UV_VER_RAW" ]; then
    # Split installed version
    _UV_MAJOR=${_UV_VER%%.*}
    _UV_REST=${_UV_VER#*.}
    _UV_MINOR=${_UV_REST%%.*}
    _UV_PATCH=${_UV_REST#*.}
    # Split minimum version
    _MIN_MAJOR=${MIN_UV_VERSION%%.*}
    _MIN_REST=${MIN_UV_VERSION#*.}
    _MIN_MINOR=${_MIN_REST%%.*}
    _MIN_PATCH=${_MIN_REST#*.}
    # Field-by-field numeric compare
    _UV_TOO_OLD=0
    if [ "$_UV_MAJOR" -lt "$_MIN_MAJOR" ]; then
        _UV_TOO_OLD=1
    elif [ "$_UV_MAJOR" -eq "$_MIN_MAJOR" ]; then
        if [ "$_UV_MINOR" -lt "$_MIN_MINOR" ]; then
            _UV_TOO_OLD=1
        elif [ "$_UV_MINOR" -eq "$_MIN_MINOR" ]; then
            if [ "$_UV_PATCH" -lt "$_MIN_PATCH" ]; then
                _UV_TOO_OLD=1
            fi
        fi
    fi
    if [ "$_UV_TOO_OLD" = "1" ]; then
        echo ""
        echo "Your installed uv (${_UV_VER}) is older than the required ${MIN_UV_VERSION}."
        echo ""
        echo "To upgrade uv (standalone installs):"
        echo "  uv self update"
        echo ""
        echo "Or reinstall uv from scratch:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo ""
        if ! prompt_yn "Your uv (${_UV_VER}) is older than the required ${MIN_UV_VERSION}. Continue anyway?" "N"; then
            echo "Aborted. Please upgrade uv to >= ${MIN_UV_VERSION} and re-run this installer."
            exit 1
        fi
        echo "Continuing despite old uv -- the install may fail."
    fi
fi

EXTRA_INDEX=""
PD_BOOK_TOOLS_EXTRAS=""
PD_INDEX_URL="https://pdomain.github.io/pdomain-index-pip/simple/"

# Auto-detect NVIDIA CUDA
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    CUDA_VER=$(nvidia-smi 2>/dev/null | sed -n 's/.*CUDA Version: \([0-9]*\.[0-9]*\).*/\1/p' | head -1)
    if [ -n "$CUDA_VER" ]; then
        CUDA_TAG="cu$(echo "$CUDA_VER" | tr -d '.')"
        EXTRA_INDEX="https://download.pytorch.org/whl/${CUDA_TAG}"
        echo "Detected CUDA ${CUDA_VER} -- will install PyTorch with ${CUDA_TAG} support."

        # CuPy (cupy-cuda12x) requires CUDA >= 12.4. Only opt into the
        # pdomain-book-tools[gpu] extra when that minimum is satisfied;
        # otherwise the [gpu] resolve fails with a CuPy version error
        # and a working CPU-only install would have been preferable.
        # POSIX-sh version compare -- no `sort -V`, no `awk`.
        CUDA_MAJOR=${CUDA_VER%.*}
        CUDA_MINOR=${CUDA_VER#*.}
        if [ "$CUDA_MAJOR" -gt 12 ] || { [ "$CUDA_MAJOR" -eq 12 ] && [ "$CUDA_MINOR" -ge 4 ]; }; then
            PD_BOOK_TOOLS_EXTRAS="[gpu]"
            echo "CUDA ${CUDA_VER} >= 12.4 -- enabling pdomain-book-tools[gpu] (CuPy + opencv-cuda)."
        else
            echo "CUDA ${CUDA_VER} < 12.4 -- installing CPU-only book-tools (cupy-cuda12x needs >= 12.4)."
        fi
    else
        echo "nvidia-smi found but could not detect CUDA version -- falling back to CPU."
    fi
# Detect Apple Silicon (MPS)
elif [ "$(uname)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    echo "Detected Apple Silicon -- MPS acceleration will be used automatically."
else
    echo "No GPU detected -- installing CPU-only PyTorch."
fi

# ---------------------------------------------------------------------------
# Resolve the latest non-prerelease GitHub Release and find the wheel asset.
# ---------------------------------------------------------------------------
# We pin to the asset URL of the .whl on the "latest" Release. The Release
# workflow (.github/workflows/release.yml) attaches both .whl and .tar.gz --
# we install the .whl directly so end users don't need a build toolchain.

WHEEL_URL=""
RELEASE_TAG=""

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    echo "Resolving latest release (gh detected)..."
    # `gh release view --json` returns assets with their download URLs.
    RELEASE_JSON=$(gh release view --repo "$REPO" --json tagName,assets 2>/dev/null || true)
    if [ -n "$RELEASE_JSON" ]; then
        RELEASE_TAG=$(printf '%s' "$RELEASE_JSON" | grep -o '"tagName":"[^"]*"' | head -1 | sed 's/.*"tagName":"\([^"]*\)".*/\1/')
        # Pull the first .whl asset's URL.
        WHEEL_URL=$(printf '%s' "$RELEASE_JSON" \
            | tr ',' '\n' \
            | grep -o '"url":"[^"]*\.whl"' \
            | head -1 \
            | sed 's/.*"url":"\([^"]*\)".*/\1/')
    fi
fi

if [ -z "$WHEEL_URL" ]; then
    echo "Resolving latest release via GitHub API..."
    RELEASE_JSON=$(curl -sSfL "https://api.github.com/repos/${REPO}/releases/latest" 2>/dev/null || true)
    if [ -z "$RELEASE_JSON" ]; then
        echo "Could not query the GitHub Releases API for ${REPO}." >&2
        echo "   Check your network, or install manually with:" >&2
        echo "     uv tool install git+https://github.com/${REPO}" >&2
        exit 1
    fi
    RELEASE_TAG=$(printf '%s' "$RELEASE_JSON" \
        | grep '"tag_name"' | head -1 \
        | sed 's/.*"tag_name": *"\([^"]*\)".*/\1/')
    WHEEL_URL=$(printf '%s' "$RELEASE_JSON" \
        | grep '"browser_download_url"' \
        | grep '\.whl"' \
        | head -1 \
        | sed 's/.*"browser_download_url": *"\([^"]*\)".*/\1/')
fi

if [ -z "$WHEEL_URL" ]; then
    echo "Latest release ${RELEASE_TAG:-?} has no wheel asset attached." >&2
    echo "   Cannot install. Please check https://github.com/${REPO}/releases" >&2
    echo "   and report the missing wheel -- or install from source with:" >&2
    echo "     uv tool install git+https://github.com/${REPO}" >&2
    exit 1
fi

echo "Latest release: ${RELEASE_TAG:-(unknown tag)}"
echo "Wheel asset:    ${WHEEL_URL}"
echo "pdomain-index-pip:       ${PD_INDEX_URL}"

# ---------------------------------------------------------------------------
# Download the wheel to a temp dir and install.
# ---------------------------------------------------------------------------
TMPDIR=$(mktemp -d)
# shellcheck disable=SC2064
trap "rm -rf '$TMPDIR'" EXIT

WHEEL_FILE="$TMPDIR/$(basename "$WHEEL_URL")"
echo "Downloading wheel..."
# `gh` asset URLs (api.github.com/repos/.../assets/<id>) require an Accept
# header to receive the binary; public browser_download_url variants do not.
# Sending the header for both forms is harmless.
if ! curl -sSfL \
        -H "Accept: application/octet-stream" \
        -o "$WHEEL_FILE" "$WHEEL_URL"; then
    echo "Failed to download wheel from ${WHEEL_URL}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Build the GPU label for the summary block.
# ---------------------------------------------------------------------------
if [ -n "$EXTRA_INDEX" ]; then
    if [ -n "$PD_BOOK_TOOLS_EXTRAS" ]; then
        _GPU_LABEL="CUDA ${CUDA_VER} (GPU build)"
    else
        _GPU_LABEL="CUDA ${CUDA_VER} (CPU-only book-tools; CUDA < 12.4)"
    fi
elif [ "$(uname)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    _GPU_LABEL="Apple Silicon / MPS"
else
    _GPU_LABEL="CPU-only"
fi

# ---------------------------------------------------------------------------
# Summary gate -- one prompt immediately before uv tool install.
# ---------------------------------------------------------------------------
echo ""
echo "About to install:"
echo "  Package:  pdomain-ocr-simple-gui ${RELEASE_TAG:-}"
echo "  GPU:      ${_GPU_LABEL}"
echo "  Desktop:  pdomain-ops[desktop] included (native --desktop window)"
echo "  Target:   uv tool  (~/.local/bin)"
echo "  Index:    ${PD_INDEX_URL}"
echo ""

if [ -n "$EXTRA_INDEX" ]; then
    echo "Heads up - disk space: the CUDA-flavored PyTorch wheels are a large"
    echo "  download, roughly 2-3 GB (more with the [gpu] CuPy + opencv-cuda"
    echo "  extras). The CPU-only build is far smaller. This can take a while"
    echo "  on a slow connection."
    echo ""
fi

if ! prompt_yn "Proceed with install?" "Y"; then
    echo "Aborted."
    exit 0
fi

echo "Installing pdomain-ocr-simple-gui ${RELEASE_TAG:-} from $(basename "$WHEEL_FILE")..."
# Build the install command incrementally so we only emit flags when relevant.
# POSIX sh has no arrays -- use `set --` to manage args.
#
# pdomain-book-tools is published on the self-hosted pdomain-index-pip (GitHub
# Pages PEP 503 index); pass --extra-index-url so uv can resolve the
# Requires-Dist entry that the wheel's METADATA carries. When CUDA >= 12.4
# was detected above, $PD_BOOK_TOOLS_EXTRAS is "[gpu]"; we pass --with to
# pull that extra in.
#
# pdomain-ops[desktop] is always included so the native window works out of
# the box (PyQt6 + pystray>=0.19).
set -- --reinstall "$WHEEL_FILE" --extra-index-url "$PD_INDEX_URL"
if [ -n "$PD_BOOK_TOOLS_EXTRAS" ]; then
    set -- "$@" --with "pdomain-book-tools${PD_BOOK_TOOLS_EXTRAS}"
fi
set -- "$@" --with "pdomain-ops[desktop]"
if [ -n "$EXTRA_INDEX" ]; then
    set -- "$@" --extra-index-url "$EXTRA_INDEX"
fi
uv tool install --python "$PYTHON_VERSION" "$@"

# ---------------------------------------------------------------------------
# Post-install: check for Qt xcb-cursor lib (X11 only).
# ---------------------------------------------------------------------------
# The Qt backend is bundled inside the tool venv via pdomain-ops[desktop].
# On X11 sessions, Qt also requires the system xcb-cursor library to launch
# the native window.  Wayland sessions do NOT need it -- Qt auto-selects the
# bundled Wayland plugin instead.
# We DETECT and WARN -- we never sudo-install system packages on the user's
# behalf.

XCB_OK=0
if ldconfig -p 2>/dev/null | grep -q "libxcb-cursor"; then
    XCB_OK=1
fi

echo ""
if [ "$XCB_OK" = "0" ]; then
    echo "NOTE: libxcb-cursor was not detected on this system."
    echo "  On X11 sessions, the --desktop (native window) mode requires this"
    echo "  small system library.  Wayland sessions can skip this -- the app"
    echo "  auto-selects the bundled Wayland Qt plugin."
    echo "  Browser mode works on both X11 and Wayland without it."
    echo ""
    echo "  Install the xcb-cursor library for your distro:"
    echo "    Debian/Ubuntu/Mint (apt):  sudo apt-get install -y libxcb-cursor0"
    echo "    Fedora (dnf):             sudo dnf install -y xcb-util-cursor"
    echo "    RHEL/CentOS (yum):        sudo yum install -y xcb-util-cursor"
    echo "    Arch (pacman):            sudo pacman -S xcb-util-cursor"
    echo "    openSUSE (zypper):        sudo zypper install libxcb-cursor0"
    echo "    Alpine (apk):             sudo apk add xcb-util-cursor"
    echo "  See other distros: docs/runbooks/install.md"
    echo ""
fi

echo "Done! Launch pdomain-ocr-simple-gui:"
echo ""
echo "  Desktop window (native):  pdomain-ocr-simple-gui --desktop"
echo "  Browser mode:             pdomain-ocr-simple-gui"
echo "                            then open http://localhost:8004"
echo ""
echo "If 'pdomain-ocr-simple-gui' is not found, add uv's tool bin to your PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
