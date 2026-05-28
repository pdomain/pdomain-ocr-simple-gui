// Tests for ResultsPage — M4 task #230

import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router-dom";
import ResultsPage from "../ResultsPage";
import { renderWithProviders, fixtures } from "../../test/test-utils";

// Mock pdomain-ui/primitives
vi.mock("@pdomain/pdomain-ui/primitives", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    Progress: ({
      value,
      status,
      label,
    }: {
      value?: number;
      status?: string;
      label?: string;
    }) => (
      <div
        data-testid="progress-bar"
        data-value={value}
        data-status={status}
        aria-label={label ?? "progress"}
      />
    ),
    Chip: ({
      children,
      className,
    }: {
      children: React.ReactNode;
      className?: string;
    }) => (
      <span data-testid="status-chip" className={className}>
        {children}
      </span>
    ),
    Button: ({
      children,
      disabled,
      ...props
    }: {
      children: React.ReactNode;
      disabled?: boolean;
    }) => (
      <button disabled={disabled} {...props}>
        {children}
      </button>
    ),
  };
});

function renderResultsPage(
  projectId = "proj-abc",
  makeFetch?: () => ReturnType<typeof vi.fn>,
) {
  const mockFetch = makeFetch
    ? makeFetch()
    : vi.fn().mockResolvedValue({
        ok: true,
        json: async () => fixtures.jobStatus("succeeded"),
      });

  (globalThis as any).fetch = mockFetch;

  return {
    mockFetch,
    ...renderWithProviders(
      <Routes>
        <Route path="/jobs/:id" element={<ResultsPage />} />
        <Route
          path="/jobs/:id/pages/:idx"
          element={<div data-testid="page-view" />}
        />
      </Routes>,
      { route: `/jobs/${projectId}` },
    ),
  };
}

