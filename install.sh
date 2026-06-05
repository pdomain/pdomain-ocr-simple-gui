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
# Usage:
#   curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/install.sh | sh

REPO="pdomain/pdomain-ocr-simple-gui"
PYTHON_VERSION="${PD_SIMPLE_GUI_INSTALL_PYTHON:-3.13}"

# Install uv if not already present
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found — installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
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
        echo "Detected CUDA ${CUDA_VER} — will install PyTorch with ${CUDA_TAG} support."

        # CuPy (cupy-cuda12x) requires CUDA >= 12.4. Only opt into the
        # pdomain-book-tools[gpu] extra when that minimum is satisfied;
        # otherwise the [gpu] resolve fails with a CuPy version error
        # and a working CPU-only install would have been preferable.
        # POSIX-sh version compare — no `sort -V`, no `awk`.
        CUDA_MAJOR=${CUDA_VER%.*}
        CUDA_MINOR=${CUDA_VER#*.}
        if [ "$CUDA_MAJOR" -gt 12 ] || { [ "$CUDA_MAJOR" -eq 12 ] && [ "$CUDA_MINOR" -ge 4 ]; }; then
            PD_BOOK_TOOLS_EXTRAS="[gpu]"
            echo "CUDA ${CUDA_VER} >= 12.4 — enabling pdomain-book-tools[gpu] (CuPy + opencv-cuda)."
        else
            echo "CUDA ${CUDA_VER} < 12.4 — installing CPU-only book-tools (cupy-cuda12x needs >= 12.4)."
        fi
    else
        echo "nvidia-smi found but could not detect CUDA version — falling back to CPU."
    fi
# Detect Apple Silicon (MPS)
elif [ "$(uname)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    echo "Detected Apple Silicon — MPS acceleration will be used automatically."
else
    echo "No GPU detected — installing CPU-only PyTorch."
fi

# ---------------------------------------------------------------------------
# Resolve the latest non-prerelease GitHub Release and find the wheel asset.
# ---------------------------------------------------------------------------
# We pin to the asset URL of the .whl on the "latest" Release. The Release
# workflow (.github/workflows/release.yml) attaches both .whl and .tar.gz —
# we install the .whl directly so end users don't need a build toolchain.

WHEEL_URL=""
RELEASE_TAG=""

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    echo "Resolving latest release via gh..."
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
    echo "   and report the missing wheel — or install from source with:" >&2
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

echo "Installing pdomain-ocr-simple-gui ${RELEASE_TAG:-} from $(basename "$WHEEL_FILE")..."
# Build the install command incrementally so we only emit flags when relevant.
# POSIX sh has no arrays — use `set --` to manage args.
#
# pdomain-book-tools is published on the self-hosted pdomain-index-pip (GitHub
# Pages PEP 503 index); pass --extra-index-url so uv can resolve the
# Requires-Dist entry that the wheel's METADATA carries. When CUDA >= 12.4
# was detected above, $PD_BOOK_TOOLS_EXTRAS is "[gpu]"; we pass --with to
# pull that extra in.
#
# pdomain-ops[desktop] is always included so the native window works out of
# the box (pywebview>=5 + pystray>=0.19).
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
# Post-install: check for WebKitGTK (required for --desktop mode).
# ---------------------------------------------------------------------------
# pywebview uses the system WebKitGTK library for the native window.
# Browser mode works without it, but --desktop will fail if it is absent.
# We DETECT and WARN — we never sudo-install system packages on the user's
# behalf.

WEBKIT_OK=0
if pkg-config --exists webkit2gtk-4.1 2>/dev/null; then
    WEBKIT_OK=1
elif pkg-config --exists webkit2gtk-4.0 2>/dev/null; then
    WEBKIT_OK=1
elif ldconfig -p 2>/dev/null | grep -q "libwebkit2gtk"; then
    WEBKIT_OK=1
fi

echo ""
if [ "$WEBKIT_OK" = "0" ]; then
    echo "NOTE: WebKitGTK was not detected on this system."
    echo "  The --desktop (native window) mode requires this system library."
    echo "  Browser mode works without it."
    echo ""
    echo "  Install WebKitGTK for your distro:"
    echo "    Debian/Ubuntu/Mint (apt):  sudo apt-get install -y gir1.2-webkit2-4.1"
    echo "    Fedora (dnf):             sudo dnf install -y webkit2gtk4.1"
    echo "    Arch (pacman):            sudo pacman -S webkit2gtk"
    echo "    openSUSE (zypper):        sudo zypper install typelib-1_0-WebKit2-4_1"
    echo "    Alpine (apk):             sudo apk add webkit2gtk"
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
