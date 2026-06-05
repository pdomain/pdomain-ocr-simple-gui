# Linux Install Runbook — pdomain-ocr-simple-gui

This runbook covers installing `pdomain-ocr-simple-gui` on Linux,
enabling GPU acceleration, and rolling back a bad release.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Linux x86_64 | Ubuntu 22.04+, Fedora 39+, Arch, openSUSE, Alpine, or any modern distro |
| Python 3.11+ | Managed automatically by `uv`; no system Python required |
| `uv` | The Python toolchain manager — installed in Step 1 |
| WebKitGTK runtime | The native webview library — installed in Step 2 (see table below) |
| Internet access | For `uv tool install` to pull wheels from `pdomain-index-pip` |

**Hardware (CPU mode — no GPU required):**
All OCR engines run on CPU by default. Expect ~5–30 s per page depending on
engine and CPU speed. GPU acceleration is optional (Step 4).

## Quick install (one-liner)

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/install.sh | sh
```

The script: installs `uv` if absent, detects CUDA and enables GPU support
automatically, downloads the latest release wheel, and always installs the
`pdomain-ops[desktop]` extra so the native window works out of the box.
It also checks for WebKitGTK and prints per-distro install hints if absent.

### Confirmation gates

The installer prompts before auto-installing `uv` and before running
`uv tool install`. It reads responses from `/dev/tty` (not stdin), so
prompts work correctly under `curl ... | sh` in a real terminal.

In headless environments (CI, cron, Docker without `-t`), all gates
auto-proceed. To skip prompts explicitly:

```sh
# Flag form (works with curl-pipe):
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/install.sh | sh -s -- -y

# Environment variable form:
ASSUME_YES=1 curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/install.sh | sh
```

---

## Manual install (step by step)

Use these commands if you prefer not to run the curl-pipe installer, or want
to understand exactly what `install.sh` does. Every step is copy-pasteable.

### Step 1 — Install uv

`uv` manages Python and tool environments. Skip this step if `uv` is already
installed (`uv --version` succeeds).

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Add `uv` to your PATH (or add this line to `~/.bashrc` / `~/.zshrc`):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Verify: `uv --version`

**uv version requirement:** this project requires `uv >= 0.11.16`
(set in `pyproject.toml` as `[tool.uv] required-version`). The installer
above always installs the latest stable uv, so a fresh install satisfies
this. If you already have uv and it is older than 0.11.16, upgrade it:

```bash
uv self update
```

Or reinstall from scratch using the command above.

### Step 2 — Install WebKitGTK (desktop mode only)

`pywebview` (the native desktop window) requires the system WebKitGTK
library. Browser mode (`pdomain-ocr-simple-gui` without `--desktop`) works
without it.

If already installed, skip this step. See the per-distro package table
in the "Gated step sequence" section below for all distro names.

Example for Ubuntu / Debian:

```bash
sudo apt-get install -y gir1.2-webkit2-4.1
```

### Step 3 — Install the app

The command below mirrors what `install.sh` runs after downloading the wheel.
Replace `3.13` with your preferred Python version if needed.

**CPU build (default — works everywhere):**

```bash
uv tool install --python 3.13 pdomain-ocr-simple-gui \
  --extra-index-url https://pdomain.github.io/pdomain-index-pip/simple/ \
  --with "pdomain-ops[desktop]"
```

The `--with "pdomain-ops[desktop]"` flag pulls in `pywebview >= 5` and
`pystray >= 0.19` so the native `--desktop` window works out of the box.

**NVIDIA GPU build (CUDA >= 12.4 required):**

```bash
# Replace cuXXX with your CUDA version tag, e.g. cu124, cu126, cu128.
# Run `nvidia-smi` to find your CUDA version.
uv tool install --python 3.13 pdomain-ocr-simple-gui \
  --extra-index-url https://pdomain.github.io/pdomain-index-pip/simple/ \
  --with "pdomain-ops[desktop]" \
  --with "pdomain-book-tools[gpu]" \
  --extra-index-url "https://download.pytorch.org/whl/cuXXX"
