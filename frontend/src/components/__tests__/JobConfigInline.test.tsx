// Tests for JobConfigInline — replaces JobConfigDialog modal flow.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  JobConfigInline,
  defaultProjectName,
  type ChosenSource,
} from "../JobConfigInline";
import type {
  JobForm,
  RuntimeConfig,
} from "../../statecharts/jobCreationTypes";
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

interface RenderInlineOptions {
  source?: ChosenSource;
  fetchMock?: ReturnType<typeof vi.fn>;
  mode?: "local" | "managed";
  onCancel?: () => void;
  onSubmitJob?: (form: JobForm) => void;
  onFormChanged?: (patch: Partial<JobForm>) => void;
  runtimeConfig?: RuntimeConfig | null;
  submitError?: string | null;
  submitting?: boolean;
}

function makeRuntimeConfig({
  mode = "local",
  tesseractAvailable = true,
}: {
  mode?: "local" | "managed";
  tesseractAvailable?: boolean;
} = {}): RuntimeConfig {
  return {
    mode,
    is_containerized: false,
    detected_device: "cpu",
    gpu_available: false,
    ocr_engines: [
      { id: "doctr", label: "DocTR", available: true, reason: null },
      {
        id: "tesseract",
        label: "Tesseract",
        available: tesseractAvailable,
        reason: tesseractAvailable
          ? null
          : "Tesseract language data is unavailable.",
      },
    ],
  };
}

