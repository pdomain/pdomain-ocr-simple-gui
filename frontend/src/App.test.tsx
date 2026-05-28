// Tests for App.tsx — AppShell renders without crashing + routing skeleton
// Issue #226

import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";

// Mock @pdomain/pdomain-ui/shell — we test App routing, not AppShell internals.
// AppShell itself uses complex CSS and zustand stores that don't run well in jsdom.
vi.mock("@pdomain/pdomain-ui/shell", () => ({
  AppShell: ({ main }: { main: React.ReactNode }) => (
    <div data-testid="app-shell-mock">{main}</div>
  ),
  AppHeader: () => <div data-testid="app-header-mock" />,
  SuiteSiblingsProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  ShortcutsHelpButton: () => <div data-testid="shortcuts-help-button-mock" />,
}));

vi.mock("@pdomain/pdomain-ui/hooks", () => ({
  ShortcutsProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useShortcuts: () => undefined,
  formatShortcut: (keys: string) => [keys],
}));

// Mock @pdomain/pdomain-ui/stages/PageWorkbench — ArtifactViewer uses Konva
// which requires a native 'canvas' module not available in jsdom.
vi.mock("@pdomain/pdomain-ui/stages/PageWorkbench", () => ({
  ArtifactViewer: ({ imageSrc }: { imageSrc: string }) => (
    <div data-testid="artifact-viewer-mock" data-src={imageSrc} />
  ),
}));

// Keep canvas mock for any remaining direct canvas consumers.
vi.mock("@pdomain/pdomain-ui/canvas", () => ({
  PageImageCanvas: ({ src }: { src: string }) => (
    <div data-testid="page-image-canvas-mock" data-src={src} />
  ),
}));

// Suppress jsdom fetch warnings in tests
beforeAll(() => {
  (globalThis as any).fetch = vi.fn().mockImplementation((url: string) => {
    // ConfigProvider fetches /api/config on mount — return a valid config so
    // HomePage renders rather than showing "Loading…".
    if (typeof url === "string" && url.includes("/api/config")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ mode: "local", is_containerized: false }),
      });
    }
    return Promise.resolve({
      ok: false,
      json: async () => ({}),
    });
  });
});

function renderWithQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("App", () => {
  it("renders without crashing and shows home page at /", async () => {
    renderWithQueryClient(<App />);
    // The AppShell mock renders its main slot which contains AppRoutes
    const shell = screen.getByTestId("app-shell-mock");
    expect(shell).toBeInTheDocument();
    // At default path "/" we should see the home page — async because
    // ConfigProvider fetches /api/config before HomePage renders content.
    expect(await screen.findByTestId("home-page")).toBeInTheDocument();
  });

  it("AppShell mock receives a main prop", () => {
    renderWithQueryClient(<App />);
    expect(screen.getByTestId("app-shell-mock")).toBeInTheDocument();
  });
});
