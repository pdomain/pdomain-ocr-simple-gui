// App root — AppShell + React Router routing skeleton
// Issues #225 (scaffold), #226 (shell)
//
// noopener note (issue #26):
// The suite launcher opens sibling apps via window.open(url, "_blank") inside the
// compiled @pdomain/pdomain-ui AppShell bundle. Our own <a> elements don't use
// target="_blank". The upstream fix (add "noopener,noreferrer" to window.open call)
// must land in pdomain-ui; once that is released, bump @pdomain/pdomain-ui here.
// See: Cross-repo recommendation in docs/research/2026-05-22-deep-code-review-security-scan.md
//
// A9.4 stores swap notes:
// - pdomain-ui createUIPrefsStore is already consumed via AppShell.uiPrefsConfig
//   (AppShell instantiates it internally). The uiPrefsConfig below is the
//   factory-config object passed to AppShell, matching UIPrefsConfig exactly.
// - persistApp is now wired to PUT /api/prefs (was a TODO stub).
// - useLongJob from pdomain-ui/stores could replace ResultsPage's hand-rolled
//   polling, BUT: (1) useLongJob status enum is {idle|pending|running|done|
//   error|cancelled} while the backend returns {queued|running|succeeded|
//   failed|cancelled}; (2) useLongJob carries only {status,progress,events}
//   — not the full JobStatus with pages/page_count/output_dir. Keeping the
//   hand-rolled fetch in ResultsPage. TODO(A9.4-polling): if backend gains a
//   SSE/WebSocket endpoint, useLongJob could be retrofitted.
//
// Step 5 — app header + useActiveJobs:
// Polls GET /api/jobs every 5s, filters to state==="running", maps to
// ActiveJob shape. No search affordance yet (simple-gui has no search feature).
//
// @pdomain/pdomain-ui 0.4.0 — utility dock migration:
// JobsPill hover popover removed upstream. JobsPill.onClick now wires to
// useUtilityDock().toggle('jobs') so the dock's built-in jobs surface opens.
// RightPanel + JobsDrawer manual jobs panel removed; AppShell owns the dock.
// ShortcutsHelpButton already inside AppShell (via header slot) — no change.
//
// @pdomain/pdomain-ui 0.5.0 — AppShell jobs prop:
// AppShell now accepts `jobs?: AppShellJobsProps` which feeds live job rows
// into the dock's Jobs surface (replacing the empty state). useActiveJobs()
// now returns both ActiveJob[] (for JobsPill count) and Job[] (for the dock).
// onJobOpen navigates to /jobs/:id. No cancel/pause API exists in simple-gui,
// so onJobCancel and onJobPauseResume are omitted (both fully optional).

import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import {
  AppShell,
  JobsPill,
  SuiteSiblingsProvider,
  ShortcutsHelpButton,
  SettingsSlot,
  useUtilityDock,
} from "@pdomain/pdomain-ui/shell";
import { ShortcutsProvider } from "@pdomain/pdomain-ui/hooks";
import type {
  UIPrefsConfig,
  InstalledApp,
  LaunchResult,
  ActiveJob,
  AppShellJobsProps,
  Job,
  JobStatus,
} from "@pdomain/pdomain-ui/shell";
import { toast } from "sonner";
import { ConfigProvider } from "./runtime/ConfigContext";
import { HomePage } from "./pages/HomePage";
import ResultsPage from "./pages/ResultsPage";
import PageViewPage from "./pages/PageViewPage";
import TesseractHelpPage from "./pages/TesseractHelpPage";

/**
 * onPersistError — surfaces a sonner toast when PUT /api/prefs fails.
 *
 * B-SHELL-008/009/010 regression fix: persistCommon and persistApp
 * previously swallowed all errors with a silent `catch {}` and never
 * checked `res.ok`. A failed PUT caused the pref to revert on reload
 * with no user feedback. This callback is wired into UIPrefsConfig so
 * pdomain-ui's createUIPrefsStore can call it when the promise rejects.
 */
function handlePersistError(err: unknown): void {
  const detail = err instanceof Error ? err.message : String(err);
  toast.error("Preferences not saved — server error", {
    description: detail,
  });
}

