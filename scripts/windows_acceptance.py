"""Manual acceptance run for the installed pdomain-ocr-simple-gui, meant for Windows.

Run it with ``uv run --no-project --with playwright python scripts\\windows_acceptance.py``.
It tests the installed tool and never imports the app package.
"""

from __future__ import annotations

import argparse
import http.client
import io
import json
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypeAlias, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

    from playwright.sync_api import Page

DEFAULT_FIXTURES: Final = Path(__file__).resolve().parent.parent / "tests" / "e2e" / "fixtures"
DEFAULT_OUT_DIR: Final = Path("windows-acceptance-out")
DEFAULT_CHANNEL: Final = "msedge"
PREFERRED_STEM: Final = "known_good_page"
EDIT_MARKER: Final = "WINDOWS ACCEPTANCE EDIT 7Q"
MIN_OVERLAP: Final = 0.6
TERMINAL_JOB_STATES: Final = frozenset({"succeeded", "failed", "cancelled"})

SERVER_START_TIMEOUT_S: Final = 240.0
API_CONFIG_TIMEOUT_S: Final = 600.0
FIRST_PASS_TIMEOUT_S: Final = 1200.0
RERUN_TIMEOUT_MS: Final = 900_000
UI_TIMEOUT_MS: Final = 30_000
OCR_TEXT_TIMEOUT_MS: Final = 120_000

JOB_URL_RE: Final = re.compile(r"/jobs/([^/?#]+)")

Scalar: TypeAlias = str | int | float | bool | None


class AcceptanceError(Exception):
    """A required check failed."""


@dataclass(frozen=True)
class Fixture:
    """A page image and its ground-truth text."""

    image: Path
    truth: Path

    @property
    def stem(self) -> str:
        return self.image.stem


@dataclass(frozen=True)
class ZipTexts:
    """Text and JSON members of an export ZIP, with CRLF normalised to LF."""

    files: dict[str, str]
    crlf_names: tuple[str, ...]


@dataclass(frozen=True)
class HttpResult:
    """A finished HTTP response."""

    status: int
    content_type: str
    body: bytes


@dataclass
class Recorder:
    """Collects steps and checks, and writes them as the results JSON."""

    started: float = field(default_factory=time.monotonic)
    steps: list[dict[str, Scalar]] = field(default_factory=list)
    checks: list[dict[str, Scalar]] = field(default_factory=list)

    def step(self, name: str, **info: Scalar) -> None:
        entry: dict[str, Scalar] = {"step": name, "t": round(time.monotonic() - self.started, 1), **info}
        self.steps.append(entry)
        print("STEP", json.dumps(entry), flush=True)

    def check(self, name: str, passed: bool, failure: str = "") -> None:
        detail = "" if passed else failure
        self.checks.append({"check": name, "passed": passed, "detail": detail})
        print("PASS" if passed else "FAIL", name, detail, flush=True)

    def require(self, name: str, passed: bool, failure: str = "") -> None:
        self.check(name, passed, failure)
        if not passed:
            raise AcceptanceError(f"{name}: {failure}")

    def skip(self, name: str, reason: str) -> None:
        self.checks.append({"check": name, "passed": True, "skipped": True, "detail": reason})
        print("SKIP", name, reason, flush=True)

    @property
    def all_passed(self) -> bool:
        return bool(self.checks) and all(c["passed"] for c in self.checks)


def words(text: str) -> set[str]:
    """Lowercase words of *text* with surrounding punctuation stripped."""
    return {w.strip(".,;:!?\"'") for w in text.lower().split()} - {""}


def word_overlap(produced: str, truth_text: str) -> float:
    """Share of the ground-truth words that appear in *produced*."""
    truth = words(truth_text)
    return len(truth & words(produced)) / max(1, len(truth))


def normalise_newlines(text: str) -> str:
    """Turn CRLF into LF; Windows writes CRLF when the app saves text files."""
    return text.replace("\r\n", "\n")


def zip_text_files(data: bytes) -> ZipTexts:
    """Read the ``.txt`` and ``.json`` members of a ZIP, normalising CRLF."""
    files: dict[str, str] = {}
    crlf: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if not name.endswith((".txt", ".json")):
                continue
            raw = archive.read(name).decode("utf-8")
            if "\r\n" in raw:
                crlf.append(name)
            files[name] = normalise_newlines(raw)
    return ZipTexts(files=files, crlf_names=tuple(crlf))


