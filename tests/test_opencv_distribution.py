"""The environment holds exactly one OpenCV package."""

from __future__ import annotations

import importlib.metadata

OPENCV_DISTRIBUTIONS = frozenset(
    {
        "opencv-python",
        "opencv-contrib-python",
        "opencv-python-headless",
        "opencv-contrib-python-headless",
    }
)


def test_environment_has_one_opencv_distribution() -> None:
    """Exactly one OpenCV package provides ``cv2``.

    All four OpenCV packages write the same ``cv2/`` folder, and a second one
    leaves a mix of files that breaks ``import cv2``. python-doctr requires
    ``opencv-python``, and pdomain-book-tools 0.31.3 declares the same one.
    See pdomain-book-tools
    ``docs/decisions/2026-11-14-opencv-python-not-contrib.md``.
    """
    installed = {
        name.lower() for dist in importlib.metadata.distributions() if (name := dist.metadata["Name"])
    }
    assert installed & OPENCV_DISTRIBUTIONS == {"opencv-python"}