/** Minimal UIPrefs config — reads/writes from /api/prefs app prefs. */
const uiPrefsConfig: UIPrefsConfig = {
  load: async () => {
    try {
      const res = await fetch("/api/prefs");
      if (!res.ok)
        return {
          theme: "dark" as const,
          density: "normal" as const,
          fontScale: 1.0,
        };
      const data = (await res.json()) as {
        ui_prefs?: { theme?: string; density?: string; fontScale?: number };
      };
      const ui = data.ui_prefs ?? {};
      return {
        theme: (ui.theme === "light" ? "light" : "dark") as "dark" | "light",
        density: (["compact", "normal", "comfortable"].includes(
          ui.density ?? "",
        )
          ? ui.density
          : "normal") as "compact" | "normal" | "comfortable",
        fontScale:
          typeof ui.fontScale === "number"
            ? Math.min(1.4, Math.max(0.8, ui.fontScale))
            : 1.0,
      };
    } catch {
      return {
        theme: "dark" as const,
        density: "normal" as const,
        fontScale: 1.0,
      };
    }
  },
  onPersistError: handlePersistError,
  persistCommon: async (prefs) => {
    const res = await fetch("/api/prefs", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ui_prefs: prefs }),
    });
    if (!res.ok) {
      throw new Error(`PUT /api/prefs failed: ${res.status}`);
    }
  },
  persistApp: async (appPrefs) => {
    const res = await fetch("/api/prefs", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ app_prefs: appPrefs }),
    });
    if (!res.ok) {
      throw new Error(`PUT /api/prefs failed: ${res.status}`);
    }
  },
};

/** Minimal suite siblings fetcher — discovers installed pd-* apps. */
const fetchInstalled = async (): Promise<InstalledApp[]> => {
  try {
    const res = await fetch("/api/suite/installed");
    if (!res.ok) return [];
    return (await res.json()) as InstalledApp[];
  } catch {
    return [];
  }
};

const postLaunch = async (id: string): Promise<LaunchResult> => {
  try {
    const res = await fetch("/api/suite/launch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!res.ok) return { kind: "requires-host-config", siblingId: id };
    return (await res.json()) as LaunchResult;
  } catch {
    return { kind: "requires-host-config", siblingId: id };
  }
};

/** Raw job shape returned by GET /api/jobs. */
interface RawJob {
  project_id: string;
  name?: string;
  state: string;
  page_count?: number;
  pages_done?: number;
  pages?: { state: string }[];
  progress_message?: string | null;
}

/**
 * Maps a backend job state string to the pdomain-ui JobStatus union.
 * Backend values: queued | running | succeeded | failed | cancelled.
 * JobStatus union:  queued | running | paused  | succeeded | done | failed.
 * "cancelled" has no JobStatus equivalent — treat as "failed" for display.
 */
function toJobStatus(state: string): JobStatus {
  if (
    state === "queued" ||
    state === "running" ||
    state === "paused" ||
    state === "succeeded" ||
    state === "done" ||
    state === "failed"
  ) {
    return state;
  }
  // "cancelled" → "failed" (closest terminal state with dock support)
  return "failed";
}

/**
 * Polls /api/jobs every 5s and maps running jobs to the ActiveJob shape
 * expected by pdomain-ui JobsPill. Backend uses `state` field
 * (not `status`). Returns count of running pages as pct where available.
 */
function progressForJob(job: RawJob): number {
  const total = job.page_count ?? job.pages?.length ?? 0;
  const done =
    job.pages_done ??
    job.pages?.filter((p) => p.state === "succeeded").length ??
    0;
  return total > 0 ? Math.round((done / total) * 100) : 0;
}

/** Return value of useActiveJobs — both shapes needed by different consumers. */
interface ActiveJobsResult {
  /** For JobsPill pill/count display (ActiveJob shape). */
  pill: ActiveJob[];
  /** For AppShell.jobs dock surface (Job shape). */
  dock: Job[];
}

/**
 * Polls GET /api/jobs every 5 s.
 *
 * Returns two mapped arrays:
 * - `pill`: ActiveJob[] for JobsPill (in-flight only — queued|running).
 * - `dock`: Job[] for AppShell.jobs.activeJobs (all jobs that have state).
 *
 * simple-gui has no cancel or pause API, so cancelable is always false.
 * onJobOpen navigates to /jobs/:id via the caller's useNavigate hook.
 */
function useActiveJobs(): ActiveJobsResult {
  const { data } = useQuery<RawJob[]>({
    queryKey: ["active-jobs"],
    queryFn: async () => {
      const res = await fetch("/api/jobs");
      if (!res.ok) return [];
      return (await res.json()) as RawJob[];
    },
    refetchInterval: 5_000,
    // Treat errors as empty list — don't surface loading state in header.
    throwOnError: false,
  });
  const all = data ?? [];
  const inFlight = all.filter(
    (j) => j.state === "running" || j.state === "queued",
  );
  const pill: ActiveJob[] = inFlight.map((j) => {
    const pct = progressForJob(j);
    return {
      id: j.project_id,
      title: j.name ?? j.project_id,
      phase: j.state,
      pct,
      project: j.project_id,
    };
  });
  const dock: Job[] = all.map((j) => {
    const pct = progressForJob(j);
    return {
      id: j.project_id,
      project: j.name ?? j.project_id,
      phase: j.state,
      pct,
      status: toJobStatus(j.state),
      cancelable: false,
    };
  });
  return { pill, dock };
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      {/* /new-job redirects to home — the dialog opens inline on HomePage */}
      <Route path="/new-job" element={<HomePage />} />
      <Route path="/jobs/:id" element={<ResultsPage />} />
      <Route path="/jobs/:id/pages/:idx" element={<PageViewPage />} />
      <Route path="/help/tesseract" element={<TesseractHelpPage />} />
    </Routes>
  );
}

