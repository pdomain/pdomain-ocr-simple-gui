// Tests for ConfigContext — A6.1 + B-HOME-014 error surfacing.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  ConfigProvider,
  useConfig,
  useConfigStatus,
} from "../ConfigContext";

function Probe() {
  const cfg = useConfig();
  const { error, reload } = useConfigStatus();
  if (error)
    return (
      <button type="button" onClick={() => void reload()}>
        error
      </button>
    );
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

// B-HOME-014 (Regression): a failed /api/config must surface an error state
// (not hang on "loading" forever). The provider exposes useConfigStatus().error.
it("surfaces an error state when /api/config returns non-ok", async () => {
  globalThis.fetch = (async (_url: string) => ({
    ok: false,
    json: async () => ({}),
  })) as unknown as typeof fetch;
  render(
    <ConfigProvider>
      <Probe />
    </ConfigProvider>,
  );
  await waitFor(() =>
    expect(screen.getByText("error")).toBeInTheDocument(),
  );
});

it("surfaces an error state when /api/config throws a network error", async () => {
  globalThis.fetch = (() =>
    Promise.reject(new Error("Network error"))) as unknown as typeof fetch;
  render(
    <ConfigProvider>
      <Probe />
    </ConfigProvider>,
  );
  await waitFor(() =>
    expect(screen.getByText("error")).toBeInTheDocument(),
  );
});

it("reload() re-fetches and clears the error on success", async () => {
  const user = userEvent.setup();
  let calls = 0;
  globalThis.fetch = (async (_url: string) => {
    calls += 1;
    if (calls === 1) return { ok: false, json: async () => ({}) };
    return {
      ok: true,
      json: async () => ({ mode: "managed", is_containerized: false }),
    };
  }) as unknown as typeof fetch;
  render(
    <ConfigProvider>
      <Probe />
    </ConfigProvider>,
  );
  // First load fails → error button shown.
  await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
  // Click retry → second load succeeds.
  await user.click(screen.getByText("error"));
  await waitFor(() =>
    expect(screen.getByText("managed/false")).toBeInTheDocument(),
  );
});