```

The `pdomain-book-tools[gpu]` extra adds CuPy and OpenCV-CUDA support.
It requires CUDA >= 12.4 because it pulls `cupy-cuda12x`.

**Apple Silicon (MPS — auto-detected, no extra flags needed):**

```bash
uv tool install --python 3.13 pdomain-ocr-simple-gui \
  --extra-index-url https://pdomain.github.io/pdomain-index-pip/simple/ \
  --with "pdomain-ops[desktop]"
```

MPS acceleration is used automatically when PyTorch detects Apple Silicon.
No extra index URL is needed.

Verify: `pdomain-ocr-simple-gui --help`

### Step 4 — Register the desktop shortcut (optional)

```bash
pdomain-ocr-simple-gui --install-desktop-shortcut
```

This adds a `.desktop` entry and icon to your application menu so the app
appears in your desktop launcher.

### Step 5 — Launch the app

```bash
# Browser mode (default):
pdomain-ocr-simple-gui
# Then open http://localhost:8004 in your browser.

# Desktop mode (native window):
pdomain-ocr-simple-gui --desktop
```

If `pdomain-ocr-simple-gui` is not found, ensure `~/.local/bin` is on your
PATH (see Step 1 above).

---

## Installation: two paths

### Path A — Double-click AppImage (recommended for end-users)

1. Download `pdomain-ocr-simple-gui-installer-x86_64.AppImage` from the
   [GitHub Releases](https://github.com/pdomain/pdomain-ocr-simple-gui/releases) page.
2. Mark it executable and run it:

```bash
chmod +x pdomain-ocr-simple-gui-installer-x86_64.AppImage
./pdomain-ocr-simple-gui-installer-x86_64.AppImage
```

The GUI wizard walks you through Steps 1–5 below, showing the exact command
before running each step and asking for confirmation.

### Path B — Gated CLI (automation / advanced users)

Run the installer engine directly:

```bash
# Interactive (prompts Y/n for each step):
python3 -m installer.wizard --cli

# Non-interactive (yes to all):
python3 -m installer.wizard --cli --yes

# Dry-run (print plan only, no changes):
python3 -m installer.wizard --cli --dry-run
```

---

## Gated step sequence

### Step 1 — Ensure `uv`

`uv` installs and manages Python and tool environments.
If already installed, this step is skipped.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify: `uv --version`

---

### Step 2 — Ensure the WebKitGTK runtime

`pywebview` (the desktop shell) uses the system WebKitGTK library.
If already installed, this step is skipped.

**Per-distro package:**

| Distro / manager | Package name |
|------------------|-------------|
| Debian / Ubuntu (`apt`) | `gir1.2-webkit2-4.1` |
| Fedora 39+ (`dnf`) | `webkit2gtk4.1` |
| Older RHEL / CentOS (`yum`) | `webkit2gtk4.1` |
| Arch Linux (`pacman`) | `webkit2gtk` |
| openSUSE (`zypper`) | `typelib-1_0-WebKit2-4_1` |
| Alpine (`apk`) | `webkit2gtk` |
| Unknown distro | Install manually (see package name for your distro above) |

Example for Ubuntu/Debian:

```bash
sudo apt-get install -y gir1.2-webkit2-4.1
```

---

### Step 3 — `uv tool install`

Installs the app from the `pdomain-index-pip` registry.

```bash
uv tool install "pdomain-ocr-simple-gui[desktop]" \
  --extra-index-url https://pdomain.github.io/pdomain-index-pip/simple/
```

The `[desktop]` extra includes `pywebview` and `pystray`.
Omit it for a headless / server-only install:

```bash
uv tool install pdomain-ocr-simple-gui \
  --extra-index-url https://pdomain.github.io/pdomain-index-pip/simple/
