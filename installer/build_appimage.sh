#!/usr/bin/env bash
# build_appimage.sh — build the Linux AppImage installer for pdomain-ocr-simple-gui.
#
# Usage:
#   ./installer/build_appimage.sh [--out <dir>]
#
# The script:
#   1. Downloads appimagetool if not already on PATH or in ./tools/.
#   2. Assembles an AppDir with:
#      - installer/appimage/AppRun       (the entry point)
#      - installer/appimage/*.desktop    (the .desktop file)
#      - installer/install_engine.py     (the engine)
#      - installer/wizard.py             (the GUI wizard)
#      - A minimal bundled Python sysroot (from the system python3 shutil tree)
#   3. Calls appimagetool to pack the AppDir into a single .AppImage file.
#
# Prerequisites: python3, fuse (or fuse2), bash.
# The resulting .AppImage runs on any Linux x86_64 distro with FUSE available.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${REPO_ROOT}/dist"
TOOLS_DIR="${REPO_ROOT}/tools"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"

# ── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --out) OUT_DIR="$2"; shift 2 ;;
        --help|-h) echo "Usage: $0 [--out <dir>]"; exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

mkdir -p "${OUT_DIR}" "${TOOLS_DIR}"

# ── Locate or download appimagetool ────────────────────────────────────────
if command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="$(command -v appimagetool)"
elif [[ -x "${TOOLS_DIR}/appimagetool" ]]; then
    APPIMAGETOOL="${TOOLS_DIR}/appimagetool"
else
    echo "appimagetool not found — downloading to ${TOOLS_DIR}/appimagetool …"
    curl -fsSL "${APPIMAGETOOL_URL}" -o "${TOOLS_DIR}/appimagetool"
    chmod +x "${TOOLS_DIR}/appimagetool"
    APPIMAGETOOL="${TOOLS_DIR}/appimagetool"
fi

echo "Using appimagetool: ${APPIMAGETOOL}"

# ── Assemble AppDir ─────────────────────────────────────────────────────────
APP_NAME="pdomain-ocr-simple-gui-installer"
APPDIR="${REPO_ROOT}/.appdir-build/${APP_NAME}.AppDir"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/lib/python"

# Entry point + desktop integration
install -m 0755 "${SCRIPT_DIR}/appimage/AppRun" "${APPDIR}/AppRun"
install -m 0644 "${SCRIPT_DIR}/appimage/${APP_NAME}.desktop" "${APPDIR}/${APP_NAME}.desktop"

# Icon (use a placeholder if the real icon isn't available)
ICON_SRC="${REPO_ROOT}/src/pdomain_ocr_simple_gui/static/favicon.ico"
if [[ -f "${ICON_SRC}" ]]; then
    install -m 0644 "${ICON_SRC}" "${APPDIR}/pdomain-ocr-simple-gui.ico"
else
    # Create a minimal 1×1 transparent PNG placeholder
    python3 -c "
import base64, sys
# Minimal 1×1 transparent PNG (67 bytes)
data = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
)
sys.stdout.buffer.write(data)
" > "${APPDIR}/pdomain-ocr-simple-gui.png" || true
fi

# Installer Python sources
mkdir -p "${APPDIR}/usr/lib/python/installer"
install -m 0644 "${SCRIPT_DIR}/install_engine.py" "${APPDIR}/usr/lib/python/installer/install_engine.py"
install -m 0644 "${SCRIPT_DIR}/wizard.py"         "${APPDIR}/usr/lib/python/installer/wizard.py"
touch "${APPDIR}/usr/lib/python/installer/__init__.py"

# Bundle a minimal Python interpreter (the system python3 + stdlib)
PYTHON3="$(command -v python3)"
PYTHON_VERSION="$("${PYTHON3}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTHON_STDLIB="$(python3 -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')"

mkdir -p "${APPDIR}/usr/bin"
cp "${PYTHON3}" "${APPDIR}/usr/bin/python3"
# Copy the stdlib (needed for tkinter, subprocess, shlex, etc.)
mkdir -p "${APPDIR}/usr/lib/python${PYTHON_VERSION}"
# Selectively copy tkinter + minimal stdlib for the wizard
for mod in tkinter subprocess shlex dataclasses argparse os sys shutil; do
    src="${PYTHON_STDLIB}/${mod}"
    if [[ -d "${src}" ]]; then
        cp -r "${src}" "${APPDIR}/usr/lib/python${PYTHON_VERSION}/"
    elif [[ -f "${src}.py" ]]; then
        cp "${src}.py" "${APPDIR}/usr/lib/python${PYTHON_VERSION}/"
    fi
done

# ── Build the AppImage ──────────────────────────────────────────────────────
OUTPUT="${OUT_DIR}/${APP_NAME}-x86_64.AppImage"
echo "Building AppImage → ${OUTPUT}"

ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT}"
chmod +x "${OUTPUT}"

echo ""
echo "AppImage built successfully:"
echo "  ${OUTPUT}"
echo ""
echo "To run on any Linux x86_64 system with FUSE:"
echo "  ./${APP_NAME}-x86_64.AppImage"
