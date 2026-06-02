// Tests for HomePage layout matrix.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HomePage } from "../HomePage";
import type { JobForm } from "../../statecharts/jobCreationTypes";

const mockSubmitForm: JobForm = {
  name: "scans",
  engine: "doctr",
  language: "en",
  straight_quotes: true,
  em_dash_to_double_hyphen: true,
  emit_illustration_placeholders: false,
  device: "auto",
  batch_pages: null,
  output: { mode: "managed" },
};

vi.mock("../../components/JobConfigInline", () => ({
  JobConfigInline: ({
    onCancel,
    onSubmitJob,
    submitError,
    submitting,
  }: {
    onCancel?: () => void;
    onSubmitJob?: (form: JobForm) => void;
    submitError?: string | null;
    submitting?: boolean;
  }) => (
    <div data-testid="job-config-inline">
      {submitError ? <p role="alert">{submitError}</p> : null}
      <button type="button" onClick={onCancel} data-testid="mock-cancel">
        Cancel
      </button>
      <button
        type="button"
        disabled={submitting}
        onClick={() => onSubmitJob?.(mockSubmitForm)}
      >
        Run OCR
      </button>
    </div>
  ),
}));

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
}

function installFetch(cfg: {
  mode: "local" | "managed";
  is_containerized: boolean;
  recentProjects?: Array<Record<string, unknown>>;
}) {
  globalThis.fetch = vi
    .fn()
    .mockImplementation((url: string, opts?: RequestInit) => {
      if (url === "/api/config") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ...cfg,
            detected_device: "cpu",
            gpu_available: false,
          }),
        });
      }
      if (url === "/api/prefs") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recent_projects: cfg.recentProjects ?? [] }),
        });
      }
      if (url === "/api/uploads" && opts?.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ upload_id: "test-upload-123" }),
        });
      }
      if (url === "/api/jobs" && opts?.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ project_id: "job-123" }),
        });
      }
      return Promise.resolve({ ok: false, json: async () => ({}) });
    }) as unknown as typeof fetch;
}

function installConfigErrorThenSuccess() {
  let attempts = 0;
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url === "/api/config") {
      attempts += 1;
      if (attempts === 1) {
        return Promise.resolve({ ok: false, json: async () => ({}) });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          mode: "local",
          is_containerized: false,
          detected_device: "cpu",
          gpu_available: false,
        }),
      });
    }
    if (url === "/api/prefs") {
      return Promise.resolve({
        ok: true,
        json: async () => ({ recent_projects: [] }),
      });
    }
    return Promise.resolve({ ok: false, json: async () => ({}) });
  }) as unknown as typeof fetch;
}

function LocationCapture({
  onLocation,
}: {
  onLocation: (path: string) => void;
}) {
  const location = useLocation();
  onLocation(location.pathname);
  return null;
}

function renderTree(onLocation?: (path: string) => void) {
  const client = makeQueryClient();
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route
            path="/jobs/:id"
            element={<LocationCapture onLocation={onLocation ?? (() => {})} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

it("local + containerized shows drop zone and path input", async () => {
  installFetch({ mode: "local", is_containerized: true });
  render(renderTree());
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();
});

it("local + not containerized shows drop, file pick, and path together", async () => {
  installFetch({ mode: "local", is_containerized: false });
  render(renderTree());
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-file-pick")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /browse folder/i }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /choose file/i }),
  ).toBeInTheDocument();
  expect(screen.getByText(/or paste a path/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^open$/i })).toBeInTheDocument();
  expect(screen.queryByText(/recent:/i)).toBeNull();
});

it("source picker recent paths render from prefs source_path values", async () => {
  installFetch({
    mode: "local",
    is_containerized: false,
    recentProjects: [
      {
        project_id: "job-1",
        name: "Belloc",
        source_path: "/Users/jess/scans/belloc",
      },
      {
        project_id: "job-2",
        name: "Fragment",
        source_path: "/Users/jess/scans/fragment.pdf",
      },
    ],
  });
  render(renderTree());

  expect(await screen.findByText(/recent:/i)).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "/Users/jess/scans/belloc" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "/Users/jess/scans/fragment.pdf" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("belloc-survivals.zip")).toBeNull();
});

it("source picker hides recent paths when prefs has projects without source paths", async () => {
  installFetch({
    mode: "local",
    is_containerized: false,
    recentProjects: [
      {
        project_id: "job-1",
        name: "Belloc",
      },
    ],
  });
  render(renderTree());

  await screen.findByTestId("source-picker-drop");
  expect(screen.queryByText(/recent:/i)).toBeNull();
  expect(screen.queryByText("belloc-survivals.zip")).toBeNull();
});