```

Verify: `pdomain-ocr-simple-gui --help`

---

### Step 4 — Enable GPU acceleration (NVIDIA only, optional)

**Auto-detect + gated.** The installer detects an NVIDIA GPU via `nvidia-smi`
and offers to swap the CPU PyTorch wheels for the CUDA (`cu12x`) build.
No CUDA toolkit is needed — PyTorch's `cu12x` wheels bundle their own runtime.

```bash
uv tool run --from pdomain-ocr-simple-gui pip install \
  torch --index-url https://download.pytorch.org/whl/cu121
```

After swapping, the app's compute-target panel (Settings dock → Compute tab)
will show the CUDA device automatically.

#### Driver requirements

The `cu12x` build requires NVIDIA driver **≥ 525** (CUDA 12 ABI).
Check your driver version:

```bash
nvidia-smi --query-gpu=driver_version --format=csv,noheader
```

**If your driver is missing or too old**, the installer will print the
official driver download link but will NOT auto-install it (driver
installation is distro-specific and may require a reboot):

- Official: <https://www.nvidia.com/en-us/drivers/>
- Ubuntu/Debian: `ubuntu-drivers devices` then `sudo ubuntu-drivers install`
- Arch Linux: `pacman -S nvidia`
- Fedora: `dnf install akmod-nvidia`

After installing or updating the driver, re-run Step 4.

---

### Step 5 — Install desktop shortcut

Adds a `.desktop` entry and icon to your application menu.

```bash
pdomain-ocr-simple-gui --install-desktop-shortcut
```

To remove:

```bash
pdomain-ocr-simple-gui --remove-desktop-shortcut
```

---

## Launching the app

**Browser mode (default):**

```bash
pdomain-ocr-simple-gui
# Opens at http://localhost:8004
```

**Desktop mode (native window, requires `[desktop]` extra):**

```bash
pdomain-ocr-simple-gui --desktop
```

---

## Upgrade

```bash
uv tool upgrade pdomain-ocr-simple-gui
```

To upgrade to a specific version:

```bash
uv tool install "pdomain-ocr-simple-gui==0.2.3"
```

---

## Rollback

If a new release breaks something, roll back to the previous version:

```bash
uv tool install "pdomain-ocr-simple-gui==<old-version>"
```

For example, to roll back from `0.2.0` to `0.1.9`:

```bash
uv tool install "pdomain-ocr-simple-gui==0.1.9"
```

All user data (projects, outputs, preferences) is stored in
`~/.local/share/pdomain-ocr-simple-gui/` (or `PD_SUITE_DATA_DIR` if set)
and is unaffected by an upgrade or rollback.

After rollback, verify:

```bash
pdomain-ocr-simple-gui --version
```

---

## Uninstall

### One-liner (recommended)

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/uninstall.sh | sh
```

The script removes the desktop shortcut, unregisters from the suite registry,
and uninstalls the tool via `uv tool uninstall`. It offers to remove `uv`
itself, defaulting to yes only if this installer originally bootstrapped it.

