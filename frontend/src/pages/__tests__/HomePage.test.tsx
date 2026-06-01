// Tests for HomePage layout matrix.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "../../runtime/ConfigContext";
import { HomePage } from "../HomePage";

// Mock JobConfigInline — keep render trivial so HomePage tests focus on
// layout matrix + chosen-source visibility, not the config form internals.
vi.mock("../../components/JobConfigInline", () => ({
  JobConfigInline: ({ onCancel }: { onCancel?: () => void }) => (
    <div data-testid="job-config-inline">
      <button type="button" onClick={onCancel} data-testid="mock-cancel">
        Cancel
      </button>
    </div>
  ),
}));

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
}

function withConfig(cfg: { mode: string; is_containerized: boolean }) {
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => cfg,
  })) as unknown as typeof fetch;
  return renderTree();
}

function withConfigError() {
  globalThis.fetch = (async () => ({
    ok: false,
    json: async () => ({}),
  })) as unknown as typeof fetch;
  return renderTree();
}

function renderTree() {
  const client = makeQueryClient();
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ConfigProvider>
          <HomePage />
        </ConfigProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

it("local + containerized shows drop zone and path input", async () => {
  render(withConfig({ mode: "local", is_containerized: true }));
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();
});

it("local + not containerized shows drop, file pick, and path together", async () => {
  render(withConfig({ mode: "local", is_containerized: false }));
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-file-pick")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();
});

it("managed shows upload-only (no path input)", async () => {
  render(withConfig({ mode: "managed", is_containerized: false }));
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.queryByTestId("source-picker-path-input")).toBeNull();
});

// B-HOME-014 (Regression): a failed /api/config must surface an error message
// + retry affordance instead of hanging on "Loading…" forever.
it("shows an error state (not infinite loading) when /api/config fails", async () => {
  render(withConfigError());
  expect(await screen.findByTestId("home-config-error")).toBeInTheDocument();
  expect(screen.getByTestId("home-config-retry")).toBeInTheDocument();
  // Must NOT be stuck on the loading text.
  expect(screen.queryByText("Loading…")).toBeNull();
});

it("JobConfigInline is hidden until a source is chosen", async () => {
  render(withConfig({ mode: "local", is_containerized: false }));
  await screen.findByTestId("source-picker-drop");
  expect(screen.queryByTestId("job-config-inline")).toBeNull();
});

it("JobConfigInline appears after a path is chosen, and clears on cancel", async () => {
  const user = userEvent.setup();
  render(withConfig({ mode: "local", is_containerized: false }));

  // Simulate path input → triggers onPathChosen → chosen set
  const pathInput = await screen.findByTestId("source-picker-path-input");
  await user.type(pathInput, "/tmp/scans");
  const useBtn = screen.getByRole("button", { name: /use this path/i });
  await user.click(useBtn);

  // After source chosen, inline config appears
  expect(await screen.findByTestId("job-config-inline")).toBeInTheDocument();

  // Click cancel → inline disappears
  const cancel = screen.getByTestId("mock-cancel");
  await user.click(cancel);
  expect(screen.queryByTestId("job-config-inline")).toBeNull();
});

// ---- Source-hide behavior (Change 1) ----
// In local+containerized mode, two SourcePickers are rendered (upload + path).
// Once one source is chosen, the alternative input must be hidden.
// Clearing the chosen source restores both inputs.

it("local+containerized: choosing upload hides the path input", async () => {
  // Mock fetch: config + uploads endpoint
  const origFetch = globalThis.fetch;
  globalThis.fetch = (async (url: string, opts?: RequestInit) => {
    if (typeof url === "string" && url.includes("/api/config")) {
      return {
        ok: true,
        json: async () => ({ mode: "local", is_containerized: true }),
      };
    }
    if (
      typeof url === "string" &&
      url.includes("/api/uploads") &&
      opts?.method === "POST"
    ) {
      return { ok: true, json: async () => ({ upload_id: "test-upload-123" }) };
    }
    return { ok: true, json: async () => ({}) };
  }) as unknown as typeof fetch;

  render(renderTree());

  // Both pickers visible initially (upload drop zone + path input)
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();

  // Simulate upload completing by triggering the SourcePicker file input
  // The upload picker's SourcePicker calls onUploadComplete → sets chosen
  // We simulate by using the file input
  const user = userEvent.setup();
  const file = new File(["fake"], "scan.png", { type: "image/png" });
  const fileInput = screen.getByTestId("source-picker-file-pick");
  await user.upload(fileInput, file);

  // After upload chosen: path input must be hidden; config form appears
  await screen.findByTestId("job-config-inline");
  expect(screen.queryByTestId("source-picker-path-input")).toBeNull();

  globalThis.fetch = origFetch;
});

it("local+containerized: choosing path hides the upload drop zone", async () => {
  globalThis.fetch = (async (url: string) => {
    if (typeof url === "string" && url.includes("/api/config")) {
      return {
        ok: true,
        json: async () => ({ mode: "local", is_containerized: true }),
      };
    }
    return { ok: true, json: async () => ({}) };
  }) as unknown as typeof fetch;

  const user = userEvent.setup();
  render(renderTree());

  // Both inputs visible initially
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();

  // Choose a path → triggers onPathChosen → sets chosen
  const pathInput = screen.getByTestId("source-picker-path-input");
  await user.type(pathInput, "/tmp/scans");
  const useBtn = screen.getByRole("button", { name: /use this path/i });
  await user.click(useBtn);

  // After path chosen: upload drop zone must be hidden
  await screen.findByTestId("job-config-inline");
  expect(screen.queryByTestId("source-picker-drop")).toBeNull();
});

it("local+containerized: clearing upload restores both source inputs", async () => {
  const origFetch = globalThis.fetch;
  globalThis.fetch = (async (url: string, opts?: RequestInit) => {
    if (typeof url === "string" && url.includes("/api/config")) {
      return {
        ok: true,
        json: async () => ({ mode: "local", is_containerized: true }),
      };
    }
    if (
      typeof url === "string" &&
      url.includes("/api/uploads") &&
      opts?.method === "POST"
    ) {
      return { ok: true, json: async () => ({ upload_id: "test-upload-456" }) };
    }
    if (
      typeof url === "string" &&
      url.includes("/api/uploads/") &&
      opts?.method === "DELETE"
    ) {
      return { ok: true, json: async () => ({}) };
    }
    return { ok: true, json: async () => ({}) };
  }) as unknown as typeof fetch;

  const user = userEvent.setup();
  render(renderTree());

  await screen.findByTestId("source-picker-drop");

  // Upload a file to choose a source
  const file = new File(["fake"], "scan.png", { type: "image/png" });
  const fileInput = screen.getByTestId("source-picker-file-pick");
  await user.upload(fileInput, file);
  await screen.findByTestId("job-config-inline");

  // Path input is now hidden
  expect(screen.queryByTestId("source-picker-path-input")).toBeNull();

  // Click the cancel button (mock-cancel is tied to handleCancel)
  // which resets chosen to null, restoring both inputs
  const cancel = screen.getByTestId("mock-cancel");
  await user.click(cancel);

  // Both source inputs restore
  expect(await screen.findByTestId("source-picker-drop")).toBeInTheDocument();
  expect(screen.getByTestId("source-picker-path-input")).toBeInTheDocument();

  globalThis.fetch = origFetch;
});