function renderInline({
  source = { kind: "path", path: "/tmp/scans" },
  fetchMock,
  mode = "local",
  onCancel,
  onSubmitJob,
  onFormChanged,
  runtimeConfig = makeRuntimeConfig({ mode }),
  submitError,
  submitting,
}: RenderInlineOptions = {}) {
  const defaultFetch = vi
    .fn()
    .mockImplementation((url: string, opts?: RequestInit) => {
      if (url === "/api/prefs" && (!opts || opts.method !== "POST")) {
        // Correct keys: AppPrefs exposes default_engine / default_language
        // (not engine / language — those were the B-HOME-006 regression keys).
        return Promise.resolve({
          ok: true,
          json: async () => ({
            default_engine: "doctr",
            default_language: "en",
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
  (globalThis as unknown as { fetch: typeof fetch }).fetch =
    mockFetch as unknown as typeof fetch;

  const result = renderWithProviders(
    <JobConfigInline
      source={source}
      mode={mode}
      onCancel={onCancel}
      onSubmitJob={onSubmitJob}
      onFormChanged={onFormChanged}
      runtimeConfig={runtimeConfig}
      submitError={submitError}
      submitting={submitting}
    />,
    { route: "/" },
  );

  return { ...result, mockFetch };
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
    renderInline({ source: { kind: "path", path: "/tmp/my-book" } });
    const nameInput = (await screen.findByLabelText(
      /project name/i,
    )) as HTMLInputElement;
    expect(nameInput.value).toBe("my-book");
  });

  it("pre-fills project name as ocr-job-<short> for uploads", async () => {
    renderInline({ source: { kind: "upload", uploadId: "abcdef123456" } });
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

  it("emits the expected job form for path source submit", async () => {
    const user = userEvent.setup();
    const onSubmitJob = vi.fn();
    renderInline({
      source: { kind: "path", path: "/tmp/scans" },
      onSubmitJob,
    });
    const submit = await screen.findByTestId("run-ocr-button");
    await user.click(submit);

    await waitFor(() => {
      expect(onSubmitJob).toHaveBeenCalledTimes(1);
      const form = onSubmitJob.mock.calls[0][0] as JobForm;
      expect(form.name).toBe("scans");
      expect(form.engine).toBe("doctr");
      expect(form.language).toBe("en");
      expect(form).not.toHaveProperty("source_path");
      expect(form).not.toHaveProperty("upload_id");
      expect(form).not.toHaveProperty("output_dir");
      // B-HOME-011 cleanup: no save_json / combined_txt knob in the body.
      expect(form).not.toHaveProperty("save_json");
      expect(form).not.toHaveProperty("combined_txt");
      expect(form.device).toBe("auto");
      expect(form.batch_pages).toBeNull();
      expect(form.output).toEqual({ mode: "next_to_source" });
    });
  });

  it("submits Tesseract English as eng while leaving the field as en", async () => {
    const user = userEvent.setup();
    const onSubmitJob = vi.fn();
    renderInline({
      source: { kind: "path", path: "/tmp/scans" },
      onSubmitJob,
      runtimeConfig: makeRuntimeConfig({ tesseractAvailable: true }),
    });

    const engineSelect = (await screen.findByLabelText(
      /engine/i,
    )) as HTMLSelectElement;
    const langInput = (await screen.findByLabelText(
      /language/i,
    )) as HTMLInputElement;
    await user.selectOptions(engineSelect, "tesseract");
    expect(langInput.value).toBe("en");

    await user.click(await screen.findByTestId("run-ocr-button"));

    await waitFor(() => {
      expect(onSubmitJob).toHaveBeenCalledTimes(1);
      const form = onSubmitJob.mock.calls[0][0] as JobForm;
      expect(form.engine).toBe("tesseract");
      expect(form.language).toBe("eng");
      expect(langInput.value).toBe("en");
    });
  });

  it("emits a managed output job form for upload source submit", async () => {
    const user = userEvent.setup();
    const onSubmitJob = vi.fn();
    renderInline({
      source: { kind: "upload", uploadId: "upload-xyz" },
      mode: "managed",
      onSubmitJob,
    });
    const submit = await screen.findByTestId("run-ocr-button");
    await user.click(submit);

    await waitFor(() => {
      expect(onSubmitJob).toHaveBeenCalledTimes(1);
      const form = onSubmitJob.mock.calls[0][0] as JobForm;
      expect(form).not.toHaveProperty("upload_id");
      expect(form).not.toHaveProperty("source_path");
      expect(form.output).toEqual({ mode: "managed" });
    });
  });

  it("does not submit directly when onSubmitJob is provided", async () => {
    const user = userEvent.setup();
    const onSubmitJob = vi.fn();
    const { mockFetch } = renderInline({ onSubmitJob });
    const submit = await screen.findByTestId("run-ocr-button");
    await user.click(submit);

    await waitFor(() => {
      expect(onSubmitJob).toHaveBeenCalledTimes(1);
    });
    expect(
      mockFetch.mock.calls.some(
        ([url, opts]: [string, RequestInit | undefined]) =>
          url === "/api/jobs" && opts?.method === "POST",
      ),
    ).toBe(false);
  });

  it("shows controlled submit error", async () => {
    renderInline({ submitError: "bad request" });
    expect(await screen.findByRole("alert")).toHaveTextContent(/bad request/i);
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
    renderInline({
      source: { kind: "path", path: "/tmp/scans" },
      mode: "local",
      onCancel,
    });
    const cancel = await screen.findByTestId("job-config-inline-cancel");
    await user.click(cancel);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  // B-HOME-006 (Regression): GET /api/prefs returns default_engine /
  // default_language (the AppPrefs shape), NOT engine / language. The form
  // must seed its engine + language fields from those keys so a saved default
  // actually applies instead of silently no-op'ing back to doctr/en.
  it("seeds engine + language from prefs default_engine/default_language", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, opts?: RequestInit) => {
        if (url === "/api/prefs" && (!opts || opts.method !== "POST")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              default_engine: "tesseract",
              default_language: "fr",
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
    renderInline({
      source: { kind: "path", path: "/tmp/scans" },
      fetchMock,
      runtimeConfig: makeRuntimeConfig({ tesseractAvailable: true }),
    });

    const engineSelect = (await screen.findByLabelText(
      /engine/i,
    )) as HTMLSelectElement;
    const langInput = (await screen.findByLabelText(
      /language/i,
    )) as HTMLInputElement;

    await waitFor(() => {
      expect(engineSelect.value).toBe("tesseract");
      expect(langInput.value).toBe("fr");
    });
  });

  it("emits the prefs-seeded engine/language in the submitted form", async () => {
    const user = userEvent.setup();
    const onSubmitJob = vi.fn();
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, opts?: RequestInit) => {
        if (url === "/api/prefs" && (!opts || opts.method !== "POST")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              default_engine: "tesseract",
              default_language: "de",
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
    renderInline({
      source: { kind: "path", path: "/tmp/scans" },
      fetchMock,
      onSubmitJob,
      runtimeConfig: makeRuntimeConfig({ tesseractAvailable: true }),
    });

    // Wait for the seed to land before submitting.
    const engineSelect = (await screen.findByLabelText(
      /engine/i,
    )) as HTMLSelectElement;
    await waitFor(() => expect(engineSelect.value).toBe("tesseract"));

    await user.click(await screen.findByTestId("run-ocr-button"));

    await waitFor(() => {
      expect(onSubmitJob).toHaveBeenCalledTimes(1);
      const form = onSubmitJob.mock.calls[0][0] as JobForm;
      expect(form.engine).toBe("tesseract");
      expect(form.language).toBe("de");
      const submitCalls = fetchMock.mock.calls.filter(
        ([url]: [string, RequestInit | undefined]) => url === "/api/jobs",
      );
      expect(submitCalls).toHaveLength(0);
    });
  });

  it("emits form patches as fields change", async () => {
    const user = userEvent.setup();
    const onFormChanged = vi.fn();
    renderInline({ onFormChanged });

    const nameInput = await screen.findByLabelText(/project name/i);
    await user.clear(nameInput);
    await user.type(nameInput, "new scans");

    await waitFor(() => {
      expect(onFormChanged).toHaveBeenCalledWith({ name: "new scans" });
    });
  });

  it("uses the controlled submitting state", async () => {
    renderInline({ submitting: true });
    const submit = await screen.findByTestId("run-ocr-button");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/run ocr/i);
  });

  // B-HOME-006: fresh prefs (empty response) must still show doctr as default.
  // This is the settings-driven default — AppPrefs.default_engine defaults to
  // "doctr", so a fresh install with no persisted prefs must show doctr without
  // user interaction.
  it("shows doctr as default when prefs returns empty object (fresh install)", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, opts?: RequestInit) => {
        if (url === "/api/prefs" && (!opts || opts.method !== "POST")) {
          // Empty prefs response — simulates a fresh install with no saved defaults.
          return Promise.resolve({
            ok: true,
            json: async () => ({}),
          });
        }
        return Promise.resolve({ ok: false, json: async () => ({}) });
      });
    renderInline({
      source: { kind: "path", path: "/tmp/scans" },
      fetchMock,
    });

    const engineSelect = (await screen.findByLabelText(
      /engine/i,
    )) as HTMLSelectElement;

    // After prefs fetch with empty body, the component must keep doctr (the
    // hardcoded init default). An empty default_engine does not overwrite a
    // valid doctr default.
    await waitFor(() => {
      expect(engineSelect.value).toBe("doctr");
    });
  });

  // B-HOME-006: explicit default_engine=doctr in prefs → select shows doctr.
  it("shows doctr as selected when prefs.default_engine is doctr", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, opts?: RequestInit) => {
        if (url === "/api/prefs" && (!opts || opts.method !== "POST")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              default_engine: "doctr",
              default_language: "en",
            }),
          });
        }
        return Promise.resolve({ ok: false, json: async () => ({}) });
      });
    renderInline({
      source: { kind: "path", path: "/tmp/scans" },
      fetchMock,
    });

    const engineSelect = (await screen.findByLabelText(
      /engine/i,
    )) as HTMLSelectElement;

    await waitFor(() => {
      expect(engineSelect.value).toBe("doctr");
    });
  });

  it("hides Tesseract and shows setup link when Tesseract is unavailable", async () => {
    renderInline({
      runtimeConfig: makeRuntimeConfig({ tesseractAvailable: false }),
    });

    const engineSelect = (await screen.findByLabelText(
      /engine/i,
    )) as HTMLSelectElement;

    expect(engineSelect.value).toBe("doctr");
    expect(screen.queryByRole("option", { name: /tesseract/i })).toBeNull();
    expect(
      screen.getByRole("link", { name: /want to use tesseract/i }),
    ).toHaveAttribute("href", "/help/tesseract");
  });

  it("falls back to DocTR when prefs default to unavailable Tesseract", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, opts?: RequestInit) => {
        if (url === "/api/prefs" && (!opts || opts.method !== "POST")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              default_engine: "tesseract",
              default_language: "fr",
            }),
          });
        }
        return Promise.resolve({ ok: false, json: async () => ({}) });
      });
    renderInline({
      fetchMock,
      runtimeConfig: makeRuntimeConfig({ tesseractAvailable: false }),
    });

    const engineSelect = (await screen.findByLabelText(
      /engine/i,
    )) as HTMLSelectElement;
    const langInput = (await screen.findByLabelText(
      /language/i,
    )) as HTMLInputElement;

    await waitFor(() => {
      expect(engineSelect.value).toBe("doctr");
      expect(langInput.value).toBe("fr");
    });
  });
});
