from __future__ import annotations

from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs/runbooks/cuda-setup.md"


def test_cuda_setup_doc_exists_and_mentions_detection_without_cuda() -> None:
    text = DOC.read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())

    assert "CUDA setup" in text
    assert "nvidia-smi" in text
    assert "NVIDIA GPU can be detected even when CUDA is not usable" in text
    assert "pdomain-ocr-simple-gui" in text
    assert "PyTorch" in text
    assert "torch.cuda.is_available()" in text
    assert "torch.cuda.device_count()" in text
    assert "same Python environment that runs or launches `pdomain-ocr-simple-gui`" in normalized_text
