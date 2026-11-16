# Pure CUDA-detection helpers for install.ps1.
# Dot-sourced by install.ps1 and by tests/test_install_ps1_cuda.py.
# Contains NO top-level side effects.

function Get-CudaVersion {
    if ($env:CUDA_VERSION) {
        return $env:CUDA_VERSION
    }

    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        return $null
    }

    try {
        $qStr = & nvidia-smi -q 2>$null | Out-String
        if ($qStr -match "CUDA (?:UMD )?Version\s*:\s*([0-9]+\.[0-9]+)") {
            return $Matches[1]
        }
    } catch {
    }

    try {
        $smiStr = & nvidia-smi 2>$null | Out-String
        if ($smiStr -match "CUDA (?:UMD )?Version:\s*([0-9]+\.[0-9]+)") {
            return $Matches[1]
        }
    } catch {
    }

    return $null
}