/**
 * SimpleGuiHeader — custom header rendered inside AppShell's header slot.
 *
 * JobsPill.onClick is wired to useUtilityDock().toggle('jobs') so the
 * utility dock's built-in jobs surface opens. AppShell provides the
 * UtilityDockContext — this component is always inside AppShell.
 */
function SimpleGuiHeader({
  activeJobs,
  actions,
}: {
  activeJobs: ActiveJob[];
  actions: ReactNode;
}) {
  const { toggle } = useUtilityDock();

  return (
    <header
      data-testid="app-header"
      style={{
        height: 52,
        flex: "0 0 auto",
        background: "var(--bg-page)",
        borderBottom: "1px solid var(--border-1)",
        display: "grid",
        gridTemplateColumns: "1fr minmax(220px, 520px) 1fr",
        alignItems: "center",
        padding: "0 20px",
        gap: 20,
      }}
    >
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}
      >
        <div
          aria-hidden
          style={{
            width: 26,
            height: 26,
            borderRadius: 6,
            background: "var(--accent)",
            color: "var(--accent-ink)",
            display: "grid",
            placeItems: "center",
            fontFamily: "var(--mono-font)",
            fontWeight: 700,
            fontSize: 14,
            flexShrink: 0,
          }}
        >
          o
        </div>
        <span
          style={{
            color: "var(--ink-1)",
            fontWeight: 600,
            fontSize: 14,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          OCR Simple GUI
        </span>
      </div>
      <button
        type="button"
        aria-label="Search"
        style={{
          display: "flex",
          alignItems: "center",
          height: 32,
          padding: "0 12px",
          background: "var(--bg-sunk)",
          border: "1px solid var(--border-2)",
          borderRadius: 6,
          color: "var(--ink-3)",
          cursor: "default",
          width: "100%",
          textAlign: "left",
          fontFamily: "var(--ui-font)",
          fontSize: 12.5,
        }}
      >
        Search...
      </button>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          justifyContent: "flex-end",
          minWidth: 0,
        }}
      >
        {actions}
        <div className="app-header__jobs-panel-owner">
          <JobsPill activeJobs={activeJobs} onClick={() => toggle("jobs")} />
        </div>
        <button
          type="button"
          data-testid="app-header-bell"
          aria-label="Notifications"
          className="app-header__icon-button"
        >
          !
        </button>
        <button
          type="button"
          data-testid="app-header-user"
          aria-label="User menu"
          className="app-header__icon-button"
        >
          u
        </button>
      </div>
    </header>
  );
}

function AppShellWithHeader() {
  const { pill, dock } = useActiveJobs();
  const navigate = useNavigate();

  /**
   * onJobOpen — opens the ResultsPage for a completed job.
   * simple-gui has no cancel/pause API; those callbacks are omitted.
   */
  const jobsProps: AppShellJobsProps = {
    activeJobs: dock,
    onJobOpen: (jobId: string) => {
      navigate(`/jobs/${jobId}`);
    },
  };

  return (
    <AppShell
      appId="pdomain-ocr-simple-gui"
      appDisplayName="OCR Simple GUI"
      appIconUrl="/api/self/icons/32"
      deployMode="local"
      launcherSlot="header"
      uiPrefsConfig={uiPrefsConfig}
      jobs={jobsProps}
      header={
        <SimpleGuiHeader
          activeJobs={pill}
          actions={
            <>
              <SettingsSlot />
              <ShortcutsHelpButton />
            </>
          }
        />
      }
      main={<AppRoutes />}
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ConfigProvider>
        <SuiteSiblingsProvider value={{ fetchInstalled, postLaunch }}>
          <ShortcutsProvider>
            <AppShellWithHeader />
          </ShortcutsProvider>
        </SuiteSiblingsProvider>
      </ConfigProvider>
    </BrowserRouter>
  );
}
