// Tests for PageViewPage — merged from co-located spec (13 cases) + word-overlay spec (5 cases)

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mocks shared across all cases
// ---------------------------------------------------------------------------

// Mock sonner — toast calls don't render to jsdom DOM; assert calls instead.
const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

// Mock @pdomain/pdomain-ui/stages/PageWorkbench — ArtifactViewer uses Konva
// which requires a native 'canvas' module not available in jsdom.
// The shim accepts wordBboxes so word-overlay tests can assert data-word-count,
// and also accepts imageSrc so existing selector tests pass.
vi.mock("@pdomain/pdomain-ui/stages/PageWorkbench", () => ({
  ArtifactViewer: ({
    imageSrc,
    wordBboxes,
  }: {
    imageSrc?: string;
    wordBboxes?: unknown[];
    [k: string]: unknown;
  }) => (
    <div
      data-canvas-src={imageSrc}
      data-testid="artifact-viewer-mock"
      data-word-count={String((wordBboxes ?? []).length)}
    />
  ),
}));

// Mock @pdomain/pdomain-ui/canvas — PageImageCanvas tracks word count.
vi.mock("@pdomain/pdomain-ui/canvas", () => ({
  PageImageCanvas: ({
    src,
    words,
  }: {
    src?: string;
    words?: unknown[];
    [k: string]: unknown;
  }) => (
    <div
      data-testid="page-image-canvas"
      data-canvas-src={src}
      data-word-count={String((words ?? []).length)}
    />
  ),
}));

// Mock hooks — prevents dual-React issue from pdomain-ui's own node_modules.
vi.mock("@pdomain/pdomain-ui/hooks", () => ({
  useShortcuts: () => undefined,
  formatShortcut: (keys: string) => [keys],
}));

// Mock PageViewerWithZoom — avoids Konva/ResizeObserver in jsdom.
// Provides interactive zoom buttons used by both zoom tests and page-nav tests.
vi.mock("../components/PageViewerWithZoom", () => ({
  PageViewerWithZoom: React.forwardRef(function PageViewerWithZoomMock(
    {
      children,
      pageWidth,
      pageHeight,
    }: {
      children?: React.ReactNode;
      pageWidth: number;
      pageHeight: number;
    },
    _ref: React.Ref<unknown>,
  ) {
    const [zoom, setZoom] = React.useState(1.0);
    const [autoFit, setAutoFit] = React.useState(true);
    return (
      <div
        data-testid="page-zoom-viewport"
        data-zoom={zoom.toFixed(4)}
        data-auto-fit={String(autoFit)}
        style={{ width: pageWidth, height: pageHeight }}
      >
        <button
          data-testid="page-zoom-in"
          onClick={() => {
            setAutoFit(false);
            setZoom((z) => z + 0.1);
          }}
        >
          +
        </button>
        <button
          data-testid="page-zoom-out"
          onClick={() => {
            setAutoFit(false);
            setZoom((z) => Math.max(0.1, z - 0.1));
          }}
        >
          -
        </button>
        <button
          data-testid="page-zoom-fit"
          onClick={() => {
            setAutoFit(true);
          }}
        >
          Fit
        </button>
        <button
          data-testid="page-zoom-100"
          onClick={() => {
            setAutoFit(false);
            setZoom(1.0);
          }}
        >
          100%
        </button>
        {children}
      </div>
    );
  }),
}));

