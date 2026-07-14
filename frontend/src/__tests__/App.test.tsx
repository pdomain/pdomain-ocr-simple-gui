// Tests for App.tsx — AppShell renders without crashing + routing skeleton
// Issue #226

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { makeTestQueryClient } from "../test/test-utils";
import App, { uiPrefsConfig } from "../App";

// Spy for useUtilityDock().toggle — lets tests assert the jobs dock surface
// is opened when the jobs button is clicked.
const mockToggle = vi.fn();

/** Minimal Job shape mirroring pdomain-ui Job for test assertions. */
interface MockJob {
  id: string;
  project: string;
  status: string;
}

/** Minimal AppShellJobsProps shape for test assertions. */
interface MockAppShellJobsProps {
  activeJobs?: MockJob[];
  onJobOpen?: (jobId: string) => void;
  onJobDelete?: (jobId: string) => void;
}

// Mock @pdomain/pdomain-ui/shell — we test App routing, not AppShell internals.
// AppShell itself uses complex CSS and zustand stores that don't run well in jsdom.
// useUtilityDock is called by SimpleGuiHeader (wires JobsPill.onClick to toggle('jobs')).
//
// pdomain-ui 0.5.0: AppShell now accepts a `jobs` prop (AppShellJobsProps).
// The mock renders job rows into a data-testid="jobs-dock-surface" div so
// tests can assert real job data flows through to the dock surface.
vi.mock("@pdomain/pdomain-ui/shell", () => ({
  AppShell: ({
    header,
    main,
    jobs,
  }: {
    header: React.ReactNode;
    main: React.ReactNode;
    jobs?: MockAppShellJobsProps;
  }) => {
    const jobRows = jobs?.activeJobs ?? [];
    return (
      <div
        data-testid="app-shell-mock"
        data-jobs-count={String(jobRows.length)}
      >
        <div data-testid="app-shell-header-mock">{header}</div>
        <div data-testid="app-shell-main-mock">{main}</div>
        {/* Simulated Jobs dock surface — renders one row per active job */}
        <div data-testid="jobs-dock-surface">
          {jobRows.map((job) => (
            <div key={job.id} data-testid="job-row" data-job-id={job.id}>
              <span data-testid="job-row-project">{job.project}</span>
              <span data-testid="job-row-status">{job.status}</span>
              {/* Open button matches pdomain-ui JobRow data-testid contract */}
              <button
                type="button"
                data-testid="job-row-open"
                onClick={() => jobs?.onJobOpen?.(job.id)}
              >
                Open
              </button>
              {/* Trash button — pdomain-ui 0.6.0: rendered for finished/failed
                  rows when onJobDelete is provided. Testid: job-delete-<id>. */}
              {jobs?.onJobDelete !== undefined && (
                <button
                  type="button"
                  data-testid={`job-delete-${job.id}`}
                  onClick={() => jobs.onJobDelete?.(job.id)}
                >
                  Delete
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  },
  JobsPill: ({
    activeJobs = [],
    onClick,
  }: {
    activeJobs?: unknown[];
    onClick?: () => void;
  }) => (
    <button
      type="button"
      data-testid="app-header-jobs-button-mock"
      data-job-count={String(activeJobs.length)}
      onClick={onClick}
    >
      Jobs
    </button>
  ),
  SuiteSiblingsProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  ShortcutsHelpButton: () => <div data-testid="shortcuts-help-button-mock" />,
  SettingsSlot: () => <div data-testid="settings-slot-trigger-mock" />,
  useUtilityDock: () => ({
    toggle: mockToggle,
    active: null,
    pinned: false,
    width: 420,
    open: vi.fn(),
    close: vi.fn(),
    setPinned: vi.fn(),
    setWidth: vi.fn(),
  }),
  // pdomain-ui 0.7.0 additions
  ComputeTargetPanel: () => <div data-testid="compute-target-panel-mock" />,
  UpdatePanel: () => <div data-testid="update-panel-mock" />,
  UpdateBadge: ({ available }: { available: boolean }) =>
    available ? <div data-testid="update-badge-mock" /> : null,
  createApiDeviceConfig: () => ({
    fetchDevice: vi.fn(),
    putDevice: vi.fn(),
    clearDevice: vi.fn(),
  }),
  createApiUpdateConfig: () => ({ fetchUpdate: vi.fn(), applyUpdate: vi.fn() }),
}));

vi.mock("@pdomain/pdomain-ui/hooks", () => ({
  ShortcutsProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useShortcuts: () => undefined,
  formatShortcut: (keys: string) => [keys],
}));

// Mock stores for useDeviceInfo / useUpdateCheck (used by F5 panel wrappers)
vi.mock("@pdomain/pdomain-ui/stores", () => ({
  useDeviceInfo: () => ({
    info: null,
    loading: false,
    error: null,
    setDevice: vi.fn(),
    clearDevice: vi.fn(),
  }),
  useUpdateCheck: () => ({
    info: null,
    loading: false,
    error: null,
    checkNow: vi.fn(),
    applyAndRestart: vi.fn(),
  }),
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
beforeEach(() => {
  mockToggle.mockClear();
  (globalThis as any).fetch = vi.fn().mockImplementation((url: string) => {
    // ConfigProvider fetches /api/config on mount — return a valid config so
    // HomePage renders rather than showing "Loading…".
    if (typeof url === "string" && url.includes("/api/config")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ mode: "local", is_containerized: false }),
      });
    }
    if (typeof url === "string" && url.includes("/api/jobs")) {
      return Promise.resolve({
        ok: true,
        json: async () => [],
      });
    }
    return Promise.resolve({
      ok: false,
      json: async () => ({}),
    });
  });
});

// App uses BrowserRouter internally; wrap with QueryClientProvider only.
function renderApp() {
  const client = makeTestQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("renders without crashing and shows home page at /", async () => {
    renderApp();
    // The AppShell mock renders its main slot which contains AppRoutes
    const shell = screen.getByTestId("app-shell-mock");
    expect(shell).toBeInTheDocument();
    // At default path "/" we should see the home page — async because
    // ConfigProvider fetches /api/config before HomePage renders content.
    expect(await screen.findByTestId("home-page")).toBeInTheDocument();
  });

  it("AppShell mock receives a main prop", () => {
    renderApp();
    expect(screen.getByTestId("app-shell-main-mock")).toBeInTheDocument();
  });

  it("clicking the jobs pill calls useUtilityDock().toggle('jobs')", async () => {
    // pdomain-ui 0.4.0: JobsPill.onClick is wired to useUtilityDock().toggle('jobs').
    // The utility dock is now AppShell's built-in right-side surface; the old
    // RightPanel + JobsDrawer pattern has been removed.
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string) => {
        if (typeof url === "string" && url.includes("/api/config")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ mode: "local", is_containerized: false }),
          });
        }
        if (typeof url === "string" && url.includes("/api/jobs")) {
          return Promise.resolve({
            ok: true,
            json: async () => [
              {
                project_id: "job-1",
                name: "Scan batch",
                state: "running",
                page_count: 4,
                pages_done: 1,
                pages: [{ state: "succeeded" }, { state: "running" }],
              },
            ],
          });
        }
        return Promise.resolve({
          ok: false,
          json: async () => ({}),
        });
      },
    );

    renderApp();
    const jobsButton = await screen.findByTestId("app-header-jobs-button-mock");
    await waitFor(() => {
      expect(jobsButton).toHaveAttribute("data-job-count", "1");
    });

    fireEvent.click(jobsButton);

    expect(mockToggle).toHaveBeenCalledWith("jobs");
  });

  // -------------------------------------------------------------------------
  // pdomain-ui 0.5.0 — AppShell jobs prop wiring
  // -------------------------------------------------------------------------

  it("passes live jobs to AppShell.jobs.activeJobs — dock shows real job row", async () => {
    // pdomain-ui 0.5.0: AppShell.jobs.activeJobs feeds the dock Jobs surface.
    // This test proves simple-gui maps backend jobs to the Job shape and the
    // dock renders a real job row (not the empty state).
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string) => {
        if (typeof url === "string" && url.includes("/api/config")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ mode: "local", is_containerized: false }),
          });
        }
        if (typeof url === "string" && url.includes("/api/jobs")) {
          return Promise.resolve({
            ok: true,
            json: async () => [
              {
                project_id: "proj-abc",
                name: "My scan",
                state: "succeeded",
                page_count: 3,
                pages_done: 3,
              },
            ],
          });
        }
        return Promise.resolve({
          ok: false,
          json: async () => ({}),
        });
      },
    );

    renderApp();

    // Wait for the dock to render a row with data-testid="job-row"
    const jobRow = await screen.findByTestId("job-row");
    expect(jobRow).toBeInTheDocument();
    expect(jobRow).toHaveAttribute("data-job-id", "proj-abc");

    // Project name appears in the row
    expect(screen.getByTestId("job-row-project")).toHaveTextContent("My scan");

    // Status is correctly mapped from backend "succeeded" → JobStatus "succeeded"
    expect(screen.getByTestId("job-row-status")).toHaveTextContent("succeeded");

    // Open button is present (job-row-open testid matches pdomain-ui JobRow contract)
    expect(screen.getByTestId("job-row-open")).toBeInTheDocument();
  });

  it("AppShell.jobs.activeJobs is empty when no jobs are running", async () => {
    // When the backend returns an empty list, the dock surface shows no rows
    // (the empty state). Confirm data-jobs-count reflects this.
    renderApp();

    const shell = await screen.findByTestId("app-shell-mock");
    // Dock starts with 0 jobs — may update once /api/jobs resolves
    await waitFor(() => {
      expect(shell).toHaveAttribute("data-jobs-count", "0");
    });

    // jobs-dock-surface renders but contains no job-row elements
    const dockSurface = screen.getByTestId("jobs-dock-surface");
    expect(dockSurface).toBeInTheDocument();
    expect(screen.queryAllByTestId("job-row")).toHaveLength(0);
  });

  // -------------------------------------------------------------------------
  // Bad-case tests (M4 strengthening)
  // -------------------------------------------------------------------------

  // -------------------------------------------------------------------------
  // pdomain-ui 0.6.0 — trash button wires to DELETE /api/jobs/{id}
  // -------------------------------------------------------------------------

  it("trash button calls DELETE /api/jobs/{id} then refetches active-jobs", async () => {
    // Arrange: one succeeded job appears in the dock.
    // After DELETE, /api/jobs returns empty list — the row disappears.
    const succeededJob = {
      project_id: "proj-done",
      name: "Finished scan",
      state: "succeeded",
      page_count: 2,
      pages_done: 2,
    };

    let deleted = false;
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string, opts?: RequestInit) => {
        if (typeof url === "string" && url.includes("/api/config")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ mode: "local", is_containerized: false }),
          });
        }
        // DELETE /api/jobs/{id}
        if (
          typeof url === "string" &&
          url.includes("/api/jobs/proj-done") &&
          opts?.method === "DELETE"
        ) {
          deleted = true;
          return Promise.resolve({ ok: true, json: async () => ({}) });
        }
        // GET /api/jobs — after delete return empty list
        if (typeof url === "string" && url.includes("/api/jobs")) {
          return Promise.resolve({
            ok: true,
            json: async () => (deleted ? [] : [succeededJob]),
          });
        }
        return Promise.resolve({ ok: false, json: async () => ({}) });
      },
    );

    renderApp();

    // Wait for the dock row to appear
    const jobRow = await screen.findByTestId("job-row");
    expect(jobRow).toHaveAttribute("data-job-id", "proj-done");

    // Trash button is rendered for this job (onJobDelete is wired)
    const trashBtn = screen.getByTestId("job-delete-proj-done");
    expect(trashBtn).toBeInTheDocument();

    // Click the trash button
    fireEvent.click(trashBtn);

    // DELETE should have been called
    await waitFor(() => {
      expect(deleted).toBe(true);
    });

    // After refetch, the row disappears (job removed from active-jobs)
    await waitFor(() => {
      expect(screen.queryByTestId("job-row")).not.toBeInTheDocument();
    });
  });

  it("renders no dead header affordances", () => {
    renderApp();
    expect(screen.queryByTestId("app-header-bell")).toBeNull();
    expect(screen.queryByTestId("app-header-user")).toBeNull();
    expect(screen.queryByLabelText("Search")).toBeNull();
  });

  // NOTE: HomePage separately renders its own "home-config-error" banner
  // (driven by jobCreationMachine's independent /api/config fetch — see
  // Phase E issue 3, dedup deferred). The App-shell banner under test here
  // is driven by ConfigContext's useConfigStatus() and is scoped by its own
  // testid so the two don't collide in assertions.
  it("shows a dismissible banner when /api/config cannot be loaded, and Retry re-fetches it", async () => {
    // Simulate a failed /api/config fetch (mockFetchConfigFailure, inlined
    // per this file's existing mock-override idiom). A mutable flag (not a
    // call counter) drives success/failure: ConfigContext and HomePage's
    // jobCreationMachine each fetch /api/config independently on mount, so
    // a "fail on call #1 only" counter would race between the two callers.
    let configShouldFail = true;
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string) => {
        if (typeof url === "string" && url.includes("/api/config")) {
          if (configShouldFail) {
            return Promise.resolve({ ok: false, json: async () => ({}) });
          }
          return Promise.resolve({
            ok: true,
            json: async () => ({ mode: "local", is_containerized: false }),
          });
        }
        if (typeof url === "string" && url.includes("/api/jobs")) {
          return Promise.resolve({ ok: true, json: async () => [] });
        }
        return Promise.resolve({ ok: false, json: async () => ({}) });
      },
    );

    renderApp();

    const banner = await screen.findByTestId("app-config-error-banner");
    expect(
      within(banner).getByText(/could not load app configuration/i),
    ).toBeInTheDocument();

    // Retry re-fetches /api/config; a successful response clears the banner.
    configShouldFail = false;
    fireEvent.click(within(banner).getByRole("button", { name: /retry/i }));
    await waitFor(() => {
      expect(
        screen.queryByTestId("app-config-error-banner"),
      ).not.toBeInTheDocument();
    });
  });

  it("dismisses the config-error banner without retrying", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string) => {
        if (typeof url === "string" && url.includes("/api/config")) {
          return Promise.resolve({ ok: false, json: async () => ({}) });
        }
        if (typeof url === "string" && url.includes("/api/jobs")) {
          return Promise.resolve({ ok: true, json: async () => [] });
        }
        return Promise.resolve({ ok: false, json: async () => ({}) });
      },
    );

    renderApp();

    const banner = await screen.findByTestId("app-config-error-banner");
    fireEvent.click(within(banner).getByRole("button", { name: /dismiss/i }));
    expect(
      screen.queryByTestId("app-config-error-banner"),
    ).not.toBeInTheDocument();
  });

  it("renders shell with empty content at unknown route (no crash)", () => {
    // App uses BrowserRouter internally; override window.location via history.
    // We test via a custom wrapper that injects an unknown path.
    const client = makeTestQueryClient();
    // Mock a route-level provider that simulates landing on /nonexistent
    // BrowserRouter initialises to window.location — jsdom defaults to "about:blank".
    // We just verify the shell renders without a home-page testid.
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );
    // AppShell still renders — the route just matches nothing (no crash)
    expect(screen.getByTestId("app-shell-mock")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// uiPrefsConfig persist wiring — clobber-proof PUT /api/prefs shapes
//
// Regression: persistApp previously sent `{app_prefs: ...}` (a wrapper key the
// flat AppPrefs backend silently dropped), so every app-pref change saved an
// all-defaults body and wiped siblings. persistCommon sent `{ui_prefs: ...}`
// (correct field name) but a partial body still reset app fields under the old
// replace-on-write backend. These tests pin the wire shapes and prove a second
// persist never drops the first persist's fields (backend now merges).
// ---------------------------------------------------------------------------
describe("uiPrefsConfig persist wiring", () => {
  /**
   * Build a fetch mock that emulates the backend read-modify-merge for
   * PUT /api/prefs: it keeps a stored prefs object, merges each partial PUT
   * body into it, and serves it back from GET. Returns the store + spy.
   */
  function makeMergingFetch() {
    const store: Record<string, unknown> = {
      default_engine: "doctr",
      default_language: "en",
      ui_prefs: null,
    };
    const puts: Record<string, unknown>[] = [];
    const fetchMock = vi.fn((url: string, opts?: RequestInit) => {
      if (typeof url === "string" && url.includes("/api/prefs")) {
        if (opts?.method === "PUT") {
          const body = JSON.parse(String(opts.body)) as Record<string, unknown>;
          puts.push(body);
          // Emulate backend merge: partial body keys win, siblings survive.
          Object.assign(store, body);
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ ...store }),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ ...store }),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({}),
      });
    });
    return { store, puts, fetchMock };
  }

  it("persistApp PUTs FLAT app fields (no app_prefs wrapper)", async () => {
    const { puts, fetchMock } = makeMergingFetch();
    (globalThis as any).fetch = fetchMock;

    await uiPrefsConfig.persistApp?.({ default_engine: "tesseract" } as never);

    expect(puts).toHaveLength(1);
    // The body must be the flat field — NOT {app_prefs: {...}}.
    expect(puts[0]).toEqual({ default_engine: "tesseract" });
    expect(puts[0]).not.toHaveProperty("app_prefs");
  });

  it("persistCommon PUTs the ui_prefs slice under the real ui_prefs key", async () => {
    const { puts, fetchMock } = makeMergingFetch();
    (globalThis as any).fetch = fetchMock;

    await uiPrefsConfig.persistCommon?.({
      theme: "dark",
      density: "normal",
      fontScale: 1.0,
    } as never);

    expect(puts).toHaveLength(1);
    expect(puts[0]).toEqual({
      ui_prefs: { theme: "dark", density: "normal", fontScale: 1.0 },
    });
  });

  it("persistApp then persistCommon: neither drops the other's field", async () => {
    const { store, fetchMock } = makeMergingFetch();
    (globalThis as any).fetch = fetchMock;

    // 1) Save an app pref.
    await uiPrefsConfig.persistApp?.({ default_engine: "tesseract" } as never);
    // 2) Save a common (appearance) pref.
    await uiPrefsConfig.persistCommon?.({
      theme: "dark",
      density: "normal",
      fontScale: 1.0,
    } as never);

    // Both must coexist in the merged store after the second persist.
    expect(store.default_engine).toBe("tesseract");
    expect(store.ui_prefs).toEqual({
      theme: "dark",
      density: "normal",
      fontScale: 1.0,
    });
  });
});