def job_id_from_url(url: str) -> str | None:
    """Return the job id in a ``/jobs/<id>`` page URL, or None."""
    match = JOB_URL_RE.search(url)
    return match.group(1) if match else None


def resolve_fixtures(path: Path) -> Fixture:
    """Find a PNG and its ``.gt.txt`` from a directory, an image, or a truth file."""
    if path.is_dir():
        preferred = path / f"{PREFERRED_STEM}.png"
        image = preferred if preferred.is_file() else next(iter(sorted(path.glob("*.png"))), None)
        if image is None:
            raise AcceptanceError(f"no .png fixture in {path}")
    elif path.name.endswith(".gt.txt"):
        image = path.with_name(path.name.removesuffix(".gt.txt") + ".png")
    else:
        image = path
    truth = image.with_name(f"{image.stem}.gt.txt")
    for needed in (image, truth):
        if not needed.is_file():
            raise AcceptanceError(f"fixture file missing: {needed}")
    return Fixture(image=image, truth=truth)


def free_port() -> int:
    """Ask the OS for an unused local TCP port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        _host, port = cast("tuple[str, int]", sock.getsockname())
    return port


def http_get(port: int, path: str, timeout: float) -> HttpResult:
    """GET *path* from the local server."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        return HttpResult(response.status, response.getheader("content-type") or "", response.read())
    finally:
        conn.close()


def json_object(body: bytes) -> dict[str, object]:
    """Parse *body* as a JSON object."""
    value = cast("object", json.loads(body))
    if not isinstance(value, dict):
        raise AcceptanceError("expected a JSON object")
    return {str(k): v for k, v in cast("dict[object, object]", value).items()}


def wait_for_server(server: subprocess.Popen[bytes], port: int) -> None:
    """Block until the server answers on *port*, or raise."""
    deadline = time.monotonic() + SERVER_START_TIMEOUT_S
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise AcceptanceError(f"server exited with code {server.returncode}")
        try:
            _ = http_get(port, "/", timeout=2)
        except OSError:
            time.sleep(1)
        else:
            return
    raise AcceptanceError("server never answered")


def wait_for_job(port: int, job_id: str) -> dict[str, object]:
    """Poll the job until it reaches a terminal state or the limit passes."""
    deadline = time.monotonic() + FIRST_PASS_TIMEOUT_S
    body: dict[str, object] = {}
    while time.monotonic() < deadline:
        body = json_object(http_get(port, f"/api/jobs/{job_id}", timeout=30).body)
        if body.get("state") in TERMINAL_JOB_STATES:
            break
        time.sleep(2)
    return body


def probe_server(rec: Recorder, port: int) -> None:
    """Time /api/config twice and check the prefs and unknown-path routes."""
    started = time.monotonic()
    config = json_object(http_get(port, "/api/config", API_CONFIG_TIMEOUT_S).body)
    engines = config.get("ocr_engines")
    names = (
        ",".join(str(e.get("name", e.get("id", "?"))) for e in engines if isinstance(e, dict))  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportUnknownArgumentType]
        if isinstance(engines, list)
        else ""
    )
    rec.step(
        "api-config",
        seconds=round(time.monotonic() - started, 1),
        device=str(config.get("detected_device")),
        engines=names,
    )
    started = time.monotonic()
    _ = http_get(port, "/api/config", API_CONFIG_TIMEOUT_S)
    rec.step("api-config-again", seconds=round(time.monotonic() - started, 1))
    prefs = http_get(port, "/api/suite/prefs", 30)
    rec.check("suite-prefs-route", prefs.status == 200, f"status {prefs.status} {prefs.content_type}")
    unknown = http_get(port, "/api/does-not-exist", 30)
    rec.check(
        "unknown-api-path-is-404", unknown.status == 404, f"status {unknown.status} {unknown.content_type}"
    )


def download_zip(page: Page, test_id: str) -> ZipTexts:
    """Click the download button *test_id* and read the ZIP it delivers."""
    with page.expect_download(timeout=60_000) as info:
        page.get_by_test_id(test_id).click()
    return zip_text_files(Path(info.value.path()).read_bytes())


def page_json(texts: ZipTexts, stem: str) -> dict[str, object]:
    """The per-page JSON member of an export."""
    return json_object(texts.files[f"{stem}.json"].encode("utf-8"))