// Mock @pdomain/pdomain-ui/primitives
vi.mock("@pdomain/pdomain-ui/primitives", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    Button: ({
      children,
      onClick,
      disabled,
      ...rest
    }: {
      children: React.ReactNode;
      onClick?: () => void;
      disabled?: boolean;
    }) => (
      <button onClick={onClick} disabled={disabled} {...rest}>
        {children}
      </button>
    ),
    // Tooltip shims — pass-through; testid/aria-label land on inner button.
    Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    TooltipTrigger: ({
      children,
    }: {
      children: React.ReactNode;
      asChild?: boolean;
    }) => <>{children}</>,
    TooltipContent: ({ children }: { children: React.ReactNode }) => (
      <div>{children}</div>
    ),
    TooltipProvider: ({ children }: { children: React.ReactNode }) => (
      <>{children}</>
    ),
    KeyCap: ({ keys }: { keys: string | string[] }) => (
      <span>{Array.isArray(keys) ? keys.join("+") : keys}</span>
    ),
    ShortcutsCheatsheet: () => null,
    StageToolbar: ({
      leftSlot,
      ...rest
    }: {
      leftSlot?: React.ReactNode;
      [k: string]: unknown;
    }) => <div {...rest}>{leftSlot}</div>,
    // Minimal DropdownMenu shim: renders trigger + items inline
    DropdownMenu: ({ children }: { children: React.ReactNode }) => (
      <div>{children}</div>
    ),
    DropdownMenuTrigger: ({
      children,
    }: {
      children: React.ReactNode;
      asChild?: boolean;
    }) => <>{children}</>,
    DropdownMenuContent: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="dropdown-content">{children}</div>
    ),
    DropdownMenuItem: ({
      children,
      onSelect,
    }: {
      children: React.ReactNode;
      onSelect?: () => void;
    }) => (
      <button role="menuitem" onClick={onSelect}>
        {children}
      </button>
    ),
    PageSplitView: ({
      toolbar,
      canvas,
      editor,
    }: {
      toolbar?: React.ReactNode;
      canvas?: React.ReactNode;
      editor?: React.ReactNode;
    }) => (
      <div data-testid="page-split-view">
        {toolbar}
        {canvas}
        {editor}
      </div>
    ),
  };
});

// Import after vi.mock so mocks are in place
import PageViewPage from "../PageViewPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface PageData {
  page_idx: number;
  page_name: string;
  state: string;
  text: string;
  width: number;
  height: number;
}

function makePageData(idx = 0, text = "Sample OCR text"): PageData {
  return {
    page_idx: idx,
    page_name: `page_00${idx + 1}.png`,
    state: "done",
    text,
    width: 800,
    height: 1200,
  };
}

function makeJobStatus(pageCount = 3, state = "done") {
  return {
    project_id: "proj-abc",
    name: "test-project",
    state,
    pages_done: pageCount,
    page_count: pageCount,
    pages: Array.from({ length: pageCount }, (_, i) => ({
      page_idx: i,
      page_name: `page_00${i + 1}.png`,
      state: "done",
      text_preview: "preview",
    })),
  };
}

function renderPageView(projectId = "proj-abc", pageIdx = 0) {
  const mockFetch = vi
    .fn()
    .mockImplementation((url: string, opts?: RequestInit) => {
      if (url.includes("/api/jobs/") && !url.includes("/pages/")) {
        return Promise.resolve({
          ok: true,
          json: async () => makeJobStatus(3),
        });
      }
      if (
        url.includes("/api/pages/") &&
        !url.endsWith("/image") &&
        !url.endsWith("/words") &&
        (!opts || !opts.method || opts.method === "GET")
      ) {
        const idxMatch = url.match(/\/pages\/[^/]+\/(\d+)$/);
        const idx = idxMatch ? parseInt(idxMatch[1], 10) : pageIdx;
        return Promise.resolve({
          ok: true,
          json: async () => makePageData(idx, `OCR text for page ${idx}`),
        });
      }
      if (url.endsWith("/words")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ words: [] }),
        });
      }
      if (
        url.includes("/api/pages/") &&
        url.endsWith("/text") &&
        opts?.method === "PUT"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ ok: true }),
        });
      }
      if (
        url.includes("/api/pages/") &&
        url.endsWith("/rerun") &&
        opts?.method === "POST"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ page_idx: pageIdx, state: "done" }),
        });
      }
      return Promise.resolve({ ok: false, json: async () => ({}) });
    });

  (globalThis as any).fetch = mockFetch;

  return {
    mockFetch,
    ...render(
      <MemoryRouter initialEntries={[`/jobs/${projectId}/pages/${pageIdx}`]}>
        <Routes>
          <Route path="/jobs/:id/pages/:idx" element={<PageViewPage />} />
        </Routes>
      </MemoryRouter>,
    ),
  };
}

