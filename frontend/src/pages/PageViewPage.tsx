// PageViewPage — M5 task #231, M6 task #232
// Screen 4: two-panel layout — image canvas + editable text
// Migrated to PageSplitView — issue #254
// A8: word overlay fetch wired to ArtifactViewer with WordBbox overlays
// feat/adopt-richer-primitives: replaced PageImageCanvas with ArtifactViewer

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArtifactViewer } from "@pdomain/pdomain-ui/stages/PageWorkbench";
import type { WordBbox } from "@pdomain/pdomain-ui/stages/PageWorkbench";
import {
  Button,
  Textarea,
  PageSplitView,
  StageToolbar,
} from "@pdomain/pdomain-ui/primitives";
import { APP_TEST_IDS } from "../lib/testids";
import {
  PageViewerWithZoom,
  type ZoomHandle,
} from "../components/PageViewerWithZoom";

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

export default function PageViewPage() {
  const { id, idx } = useParams<{ id: string; idx: string }>();
  const navigate = useNavigate();

  const pageIdx = parseInt(idx ?? "0", 10);

  const [pageData, setPageData] = useState<PageData | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [text, setText] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving">("idle");
  const [rerunStatus, setRerunStatus] = useState<"idle" | "running">("idle");
  const [wordBboxes, setWordBboxes] = useState<WordBbox[]>([]);
  const zoomRef = useRef<ZoomHandle | null>(null);

  // Load job status to know total page count
  useEffect(() => {
    let cancelled = false;
    fetch(`/api/jobs/${id ?? ""}`)
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

    fetch(`/api/pages/${id ?? ""}/${pageIdx}`)
      .then(async (res) => {
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as PageData;
        if (!cancelled) {
          setPageData(data);
          setText(data.text ?? "");
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
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
        const res = await fetch(`/api/pages/${id ?? ""}/${pageIdx}/words`);
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
      const res = await fetch(`/api/pages/${id}/${pageIdx}/text`, {
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
      const res = await fetch(`/api/pages/${id}/${pageIdx}/rerun`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engine }),
      });
      if (res.ok) {
        // Refetch page data to update textarea
        const pageRes = await fetch(`/api/pages/${id}/${pageIdx}`);
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
      <Button
        variant="ghost"
        onClick={() => goToPage(pageIdx - 1)}
        disabled={!hasPrev}
        aria-label="Prev page"
      >
        ← Prev
      </Button>

      <span className="page-view-page__page-indicator">
        {pageData?.page_name ?? `Page ${pageIdx + 1}`}
        {totalPages > 0 ? ` (${pageIdx + 1} / ${totalPages})` : ""}
      </span>

      <Button
        variant="ghost"
        onClick={() => goToPage(pageIdx + 1)}
        disabled={!hasNext}
        aria-label="Next page"
      >
        Next →
      </Button>

    </>
  );

  const editorToolbar = (
    <StageToolbar
      aria-label="Page actions"
      data-testid="page-editor-toolbar"
      leftSlot={
        <Button
          variant="primary"
          onClick={() => {
            void handleSave();
          }}
          disabled={saveStatus === "saving" || loading}
          aria-label="Save edits"
        >
          {saveStatus === "saving" ? "Saving…" : "Save edits"}
        </Button>
      }
      centerSlot={
        <>
          <Button
            variant="ghost"
            onClick={() => {
              void handleRerun("doctr");
            }}
            disabled={rerunStatus === "running" || loading}
            aria-label="Re-run with DocTR"
          >
            {rerunStatus === "running" ? "Re-running…" : "Re-run DocTR"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              void handleRerun("tesseract");
            }}
            disabled={rerunStatus === "running" || loading}
            aria-label="Re-run with Tesseract"
          >
            Re-run Tesseract
          </Button>
        </>
      }
      rightSlot={
        <>
          <Button
            variant="ghost"
            data-testid={APP_TEST_IDS.pageDownloadText}
            onClick={() => {
              window.location.href = `/api/jobs/${id ?? ""}/download?include=text`;
            }}
            disabled={loading}
            aria-label="Download text only"
          >
            ⤓ .txt
          </Button>
          <Button
            variant="ghost"
            data-testid={APP_TEST_IDS.pageDownloadJson}
            onClick={() => {
              window.location.href = `/api/jobs/${id ?? ""}/download?include=json`;
            }}
            disabled={loading}
            aria-label="Download JSON sidecars only"
          >
            ⤓ .json
          </Button>
          <Button
            variant="primary"
            data-testid={APP_TEST_IDS.pageDownloadBoth}
            onClick={() => {
              window.location.href = `/api/jobs/${id ?? ""}/download?include=text,json`;
            }}
            disabled={loading}
            aria-label="Download text and JSON zip"
          >
            ⤓ .zip
          </Button>
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
        rows={40}
      />
    </div>
  );

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
