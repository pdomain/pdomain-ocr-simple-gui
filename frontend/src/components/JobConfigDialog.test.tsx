// Tests for JobConfigDialog — M4 task #229

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { JobConfigDialog } from "./JobConfigDialog";

// Mock pd-ui/primitives radix dialog (jsdom doesn't support portals well)
vi.mock("@concavetrillion/pd-ui/primitives", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    // Override Dialog components so they render inline without portals
    Dialog: ({ children, open }: { children: React.ReactNode; open?: boolean }) =>
      open !== false ? <div data-testid="dialog-root">{children}</div> : null,
    DialogContent: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="dialog-content">{children}</div>
    ),
    DialogHeader: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="dialog-header">{children}</div>
    ),
    DialogTitle: ({ children }: { children: React.ReactNode }) => (
      <h2 data-testid="dialog-title">{children}</h2>
    ),
    DialogFooter: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="dialog-footer">{children}</div>
    ),
    DialogDescription: ({ children }: { children: React.ReactNode }) => (
      <p data-testid="dialog-description">{children}</p>
    ),
  };
});

// Capture navigation target
function LocationCapture({ onLocation }: { onLocation: (p: string) => void }) {
  const loc = useLocation();
  onLocation(loc.pathname);
  return null;
}

function renderDialog(
  sourcePath = "/tmp/scans",
  fetchMock?: ReturnType<typeof vi.fn>
) {
  const navigatedTo: string[] = [];
  const onClose = vi.fn();

  // Default fetch mock: GET /api/prefs + POST /api/jobs
  const defaultFetch = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
    if (url === "/api/prefs" && (!opts || opts.method !== "POST")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          engine: "doctr",
          language: "eng",
          output_dir: "/tmp/ocr-out",
        }),
      });
    }
    if (url === "/api/jobs" && opts?.method === "POST") {
      return Promise.resolve({
        ok: true,
        json: async () => ({ project_id: "proj-123" }),
      });
    }
    return Promise.resolve({ ok: false, json: async () => ({}) });
  });

  const mockFetch = fetchMock ?? defaultFetch;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).fetch = mockFetch;

  const result = render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route
          path="/"
          element={
            <JobConfigDialog
              open={true}
              sourcePath={sourcePath}
              onClose={onClose}
            />
          }
        />
        <Route
          path="/jobs/:id"
          element={
            <LocationCapture
              onLocation={(p) => navigatedTo.push(p)}
            />
          }
        />
      </Routes>
    </MemoryRouter>
  );

  return { ...result, navigatedTo, onClose, mockFetch };
}

describe("JobConfigDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders dialog with title", async () => {
    renderDialog();
    expect(screen.getByTestId("dialog-root")).toBeInTheDocument();
    expect(screen.getByTestId("dialog-title")).toHaveTextContent(/job/i);
  });

  it("pre-fills project name from source path basename", async () => {
    renderDialog("/home/user/my-scans");
    await waitFor(() => {
      const nameInput = screen.getByLabelText(/project name/i) as HTMLInputElement;
      expect(nameInput.value).toBe("my-scans");
    });
  });

  it("pre-fills output dir from GET /api/prefs", async () => {
    renderDialog();
    await waitFor(() => {
      const outputInput = screen.getByLabelText(/output/i) as HTMLInputElement;
      expect(outputInput.value).toBe("/tmp/ocr-out");
    });
  });

  it("blocks submit when output_dir is empty", async () => {
    const user = userEvent.setup();
    renderDialog();

    // Wait for prefs to load
    await waitFor(() => {
      const outputInput = screen.getByLabelText(/output/i) as HTMLInputElement;
      expect(outputInput.value).toBe("/tmp/ocr-out");
    });

    // Clear the output dir field
    const outputInput = screen.getByLabelText(/output/i);
    await user.clear(outputInput);

    // Try to submit
    const submitBtn = screen.getByRole("button", { name: /run ocr/i });
    await user.click(submitBtn);

    // Should see validation error
    expect(screen.getByRole("alert")).toBeInTheDocument();
    // fetch POST should NOT have been called
    const mockFetch = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch;
    const postCalls = mockFetch.mock.calls.filter(
      ([url, opts]: [string, RequestInit | undefined]) => url === "/api/jobs" && opts?.method === "POST"
    );
    expect(postCalls).toHaveLength(0);
  });

  it("blocks submit when source_path is empty", async () => {
    const user = userEvent.setup();
    renderDialog(""); // Empty source path

    await waitFor(() => {
      const outputInput = screen.getByLabelText(/output/i) as HTMLInputElement;
      expect(outputInput.value).toBe("/tmp/ocr-out");
    });

    const submitBtn = screen.getByRole("button", { name: /run ocr/i });
    await user.click(submitBtn);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    const mockFetch = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch;
    const postCalls = mockFetch.mock.calls.filter(
      ([url, opts]: [string, RequestInit | undefined]) => url === "/api/jobs" && opts?.method === "POST"
    );
    expect(postCalls).toHaveLength(0);
  });

  it("calls POST /api/jobs on successful submit", async () => {
    const user = userEvent.setup();
    const { mockFetch } = renderDialog("/tmp/scans");

    // Wait for prefs to load
    await waitFor(() => {
      const outputInput = screen.getByLabelText(/output/i) as HTMLInputElement;
      expect(outputInput.value).toBe("/tmp/ocr-out");
    });

    const submitBtn = screen.getByRole("button", { name: /run ocr/i });
    await user.click(submitBtn);

    await waitFor(() => {
      const postCalls = mockFetch.mock.calls.filter(
        ([url, opts]: [string, RequestInit | undefined]) => url === "/api/jobs" && opts?.method === "POST"
      );
      expect(postCalls).toHaveLength(1);
    });
  });

  it("navigates to /jobs/:id after successful submit", async () => {
    const user = userEvent.setup();
    const { navigatedTo } = renderDialog("/tmp/scans");

    await waitFor(() => {
      const outputInput = screen.getByLabelText(/output/i) as HTMLInputElement;
      expect(outputInput.value).toBe("/tmp/ocr-out");
    });

    const submitBtn = screen.getByRole("button", { name: /run ocr/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(navigatedTo.some((p) => p.startsWith("/jobs/"))).toBe(true);
    });
  });

  it("shows all required form fields", async () => {
    renderDialog("/tmp/scans");
    await waitFor(() => {
      expect(screen.getByLabelText(/project name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/output/i)).toBeInTheDocument();
      // Engine select or radio
      expect(screen.getByLabelText(/engine/i)).toBeInTheDocument();
    });
  });

  it("has data-testid attributes for Playwright targeting", async () => {
    renderDialog("/tmp/scans");
    await waitFor(() => {
      expect(screen.getByTestId("job-config-dialog-form")).toBeInTheDocument();
      expect(screen.getByTestId("engine-select")).toBeInTheDocument();
      expect(screen.getByTestId("language-input")).toBeInTheDocument();
      expect(screen.getByTestId("run-ocr-button")).toBeInTheDocument();
    });
  });
});
