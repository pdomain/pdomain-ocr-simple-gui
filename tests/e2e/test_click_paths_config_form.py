"""5.9 — full click-path: config form → choose engine/language → submit.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Uploads a file, then interacts with the inline config form:
  - changes engine to "tesseract" via the engine-select dropdown
  - changes language to "fr" via the language-input field
  - clicks a Toggle label (straight-quotes) so at least one boolean option
    is exercised
  - submits the job

Asserts:
  - The results page appears (meaning the server accepted the non-default
    engine/language config — no 422).
  - At least one page-row populates (job ran and produced output).

The fake dispatcher ignores engine/language and always returns deterministic
output, so correctness of OCR output is not asserted here — only that the
front-end correctly transmits the chosen config to the backend.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect

# Minimal valid 1x1 greyscale PNG
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"
    b"\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.slow
@pytest.mark.e2e
def test_config_form_engine_language_choice_accepted(
    page: Page, live_server_url: str, tmp_path: Path
) -> None:
    """Change engine + language in the config form; job succeeds with chosen config."""
    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # 1. Pick a file to reveal the inline config form
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    # 2. Change engine from "doctr" (default) to "tesseract"
    engine_select = page.get_by_test_id("engine-select")
    expect(engine_select).to_be_visible()
    engine_select.select_option("tesseract")
    # Verify the select reflects the new value
    expect(engine_select).to_have_value("tesseract")

    # 3. Change language from "en" (default) to "fr"
    lang_input = page.get_by_test_id("language-input")
    expect(lang_input).to_be_visible()
    lang_input.fill("fr")
    expect(lang_input).to_have_value("fr")

    # 4. Toggle the "Convert curly quotes" label — click the label to flip the switch.
    #    We use the label text because the Toggle component (Radix Switch) does not
    #    forward data-testid to the DOM element.
    page.get_by_label("Convert curly quotes to straight").click()

    # 5. Submit the job
    page.get_by_test_id("run-ocr-button").click()

    # 6. Results page appears (server accepted the config — no 422)
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)

    # 7. At least one page-row populates
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="page-row"]').length > 0""",
        timeout=15_000,
    )
    expect(page.get_by_test_id("page-row").first).to_be_visible(timeout=5_000)
