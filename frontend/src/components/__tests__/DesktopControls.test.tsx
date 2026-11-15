import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../api/apiFetch";
import { DesktopControls } from "../DesktopControls";

vi.mock("../../api/apiFetch", () => ({ apiFetch: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
});

function setup(quitReplies: object[]) {
  vi.stubGlobal(
    "WebSocket",
    class {
      close() {}
    },
  );
  vi.mocked(apiFetch).mockImplementation(async (url) => {
    if (url === "/api/lifecycle/bootstrap") {
      return Response.json({ managed: true, instance_id: "a".repeat(32) });
    }
    const reply = quitReplies.shift();
    if (!reply) throw new Error("Unexpected quit request");
    return Response.json(reply);
  });
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <DesktopControls />
    </QueryClientProvider>,
  );
  return { user: userEvent.setup(), client };
}

describe("desktop app controls", () => {
  it("keeps the app running while OCR is active", async () => {
    const { user, client } = setup([
      {
        accepted: false,
        live_tabs: 1,
        active_operations: 1,
        message: "Work is still running.",
      },
    ]);
    try {
      await user.click(await screen.findByRole("button", { name: "Quit app" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Work is still running.",
      );
      expect(screen.getByRole("button", { name: "Quit app" })).toBeEnabled();
      expect(
        screen.queryByRole("button", { name: "Quit all tabs" }),
      ).not.toBeInTheDocument();
    } finally {
      client.clear();
    }
  });

  it("asks before quitting other tabs and shows the stopped state", async () => {
    const { user, client } = setup([
      {
        accepted: false,
        live_tabs: 2,
        active_operations: 0,
        message: "Another tab is open.",
      },
      {
        accepted: true,
        live_tabs: 2,
        active_operations: 0,
        message: "App is stopping.",
      },
    ]);
    try {
      await user.click(await screen.findByRole("button", { name: "Quit app" }));
      await user.click(
        await screen.findByRole("button", { name: "Quit all tabs" }),
      );
      await waitFor(() =>
        expect(
          screen.queryByRole("button", { name: "Quit app" }),
        ).not.toBeInTheDocument(),
      );
      expect(screen.getByRole("status")).toHaveTextContent(
        "Open the app icon to start again.",
      );
      expect(vi.mocked(apiFetch)).toHaveBeenLastCalledWith(
        "/api/lifecycle/browser-quit",
        expect.objectContaining({
          body: expect.stringContaining('"confirm_other_tabs":true,"page_id":'),
        }),
      );
    } finally {
      client.clear();
    }
  });
});
