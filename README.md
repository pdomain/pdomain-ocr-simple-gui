---
Status: active
Owner: CT
Created: 2026-05-17
Last verified: 2026-11-14
Kind: usage
---

# pdomain-ocr-simple-gui

A minimal drag-and-drop OCR app — drop a folder of scanned images, run OCR,
get plain-text output. Built on FastAPI + React/Vite, using `pdomain-book-tools`
for OCR and `pdomain-ops` for suite plumbing. Serves as the Phase 3 reference
consumer that validates `pdomain-ops`' `LocalStageDispatcher`.

Contributors and coding agents must start with [AGENTS.md](AGENTS.md).

The app runs as a local web server and **opens your default browser automatically**
on launch. No native window or Qt library is required.

## Install

### Tier 1 — curl one-liner (easiest, Linux x86\_64)

Paste this into a terminal. When the latest release carries the AppImage, it
downloads it, marks it executable, and launches the installer wizard
automatically — no separate steps needed:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/install.sh | sh
```

The wizard walks you through the gated install steps (uv, `uv tool install`,
desktop shortcut).

On non-desktop systems (CI, headless servers, macOS, non-x86\_64), or when the
AppImage asset is unavailable, the script falls back to a uv-tool install
automatically. The latest release, v0.5.0, has no AppImage asset: the workflow
that built it was removed on 2026-09-13, so the one-liner currently takes the
uv-tool path.

To skip the AppImage wizard and use uv-tool directly:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/install.sh | sh -s -- --no-appimage
# or: NO_APPIMAGE=1 curl -sSL .../install.sh | sh
```

### Tier 2 — AppImage download (Linux x86\_64)

Download the `.AppImage` from the [Releases](https://github.com/pdomain/pdomain-ocr-simple-gui/releases) page.
Only releases v0.3.5 through v0.4.0 carry it; v0.5.0 does not.

Browsers download files without the executable bit set — this is standard Linux
behavior, not specific to this app. You must mark the file executable once before
it can run.

**Without a terminal (file manager):** right-click the `.AppImage` → Properties →
Permissions tab → check "Allow executing file as program" (wording varies by file
manager; in Nemo on Linux Mint it is exactly that) → then double-click it.

**Terminal equivalent:**

```sh
chmod +x pdomain-ocr-simple-gui-installer-x86_64.AppImage
./pdomain-ocr-simple-gui-installer-x86_64.AppImage
```

### Tier 3 — manual install via uv

Linux and macOS:

```sh
uv tool install pdomain-ocr-simple-gui --python 3.13 \
  --index-strategy first-index \
  --index pdomain=https://pdomain.github.io/pdomain-index-pip/simple/
```

Windows (PowerShell, no administrator rights needed):

```powershell
uv tool install pdomain-ocr-simple-gui --python 3.13 --index-strategy first-index --index pdomain=https://pdomain.github.io/pdomain-index-pip/simple/
```

To upgrade an existing install, run the same command with `--reinstall`.
Releases before 0.5.6 installed two copies of OpenCV, and `--reinstall`
replaces the whole tool environment, so no stale files are left behind.

On a Linux server or in a container, OCR and startup fail with
`libxcb.so.1: cannot open shared object file` until OpenCV's X11 and OpenGL
libraries are installed. Desktop Linux already has them. Install them once,
as root:

| Distribution | Command |
|---|---|
| Ubuntu 24.04+, Debian 13+ | `apt install libgl1 libsm6 libice6 libx11-6 libxext6 libxcb1 libglib2.0-0t64` |
| Older Ubuntu and Debian | `apt install libgl1 libsm6 libice6 libx11-6 libxext6 libxcb1 libglib2.0-0` |
| Fedora, AlmaLinux, RHEL | `dnf install mesa-libGL libSM libICE libX11 libXext libxcb glib2` |
| Arch | `pacman -S libglvnd mesa libsm libice libx11 libxext libxcb glib2` |
| openSUSE | `zypper in Mesa-libGL1 libSM6 libICE6 libX11-6 libXext6 libxcb1 libglib-2_0-0 libgthread-2_0-0` |

These lists were tested on 2026-11-14 in Ubuntu 24.04 and 22.04, Debian 13,
Fedora 45, AlmaLinux 9.8, Arch and openSUSE Tumbleweed containers.

On Windows, OCR also needs the Microsoft Visual C++ Redistributable (x64).
If it is missing, the home page says "DocTR cannot run on this computer".
An administrator installs it from <https://aka.ms/vc14/vc_redist.x64.exe>;
then restart the app.

The named `--index` keeps the pdomain packages from resolving from any other
index, including one set in the `UV_INDEX` environment variable.

On a computer with an NVIDIA GPU, add `--torch-backend auto`. uv then installs
the CUDA build of PyTorch that matches the driver. Do not add the PyTorch index
itself. It also holds old copies of common packages, and the install fails.

## Launch

```sh
pdomain-ocr-simple-gui
```

The app starts the local web server and opens `http://127.0.0.1:8004` in your
default browser automatically. If port 8004 is taken, it uses the next free
port and prints the URL. Drop a folder of images, pick an OCR engine,
and run. Output `.txt` files appear in the directory you choose.

To suppress the browser auto-open (headless servers, CI, docker):

```sh
pdomain-ocr-simple-gui --no-browser
# then open http://127.0.0.1:8004 (or the printed URL) in your browser
```

## Uninstall

One-liner:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/uninstall.sh | sh
```

The script removes the desktop shortcut (if installed), unregisters from the
suite registry, and uninstalls the tool via `uv tool uninstall`. It also offers
to remove `uv` itself, defaulting to yes only if this installer originally
bootstrapped it.

Unattended (skip all prompts):

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/uninstall.sh | sh -s -- -y
```

User data (`~/.local/share/pdomain-ocr-simple-gui/`) is not removed
automatically. OCR model weights (`~/.cache/doctr/`) are also left in place.