def engine_payload(data: dict[str, object]) -> dict[str, object]:
    """Page JSON without the user's edit, so only the engine output remains."""
    return {k: v for k, v in data.items() if k != "edited_text"}


def edited_text_of(data: dict[str, object]) -> str:
    """The ``edited_text`` field of the page JSON, newlines normalised."""
    value = data.get("edited_text")
    return normalise_newlines(value) if isinstance(value, str) else ""


def drive_browser(rec: Recorder, args: AcceptanceArgs, fixture: Fixture, port: int) -> None:
    """Upload, OCR, edit, save, export, rerun with DocTR, export again."""
    from playwright.sync_api import expect, sync_playwright

    out_dir = args.out_dir
    stem = fixture.stem
    truth_text = fixture.truth.read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        channel = None if args.browser_channel == "chromium" else args.browser_channel
        browser = playwright.chromium.launch(
            channel=channel, headless=args.headless, slow_mo=0 if args.headless else 100
        )
        try:
            page = browser.new_page(accept_downloads=True)
            _ = page.goto(f"http://127.0.0.1:{port}")
            expect(page.get_by_test_id("home-page")).to_be_visible(timeout=OCR_TEXT_TIMEOUT_MS)
            page.get_by_test_id("source-picker-file-pick").set_input_files(str(fixture.image))
            expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=UI_TIMEOUT_MS)
            page.get_by_test_id("run-ocr-button").click()
            expect(page.get_by_test_id("results-page")).to_be_visible(timeout=UI_TIMEOUT_MS)

            job_id = job_id_from_url(page.url)
            rec.require("job-id-in-url", job_id is not None, page.url)
            if job_id is None:
                return
            job = wait_for_job(port, job_id)
            rec.step("first-pass", state=str(job.get("state")), error=str(job.get("error")))
            rec.require("first-pass-succeeded", job.get("state") == "succeeded", str(job.get("error")))

            page.get_by_test_id("page-row").first.click()
            expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=UI_TIMEOUT_MS)
            _ = page.wait_for_function(
                """() => { const el = document.querySelector('textarea[aria-label="OCR text"]');
                return el instanceof HTMLTextAreaElement && el.value.trim().length > 0; }""",
                timeout=OCR_TEXT_TIMEOUT_MS,
            )
            text = page.get_by_label("OCR text").input_value()
            overlap = word_overlap(text, truth_text)
            rec.step("ocr-text", overlap=round(overlap, 3), chars=len(text))
            if args.skip_text_quality:
                rec.skip("ocr-text-overlap", "--skip-text-quality")
            else:
                rec.require(
                    "ocr-text-overlap",
                    overlap >= MIN_OVERLAP,
                    f"overlap {overlap:.3f}, need {MIN_OVERLAP}: {text!r}",
                )

            edited = f"{text.rstrip()}\n{EDIT_MARKER}"
            page.get_by_label("OCR text").fill(edited)
            page.get_by_test_id("page-save-button").click()
            expect(page.get_by_text("Saved", exact=True).first).to_be_visible(timeout=UI_TIMEOUT_MS)

            after_edit = download_zip(page, "download-images-text-json")
            _ = (out_dir / "zip-after-edit.json").write_text(
                json.dumps(after_edit.files, indent=1), encoding="utf-8"
            )
            edit_data = page_json(after_edit, stem)
            rec.step(
                "zip-after-edit",
                files=",".join(sorted(after_edit.files)),
                crlf=",".join(after_edit.crlf_names),
            )
            rec.require(
                "zip-page-text-has-edit",
                after_edit.files.get(f"{stem}.txt") == edited,
                f"{stem}.txt differs from the saved edit",
            )
            rec.require("zip-page-json-has-edit", edited_text_of(edit_data) == edited, "edited_text differs")
            rec.require(
                "zip-combined-text-has-edit",
                any(n != f"{stem}.txt" and EDIT_MARKER in body for n, body in after_edit.files.items()),
                "no other ZIP member carries the edit",
            )
            before_payload = engine_payload(edit_data)
            _ = page.screenshot(path=str(out_dir / "page-view.png"), full_page=True)

            rerun = page.get_by_test_id("page-rerun-doctr")
            expect(rerun).to_be_enabled(timeout=60_000)
            rerun.click()
            expect(page.get_by_text("Re-run complete", exact=True).first).to_be_visible(
                timeout=RERUN_TIMEOUT_MS
            )

            after_rerun = download_zip(page, "download-images-text-json")
            rerun_data = page_json(after_rerun, stem)
            rec.require(
                "rerun-page-text-keeps-edit",
                after_rerun.files.get(f"{stem}.txt") == edited,
                f"{stem}.txt lost the saved edit",
            )
            rec.require(
                "rerun-page-json-keeps-edit", edited_text_of(rerun_data) == edited, "edited_text lost"
            )
            if args.skip_text_quality:
                rec.skip("rerun-engine-payload-changed", "--skip-text-quality")
            else:
                rec.require(
                    "rerun-engine-payload-changed",
                    engine_payload(rerun_data) != before_payload,
                    "exported engine output is the same as before the rerun",
                )

            tesseract = page.get_by_test_id("page-rerun-tesseract")
            visible = tesseract.is_visible()
            rec.step("tesseract-rerun-button", visible=visible, enabled=visible and tesseract.is_enabled())
            _ = page.screenshot(path=str(out_dir / "after-rerun.png"), full_page=True)
        finally:
            browser.close()