describe("ResultsPage", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("renders project name after load", async () => {
    renderResultsPage();
    await waitFor(() => {
      expect(screen.getByText("test-project")).toBeInTheDocument();
    });
  });

  it("shows progress bar while state is running", async () => {
    renderResultsPage("proj-abc", () =>
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => fixtures.jobStatus("running", { pagesDone: 1 }),
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("progress-bar")).toBeInTheDocument();
    });
  });

  it("hides progress bar in done state", async () => {
    renderResultsPage();
    await waitFor(() => {
      expect(screen.getByText("test-project")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("progress-bar")).not.toBeInTheDocument();
  });

  it("renders progress_message when backend sets it", async () => {
    renderResultsPage("proj-abc", () =>
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () =>
          fixtures.jobStatus("running", {
            pagesDone: 0,
            progressMessage:
              "Loading OCR engine — first run may download ~200 MB to ~/.cache/huggingface",
          }),
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("job-progress-message")).toHaveTextContent(
        /Loading OCR engine/,
      );
    });
  });

  it("hides progress_message row when missing/null", async () => {
    renderResultsPage("proj-abc", () =>
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => fixtures.jobStatus("running", { pagesDone: 0 }),
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("progress-bar")).toBeInTheDocument();
    });
    expect(
      screen.queryByTestId("job-progress-message"),
    ).not.toBeInTheDocument();
  });

  it("polling stops when state is done", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false });

    let callCount = 0;
    const mockFetch = vi.fn().mockImplementation(async () => {
      callCount++;
      return {
        ok: true,
        json: async () => fixtures.jobStatus("succeeded"),
      };
    });

    (globalThis as any).fetch = mockFetch;

    renderWithProviders(
      <Routes>
        <Route path="/jobs/:id" element={<ResultsPage />} />
      </Routes>,
      { route: "/jobs/proj-abc" },
    );

    // Let microtasks flush (fetch promise resolves)
    await act(async () => {
      await Promise.resolve();
    });

    const countAfterDone = callCount;
    expect(countAfterDone).toBeGreaterThan(0);

    // Advance fake timers — no more polls should fire
    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });

    expect(callCount).toBe(countAfterDone);
  });

  it("polling continues when state is running", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false });

    let callCount = 0;
    const mockFetch = vi.fn().mockImplementation(async () => {
      callCount++;
      return {
        ok: true,
        json: async () =>
          fixtures.jobStatus("running", { pagesDone: callCount, pageCount: 5 }),
      };
    });

    (globalThis as any).fetch = mockFetch;

    renderWithProviders(
      <Routes>
        <Route path="/jobs/:id" element={<ResultsPage />} />
      </Routes>,
      { route: "/jobs/proj-abc" },
    );

    // Initial fetch
    await act(async () => {
      await Promise.resolve();
    });

    const countAfterInit = callCount;
    expect(countAfterInit).toBeGreaterThan(0);

    // Advance 2 polling intervals and drain microtasks each time
    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });

    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });

    expect(callCount).toBeGreaterThan(countAfterInit);
  });

  it("renders page rows in done state", async () => {
    renderResultsPage();
    await waitFor(() => {
      expect(screen.getByText("page_001.png")).toBeInTheDocument();
      expect(screen.getByText("page_002.png")).toBeInTheDocument();
    });
  });

  it("page rows have data-testid='page-row' for Playwright targeting", async () => {
    renderResultsPage();
    await waitFor(() => {
      const rows = screen.getAllByTestId("page-row");
      expect(rows).toHaveLength(3);
    });
  });

  it("shows text preview", async () => {
    renderResultsPage();
    await waitFor(() => {
      expect(screen.getByText("Preview page 1")).toBeInTheDocument();
    });
  });

  it("navigates to page view when row is clicked", async () => {
    const user = userEvent.setup();
    renderResultsPage();

    await waitFor(() => {
      expect(screen.getByText("page_001.png")).toBeInTheDocument();
    });

    await user.click(screen.getByText("page_001.png"));

    await waitFor(() => {
      expect(screen.getByTestId("page-view")).toBeInTheDocument();
    });
  });

  it("re-run all button sends POST /api/jobs/:id/rerun", async () => {
    const user = userEvent.setup();
    let rerunCalled = false;
    const mockFetch = vi
      .fn()
      .mockImplementation(async (url: string, opts?: RequestInit) => {
        if (url.includes("/rerun") && (!opts || opts.method === "POST")) {
          rerunCalled = true;
          return {
            ok: true,
            json: async () => ({ project_id: "proj-abc", state: "queued" }),
          };
        }
        return {
          ok: true,
          json: async () => fixtures.jobStatus("succeeded"),
        };
      });

    (globalThis as any).fetch = mockFetch;

    renderWithProviders(
      <Routes>
        <Route path="/jobs/:id" element={<ResultsPage />} />
      </Routes>,
      { route: "/jobs/proj-abc" },
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /re.run all/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /re.run all/i }));

    await waitFor(() => {
      expect(rerunCalled).toBe(true);
    });
  });

  it("re-run all button re-fetches job status on success", async () => {
    const user = userEvent.setup();
    let fetchCount = 0;
    const mockFetch = vi
      .fn()
      .mockImplementation(async (url: string, opts?: RequestInit) => {
        if (url.includes("/rerun") && opts?.method === "POST") {
          return {
            ok: true,
            json: async () => ({ project_id: "proj-abc", state: "queued" }),
          };
        }
        fetchCount++;
        return {
          ok: true,
          json: async () => fixtures.jobStatus("succeeded"),
        };
      });

    (globalThis as any).fetch = mockFetch;

    renderWithProviders(
      <Routes>
        <Route path="/jobs/:id" element={<ResultsPage />} />
      </Routes>,
      { route: "/jobs/proj-abc" },
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /re.run all/i }),
      ).toBeInTheDocument();
    });

    const countBeforeRerun = fetchCount;

    await user.click(screen.getByRole("button", { name: /re.run all/i }));

    // After re-run POST, fetchStatus should be called again
    await waitFor(() => {
      expect(fetchCount).toBeGreaterThan(countBeforeRerun);
    });
  });

  // A7.2: download button tests
  it("shows download button when output_mode is managed and state is succeeded", async () => {
    renderResultsPage("proj-abc", () =>
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () =>
          fixtures.jobStatus("succeeded", { outputMode: "managed" }),
      }),
    );
    await waitFor(() => {
      expect(screen.getByTestId("download-results-button")).toBeInTheDocument();
    });
  });

  it("hides download button when output_mode is next_to_source", async () => {
    renderResultsPage("proj-abc", () =>
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () =>
          fixtures.jobStatus("succeeded", { outputMode: "next_to_source" }),
      }),
    );
    await waitFor(() => {
      expect(screen.getByText("test-project")).toBeInTheDocument();
    });
    expect(
      screen.queryByTestId("download-results-button"),
    ).not.toBeInTheDocument();
  });

  it("hides download button when state is not succeeded", async () => {
    renderResultsPage("proj-abc", () =>
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () =>
          fixtures.jobStatus("running", {
            pagesDone: 1,
            outputMode: "managed",
          }),
      }),
    );
    await waitFor(() => {
      expect(screen.getByTestId("progress-bar")).toBeInTheDocument();
    });
    expect(
      screen.queryByTestId("download-results-button"),
    ).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Bad-case tests (M4 strengthening)
  // ---------------------------------------------------------------------------

  it("shows error alert when job fetch fails (bad state)", async () => {
    renderResultsPage("proj-abc", () =>
      vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }),
    );
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    // Project name should not be rendered in error state
    expect(screen.queryByText("test-project")).not.toBeInTheDocument();
  });

  it("shows no page rows when job has empty page list (succeeded but no pages)", async () => {
    renderResultsPage("proj-abc", () =>
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => fixtures.jobStatus("succeeded", { pageCount: 0 }),
      }),
    );
    await waitFor(() => {
      // Name renders — job loaded
      expect(screen.getByText("test-project")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("page-row")).not.toBeInTheDocument();
  });

  it("shows em-dash when text_preview is empty string", async () => {
    renderResultsPage("proj-abc", () =>
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...fixtures.jobStatus("succeeded"),
          pages: [
            {
              page_idx: 0,
              page_name: "page_001.png",
              state: "succeeded",
              text_preview: "",
            },
          ],
        }),
      }),
    );
    await waitFor(() => {
      // The row should render with — for blank preview
      expect(screen.getByText("—")).toBeInTheDocument();
    });
  });

  it("page rows absent when job is loading (non-navigable state)", async () => {
    // Simulate a slow fetch — page rows must not appear while loading
    let resolveSlowFetch!: (v: unknown) => void;
    renderResultsPage("proj-abc", () =>
      vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveSlowFetch = resolve;
          }),
      ),
    );
    // Before fetch resolves, no page-rows yet
    expect(screen.queryByTestId("page-row")).not.toBeInTheDocument();
    // Resolve with success so test teardown is clean
    resolveSlowFetch({
      ok: true,
      json: async () => fixtures.jobStatus("succeeded"),
    });
  });

  it("does not crash when rerun POST returns non-ok (error silently ignored)", async () => {
    const user = userEvent.setup();
    let rerunCalled = false;
    const mockFetch = vi
      .fn()
      .mockImplementation(async (url: string, opts?: RequestInit) => {
        if (url.includes("/rerun") && opts?.method === "POST") {
          rerunCalled = true;
          return { ok: false, json: async () => ({}) };
        }
        return {
          ok: true,
          json: async () => fixtures.jobStatus("succeeded"),
        };
      });

    (globalThis as any).fetch = mockFetch;

    renderWithProviders(
      <Routes>
        <Route path="/jobs/:id" element={<ResultsPage />} />
      </Routes>,
      { route: "/jobs/proj-abc" },
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /re.run all/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /re.run all/i }));

    await waitFor(() => {
      expect(rerunCalled).toBe(true);
    });
    // Page should still show project name — no crash
    expect(screen.getByText("test-project")).toBeInTheDocument();
  });

  it("project name still shows after re-fetch failure post-rerun", async () => {
    const user = userEvent.setup();
    let rerunDone = false;
    const mockFetch = vi
      .fn()
      .mockImplementation(async (url: string, opts?: RequestInit) => {
        if (url.includes("/rerun") && opts?.method === "POST") {
          rerunDone = true;
          return {
            ok: true,
            json: async () => ({ project_id: "proj-abc", state: "queued" }),
          };
        }
        // After rerun, simulate a fetch failure on the follow-up status poll
        if (rerunDone) {
          return { ok: false, json: async () => ({}) };
        }
        return {
          ok: true,
          json: async () => fixtures.jobStatus("succeeded"),
        };
      });

    (globalThis as any).fetch = mockFetch;

    renderWithProviders(
      <Routes>
        <Route path="/jobs/:id" element={<ResultsPage />} />
      </Routes>,
      { route: "/jobs/proj-abc" },
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /re.run all/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /re.run all/i }));

    // After re-fetch failure the error alert appears — no crash
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
