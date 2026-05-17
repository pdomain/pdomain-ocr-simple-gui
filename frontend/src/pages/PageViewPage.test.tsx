// Tests for PageViewPage — M5 task #231

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import PageViewPage from "./PageViewPage";

// Mock pd-ui canvas — PageImageCanvas needs a Konva/canvas environment we don't have in jsdom
vi.mock("@concavetrillion/pd-ui/canvas", () => ({
  PageImageCanvas: ({ src }: { src: string }) => (
    <div data-testid="page-image-canvas" data-src={src} />
  ),
}));

// Mock pd-ui/primitives
vi.mock("@concavetrillion/pd-ui/primitives", async (importOriginal) => {
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
  };
});

interface PageData {
  page_idx: number;
  name: string;
  state: string;
  text: string;
  width: number;
  height: number;
}

function makePageData(idx = 0, text = "Sample OCR text"): PageData {
  return {
    page_idx: idx,
    name: `page_00${idx + 1}.png`,
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
      name: `page_00${i + 1}.png`,
      state: "done",
      text_preview: "preview",
    })),
  };
}

function renderPageView(projectId = "proj-abc", pageIdx = 0) {
  const mockFetch = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
    if (url.includes("/api/jobs/") && !url.includes("/pages/")) {
      return Promise.resolve({
        ok: true,
        json: async () => makeJobStatus(3),
      });
    }
    if (url.includes("/api/pages/") && !url.endsWith("/image") && (!opts || !opts.method || opts.method === "GET")) {
      const idxMatch = url.match(/\/pages\/[^/]+\/(\d+)$/);
      const idx = idxMatch ? parseInt(idxMatch[1], 10) : pageIdx;
      return Promise.resolve({
        ok: true,
        json: async () => makePageData(idx, `OCR text for page ${idx}`),
      });
    }
    if (url.includes("/api/pages/") && url.endsWith("/text") && opts?.method === "PUT") {
      return Promise.resolve({
        ok: true,
        json: async () => ({ ok: true }),
      });
    }
    return Promise.resolve({ ok: false, json: async () => ({}) });
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).fetch = mockFetch;

  return {
    mockFetch,
    ...render(
      <MemoryRouter initialEntries={[`/jobs/${projectId}/pages/${pageIdx}`]}>
        <Routes>
          <Route path="/jobs/:id/pages/:idx" element={<PageViewPage />} />
        </Routes>
      </MemoryRouter>
    ),
  };
}

describe("PageViewPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders canvas with correct image src", async () => {
    renderPageView("proj-abc", 0);
    await waitFor(() => {
      const canvas = screen.getByTestId("page-image-canvas");
      expect(canvas).toBeInTheDocument();
      expect(canvas.getAttribute("data-src")).toBe("/api/pages/proj-abc/0/image");
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
          url.includes("/api/pages/") && url.endsWith("/text") && opts?.method === "PUT"
      );
      expect(putCalls).toHaveLength(1);
      const body = JSON.parse(putCalls[0][1].body as string) as { text: string };
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
      expect(screen.getByText(/saved/i)).toBeInTheDocument();
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
      const canvas = screen.getByTestId("page-image-canvas");
      expect(canvas.getAttribute("data-src")).toBe("/api/pages/proj-abc/1/image");
    });
  });

  it("next button is disabled on last page", async () => {
    renderPageView("proj-abc", 2); // last page of 3 (0-indexed: 0,1,2)
    await waitFor(() => {
      const nextBtn = screen.getByRole("button", { name: /next/i });
      expect(nextBtn).toBeDisabled();
    });
  });

  it("re-run page button is rendered (stub)", async () => {
    renderPageView("proj-abc", 0);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /re.run/i })).toBeInTheDocument();
    });
  });
});
