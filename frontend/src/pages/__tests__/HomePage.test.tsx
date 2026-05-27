// Tests for HomePage layout matrix — A6.3
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "../../runtime/ConfigContext";
import { HomePage } from "../HomePage";

// Mock JobConfigDialog — not under test here
vi.mock("../../components/JobConfigDialog", () => ({
  JobConfigDialog: () => null,
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
