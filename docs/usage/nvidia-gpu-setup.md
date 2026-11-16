---
Status: active
Owner: CT
Created: 2026-11-15
Last verified: 2026-11-15
Kind: usage
---

# Get GPU reading after the NVIDIA driver is installed

Go to [Run the installer again](#run-the-installer-again) when `nvidia-smi` already lists your GPU and a CUDA version. That is the setup after the driver is installed.

You do not have to uninstall first.

`nvidia-smi` is the command that lists your graphics card. The graphics card is the GPU. CUDA Version is a label on that screen.

The OCR installers do not install the NVIDIA driver.

When `nvidia-smi` cannot report a CUDA version, the installers install a CPU copy of PyTorch. PyTorch is that package. OCR still reads pages on the CPU, the computer's main processor.

A later install downloads the CUDA build of PyTorch in either of these cases:

- A Linux or Windows script can read a CUDA version.
- The desktop wizard sees driver 525 or newer.

The download is roughly 2–3 GB.

OCR Simple GUI and command-line OCR use the CUDA libraries inside that package. OCR does not need a separate CUDA toolkit download.

## Agent Index

- **Kind:** usage
- **Status:** active
- **Read when:** the installer found no NVIDIA driver, or GPU reading stays on the CPU.
- **Search terms:** NVIDIA driver, CUDA, nvidia-smi, GPU setup, PyTorch.

## Macs have no NVIDIA driver step

Do not install an NVIDIA driver. Return to the installer and continue.

Apple Silicon Macs keep their own GPU path.

Intel Macs stay on the CPU.

## Run the installer again

Do this when `nvidia-smi` shows a CUDA version.

You do not have to uninstall first.

1. Open a terminal. On Windows, open PowerShell.
2. Run `nvidia-smi`.

The top line has two labels. Read both.

CUDA Version is a number such as 12.4 or 13.0. Driver Version is a number such as 550.54.

If the top line has no CUDA Version, do not start the installer. Go to [Check whether a driver is already installed](#check-whether-a-driver-is-already-installed).

If you use the desktop wizard and Driver Version is below 525, do not click Install. Go to [Install driver 525 or newer](#install-driver-525-or-newer).

The Linux and Windows install scripts still download the CUDA build of PyTorch when `nvidia-smi` prints any CUDA version. That includes a Driver Version below 525.

The desktop wizard skips that download when Driver Version is below 525.

When a CUDA Version is shown, run the commands below. For the desktop wizard, wait until Driver Version is 525 or newer.

OCR Simple GUI: open the installer and click Install.

On Linux and macOS you can also run `install.sh`.

On Windows, run `install.ps1` in PowerShell only when that file is already on the computer. If it is not, click Install.

Command-line OCR on Linux and macOS:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-cli/master/install.sh | sh
```

Command-line OCR on Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/pdomain/pdomain-ocr-cli/master/install.ps1 | iex
```

`Detected CUDA` means the download is the CUDA build. That line can appear before the download finishes.

Do not open the app yet.

Wait until the installer prints `Done!`.

If it prints `Done, but Windows must restart before OCR can run`, restart Windows before you open the app.

The installer does not restart Windows itself.

On the Linux install window, wait until **Close** is available.

On macOS, wait for the window that says the installation is complete, then click **OK**.

The install stayed on the CPU when the installer prints `falling back to CPU`, `CPU-only`, or `GPU acceleration step will be skipped`.

The installer reads the CUDA version from `nvidia-smi`. It passes `--torch-backend auto` to uv. uv is the tool that then downloads the matching CUDA build of PyTorch.

The download is roughly 2–3 GB.

Either button opens this page. On Linux and Windows the install window button is **GPU setup guide**. On macOS the button is **GPU guide**.

If OCR Simple GUI is already open, click **Quit app** in the top bar. If **Quit all tabs** appears, click that too. Then wait until the page says `App stopped. Open the app icon to start again.`

Then open OCR Simple GUI from your applications menu on Linux, or from the Start menu on Windows.

1. Drop in a folder of page images.
2. Open Settings, then Compute.

GPU reading is available when that panel lists the CUDA device as a choice.

GPU reading stayed on the CPU when the panel lists the NVIDIA GPU as unavailable.

For the command-line app, run `pdomain-ocr` on one image. It prints `NVIDIA GPU detected but PyTorch is the CPU build` when the install stayed on the CPU.

If `nvidia-smi` shows a CUDA Version but the PowerShell installer still cannot read it, set the version in that same PowerShell window.

Replace `13.0` with the CUDA Version on the `nvidia-smi` top line. Then run that app's install command again in the same window.

Command-line OCR:

```powershell
$env:CUDA_VERSION = "13.0"
irm https://raw.githubusercontent.com/pdomain/pdomain-ocr-cli/master/install.ps1 | iex
```

OCR Simple GUI: set `$env:CUDA_VERSION` the same way, then run `install.ps1` again in that window.

Do not use the command-line command above for the GUI.

The Windows Setup window and `install.sh` ignore `CUDA_VERSION`. They only parse `nvidia-smi`.

A value you set in one PowerShell window is not visible to Setup.

## Check whether a driver is already installed

Open a terminal and run `nvidia-smi`.

If the command is missing, or it does not list a GPU, install a driver in the next section.

If it lists the GPU but the top line has no CUDA Version, the driver is not ready. Install a driver in the next section. Do not start the OCR installer.

If it lists the GPU and a CUDA Version, use [Run the installer again](#run-the-installer-again).

## Install driver 525 or newer

Download a current driver from <https://www.nvidia.com/en-us/drivers/>.

Version 525 is the oldest driver the desktop wizard accepts for a GPU install.

On Linux you can use the distribution package instead of the download from the NVIDIA page. The terminal asks for your password and does not show what you type.

- Ubuntu or Debian: run `ubuntu-drivers devices`, then `sudo ubuntu-drivers install`.
- Arch Linux: run `sudo pacman -S nvidia`.
- Fedora: run `sudo dnf install akmod-nvidia`.

On Windows, run the installer from the NVIDIA page. Windows may ask for an administrator password.

1. Reboot when the driver installer tells you to.
2. Open a new terminal and run `nvidia-smi` again.

If the top line lists the GPU and a CUDA Version, go to [Run the installer again](#run-the-installer-again).

When Driver Version is below 525, the install scripts can still download the CUDA build. The desktop wizard cannot.

For the wizard, upgrade the driver first.

If the new terminal still shows no GPU, or no CUDA Version, stop. Do not run the OCR installer. OCR stays on the CPU.

## When the install stays on the CPU

Any one of these leads to the CPU build:

- A missing driver
- A driver older than 525 in the desktop wizard
- A CUDA version the installer cannot read

You do not have to uninstall the app first.

If the driver was missing, install it, then use [Run the installer again](#run-the-installer-again).

If the desktop wizard skipped the download because Driver Version is below 525, upgrade the driver, then use [Run the installer again](#run-the-installer-again).

If `nvidia-smi` already shows a CUDA Version and the PowerShell installer still used the CPU build, set `$env:CUDA_VERSION` in that same window.

Then run that app's install command again there.