Unattended (skip all prompts):

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/uninstall.sh | sh -s -- -y
```

### Manual uninstall (step by step)

Use these commands if you prefer not to run the curl-pipe uninstaller, or
want to understand exactly what `uninstall.sh` does.

#### Step 1 — Remove the desktop shortcut (best-effort)

```bash
pdomain-ocr-simple-gui --remove-desktop-shortcut 2>/dev/null || true
```

This removes the `.desktop` entry and icon from your application menu.
It is best-effort: if the binary is not on PATH, or if no shortcut was
installed, the command exits cleanly without error.

#### Step 2 — Unregister from the suite registry (best-effort)

```bash
pdomain-ocr-simple-gui --unregister-suite 2>/dev/null || true
```

This removes the `[apps.pdomain-ocr-simple-gui]` entry from the suite
registry at:

```text
~/.local/share/pd-suite/installed.toml
```

If the binary is not on PATH, edit `installed.toml` directly and delete
the `[apps.pdomain-ocr-simple-gui]` block.

#### Step 3 — Uninstall the tool

```bash
uv tool uninstall pdomain-ocr-simple-gui
```

This removes the `pdomain-ocr-simple-gui` binary and its isolated virtual
environment from `~/.local/share/uv/tools/pdomain-ocr-simple-gui/`.

#### Step 4 — Remove uv (optional)

Removing uv affects ALL uv-managed tools and Python environments on your
system. Leave it installed unless you are certain nothing else depends on it.

For standalone installs (the usual case — `astral.sh/uv/install.sh`):

```bash
uv self uninstall
```

If `uv self uninstall` is not available (uv was installed via a system
package manager), remove the binaries manually:

```bash
rm -f "$HOME/.local/bin/uv" "$HOME/.local/bin/uvx"
rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/uv"
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/uv"
```

Also remove the installer marker written by `install.sh` (if present):

```bash
rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/pdomain-ocr-simple-gui"
```

#### Step 5 — Remove WebKitGTK (optional)

WebKitGTK is a system library installed separately. Remove it with your
package manager only if nothing else on your system needs it.

| Distro | Remove command |
|--------|---------------|
| Debian / Ubuntu | `sudo apt-get remove gir1.2-webkit2-4.1` |
| Fedora | `sudo dnf remove webkit2gtk4.1` |
| Arch | `sudo pacman -Rs webkit2gtk` |
| openSUSE | `sudo zypper remove typelib-1_0-WebKit2-4_1` |
| Alpine | `sudo apk del webkit2gtk` |

#### Step 6 — Remove user data (optional)

User data is NOT removed by any of the above steps. To also wipe app data,
model weights, and cache:

```bash
# App data (projects, preferences)
rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/pdomain-ocr-simple-gui"

# OCR model weights
# DocTR and PyTorch/HuggingFace cache model weights under the platform cache
# directory. The exact paths depend on your environment; common locations:
rm -rf ~/.cache/doctr          # DocTR model weights
rm -rf ~/.cache/torch          # PyTorch/DocTR model cache
rm -rf ~/.cache/huggingface    # HuggingFace model cache (if used)
```

---

## Known limitations

### AppImage Python portability

The AppImage distributed via GitHub Releases is currently a **CI build
artifact**.  It bundles the system `python3` ELF binary from the build
runner, which is not portable across Linux distributions (glibc version and
shared library paths differ).  True cross-distro portability requires a
self-contained standalone Python (e.g.
[python-build-standalone](https://github.com/indygreg/python-build-standalone)),
which is deferred as future work.  If the AppImage fails to run on your
distro, use Path B (Gated CLI) instead.

### `.deb` package (Debian/Ubuntu)

The spec (§7.2) describes an optional `.deb` package for native APT
integration.  This is **deferred** and not included in v1.  Use Path A
(AppImage) or Path B (Gated CLI) in the meantime.

---

## Troubleshooting

### `pdomain-ocr-simple-gui: command not found`

`uv tool install` puts binaries in `~/.local/bin` (or `~/.cargo/bin` for some
`uv` builds).  Add it to your PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
# Add to ~/.bashrc or ~/.zshrc for persistence
```

### WebKitGTK version mismatch (`libwebkit2gtk-4.1.so.0: cannot open`)

The app needs the **4.1 API** series. If your distro only ships the 4.0 series,
install `libwebkitgtk-4.0-dev` as a fallback or upgrade your distro to a
release that includes webkit2gtk 4.1 (Ubuntu 22.04+ and Fedora 39+).

### CUDA: `RuntimeError: CUDA error: no kernel image is available`

Your GPU is older than the `cu121` build requires (roughly Kepler / Maxwell,
pre-2015). Use the CPU build (default) or find a compatible `cu118` wheel
and install manually.

### Port 8004 already in use

Set a different port:

```bash
pdomain-ocr-simple-gui --port 8005
```

Or set the environment variable:

```bash
PD_OCR_SIMPLE_GUI_PORT=8005 pdomain-ocr-simple-gui
```
