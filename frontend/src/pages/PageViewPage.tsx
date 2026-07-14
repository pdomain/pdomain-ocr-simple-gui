// PageViewPage — M5 task #231, M6 task #232
// Screen 4: two-panel layout — image canvas + editable text
// Migrated to PageSplitView — issue #254
// A8: word overlay fetch wired to ArtifactViewer with WordBbox overlays
// feat/adopt-richer-primitives: replaced PageImageCanvas with ArtifactViewer
// feat(viewer): keyboard shortcuts + hover tooltips + ? cheatsheet

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArtifactViewer } from "@pdomain/pdomain-ui/stages/PageWorkbench";
import type { WordBbox } from "@pdomain/pdomain-ui/stages/PageWorkbench";
import {
  Button,
  Textarea,
  PageSplitView,
  StageToolbar,
  KeyCap,
} from "@pdomain/pdomain-ui/primitives";
import { useShortcuts, formatShortcut } from "@pdomain/pdomain-ui/hooks";
import type { ShortcutBinding } from "@pdomain/pdomain-ui/hooks";
import { apiFetch } from "../api/apiFetch";
import { APP_TEST_IDS } from "../lib/testids";
import {
  PageViewerWithZoom,
  type ZoomHandle,
} from "../components/PageViewerWithZoom";
import { useConfig } from "../runtime/ConfigContext";
import { engineIsAvailable } from "../runtime/ocrEngines";

interface PageData {
  page_idx: number;
  page_name: string;
  state: string;
  text: string;
  width: number;
  height: number;
}

interface JobStatus {
  project_id: string;
  name: string;
  state: string;
  page_count: number;
  progress_message?: string | null;
}

/** Normalized word bbox from GET /api/pages/{id}/{idx}/words. */
interface ApiWordBbox {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface ApiWord {
  text: string;
  bbox: ApiWordBbox;
  confidence: number;
}

/**
 * Convert a normalized-coord bbox {x,y,w,h} (0–1 page-relative) into a
 * WordBbox that ArtifactViewer's WordBboxOverlay expects.
 * bbox is [x, y, w, h] — same normalization, tuple form.
 */
function apiWordToWordBbox(word: ApiWord, index: number): WordBbox {
  const { x, y, w, h } = word.bbox;
  return {
    id: `w-${index}`,
    bbox: [x, y, w, h],
    confidence: word.confidence,
  };
}

/**
 * KeyButton — Button with an always-visible inline keycap pill after the
 * label, showing the OS-aware shortcut (⌘S on Mac, Ctrl S elsewhere via
 * formatShortcut). Spreads all props (data-testid, aria-label) to the inner
 * Button so existing test selectors are unaffected.
 */
function KeyButton({
  shortcutKeys,
  children,
  variant,
  onClick,
  disabled,
  ...rest
}: {
  shortcutKeys: string;
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  onClick?: () => void;
  disabled?: boolean;
  [k: string]: unknown;
}) {
  return (
    <Button variant={variant} onClick={onClick} disabled={disabled} {...rest}>
      <span className="key-button__label">{children}</span>
      <KeyCap keys={formatShortcut(shortcutKeys)} className="key-button__cap" />
    </Button>
  );
}

export default function PageViewPage() {
  const { id, idx } = useParams<{ id: string; idx: string }>();
  const navigate = useNavigate();
  const runtimeConfig = useConfig();
  const tesseractAvailable = engineIsAvailable(runtimeConfig, "tesseract");

  const pageIdx = parseInt(idx ?? "0", 10);

  const [pageData, setPageData] = useState<PageData | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [text, setText] = useState<string>("");
  const [loading, setLoading] = useState(true);
  // Page-fetch failure: "not-found" for a 404 (page/project missing), "error"
  // for any other non-ok status or a network reject. Drives the dedicated
  // error blocks (mirrors ResultsPage's results-not-found / results-error).
  const [fetchError, setFetchError] = useState<"not-found" | "error" | null>(
    null,
  );
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving">("idle");
  const [rerunStatus, setRerunStatus] = useState<"idle" | "running">("idle");
  const [wordBboxes, setWordBboxes] = useState<WordBbox[]>([]);
  const zoomRef = useRef<ZoomHandle | null>(null);

  // Load job status to know total page count
  useEffect(() => {
    let cancelled = false;
    apiFetch(`/api/jobs/${id ?? ""}`)
      .then(async (res) => {
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as JobStatus;
        if (!cancelled) setJobStatus(data);
      })
      .catch(() => {
        // ignore — pageCount will default to 0, disabling next
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  // Load page data
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setSaveStatus("idle");
    setFetchError(null);

    apiFetch(`/api/pages/${id ?? ""}/${pageIdx}`)
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          // Surface a dedicated error affordance instead of leaving the screen
          // stuck loading on a blank shell. 404 → "not found"; anything else
          // (e.g. 400 malformed id, 5xx) → the generic error block.
          setFetchError(res.status === 404 ? "not-found" : "error");
          setLoading(false);
          return;
        }
        const data = (await res.json()) as PageData;
        if (!cancelled) {
          setPageData(data);
          setText(data.text ?? "");
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFetchError("error");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [id, pageIdx]);

  // Load word overlays — A8
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch(`/api/pages/${id ?? ""}/${pageIdx}/words`);
        if (!res.ok || cancelled) return;
        const body = (await res.json()) as { words: ApiWord[] };
        if (!cancelled) {
          setWordBboxes(body.words.map((w, i) => apiWordToWordBbox(w, i)));
        }
      } catch {
        // words overlay is non-critical — silently degrade to empty
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, pageIdx]);

  async function handleSave() {
    if (!id) return;
    setSaveStatus("saving");
    try {
      const res = await apiFetch(`/api/pages/${id}/${pageIdx}/text`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (res.ok) {
        toast.success("Saved");
      } else {
        toast.error("Save failed");
      }
    } catch {
      toast.error("Save failed");
    } finally {
      setSaveStatus("idle");
    }
  }

  async function handleRerun(engine: "doctr" | "tesseract") {
    if (!id) return;
    setRerunStatus("running");
    try {
      const res = await apiFetch(`/api/pages/${id}/${pageIdx}/rerun`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engine }),
      });
      if (res.ok) {
        // Refetch page data to update textarea
        const pageRes = await apiFetch(`/api/pages/${id}/${pageIdx}`);
        if (pageRes.ok) {
          const data = (await pageRes.json()) as PageData;
          setPageData(data);
          setText(data.text ?? "");
        }
        toast.success("Re-run complete");
      } else {
        toast.error("Re-run failed");
      }
    } catch {
      toast.error("Re-run failed");
    } finally {
      setRerunStatus("idle");
    }
  }