/** Stub fetch for word-overlay tests — returns given words on /words endpoint. */
function stubFetchWithWords(words: unknown[] = []) {
  globalThis.fetch = (async (url: string) => {
    if ((url as string).endsWith("/words")) {
      return { ok: true, json: async () => ({ words }) };
    }
    return {
      ok: true,
      json: async () => ({
        page_idx: 0,
        page_name: "page-001.png",
        state: "succeeded",
        text: "",
        width: 800,
        height: 1200,
        project_id: "job-1",
        name: "Test",
        page_count: 1,
      }),
    };
  }) as unknown as typeof fetch;
}

function renderWithRoute(jobId: string, idx: number) {
  return render(
    <MemoryRouter initialEntries={[`/jobs/${jobId}/pages/${idx}`]}>
      <Routes>
        <Route path="/jobs/:id/pages/:idx" element={<PageViewPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Test suites
// ---------------------------------------------------------------------------

describe("PageViewPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders canvas with correct image src", async () => {
    renderPageView("proj-abc", 0);
    await waitFor(() => {
      const wrapper = screen.getByTestId("page-image-canvas");
      expect(wrapper).toBeInTheDocument();
      // data-canvas-src may be on the element or a child — check both paths
      const directSrc = wrapper.getAttribute("data-canvas-src");
      const innerEl = wrapper.querySelector("[data-canvas-src]");
      const canvasSrc = directSrc ?? innerEl?.getAttribute("data-canvas-src");
      expect(canvasSrc).toBe("/api/pages/proj-abc/0/image");
    });
  });

  it("renders textarea with page OCR text", async () => {
    renderPageView("proj-abc", 0);
    await waitFor(() => {
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      expect(textarea.value).toBe("OCR text for page 0");
    });
  });

  it("save button calls PUT /api/pages/:id/:idx/text", async () => {
    const user = userEvent.setup();
    const { mockFetch } = renderPageView("proj-abc", 0);

    await waitFor(() => {
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    // Edit the textarea
    const textarea = screen.getByRole("textbox");
    await user.clear(textarea);
    await user.type(textarea, "Edited text");

    // Click Save
    const saveBtn = screen.getByRole("button", { name: /save/i });
    await user.click(saveBtn);

    await waitFor(() => {
      const putCalls = mockFetch.mock.calls.filter(
        ([url, opts]: [string, RequestInit | undefined]) =>
          url.includes("/api/pages/") &&
          url.endsWith("/text") &&
          opts?.method === "PUT",
      );
      expect(putCalls).toHaveLength(1);
      const body = JSON.parse(putCalls[0][1].body as string) as {
        text: string;
      };
      expect(body.text).toBe("Edited text");
    });
  });

  it("shows success toast after save", async () => {
    const user = userEvent.setup();
    renderPageView("proj-abc", 0);

    await waitFor(() => {
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    const saveBtn = screen.getByRole("button", { name: /save/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("Saved");
    });
  });

  it("prev button is disabled on first page", async () => {
    renderPageView("proj-abc", 0);
    await waitFor(() => {
      const prevBtn = screen.getByRole("button", { name: /prev/i });
      expect(prevBtn).toBeDisabled();
    });
  });

  it("next button navigates to next page", async () => {
    const user = userEvent.setup();
    renderPageView("proj-abc", 0);

    await waitFor(() => {
      const nextBtn = screen.getByRole("button", { name: /next/i });
      expect(nextBtn).not.toBeDisabled();
    });

    const nextBtn = screen.getByRole("button", { name: /next/i });
    await user.click(nextBtn);

    await waitFor(() => {
      const wrapper = screen.getByTestId("page-image-canvas");
      const directSrc = wrapper.getAttribute("data-canvas-src");
      const innerEl = wrapper.querySelector("[data-canvas-src]");
      const canvasSrc = directSrc ?? innerEl?.getAttribute("data-canvas-src");
      expect(canvasSrc).toBe("/api/pages/proj-abc/1/image");
    });
  });

  it("next button is disabled on last page", async () => {
    renderPageView("proj-abc", 2); // last page of 3 (0-indexed: 0,1,2)
    await waitFor(() => {
      const nextBtn = screen.getByRole("button", { name: /next/i });
      expect(nextBtn).toBeDisabled();
    });
  });

  it("re-run page trigger button is rendered", async () => {
    renderPageView("proj-abc", 0);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /re-run with doctr/i }),
      ).toBeInTheDocument();
    });
  });

  it("DocTR menu item calls POST /api/pages/:id/:idx/rerun with engine doctr", async () => {
    const user = userEvent.setup();
    const { mockFetch } = renderPageView("proj-abc", 0);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /re-run with doctr/i }),
      ).toBeInTheDocument();
    });

    // Click the DocTR menu item (rendered inline by our DropdownMenuItem shim)
    const doctrItem = screen.getByRole("button", { name: /re-run with doctr/i });
    await user.click(doctrItem);

    await waitFor(() => {
      const rerunCalls = mockFetch.mock.calls.filter(
        ([url, opts]: [string, RequestInit | undefined]) =>
          url.includes("/api/pages/") &&
          url.endsWith("/rerun") &&
          opts?.method === "POST",
      );
      expect(rerunCalls).toHaveLength(1);
      const body = JSON.parse(rerunCalls[0][1].body as string) as {
        engine: string;
      };
      expect(body.engine).toBe("doctr");
    });
  });

  it("Tesseract menu item calls POST with engine tesseract", async () => {
    const user = userEvent.setup();
    const { mockFetch } = renderPageView("proj-abc", 0);

    await waitFor(() => {
      // Tesseract re-run is now a plain button in the editor toolbar.
    });

    const tessItem = screen.getByRole("button", { name: /re-run with tesseract/i });
    await user.click(tessItem);

    await waitFor(() => {
      const rerunCalls = mockFetch.mock.calls.filter(
        ([url, opts]: [string, RequestInit | undefined]) =>
          url.includes("/api/pages/") &&
          url.endsWith("/rerun") &&
          opts?.method === "POST",
      );
      expect(rerunCalls).toHaveLength(1);
      const body = JSON.parse(rerunCalls[0][1].body as string) as {
        engine: string;
      };
      expect(body.engine).toBe("tesseract");
    });
  });

  it("textarea updates after rerun completes", async () => {
    const user = userEvent.setup();

    // Set up fetch to return updated page data after rerun
    let rerunCalled = false;
    const mockFetch = vi
      .fn()
      .mockImplementation((url: string, opts?: RequestInit) => {
        if (url.includes("/api/jobs/") && !url.includes("/pages/")) {
          return Promise.resolve({
            ok: true,
            json: async () => makeJobStatus(3),
          });
        }
        if (
          url.includes("/api/pages/") &&
          url.endsWith("/rerun") &&
          opts?.method === "POST"
        ) {
          rerunCalled = true;
          return Promise.resolve({
            ok: true,
            json: async () => ({ page_idx: 0, state: "done" }),
          });
        }
        if (url.endsWith("/words")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ words: [] }),
          });
        }
        if (
          url.includes("/api/pages/") &&
          !url.endsWith("/image") &&
          (!opts || !opts.method || opts.method === "GET")
        ) {
          const text = rerunCalled ? "new rerun text" : "OCR text for page 0";
          return Promise.resolve({
            ok: true,
            json: async () => makePageData(0, text),
          });
        }
        return Promise.resolve({ ok: false, json: async () => ({}) });
      });

    (globalThis as any).fetch = mockFetch;

    renderWithRoute("proj-abc", 0);

    await waitFor(() => {
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      expect(textarea.value).toBe("OCR text for page 0");
    });

    const doctrItem = screen.getByRole("button", { name: /re-run with doctr/i });
    await user.click(doctrItem);

    await waitFor(() => {
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      expect(textarea.value).toBe("new rerun text");
    });
  });

  it("renders progress_message when job is mid-flight", async () => {
    (globalThis as any).fetch = vi
      .fn()
      .mockImplementation((url: string) => {
        if (url.includes("/api/jobs/") && !url.includes("/pages/")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              ...makeJobStatus(3, "running"),
              progress_message:
                "Loading OCR engine — first run may download ~200 MB to ~/.cache/huggingface",
            }),
          });
        }
        if (url.endsWith("/words")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ words: [] }),
          });
        }
        if (url.includes("/api/pages/") && !url.endsWith("/image")) {
          return Promise.resolve({
            ok: true,
            json: async () => makePageData(0, "text"),
          });
        }
        return Promise.resolve({ ok: false, json: async () => ({}) });
      });

    renderWithRoute("proj-abc", 0);

    await waitFor(() => {
      expect(screen.getByTestId("page-progress-message")).toHaveTextContent(
        /Loading OCR engine/,
      );
    });
  });

  it("hides progress_message when missing/null", async () => {
    renderPageView("proj-abc", 0);
    // Wait for the page to load (default makeJobStatus has no progress_message).
    await waitFor(() => {
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });
    expect(
      screen.queryByTestId("page-progress-message"),
    ).not.toBeInTheDocument();
  });
});

