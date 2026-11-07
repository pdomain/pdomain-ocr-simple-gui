---
Status: active
Owner: CT
Created: 2026-06-05
Last verified: 2026-11-07
Kind: runbook
---

# CUDA setup

## Agent Index

- **Kind:** runbook
- **Status:** active
- **Read when:** an NVIDIA GPU is detected but DocTR cannot use CUDA.
- **Search terms:** CUDA, NVIDIA, PyTorch, DocTR, GPU detection.

## Trigger

Use this runbook when the Settings → Compute panel lists an NVIDIA GPU as
unavailable, with a reason, instead of as a selectable CUDA device, or when
DocTR unexpectedly runs on CPU. The "CUDA setup" box below that panel gives a
short version of these steps.

An NVIDIA GPU can be detected even when CUDA is not usable by PyTorch. The
driver, CUDA-compatible PyTorch build, and runtime libraries must all be visible
inside the application environment.

## Preconditions

For a tool install, use the Settings → Compute panel because it reports the
devices seen by the running `pdomain-ocr-simple-gui` process. From a synced source
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
reinstall through the supported installer, `install.sh` (see
[installation](install.md)). It reads the CUDA version from `nvidia-smi`,
installs PyTorch from the matching `download.pytorch.org/whl/cu<NNN>` index,
and adds the `pdomain-book-tools[gpu]` extra only for CUDA 12.4 or newer. Do not
mix an unrelated system Python with the `uv tool` environment.

## Verification

Restart the app and confirm the Settings → Compute panel lists the CUDA device
as a selectable target, not as an unavailable NVIDIA entry. The command above
must print `True` and a positive device count.

## Rollback

OCR remains supported on CPU when CUDA cannot be configured safely. Select CPU
in the Settings → Compute panel; the choice persists. `install.sh` has no
option to force a CPU-only install; it picks its package set from what
`nvidia-smi` reports.