  const totalPages = jobStatus?.page_count ?? 0;
  const hasPrev = pageIdx > 0;
  const hasNext = pageIdx < totalPages - 1;

  function goToPage(newIdx: number) {
    navigate(`/jobs/${id ?? ""}/pages/${newIdx}`);
  }

  const imageSrc = `/api/pages/${id ?? ""}/${pageIdx}/image`;
  const pageWidth = pageData?.width ?? 800;
  const pageHeight = pageData?.height ?? 1200;

  const jobInFlight =
    jobStatus !== null &&
    (jobStatus.state === "queued" || jobStatus.state === "running");
  const showJobProgressMessage = jobInFlight && !!jobStatus.progress_message;

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  // Stable bindings: the `when` guards + `handler` functions use refs to read
  // the latest values without changing the array reference.  This prevents the
  // ShortcutsContext infinite-loop: allBindings change → re-render → new array
  // → second useEffect in useShortcuts fires → register again → loop.
  const shortcutCtxRef = useRef({
    pageIdx,
    hasPrev,
    hasNext,
    loading,
    saveStatus,
    rerunStatus,
    tesseractAvailable,
    id,
    handleSave,
    handleRerun,
    goToPage,
  });
  // Keep ref current on every render (no extra re-renders caused).
  shortcutCtxRef.current = {
    pageIdx,
    hasPrev,
    hasNext,
    loading,
    saveStatus,
    rerunStatus,
    tesseractAvailable,
    id,
    handleSave,
    handleRerun,
    goToPage,
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const bindings = useMemo<ShortcutBinding[]>(
    () => [
      // Navigation
      {
        keys: "arrowleft",
        label: "Previous page",
        group: "Navigation",
        handler: () =>
          shortcutCtxRef.current.goToPage(shortcutCtxRef.current.pageIdx - 1),
        when: () => shortcutCtxRef.current.hasPrev,
      },
      {
        keys: "k",
        label: "Previous page (alt)",
        group: "Navigation",
        handler: () =>
          shortcutCtxRef.current.goToPage(shortcutCtxRef.current.pageIdx - 1),
        when: () => shortcutCtxRef.current.hasPrev,
      },
      {
        keys: "arrowright",
        label: "Next page",
        group: "Navigation",
        handler: () =>
          shortcutCtxRef.current.goToPage(shortcutCtxRef.current.pageIdx + 1),
        when: () => shortcutCtxRef.current.hasNext,
      },
      {
        keys: "j",
        label: "Next page (alt)",
        group: "Navigation",
        handler: () =>
          shortcutCtxRef.current.goToPage(shortcutCtxRef.current.pageIdx + 1),
        when: () => shortcutCtxRef.current.hasNext,
      },
      // Editing
      {
        keys: "mod+s",
        label: "Save edits",
        group: "Editing",
        handler: () => {
          void shortcutCtxRef.current.handleSave();
        },
        when: () =>
          !shortcutCtxRef.current.loading &&
          shortcutCtxRef.current.saveStatus === "idle",
      },
      // OCR
      {
        keys: "mod+r",
        label: "Re-run DocTR",
        group: "OCR",
        handler: () => {
          void shortcutCtxRef.current.handleRerun("doctr");
        },
        when: () =>
          !shortcutCtxRef.current.loading &&
          shortcutCtxRef.current.rerunStatus === "idle" &&
          shortcutCtxRef.current.tesseractAvailable,
      },
      {
        keys: "mod+shift+r",
        label: "Re-run Tesseract",
        group: "OCR",
        handler: () => {
          void shortcutCtxRef.current.handleRerun("tesseract");
        },
        when: () =>
          !shortcutCtxRef.current.loading &&
          shortcutCtxRef.current.rerunStatus === "idle",
      },
      // Export — Task 9: two explicit downloads (text; text+JSON).
      // JSON-only shortcut removed (no corresponding button in the UI).
      {
        keys: "mod+shift+t",
        label: "Download images + text",
        group: "Export",
        handler: () => {
          window.location.href = `/api/jobs/${shortcutCtxRef.current.id ?? ""}/download?include=text`;
        },
        when: () => !shortcutCtxRef.current.loading,
      },
      {
        keys: "mod+d",
        label: "Download images + text + JSON",
        group: "Export",
        handler: () => {
          window.location.href = `/api/jobs/${shortcutCtxRef.current.id ?? ""}/download?include=${encodeURIComponent("text,json")}`;
        },
        when: () => !shortcutCtxRef.current.loading,
      },
      // Empty deps: the array is created once; handlers use shortcutCtxRef for
      // latest values. This is intentional — DO NOT add deps here.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    ],
    [],
  );

  // Registers these bindings into the app-level ShortcutsProvider, so the
  // header ? button's cheatsheet is screen-aware. The provider owns the ?
  // key + cheatsheet rendering globally.
  useShortcuts(bindings);

  const toolbarContent = (
    <>
      {showJobProgressMessage && (
        <span
          className="page-view-page__progress-message"
          data-testid={APP_TEST_IDS.pageProgressMessage}
        >
          {jobStatus.progress_message}
        </span>
      )}
      <KeyButton
        shortcutKeys="arrowleft"
        variant="ghost"
        onClick={() => goToPage(pageIdx - 1)}
        disabled={!hasPrev}
        aria-label="Prev page"
        data-testid={APP_TEST_IDS.pagePrevButton}
      >
        ← Prev
      </KeyButton>

      <span className="page-view-page__page-indicator">
        {pageData?.page_name ?? `Page ${pageIdx + 1}`}
        {totalPages > 0 ? ` (${pageIdx + 1} / ${totalPages})` : ""}
      </span>

      <KeyButton
        shortcutKeys="arrowright"
        variant="ghost"
        onClick={() => goToPage(pageIdx + 1)}
        disabled={!hasNext}
        aria-label="Next page"
        data-testid={APP_TEST_IDS.pageNextButton}
      >
        Next →
      </KeyButton>
    </>
  );

  const editorToolbar = (
    <StageToolbar
      aria-label="Page actions"
      data-testid="page-editor-toolbar"
      leftSlot={
        <>
          <KeyButton
            shortcutKeys="mod+s"
            variant="primary"
            onClick={() => {
              void handleSave();
            }}
            disabled={saveStatus === "saving" || loading}
            aria-label="Save edits"
            data-testid={APP_TEST_IDS.pageSaveButton}
          >
            {saveStatus === "saving" ? "Saving…" : "Save edits"}
          </KeyButton>
          <KeyButton
            shortcutKeys="mod+r"
            variant="primary"
            onClick={() => {
              void handleRerun("doctr");
            }}
            disabled={rerunStatus === "running" || loading}
            aria-label="Re-run with DocTR"
            data-testid={APP_TEST_IDS.pageRerunDoctr}
          >
            {rerunStatus === "running" ? "Re-running…" : "Re-run DocTR"}
          </KeyButton>
          {tesseractAvailable ? (
            <KeyButton
              shortcutKeys="mod+shift+r"
              variant="primary"
              onClick={() => {
                void handleRerun("tesseract");
              }}
              disabled={rerunStatus === "running" || loading}
              aria-label="Re-run with Tesseract"
              data-testid={APP_TEST_IDS.pageRerunTesseract}
            >
              Re-run Tesseract
            </KeyButton>
          ) : null}
          {/* Task 9: two explicit download buttons mirror ResultsPage's UI.
              Keyboard shortcut mod+shift+t fires the text-only download;
              mod+d fires the text+JSON download. */}
          <KeyButton
            shortcutKeys="mod+shift+t"
            variant="primary"
            data-testid="download-images-text"
            onClick={() => {
              window.location.href = `/api/jobs/${id ?? ""}/download?include=text`;
            }}
            disabled={loading}
            aria-label="Download images + text"
          >
            ⤓ images + text
          </KeyButton>
          <KeyButton
            shortcutKeys="mod+d"
            variant="primary"
            data-testid="download-images-text-json"
            onClick={() => {
              window.location.href = `/api/jobs/${id ?? ""}/download?include=${encodeURIComponent("text,json")}`;
            }}
            disabled={loading}
            aria-label="Download images + text + JSON"
          >
            ⤓ images + text + JSON
          </KeyButton>
        </>
      }
    />
  );

  // Wrapper div carries data-testid and data-word-count for tests.
  // ArtifactViewer is Konva-backed and does not propagate data-* to the DOM —
  // the wrapper is the observable element for Playwright / vitest selectors.
  const canvasContent = !loading ? (
    <div
      data-testid={APP_TEST_IDS.pageImageCanvas}
      data-word-count={String(wordBboxes.length)}
      style={{ width: "100%", height: "100%" }}
    >
      <PageViewerWithZoom
        ref={zoomRef}
        pageWidth={pageWidth}
        pageHeight={pageHeight}
      >
        <ArtifactViewer
          imageSrc={imageSrc}
          pageWidth={pageWidth}
          pageHeight={pageHeight}
          overlayMode="words"
          wordBboxes={wordBboxes}
        />
      </PageViewerWithZoom>
    </div>
  ) : null;

  // Task 10: rows={40} removed — the textarea fills the PageSplitView editor
  // slot height.  The parent flex container uses height: 100% + column
  // direction; the Textarea needs flex: 1 + minHeight: 0 so it expands to
  // fill the remaining space after the toolbar (not just its natural height).
  // data-testid="ocr-text" lets tests and e2e selectors target the textarea.
  const editorContent = (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {editorToolbar}
      <Textarea
        value={text}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
          setText(e.target.value)
        }
        disabled={loading}
        aria-label="OCR text"
        data-testid="ocr-text"
        style={{ flex: 1, minHeight: 0 }}
      />
    </div>
  );

  // A failed page fetch surfaces a dedicated block (no blank loading shell).
  // 404 → "page not found" with a way back to the job; other errors → a
  // generic error message. Mirrors ResultsPage's not-found / error blocks.
  if (fetchError !== null) {
    return (
      <div
        data-testid={APP_TEST_IDS.pageViewPage}
        className="page-split-view-wrapper"
      >
        {fetchError === "not-found" ? (
          <div
            role="alert"
            data-testid={APP_TEST_IDS.pageNotFound}
            className="page-view-page__error"
          >
            <p>Page not found. It may have been deleted or never existed.</p>
            <Button
              variant="ghost"
              onClick={() => navigate(`/jobs/${id ?? ""}`)}
            >
              Back to job
            </Button>
          </div>
        ) : (
          <p
            role="alert"
            data-testid={APP_TEST_IDS.pageError}
            className="page-view-page__error"
          >
            Error loading page. Please try again.
          </p>
        )}
      </div>
    );
  }

  return (
    <div
      data-testid={APP_TEST_IDS.pageViewPage}
      className="page-split-view-wrapper"
    >
      <PageSplitView
        toolbar={toolbarContent}
        canvas={canvasContent}
        editor={editorContent}
      />
    </div>
  );
}
