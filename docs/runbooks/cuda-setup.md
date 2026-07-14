---
Status: active
Owner: CT
Created: 2026-06-05
Last verified: 2026-07-14
Kind: runbook
---

# CUDA setup

## Agent Index

- **Kind:** runbook
- **Status:** active
- **Read when:** an NVIDIA GPU is detected but DocTR cannot use CUDA.
- **Search terms:** CUDA, NVIDIA, PyTorch, DocTR, GPU detection.

## Trigger

Use this runbook when the settings panel reports an NVIDIA GPU but CUDA is not
usable, or when DocTR unexpectedly runs on CPU.

An NVIDIA GPU can be detected even when CUDA is not usable by PyTorch. The
driver, CUDA-compatible PyTorch build, and runtime libraries must all be visible
inside the application environment.

## Preconditions

For a tool install, use the application's settings panel because it probes the
environment that launches `pdomain-ocr-simple-gui`. From a synced source
checkout, run the command below in that checkout's environment.
Hardware detection alone does not prove that the installed PyTorch build can
use CUDA.

## Steps

First run `nvidia-smi` and confirm the driver sees the GPU. Then inspect the
application environment:

```bash
uv run python -c \
  'import torch; print(torch.cuda.is_available(), torch.cuda.device_count())'
```

This source-checkout command uses the same Python environment that runs or
launches `pdomain-ocr-simple-gui` during development. If CUDA is unavailable,
reinstall through the supported installer path so its
CUDA compatibility checks can select the appropriate dependencies. Do not mix
an unrelated system Python with the `uv tool` environment.

## Verification

Restart the app and confirm the settings panel reports CUDA usable. The command
above must print `True` and a positive device count.

## Rollback

Reinstall the CPU-compatible package set through the standard installer. OCR
remains supported on CPU when CUDA cannot be configured safely.