describe("PageViewPage — word overlay wiring", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("passes fetched words to PageImageCanvas", async () => {
    const words = [
      { text: "Hi", bbox: { x: 0, y: 0, w: 0.1, h: 0.08 }, confidence: 0.9 },
    ];

    stubFetchWithWords(words);
    const { container } = renderWithRoute("job-1", 0);

    await waitFor(() => {
      const canvas = container.querySelector('[data-testid="page-image-canvas"]');
      expect(canvas).not.toBeNull();
      expect(canvas?.getAttribute("data-word-count")).toBe("1");
    });
  });

  it("renders zoom toolbar with +/-/Fit/100% buttons", async () => {
    stubFetchWithWords();
    const { findByTestId } = renderWithRoute("job-1", 0);
    expect(await findByTestId("page-zoom-in")).toBeTruthy();
    expect(await findByTestId("page-zoom-out")).toBeTruthy();
    expect(await findByTestId("page-zoom-fit")).toBeTruthy();
    expect(await findByTestId("page-zoom-100")).toBeTruthy();
  });

  it("Fit returns the viewer to auto-fit after zooming in", async () => {
    stubFetchWithWords();
    const { findByTestId } = renderWithRoute("job-1", 0);
    const zoomIn = await findByTestId("page-zoom-in");
    const fit = await findByTestId("page-zoom-fit");
    const viewport = await findByTestId("page-zoom-viewport");
    // Zoom in twice → manual override, autoFit=false
    await act(async () => {
      zoomIn.click();
      zoomIn.click();
    });
    await waitFor(() => {
      expect(viewport.getAttribute("data-auto-fit")).toBe("false");
    });
    // Hit Fit → autoFit re-engaged
    await act(async () => {
      fit.click();
    });
    await waitFor(() => {
      expect(viewport.getAttribute("data-auto-fit")).toBe("true");
    });
  });

  it("100% sets zoom to native 1.0", async () => {
    stubFetchWithWords();
    const { findByTestId } = renderWithRoute("job-1", 0);
    const hundred = await findByTestId("page-zoom-100");
    await act(async () => {
      hundred.click();
    });
    const viewport = await findByTestId("page-zoom-viewport");
    await waitFor(() => {
      expect(viewport.getAttribute("data-zoom")).toBe("1.0000");
    });
  });

  it("renders canvas with zero words when words fetch fails", async () => {
    globalThis.fetch = (async (url: string) => {
      if ((url as string).endsWith("/words")) {
        return { ok: false };
      }
      return {
        ok: true,
        json: async () => ({
          page_idx: 0,
          page_name: "page-001.png",
          state: "succeeded",
          text: "",
          width: 800,
          height: 1200,
          project_id: "job-1",
          name: "Test",
          page_count: 1,
        }),
      };
    }) as unknown as typeof fetch;

    const { container } = renderWithRoute("job-1", 0);

    await waitFor(() => {
      const canvas = container.querySelector('[data-testid="page-image-canvas"]');
      expect(canvas).not.toBeNull();
      expect(canvas?.getAttribute("data-word-count")).toBe("0");
    });
  });
});