it("managed shows upload-only with no path affordances", async () => {
  installFetch({ mode: "managed", is_containerized: false });
  render(renderTree());
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.queryByTestId("source-picker-path-input")).toBeNull();
  expect(screen.queryByText(/or paste a path/i)).toBeNull();
  expect(screen.queryByText(/recent:/i)).toBeNull();
});

// B-HOME-014 (Regression): a failed /api/config must surface an error message
// + retry affordance instead of hanging on "Loading..." forever.
it("shows an error state (not infinite loading) when /api/config fails", async () => {
  installConfigErrorThenSuccess();
  const user = userEvent.setup();
  render(renderTree());

  expect(await screen.findByTestId("home-config-error")).toBeInTheDocument();
  expect(screen.getByTestId("home-config-retry")).toBeInTheDocument();
  expect(screen.queryByText("Loading...")).toBeNull();

  await user.click(screen.getByTestId("home-config-retry"));
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
});

it("JobConfigInline is hidden until a source is chosen", async () => {
  installFetch({ mode: "local", is_containerized: false });
  render(renderTree());
  await screen.findByTestId("source-picker-drop");
  expect(screen.queryByTestId("job-config-inline")).toBeNull();
});

it("JobConfigInline appears after a path is chosen, and clears on cancel", async () => {
  installFetch({ mode: "local", is_containerized: false });
  const user = userEvent.setup();
  render(renderTree());

  const pathInput = await screen.findByTestId("source-picker-path-input");
  await user.type(pathInput, "/tmp/scans");
  await user.click(screen.getByRole("button", { name: /^open$/i }));

  expect(await screen.findByTestId("job-config-inline")).toBeInTheDocument();

  await user.click(screen.getByTestId("mock-cancel"));
  expect(screen.queryByTestId("job-config-inline")).toBeNull();
});

it("navigates to the submitted job when the machine submit succeeds", async () => {
  installFetch({ mode: "local", is_containerized: false });
  const user = userEvent.setup();
  const locations: string[] = [];
  render(renderTree((path) => locations.push(path)));

  const pathInput = await screen.findByTestId("source-picker-path-input");
  await user.type(pathInput, "/tmp/scans");
  await user.click(screen.getByRole("button", { name: /^open$/i }));
  await user.click(await screen.findByRole("button", { name: /run ocr/i }));

  await waitFor(() => {
    expect(locations).toContain("/jobs/job-123");
  });
});

it("local+containerized: choosing upload hides the path input", async () => {
  installFetch({ mode: "local", is_containerized: true });
  const user = userEvent.setup();
  render(renderTree());

  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();

  const file = new File(["fake"], "scan.png", { type: "image/png" });
  await user.upload(screen.getByTestId("source-picker-file-pick"), file);

  await screen.findByTestId("job-config-inline");
  expect(screen.queryByTestId("source-picker-path-input")).toBeNull();
});

it("local+containerized: choosing path hides the upload drop zone", async () => {
  installFetch({ mode: "local", is_containerized: true });
  const user = userEvent.setup();
  render(renderTree());

  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();

  const pathInput = screen.getByTestId("source-picker-path-input");
  await user.type(pathInput, "/tmp/scans");
  await user.click(screen.getByRole("button", { name: /^open$/i }));

  await screen.findByTestId("job-config-inline");
  expect(screen.queryByTestId("source-picker-drop")).toBeNull();
});

it("local+containerized: clearing upload restores both source inputs", async () => {
  installFetch({ mode: "local", is_containerized: true });
  const user = userEvent.setup();
  render(renderTree());

  await screen.findByTestId("source-picker-drop");

  const file = new File(["fake"], "scan.png", { type: "image/png" });
  await user.upload(screen.getByTestId("source-picker-file-pick"), file);
  await screen.findByTestId("job-config-inline");

  expect(screen.queryByTestId("source-picker-path-input")).toBeNull();

  await user.click(screen.getByTestId("mock-cancel"));

  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();
});

it("clearing an uploaded source deletes the staged upload", async () => {
  installFetch({ mode: "local", is_containerized: true });
  const user = userEvent.setup();
  render(renderTree());

  await screen.findByTestId("source-picker-drop");

  const file = new File(["fake"], "scan.png", { type: "image/png" });
  await user.upload(screen.getByTestId("source-picker-file-pick"), file);
  await screen.findByTestId("job-config-inline");

  await user.click(screen.getByTestId("mock-cancel"));

  await waitFor(() => {
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/uploads/test-upload-123",
      { method: "DELETE" },
    );
  });
});
