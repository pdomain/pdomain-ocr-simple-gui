/**
 * TDD tests for HomePage keyboard shortcut binding (B-SHELL-013).
 *
 * Q3 from the M6 interview: "add a real useShortcuts binding to HomePage so
 * the cheatsheet is not empty when on the home route."
 *
 * Chosen binding: "n" key → focus/trigger the source picker (open the file
 * picker or trigger the path input).  Safe, non-destructive, and visible to
 * the user in the cheatsheet.
 *
 * These tests verify:
 * 1. useShortcuts is called by HomePage with at least one binding.
 * 2. The binding keys include "n" (the chosen home shortcut).
 * 3. Pressing the "n" key actually calls the binding handler (e.g. triggers
 *    focus on the path input).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "../../runtime/ConfigContext";
import { HomePage } from "../HomePage";

// Capture useShortcuts calls
const registeredBindings: {
  keys: string;
  label: string;
  handler: () => void;
}[] = [];

vi.mock("@pdomain/pdomain-ui/hooks", () => ({
  ShortcutsProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useShortcuts: (
    bindings: { keys: string; label: string; handler: () => void }[],
  ) => {
    // Capture the bindings registered by HomePage.
    registeredBindings.splice(0, registeredBindings.length, ...bindings);
  },
  formatShortcut: (keys: string) => [keys],
}));

// Mock JobConfigInline — keep it trivial
vi.mock("../../components/JobConfigInline", () => ({
  JobConfigInline: () => <div data-testid="job-config-inline" />,
}));

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
}

function renderHomePage(mode = "local", containerized = false) {
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({ mode, is_containerized: containerized }),
  })) as unknown as typeof fetch;

  const client = makeQueryClient();
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ConfigProvider>
          <HomePage />
        </ConfigProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  registeredBindings.splice(0);
});

describe("HomePage shortcut binding (B-SHELL-013)", () => {
  it("registers at least one keyboard binding via useShortcuts", async () => {
    renderHomePage();
    // Wait for the page to resolve config and render
    await screen.findByTestId("home-page");
    expect(registeredBindings.length).toBeGreaterThan(0);
  });

  it("the registered binding keys include 'n' (New source / open picker)", async () => {
    renderHomePage();
    await screen.findByTestId("home-page");
    const nBinding = registeredBindings.find((b) => b.keys === "n");
    expect(nBinding).toBeDefined();
  });

  it("the 'n' binding has a human-readable label shown in cheatsheet", async () => {
    renderHomePage();
    await screen.findByTestId("home-page");
    const nBinding = registeredBindings.find((b) => b.keys === "n");
    expect(nBinding?.label).toBeTruthy();
    // Should mention source, picker, or path in the label
    expect(nBinding?.label.toLowerCase()).toMatch(/source|pick|path|new/);
  });

  it("the 'n' binding handler focuses the source path input (local mode)", async () => {
    renderHomePage("local", false);
    await screen.findByTestId("home-page");

    const pathInput = screen.getByTestId("source-picker-path-input");
    expect(document.activeElement).not.toBe(pathInput);

    // Invoke the 'n' binding handler directly (useShortcuts is mocked —
    // we call the captured handler rather than simulating a real keydown).
    const nBinding = registeredBindings.find((b) => b.keys === "n");
    expect(nBinding).toBeDefined();
    nBinding!.handler();

    // The binding should focus the path input
    expect(document.activeElement).toBe(pathInput);
  });
});
