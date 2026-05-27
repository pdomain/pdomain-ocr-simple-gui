// Tests for PageViewPage A8 — word overlay wiring
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// Mock @pdomain/pdomain-ui/stages/PageWorkbench — ArtifactViewer uses Konva
// which requires a native 'canvas' module not available in jsdom.
// The wrapper div in PageViewPage carries data-word-count so we assert there.
vi.mock("@pdomain/pdomain-ui/stages/PageWorkbench", () => ({
  ArtifactViewer: ({
    wordBboxes,
  }: {
    wordBboxes?: unknown[];
    [k: string]: unknown;
  }) => (
    <div
      data-testid="artifact-viewer-mock"
      data-word-count={String((wordBboxes ?? []).length)}
    />
  ),
}));

// Keep canvas mock for any remaining direct canvas consumers.
vi.mock("@pdomain/pdomain-ui/canvas", () => ({
  PageImageCanvas: ({ words }: { words: unknown[]; [k: string]: unknown }) => (
    <div
      data-testid="page-image-canvas"
      data-word-count={String(words.length)}
    />
  ),
}));

// Minimal primitives mock — avoids ResizeObserver / Radix deps in jsdom.
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
      <div>{children}</div>
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

function renderWithRoute(jobId: string, idx: number) {
  return render(
    <MemoryRouter initialEntries={[`/jobs/${jobId}/pages/${idx}`]}>
      <Routes>
        <Route path="/jobs/:id/pages/:idx" element={<PageViewPageDefault />} />
      </Routes>
    </MemoryRouter>,
  );
}

// Import after vi.mock so the mock is in place
import PageViewPageDefault from "../PageViewPage";

it("passes fetched words to PageImageCanvas", async () => {
  const words = [
    { text: "Hi", bbox: { x: 0, y: 0, w: 0.1, h: 0.08 }, confidence: 0.9 },
  ];

  globalThis.fetch = (async (url: string) => {
    if ((url as string).endsWith("/words")) {
      return { ok: true, json: async () => ({ words }) };
    }
    // page data and job status
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
    expect(canvas?.getAttribute("data-word-count")).toBe("1");
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