@dataclass(frozen=True)
class AcceptanceArgs:
    """Parsed command line."""

    out_dir: Path
    fixtures: Path
    browser_channel: str
    headless: bool
    exe: str | None
    skip_text_quality: bool


class _Namespace(argparse.Namespace):
    out_dir: Path = DEFAULT_OUT_DIR
    fixtures: Path = DEFAULT_FIXTURES
    browser_channel: str = DEFAULT_CHANNEL
    headless: bool = False
    exe: str | None = None
    skip_text_quality: bool = False


def parse_args(argv: Sequence[str] | None = None) -> AcceptanceArgs:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description="Acceptance run for the installed pdomain-ocr-simple-gui.")
    _ = parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    _ = parser.add_argument(
        "--fixtures", type=Path, default=DEFAULT_FIXTURES, help="directory, .png, or .gt.txt"
    )
    _ = parser.add_argument("--browser-channel", default=DEFAULT_CHANNEL)
    _ = parser.add_argument("--headless", action="store_true")
    _ = parser.add_argument("--exe", help="path to pdomain-ocr-simple-gui; default: search PATH")
    _ = parser.add_argument(
        "--skip-text-quality",
        action="store_true",
        help="skip the checks that need real OCR output (word overlap, changed rerun payload); fake-OCR smoke runs only",
    )
    ns = parser.parse_args(argv, namespace=_Namespace())
    return AcceptanceArgs(
        out_dir=ns.out_dir,
        fixtures=ns.fixtures,
        browser_channel=ns.browser_channel,
        headless=ns.headless,
        exe=ns.exe,
        skip_text_quality=ns.skip_text_quality,
    )


def run(args: AcceptanceArgs, rec: Recorder) -> None:
    """Start the installed app, probe it, and drive the browser flow."""
    exe = args.exe or shutil.which("pdomain-ocr-simple-gui")
    rec.require(
        "exe-found", exe is not None, "" if exe else "pdomain-ocr-simple-gui is not on PATH; pass --exe"
    )
    if exe is None:
        return
    fixture = resolve_fixtures(args.fixtures)
    port = free_port()
    with (args.out_dir / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [exe, "--no-browser", "--port", str(port)], stdout=log, stderr=subprocess.STDOUT
        )
        try:
            wait_for_server(server, port)
            rec.step("server-up", exe=exe, port=port)
            probe_server(rec, port)
            drive_browser(rec, args, fixture, port)
        finally:
            server.terminate()
            try:
                _ = server.wait(20)
            except subprocess.TimeoutExpired:
                server.kill()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the acceptance flow and return the process exit code."""
    from playwright.sync_api import Error as PlaywrightError

    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rec = Recorder()
    error: str | None = None
    try:
        run(args, rec)
    except (AcceptanceError, AssertionError, OSError, ImportError, PlaywrightError):
        error = traceback.format_exc()
        print(error, flush=True)
    passed = rec.all_passed and error is None
    results = {
        "passed": passed,
        "seconds": round(time.monotonic() - rec.started, 1),
        "error": error,
        "steps": rec.steps,
        "checks": rec.checks,
    }
    _ = (args.out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [str(c["check"]) for c in rec.checks if not c["passed"]]
    print("WINDOWS-ACCEPTANCE", "PASS" if passed else f"FAIL ({', '.join(failed) or 'error'})", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
