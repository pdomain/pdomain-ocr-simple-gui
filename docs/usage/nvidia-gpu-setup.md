---
Status: active
Owner: CT
Created: 2026-11-15
Last verified: 2026-11-15
Kind: usage
---

# Install an NVIDIA driver for GPU reading

If `nvidia-smi` already lists your GPU, go to [Run the installer again](#run-the-installer-again). That is the setup after the driver is installed.

The OCR installers do not install the NVIDIA driver.

When `nvidia-smi` cannot report a CUDA version, they install a CPU copy of PyTorch. OCR still reads pages on the CPU.

A later install with a working driver downloads the CUDA build of PyTorch, roughly 2–3 GB. These apps use the CUDA libraries inside that package. OCR does not need a separate CUDA toolkit download.

## Agent Index

- **Kind:** usage
- **Status:** active
- **Read when:** the installer found no NVIDIA driver, or GPU reading stays on the CPU.
- **Search terms:** NVIDIA driver, CUDA, nvidia-smi, GPU setup, PyTorch.

## Macs have no NVIDIA driver step

On a Mac, stop here.

Apple Silicon Macs do not use an NVIDIA driver. The installer keeps that Mac on its own GPU path.

Intel Macs stay on the CPU.

Neither Mac has an NVIDIA driver step.

## Run the installer again

Do this when `nvidia-smi` lists the GPU and its top line shows a CUDA version. You do not have to uninstall first.

Read the driver version on that screen before you start.

When the version is below 525, upgrade the driver before you use the desktop wizard. The Linux and Windows install scripts still download the CUDA build of PyTorch when `nvidia-smi` prints any CUDA version. The desktop wizard skips that download below 525.

When the driver is 525 or newer, run the installer again.

OCR Simple GUI: open the installer and click Install.

On Linux and macOS you can also run `install.sh`. On Windows, run `install.ps1`.

Command-line OCR on Linux and macOS:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-cli/master/install.sh | sh
```

Command-line OCR on Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/pdomain/pdomain-ocr-cli/master/install.ps1 | iex
```

The installer reads the CUDA version from `nvidia-smi` and passes `--torch-backend auto` to uv. uv then downloads the matching CUDA build of PyTorch. The download is roughly 2–3 GB.

The download is the CUDA build when the installer prints `Detected CUDA`.

It stayed on the CPU when the installer prints `falling back to CPU`, `CPU-only`, or `GPU acceleration step will be skipped`.

On Linux and Windows the install window button is **GPU setup guide**. On macOS the button is **GPU guide**. Either button opens this page.

After OCR Simple GUI is installed, open it and drop in a folder of page images. Then open Settings, then Compute. GPU reading is available when that panel lists the CUDA device as a choice. It stayed on the CPU when the panel lists the NVIDIA GPU as unavailable.

For the command-line app, run `pdomain-ocr` on one image. It prints `NVIDIA GPU detected but PyTorch is the CPU build` when the install stayed on the CPU.

If `nvidia-smi` works but the PowerShell installer still cannot read a CUDA version, set the version in that same window. Then run the installer there. Replace `13.0` with the CUDA version `nvidia-smi` shows.

```powershell
$env:CUDA_VERSION = "13.0"
```

`install.sh` and the desktop wizard do not read `CUDA_VERSION`. They only parse `nvidia-smi`. The Windows Setup window does not see a value you set in a different PowerShell window.

## Check whether a driver is already installed

Open a terminal and run `nvidia-smi`.

If the command is missing, or it does not list a GPU, install a driver in the next section.

If it lists the GPU and a CUDA version, use [Run the installer again](#run-the-installer-again).

## Install driver 525 or newer

Download a current driver from <https://www.nvidia.com/en-us/drivers/>.

Version 525 is the oldest driver the desktop wizard accepts for a GPU install.

On Linux you can use the distribution package instead:

1. Ubuntu or Debian: run `ubuntu-drivers devices`, then `sudo ubuntu-drivers install`.
2. Arch Linux: run `sudo pacman -S nvidia`.
3. Fedora: run `sudo dnf install akmod-nvidia`.

On Windows, run the installer from the NVIDIA page. Windows may ask for an administrator password.

Reboot when the driver installer tells you to. Open a new terminal and run `nvidia-smi` again.

Stop if it still does not list the GPU and a CUDA version. Finish the driver install before you run the OCR installer again.

The install scripts download the CUDA build of PyTorch whenever `nvidia-smi` prints a CUDA version. The desktop wizard also skips that download when the driver version is below 525.

## When the install stays on the CPU

Any one of these leads to the CPU build:

- A missing driver
- A driver older than 525 in the desktop wizard
- A CUDA version the installer cannot read

Re-run the installer after `nvidia-smi` shows a CUDA version. For the desktop wizard, the driver also has to be 525 or newer. You do not have to uninstall the app first.
