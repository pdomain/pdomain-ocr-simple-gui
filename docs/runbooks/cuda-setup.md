# CUDA setup

This guide explains how to make `pdomain-ocr-simple-gui` use an NVIDIA GPU for
DocTR OCR.

## What the app detects

The settings panel separates two facts:

- An NVIDIA GPU can be detected even when CUDA is not usable by PyTorch.
- CUDA is usable only when the NVIDIA driver, CUDA-compatible PyTorch build,
  and runtime libraries are visible to the Python environment running
  `pdomain-ocr-simple-gui`.

If the app says an NVIDIA GPU was detected but CUDA is not usable, the hardware
is present but OCR will run on CPU until the runtime setup is fixed.

## Check the NVIDIA driver

Run:

```bash
nvidia-smi
```

Expected: the command prints your GPU model and driver version. If the command
is missing or fails, install or update the NVIDIA driver for your operating
system before changing Python packages.

## Check PyTorch CUDA visibility

Run this check in the same Python environment that runs or launches
`pdomain-ocr-simple-gui`:

```bash
python - <<'PY'
import torch

print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
print("device count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("device 0:", torch.cuda.get_device_name(0))
PY
```

Expected for GPU OCR:

```text
cuda available: True
device count: 1
```

If `nvidia-smi` works but `torch.cuda.is_available()` is `False`, install a
CUDA-enabled PyTorch build that matches your platform. Use PyTorch's selector
for the exact command:

[PyTorch Get Started](https://pytorch.org/get-started/locally/)

## Recheck the app

Restart `pdomain-ocr-simple-gui` after changing drivers or Python packages.
Open Settings, then Compute. A usable CUDA device appears as a selectable GPU
target. If only CPU is selectable, OCR will still run correctly, just slower.
