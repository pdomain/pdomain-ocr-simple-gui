"""Deterministically render the Tier-B known-good OCR fixture page.

Run once to (re)generate ``known_good_page.png`` from the transcript in
``known_good_page.gt.txt``. The image is a clean, high-contrast black-on-white
rendering of a short paragraph of common English words — chosen so the real
DocTR engine transcribes it with high word overlap.

Usage::

    uv run python tests/e2e/fixtures/_make_known_good_page.py

The PNG is committed so the Tier-B test does not depend on this script at run
time; regenerate only when the transcript changes.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
GT_PATH = HERE / "known_good_page.gt.txt"
PNG_PATH = HERE / "known_good_page.png"

# The known transcript — one phrase per line. Plain ASCII, common words, no
# tricky punctuation, so the real OCR engine reproduces it faithfully.
LINES = [
    "The quick brown fox jumps",
    "over the lazy dog while",
    "the morning sun rises slowly",
    "above the quiet green hills.",
]

# Candidate fonts, in preference order. Liberation Serif renders cleanly and is
# OCR-friendly; fall back to DejaVu, then Pillow's bundled default.
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

FONT_SIZE = 40
MARGIN = 60
LINE_SPACING = 24


def _load_font() -> ImageFont.FreeTypeFont:
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, FONT_SIZE)
    # Last resort — Pillow's bundled bitmap font (small, but better than failing).
    return ImageFont.load_default()  # pyright: ignore[reportReturnType]


def render() -> None:
    """Write the transcript to disk and render the matching PNG."""
    transcript = "\n".join(LINES) + "\n"
    GT_PATH.write_text(transcript, encoding="utf-8")

    font = _load_font()

    # Measure each line to size the canvas with generous margins.
    measure_img = Image.new("RGB", (1, 1), "white")
    measure = ImageDraw.Draw(measure_img)
    widths: list[int] = []
    heights: list[int] = []
    for line in LINES:
        box = measure.textbbox((0, 0), line, font=font)
        widths.append(box[2] - box[0])
        heights.append(box[3] - box[1])

    line_height = max(heights) + LINE_SPACING
    width = max(widths) + 2 * MARGIN
    height = line_height * len(LINES) + 2 * MARGIN

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = MARGIN
    for line in LINES:
        draw.text((MARGIN, y), line, fill="black", font=font)
        y += line_height

    img.save(PNG_PATH, optimize=True)


if __name__ == "__main__":
    render()
    print(f"wrote {PNG_PATH} and {GT_PATH}")
