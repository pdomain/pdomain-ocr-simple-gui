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
