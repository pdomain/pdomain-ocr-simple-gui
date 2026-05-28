// Tests for ConfigContext — A6.1
import { render, screen, waitFor } from "@testing-library/react";
import { ConfigProvider, useConfig } from "../ConfigContext";

function Probe() {
  const cfg = useConfig();
  if (!cfg) return <span>loading</span>;
  return <span>{`${cfg.mode}/${cfg.is_containerized}`}</span>;
}

it("fetches /api/config on mount", async () => {
  globalThis.fetch = (async (_url: string) => ({
    ok: true,
    json: async () => ({ mode: "local", is_containerized: true }),
  })) as unknown as typeof fetch;
  render(
    <ConfigProvider>
      <Probe />
    </ConfigProvider>,
  );
  await waitFor(() => screen.getByText("local/true"));
});

it("keeps loading state when /api/config fetch fails (non-ok response)", async () => {
  // ConfigProvider catches errors silently and keeps cfg=null (loading).
  // Children should remain in the loading/fallback state, not crash.
  globalThis.fetch = (async (_url: string) => ({
    ok: false,
    json: async () => ({}),
  })) as unknown as typeof fetch;
  render(
    <ConfigProvider>
      <Probe />
    </ConfigProvider>,
  );
  // Give the effect time to resolve
  await new Promise((r) => setTimeout(r, 50));
  // cfg stays null → Probe shows "loading"
  expect(screen.getByText("loading")).toBeInTheDocument();
});

it("keeps loading state when /api/config fetch throws a network error", async () => {
  globalThis.fetch = (() =>
    Promise.reject(new Error("Network error"))) as unknown as typeof fetch;
  render(
    <ConfigProvider>
      <Probe />
    </ConfigProvider>,
  );
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.getByText("loading")).toBeInTheDocument();
});
