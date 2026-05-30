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
