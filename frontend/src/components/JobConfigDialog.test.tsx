// Tests for JobConfigDialog — M4 task #229
// Updated for BaseJobConfigDialog migration (issue #256)

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { JobConfigDialog } from "./JobConfigDialog";

// Mock pd-ui/primitives — replace BaseJobConfigDialog with a testable shim
// that renders the form shell inline (no Radix portals) and exposes the same
// testids the component tests rely on.
vi.mock("@concavetrillion/pd-ui/primitives", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;

  const React = await import("react");

  // Shim for BaseJobConfigDialog: renders project-name, output-dir, error,
  // children, cancel and submit buttons — all inline, no portals.
  function BaseJobConfigDialogShim({
    open,
    title,
    sourcePath: _sourcePath,
    onClose,
    onSubmit,
    submitLabel,
    children,
  }: {
    open?: boolean;
    title?: string;
    sourcePath?: string;
    onClose?: () => void;
    onSubmit?: (base: { projectName: string; outputDir: string }) => Promise<void>;
    submitLabel?: string;
    children?: React.ReactNode;
  }) {
    const [projectName, setProjectName] = React.useState("");
    const [outputDir, setOutputDir] = React.useState("");
    const [error, setError] = React.useState<string | null>(null);
    const [submitting, setSubmitting] = React.useState(false);

    if (!open) return null;

    async function handleSubmit(e: React.FormEvent) {
      e.preventDefault();
      if (!projectName.trim() || !outputDir.trim()) {
        setError("Project name and output directory are required.");
        return;
      }
      setError(null);
      setSubmitting(true);
      try {
        await onSubmit?.({ projectName, outputDir });
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred.");
      } finally {
        setSubmitting(false);
      }
    }

    return React.createElement(
      "div",
      { "data-testid": "dialog-root" },
      React.createElement(
        "div",
        { "data-testid": "dialog-content" },
        React.createElement(
          "div",
          { "data-testid": "dialog-header" },
          React.createElement("h2", { "data-testid": "dialog-title" }, title)
        ),
        React.createElement(
          "form",
          {
            "data-testid": "job-config-dialog-form",
            onSubmit: (e: React.FormEvent) => { void handleSubmit(e); },
            noValidate: true,
          },
          error !== null &&
            React.createElement("p", { role: "alert", className: "job-config-dialog__error" }, error),
          React.createElement(
            "label",
            { htmlFor: "bjcd-name" },
            "Project name"
          ),
          React.createElement("input", {
            id: "bjcd-name",
            "aria-label": "Project name",
            value: projectName,
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => setProjectName(e.target.value),
          }),
          React.createElement(
            "label",
            { htmlFor: "bjcd-output" },
            "Output directory"
          ),
          React.createElement("input", {
            id: "bjcd-output",
            "aria-label": "Output directory",
            value: outputDir,
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => setOutputDir(e.target.value),
          }),
          children,
          React.createElement(
            "div",
            { "data-testid": "dialog-footer" },
            React.createElement(
              "button",
              { type: "button", onClick: onClose, disabled: submitting },
              "Cancel"
            ),
            React.createElement(
              "button",
              {
                type: "submit",
                disabled: submitting || !projectName.trim() || !outputDir.trim(),
                "data-testid": "run-ocr-button",
              },
              submitting ? `${submitLabel ?? "Run →"}…` : (submitLabel ?? "Run →")
            )
          )
        )
      )
    );
  }

  BaseJobConfigDialogShim.displayName = "BaseJobConfigDialog";

  return {
    ...actual,
    BaseJobConfigDialog: BaseJobConfigDialogShim,
    // Keep Input and Field from actual so children render correctly
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

  // Default fetch mock: GET /api/prefs (engine/language only) + POST /api/jobs
  const defaultFetch = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
    if (url === "/api/prefs" && (!opts || opts.method !== "POST")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          engine: "doctr",
          language: "en",
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

  it("renders output dir field (managed by BaseJobConfigDialog)", async () => {
    renderDialog();
    await waitFor(() => {
      const outputInput = screen.getByLabelText(/output/i) as HTMLInputElement;
      expect(outputInput).toBeInTheDocument();
      // BaseJobConfigDialog starts with empty outputDir (no prefs pre-fill)
      expect(outputInput.value).toBe("");
    });
  });

  it("blocks submit when output_dir is empty", async () => {
    const user = userEvent.setup();
    renderDialog();

    // Submit button disabled when outputDir empty
    const submitBtn = screen.getByTestId("run-ocr-button");
    expect(submitBtn).toBeDisabled();

    // Fill project name only — submit still disabled
    const nameInput = screen.getByLabelText(/project name/i);
    await user.type(nameInput, "my-project");
    expect(submitBtn).toBeDisabled();

    // Fill output dir — now enabled
    const outputInput = screen.getByLabelText(/output/i);
    await user.type(outputInput, "/tmp/out");
    expect(submitBtn).not.toBeDisabled();
  });

  it("blocks submit when source_path is empty (server error path)", async () => {
    const user = userEvent.setup();
    // sourcePath="" — the server will reject, BaseJobConfigDialog shows thrown error
    const fetchMock = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      if (url === "/api/prefs") {
        return Promise.resolve({ ok: true, json: async () => ({ engine: "doctr", language: "en" }) });
      }
      if (url === "/api/jobs" && opts?.method === "POST") {
        return Promise.resolve({ ok: false, text: async () => "source path required" });
      }
      return Promise.resolve({ ok: false, json: async () => ({}) });
    });
    renderDialog("", fetchMock);

    // Fill in form fields
    const nameInput = screen.getByLabelText(/project name/i);
    await user.type(nameInput, "test");
    const outputInput = screen.getByLabelText(/output/i);
    await user.type(outputInput, "/tmp/out");

    const submitBtn = screen.getByTestId("run-ocr-button");
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    const postCalls = fetchMock.mock.calls.filter(
      ([url, opts]: [string, RequestInit | undefined]) => url === "/api/jobs" && opts?.method === "POST"
    );
    expect(postCalls).toHaveLength(1);
  });

  it("calls POST /api/jobs on successful submit", async () => {
    const user = userEvent.setup();
    const { mockFetch } = renderDialog("/tmp/scans");

    // Fill required fields
    const nameInput = screen.getByLabelText(/project name/i);
    await user.type(nameInput, "my-project");
    const outputInput = screen.getByLabelText(/output/i);
    await user.type(outputInput, "/tmp/ocr-out");

    const submitBtn = screen.getByTestId("run-ocr-button");
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

    const nameInput = screen.getByLabelText(/project name/i);
    await user.type(nameInput, "my-project");
    const outputInput = screen.getByLabelText(/output/i);
    await user.type(outputInput, "/tmp/ocr-out");

    const submitBtn = screen.getByTestId("run-ocr-button");
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
      // Engine select rendered as child
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
