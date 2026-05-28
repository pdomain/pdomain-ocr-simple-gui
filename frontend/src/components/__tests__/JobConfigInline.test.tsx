// Tests for JobConfigInline — replaces JobConfigDialog modal flow.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route, useLocation } from "react-router-dom";
import {
  JobConfigInline,
  defaultProjectName,
  type ChosenSource,
} from "../JobConfigInline";
import { renderWithProviders } from "../../test/test-utils";

// Shim Toggle so tests can interact with it as a plain checkbox (avoid Radix
// ResizeObserver dependency in jsdom).
vi.mock("@pdomain/pdomain-ui/primitives", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  const React = await import("react");

  function ToggleShim({
    checked,
    onCheckedChange,
    label,
    id,
  }: {
    checked: boolean;
    onCheckedChange: (v: boolean) => void;
    label?: string;
    id?: string;
    disabled?: boolean;
  }) {
    return React.createElement(
      "label",
      { htmlFor: id },
      label,
      React.createElement("input", {
        id,
        type: "checkbox",
        checked,
        onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
          onCheckedChange(e.target.checked),
      }),
    );
  }
  ToggleShim.displayName = "Toggle";

  return {
    ...actual,
    Toggle: ToggleShim,
  };
});

function LocationCapture({ onLocation }: { onLocation: (p: string) => void }) {
  const loc = useLocation();
  onLocation(loc.pathname);
  return null;
}

