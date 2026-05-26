// PageViewPage — M5 task #231, M6 task #232
// Screen 4: two-panel layout — image canvas + editable text
// Migrated to PageSplitView — issue #254
// A8: word overlay fetch wired to PageImageCanvas

import { useEffect, useState, useRef, type ChangeEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageImageCanvas } from "@concavetrillion/pd-ui/canvas";
import type { CanvasPage, CanvasWord } from "@concavetrillion/pd-ui/canvas";
import {
  Button,
  Textarea,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  PageSplitView,
} from "@concavetrillion/pd-ui/primitives";

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
 * CanvasWord with pixel-space bounding_box that PageImageCanvas expects.
 */
function apiWordToCanvasWord(
  word: ApiWord,
  pageWidth: number,
  pageHeight: number,
): CanvasWord {
  const { x, y, w, h } = word.bbox;
  return {
    text: word.text,
    ocr_confidence: word.confidence,
    bounding_box: {
      top_left: { x: x * pageWidth, y: y * pageHeight },
      bottom_right: {
        x: (x + w) * pageWidth,
        y: (y + h) * pageHeight,
      },
    },
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
  const [saveStatus, setSaveStatus] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");
  const saveToastRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [rerunStatus, setRerunStatus] = useState<
    "idle" | "running" | "done" | "error"
  >("idle");
  const [words, setWords] = useState<CanvasWord[]>([]);

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
          const pw = pageData?.width ?? 800;
          const ph = pageData?.height ?? 1200;
          setWords(body.words.map((w) => apiWordToCanvasWord(w, pw, ph)));
        }
      } catch {
        // words overlay is non-critical — silently degrade to empty
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, pageIdx, pageData]);

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
        setSaveStatus("saved");
        // Clear any pending toast timer
        if (saveToastRef.current) clearTimeout(saveToastRef.current);
        saveToastRef.current = setTimeout(() => setSaveStatus("idle"), 3000);
      } else {
        setSaveStatus("error");
      }
    } catch {
      setSaveStatus("error");
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
        setRerunStatus("done");
        // Refetch page data to update textarea
        const pageRes = await fetch(`/api/pages/${id}/${pageIdx}`);
        if (pageRes.ok) {
          const data = (await pageRes.json()) as PageData;
          setPageData(data);
          setText(data.text ?? "");
        }
        setTimeout(() => setRerunStatus("idle"), 3000);
      } else {
        setRerunStatus("error");
        setTimeout(() => setRerunStatus("idle"), 3000);
      }
    } catch {
      setRerunStatus("error");
      setTimeout(() => setRerunStatus("idle"), 3000);
    }
  }

  const totalPages = jobStatus?.page_count ?? 0;
  const hasPrev = pageIdx > 0;
  const hasNext = pageIdx < totalPages - 1;

  function goToPage(newIdx: number) {
    navigate(`/jobs/${id ?? ""}/pages/${newIdx}`);
  }

  const imageSrc = `/api/pages/${id ?? ""}/${pageIdx}/image`;

  // Minimal CanvasPage for read-only display — width/height from page data
  const canvasPage: CanvasPage = {
    width: pageData?.width ?? 800,
    height: pageData?.height ?? 1200,
  };

  const toolbarContent = (
    <>
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

      {saveStatus === "saved" && (
        <span role="status" className="page-toast page-toast--success">
          Saved
        </span>
      )}
      {saveStatus === "error" && (
        <span role="alert" className="page-toast page-toast--error">
          Save failed
        </span>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            disabled={rerunStatus === "running" || loading}
            aria-label="Re-run page"
          >
            {rerunStatus === "running" ? "Re-running…" : "Re-run page ▾"}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem
            onSelect={() => {
              void handleRerun("doctr");
            }}
          >
            DocTR
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              void handleRerun("tesseract");
            }}
          >
            Tesseract
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {rerunStatus === "done" && (
        <span role="status" className="page-toast page-toast--success">
          Re-run complete
        </span>
      )}
      {rerunStatus === "error" && (
        <span role="alert" className="page-toast page-toast--error">
          Re-run failed
        </span>
      )}
    </>
  );

  // Wrapper div carries data-testid and data-word-count for tests.
  // PageImageCanvas is a Konva canvas and does not propagate arbitrary
  // data-* props to the DOM — the wrapper is the observable element.
  const canvasContent = !loading ? (
    <div data-testid="page-image-canvas" data-word-count={String(words.length)}>
      <PageImageCanvas src={imageSrc} page={canvasPage} words={words} />
    </div>
  ) : null;

  const editorContent = (
    <Textarea
      value={text}
      onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
        setText(e.target.value)
      }
      disabled={loading}
      aria-label="OCR text"
      rows={40}
    />
  );

  return (
    <div data-testid="page-view-page" className="page-split-view-wrapper">
      <PageSplitView
        toolbar={toolbarContent}
        canvas={canvasContent}
        editor={editorContent}
      />
    </div>
  );
}
