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
#      NOTE: No Python binary is bundled.  AppRun locates system python3.
#            Bundling a system Python ELF is NOT portable (glibc version +
#            shared library paths differ across distros).  Using system python3
#            avoids all stdlib-portability issues and keeps the AppImage small.
#            The AppImage is a wizard-installer, not a full app bundle.
#   3. Calls appimagetool to pack the AppDir into a single .AppImage file.
#
# Prerequisites: python3, bash.
# FUSE is NOT required when APPIMAGE_EXTRACT_AND_RUN=1 is set.
# The resulting .AppImage runs on any Linux x86_64 distro with python3 >= 3.8.

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

# Verify python3 is available (required at runtime for the wizard)
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. The AppImage wizard requires python3 at runtime." >&2
    exit 1
fi
echo "Using system python3: $(command -v python3) ($(python3 --version))"

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
mkdir -p "${APPDIR}/usr/lib/python"

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

# Installer Python sources (no Python binary — AppRun uses system python3)
mkdir -p "${APPDIR}/usr/lib/python/installer"
install -m 0644 "${SCRIPT_DIR}/install_engine.py" "${APPDIR}/usr/lib/python/installer/install_engine.py"
install -m 0644 "${SCRIPT_DIR}/wizard.py"         "${APPDIR}/usr/lib/python/installer/wizard.py"
touch "${APPDIR}/usr/lib/python/installer/__init__.py"

# ── Build the AppImage ──────────────────────────────────────────────────────
OUTPUT="${OUT_DIR}/${APP_NAME}-x86_64.AppImage"
echo "Building AppImage → ${OUTPUT}"

ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT}"
chmod +x "${OUTPUT}"

# ── Verify the built AppImage can be invoked ───────────────────────────────
echo ""
echo "Verifying AppImage smoke-run (--cli --dry-run)..."
APPIMAGE_EXTRACT_AND_RUN=1 "${OUTPUT}" --cli --dry-run
echo ""
echo "AppImage built and verified successfully:"
echo "  ${OUTPUT}"
echo ""
echo "To run (FUSE-less, for containers/CI):"
echo "  APPIMAGE_EXTRACT_AND_RUN=1 ./${APP_NAME}-x86_64.AppImage [--cli] [--dry-run]"