function renderInline(
  source: ChosenSource = { kind: "path", path: "/tmp/scans" },
  fetchMock?: ReturnType<typeof vi.fn>,
  mode: "local" | "managed" = "local",
  onCancel?: () => void,
) {
  const navigatedTo: string[] = [];

  const defaultFetch = vi
    .fn()
    .mockImplementation((url: string, opts?: RequestInit) => {
      if (url === "/api/prefs" && (!opts || opts.method !== "POST")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ engine: "doctr", language: "en" }),
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
  (globalThis as unknown as { fetch: typeof fetch }).fetch =
    mockFetch as unknown as typeof fetch;

  const result = renderWithProviders(
    <Routes>
      <Route
        path="/"
        element={
          <JobConfigInline source={source} mode={mode} onCancel={onCancel} />
        }
      />
      <Route
        path="/jobs/:id"
        element={<LocationCapture onLocation={(p) => navigatedTo.push(p)} />}
      />
    </Routes>,
    { route: "/" },
  );

  return { ...result, navigatedTo, mockFetch };
}

describe("defaultProjectName", () => {
  it("returns basename for path source", () => {
    expect(defaultProjectName({ kind: "path", path: "/tmp/scans" })).toBe(
      "scans",
    );
    expect(defaultProjectName({ kind: "path", path: "/home/me/book-a/" })).toBe(
      "book-a",
    );
    expect(
      defaultProjectName({ kind: "path", path: "C:\\Users\\me\\book" }),
    ).toBe("book");
  });

  it("returns ocr-job-<short> for upload source", () => {
    expect(
      defaultProjectName({ kind: "upload", uploadId: "abc123def456ghi" }),
    ).toBe("ocr-job-abc123de");
  });

  it("returns ocr-job fallback for empty path", () => {
    expect(defaultProjectName({ kind: "path", path: "" })).toBe("ocr-job");
    expect(defaultProjectName({ kind: "path", path: "/" })).toBe("ocr-job");
    expect(defaultProjectName({ kind: "path", path: "\\" })).toBe("ocr-job");
  });
});

describe("JobConfigInline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all required form fields", async () => {
    renderInline();
    await waitFor(() => {
      expect(screen.getByLabelText(/project name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/engine/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/language/i)).toBeInTheDocument();
      expect(screen.getByTestId("output-config-panel")).toBeInTheDocument();
      expect(screen.getByTestId("run-ocr-button")).toBeInTheDocument();
    });
  });

  it("pre-fills project name from source basename", async () => {
    renderInline({ kind: "path", path: "/tmp/my-book" });
    const nameInput = (await screen.findByLabelText(
      /project name/i,
    )) as HTMLInputElement;
    expect(nameInput.value).toBe("my-book");
  });

  it("pre-fills project name as ocr-job-<short> for uploads", async () => {
    renderInline({ kind: "upload", uploadId: "abcdef123456" });
    const nameInput = (await screen.findByLabelText(
      /project name/i,
    )) as HTMLInputElement;
    expect(nameInput.value).toBe("ocr-job-abcdef12");
  });

  it("does NOT render a separate output-dir field", async () => {
    renderInline();
    await waitFor(() => {
      expect(screen.getByLabelText(/project name/i)).toBeInTheDocument();
    });
    // No <input> labeled "Output directory" / "Output dir"
    expect(screen.queryByLabelText(/output dir/i)).toBeNull();
    expect(screen.queryByLabelText(/output directory/i)).toBeNull();
  });

  it("POSTs /api/jobs with the expected body shape for path source", async () => {
    const user = userEvent.setup();
    const { mockFetch } = renderInline({ kind: "path", path: "/tmp/scans" });
    const submit = await screen.findByTestId("run-ocr-button");
    await user.click(submit);

    await waitFor(() => {
      const postCalls = mockFetch.mock.calls.filter(
        ([url, opts]: [string, RequestInit | undefined]) =>
          url === "/api/jobs" && opts?.method === "POST",
      );
      expect(postCalls).toHaveLength(1);
      const body = JSON.parse(
        (postCalls[0][1] as RequestInit).body as string,
      ) as Record<string, unknown>;
      expect(body.name).toBe("scans");
      expect(body.engine).toBe("doctr");
      expect(body.language).toBe("en");
      expect(body.source_path).toBe("/tmp/scans");
      expect(body).not.toHaveProperty("upload_id");
      expect(body).not.toHaveProperty("output_dir");
      expect(body.save_json).toBe(true);
      expect(body.combined_txt).toBe(true);
      expect(body.device).toBe("auto");
      expect(body.batch_pages).toBeNull();
      expect(body.output).toEqual({ mode: "next_to_source" });
    });
  });

  it("POSTs /api/jobs with upload_id for upload source", async () => {
    const user = userEvent.setup();
    const { mockFetch } = renderInline(
      { kind: "upload", uploadId: "upload-xyz" },
      undefined,
      "managed",
    );
    const submit = await screen.findByTestId("run-ocr-button");
    await user.click(submit);

    await waitFor(() => {
      const postCalls = mockFetch.mock.calls.filter(
        ([url, opts]: [string, RequestInit | undefined]) =>
          url === "/api/jobs" && opts?.method === "POST",
      );
      expect(postCalls).toHaveLength(1);
      const body = JSON.parse(
        (postCalls[0][1] as RequestInit).body as string,
      ) as Record<string, unknown>;
      expect(body.upload_id).toBe("upload-xyz");
      expect(body).not.toHaveProperty("source_path");
      expect(body.output).toEqual({ mode: "managed" });
    });
  });

  it("navigates to /jobs/:id on successful submit", async () => {
    const user = userEvent.setup();
    const { navigatedTo } = renderInline();
    const submit = await screen.findByTestId("run-ocr-button");
    await user.click(submit);
    await waitFor(() => {
      expect(navigatedTo.some((p) => p.startsWith("/jobs/"))).toBe(true);
    });
  });

  it("shows inline error when /api/jobs fails", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, opts?: RequestInit) => {
        if (url === "/api/prefs") {
          return Promise.resolve({
            ok: true,
            json: async () => ({ engine: "doctr", language: "en" }),
          });
        }
        if (url === "/api/jobs" && opts?.method === "POST") {
          return Promise.resolve({
            ok: false,
            text: async () => "bad request",
          });
        }
        return Promise.resolve({ ok: false, json: async () => ({}) });
      });
    renderInline({ kind: "path", path: "/tmp/scans" }, fetchMock);
    const submit = await screen.findByTestId("run-ocr-button");
    await user.click(submit);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/bad request/i);
    });
  });

  it("blocks submit when project name is empty", async () => {
    const user = userEvent.setup();
    renderInline();
    const nameInput = await screen.findByLabelText(/project name/i);
    await user.clear(nameInput);
    const submit = screen.getByTestId("run-ocr-button");
    expect(submit).toBeDisabled();
  });

  it("calls onCancel when 'Use different files' is clicked", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    renderInline(
      { kind: "path", path: "/tmp/scans" },
      undefined,
      "local",
      onCancel,
    );
    const cancel = await screen.findByTestId("job-config-inline-cancel");
    await user.click(cancel);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
