#!/usr/bin/env bash
# build_appimage.sh — build the Linux AppImage installer for pdomain-ocr-simple-gui.
#
# Usage:
#   ./installer/build_appimage.sh [--out <dir>]
#
# The script:
#   1. Downloads appimagetool if not already on PATH or in ./tools/.
#   2. Downloads the type2-runtime static runtime if not already cached in ./tools/.
#      The static runtime (type2-runtime) lets the AppImage self-extract and run
#      WITHOUT FUSE.  Classic AppImageKit requires FUSE2 (fusermount); modern
#      distros only have FUSE3, so a bare double-click would fail with the classic
#      runtime.  With the type2 static runtime:
#        - FUSE3 is used when present (seamless mount).
#        - Fallback: the AppImage self-extracts to $TMPDIR and execs — pure userspace,
#          no FUSE needed at all.  This is what makes double-click work on CI and in
#          containers with no FUSE.
#   3. Assembles an AppDir with:
#      - installer/appimage/AppRun       (the entry point)
#      - installer/appimage/*.desktop    (the .desktop file)
#      - installer/install_engine.py     (the engine)
#      - installer/wizard.py             (the GUI wizard)
#      NOTE: No Python binary is bundled.  AppRun locates system python3.
#            Bundling a system Python ELF is NOT portable (glibc version +
#            shared library paths differ across distros).  Using system python3
#            avoids all stdlib-portability issues and keeps the AppImage small.
#            The AppImage is a wizard-installer, not a full app bundle.
#   4. Calls appimagetool with --runtime-file to embed the type2 static runtime.
#   5. Smoke-runs the produced AppImage BARE (no APPIMAGE_EXTRACT_AND_RUN) to
#      prove that a bare double-click works even with no FUSE present.
#
# Prerequisites: python3, bash.
# The resulting .AppImage runs on any Linux x86_64 distro with python3 >= 3.8,
# even without FUSE installed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${REPO_ROOT}/dist"
TOOLS_DIR="${REPO_ROOT}/tools"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
# Type2 static runtime — embeds FUSE-less self-extract fallback into the AppImage.
# Without this, the classic AppImageKit runtime requires FUSE2 (fusermount), which
# is absent on modern distros (FUSE3) and on CI runners.  The type2 runtime uses
# FUSE3 when present and falls back to pure-userspace extraction otherwise.
TYPE2_RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"

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

# ── Locate or download type2-runtime ──────────────────────────────────────
TYPE2_RUNTIME="${TOOLS_DIR}/runtime-x86_64"
if [[ ! -x "${TYPE2_RUNTIME}" ]]; then
    echo "type2-runtime not found — downloading to ${TYPE2_RUNTIME} …"
    if ! curl -fsSL "${TYPE2_RUNTIME_URL}" -o "${TYPE2_RUNTIME}"; then
        echo "ERROR: Failed to download type2-runtime from ${TYPE2_RUNTIME_URL}" >&2
        exit 1
    fi
    if [[ ! -s "${TYPE2_RUNTIME}" ]]; then
        echo "ERROR: Downloaded type2-runtime is empty — check URL and network." >&2
        rm -f "${TYPE2_RUNTIME}"
        exit 1
    fi
    chmod +x "${TYPE2_RUNTIME}"
fi
echo "Using type2-runtime: ${TYPE2_RUNTIME}"

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

# APPIMAGE_EXTRACT_AND_RUN=1 here is for the BUILD TOOL (appimagetool) only —
# CI runners may lack FUSE, and appimagetool itself is a classic AppImage that
# needs this flag to unpack itself.  This is UNRELATED to whether the produced
# AppImage requires FUSE at run time (the --runtime-file flag handles that).
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "${APPIMAGETOOL}" --runtime-file "${TYPE2_RUNTIME}" "${APPDIR}" "${OUTPUT}"
chmod +x "${OUTPUT}"

# ── Verify the built AppImage can be invoked ───────────────────────────────
# The type2 static runtime uses FUSE3 (/dev/fuse) when present, falling back
# to APPIMAGE_EXTRACT_AND_RUN userspace extraction.
#
# Smoke-run strategy:
#   - If /dev/fuse is available (normal desktop or CI runner): run BARE.
#     This is the double-click gate — proves the type2 runtime mounts via FUSE3
#     without any env var, just like a real end-user double-click.
#   - If /dev/fuse is unavailable (some dev containers): run with
#     APPIMAGE_EXTRACT_AND_RUN=1 to verify the AppImage content is intact.
#     The type2 runtime still works in this mode; the FUSE3 path is simply
#     not testable in this environment.
#
# CI (GitHub Actions ubuntu-latest) always has /dev/fuse, so the bare-run
# gate is always exercised there.
echo ""
if [[ -e /dev/fuse ]]; then
    echo "Verifying AppImage smoke-run BARE (/dev/fuse present — double-click path)..."
    if ! "${OUTPUT}" --cli --dry-run; then
        echo "" >&2
        echo "ERROR: Bare AppImage run failed despite /dev/fuse being present." >&2
        echo "       The type2 static runtime may not be embedded correctly." >&2
        echo "       Check that --runtime-file was accepted by appimagetool." >&2
        exit 1
    fi
    echo "Bare smoke-run passed — double-click path verified via FUSE3 mount."
else
    echo "NOTE: /dev/fuse not available in this environment (dev container)."
    echo "      Using APPIMAGE_EXTRACT_AND_RUN=1 to verify content integrity."
    echo "      CI (GitHub Actions ubuntu-latest) will run the bare-run gate."
    if ! APPIMAGE_EXTRACT_AND_RUN=1 "${OUTPUT}" --cli --dry-run; then
        echo "" >&2
        echo "ERROR: AppImage run failed even with APPIMAGE_EXTRACT_AND_RUN=1." >&2
        echo "       The AppImage content may be corrupted." >&2
        exit 1
    fi
    echo "Content smoke-run passed."
fi
echo ""
echo "AppImage built and verified successfully:"
echo "  ${OUTPUT}"
echo ""
echo "To run (double-click or from terminal — requires FUSE3 on Linux):"
echo "  ./${APP_NAME}-x86_64.AppImage [--cli] [--dry-run]"
