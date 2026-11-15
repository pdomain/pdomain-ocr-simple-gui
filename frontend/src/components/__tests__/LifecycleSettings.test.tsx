import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { apiFetch } from "../../api/apiFetch";
import { LifecycleSettings } from "../LifecycleSettings";

vi.mock("../../api/apiFetch", () => ({ apiFetch: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("persists the server's keep-running choice", async () => {
  let keepRunning = false;
  vi.mocked(apiFetch).mockImplementation(async (path) => {
    if (path === "/api/lifecycle/bootstrap")
      return Response.json({ managed: true });
    if (path === "/api/prefs")
      return Response.json({ keep_running: keepRunning });
    if (path === "/api/lifecycle/options") {
      keepRunning = true;
      return Response.json({ keep_running: true });
    }
    throw new Error("Unexpected request");
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  try {
    render(
      <QueryClientProvider client={client}>
        <LifecycleSettings />
      </QueryClientProvider>,
    );
    const checkbox = await screen.findByRole("checkbox", {
      name: "Keep app running after all tabs close",
    });
    expect(checkbox).not.toBeChecked();
    await userEvent.click(checkbox);
    await waitFor(() => expect(checkbox).toBeChecked());
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/lifecycle/options",
      expect.objectContaining({ body: JSON.stringify({ keep_running: true }) }),
    );
  } finally {
    client.clear();
  }
});

it("explains an independently managed session without offering an ineffective toggle", async () => {
  vi.mocked(apiFetch).mockResolvedValue(Response.json({ managed: false }));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  try {
    render(
      <QueryClientProvider client={client}>
        <LifecycleSettings />
      </QueryClientProvider>,
    );
    expect(
      await screen.findByText(
        "This session keeps running until it is stopped.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  } finally {
    client.clear();
  }
});
