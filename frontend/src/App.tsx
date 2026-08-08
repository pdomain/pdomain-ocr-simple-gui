// App root — AppShell + React Router routing skeleton
// Issues #225 (scaffold), #226 (shell)
//
// noopener note (issue #26):
// The suite launcher opens sibling apps via window.open(url, "_blank") inside the
// compiled @pdomain/pdomain-ui AppShell bundle. Our own <a> elements don't use
// target="_blank". The upstream fix (add "noopener,noreferrer" to window.open call)
// must land in pdomain-ui; once that is released, bump @pdomain/pdomain-ui here.
// Tracked as blocked upstream in docs/context/intent-map.md.
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
// ActiveJob shape.
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
// onJobOpen navigates to /jobs/:id. simple-gui has no cancel/pause API (the
// backend's cancel transition was never reachable and was stripped —
// ocr-container-meta#395), so onJobCancel and onJobPauseResume are omitted
// (both fully optional).

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import {
  AppShell,
  JobsPill,
  SuiteSiblingsProvider,
  ShortcutsHelpButton,
  SettingsSlot,
  useUtilityDock,
  UpdatePanel,
  UpdateBadge,
  ComputeTargetPanel,
  createApiDeviceConfig,
  createApiUpdateConfig,
} from "@pdomain/pdomain-ui/shell";
import { ShortcutsProvider } from "@pdomain/pdomain-ui/hooks";
import { useDeviceInfo, useUpdateCheck } from "@pdomain/pdomain-ui/stores";
import type {
  UIPrefsConfig,
  InstalledApp,
  LaunchResult,
  ActiveJob,
  AppShellJobsProps,
  Job,
  JobStatus,
  SettingsPanelDescriptor,
  UpdatePolicy,
} from "@pdomain/pdomain-ui/shell";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ConfigProvider, useConfigStatus } from "./runtime/ConfigContext";
import { HomePage } from "./pages/HomePage";
import ResultsPage from "./pages/ResultsPage";
import PageViewPage from "./pages/PageViewPage";
import TesseractHelpPage from "./pages/TesseractHelpPage";
import { JobsLocationSettings } from "./components/JobsLocationSettings";
import { CudaSetupGuidance } from "./components/CudaSetupGuidance";
import { ModelCacheSettings } from "./components/ModelCacheSettings";
import { ApiTokenSettings } from "./components/ApiTokenSettings";
import { apiFetch } from "./api/apiFetch";

/**
 * API-backed update config for UpdatePanel.
 * createApiUpdateConfig reads/writes /api/suite/update.
 */
const _updateConfig = createApiUpdateConfig();
const _deviceConfig = createApiDeviceConfig();
let _computeStateWarmupStarted = false;

export function ComputeStateWarmup() {
  useEffect(() => {
    if (_computeStateWarmupStarted) return;
    _computeStateWarmupStarted = true;
    // Fire-and-forget warmup: tolerate a fetchDevice() that returns a
    // non-promise (e.g. test mocks) so it can never crash the app shell.
    void Promise.resolve(_deviceConfig.fetchDevice()).catch(() => undefined);
  }, []);
  return null;
}

/** Inner component for the Compute panel — calls hooks inside the component tree. */
function ComputePanelContent() {
  const device = useDeviceInfo(_deviceConfig);

  let body: ReactNode;
  if (device.loading && !device.info) {
    body = (
      <p key="compute-loading" style={{ margin: 0 }}>
        Checking compute devices
      </p>
    );
  } else if (device.error && !device.info) {
    body = (
      <p
        key="compute-error"
        role="alert"
        style={{ margin: 0, color: "var(--color-danger)" }}
      >
        {device.error instanceof Error
          ? device.error.message
          : String(device.error)}
      </p>
    );
  } else {
    body = (
      <ComputeTargetPanel
        key="compute-target"
        info={device.info}
        onSelect={(deviceId) => void device.setDevice("app", deviceId)}
        onClear={(scope) => void device.clearDevice(scope)}
        cudaDocsUrl="/docs/runbooks/cuda-setup.md"
      />
    );
  }

  return (
    <div>
      {body}
      <CudaSetupGuidance key="cuda-guidance" />
    </div>
  );
}

/** Shape of the `common` slice of GET/PUT /api/suite/prefs (partial — we
 * only read/write the fields we know about; unknown fields must survive a
 * read-modify-write round trip, so this stays a loose record). */
type SuiteCommonPrefs = Record<string, unknown> & {
  update_policy?: UpdatePolicy | null;
};

/**
 * Inner component for the Updates panel — calls hooks inside the component
 * tree.
 *
 * The update-policy selector is backed by suite prefs, not local state:
 * `GET /api/suite/prefs` supplies `common.update_policy` on mount, and each
 * selector change re-reads `common` fresh and PUTs the WHOLE object back to
 * `/api/suite/prefs/common` — that route replaces `common` wholesale, so a
 * partial body would blank sibling fields (theme, density, ...).
 */
function UpdatePanelContent() {
  const update = useUpdateCheck(_updateConfig);
  const [policy, setPolicy] = useState<UpdatePolicy>("notify");
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch("/api/suite/prefs");
        if (!res.ok) {
          if (!cancelled) {
            setLoadError(`GET /api/suite/prefs failed: ${res.status}`);
          }
          return;
        }
        const data = (await res.json()) as { common?: SuiteCommonPrefs };
        if (!cancelled) {
          setPolicy(data.common?.update_policy ?? "notify");
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : String(err));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handlePolicyChange = useCallback((next: UpdatePolicy): void => {
    void (async () => {
      try {
        const getRes = await apiFetch("/api/suite/prefs");
        if (!getRes.ok) {
          throw new Error(`GET /api/suite/prefs failed: ${getRes.status}`);
        }
        const data = (await getRes.json()) as { common?: SuiteCommonPrefs };
        const common: SuiteCommonPrefs = {
          ...(data.common ?? {}),
          update_policy: next,
        };
        const putRes = await apiFetch("/api/suite/prefs/common", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(common),
        });
        if (!putRes.ok) {
          throw new Error(
            `PUT /api/suite/prefs/common failed: ${putRes.status}`,
          );
        }
        setPolicy(next);
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        toast.error("Update policy not saved — server error", {
          description: detail,
        });
      }
    })();
  }, []);

  if (loadError) {
    return (
      <p role="alert" style={{ margin: 0, color: "var(--color-danger)" }}>
        {loadError}
      </p>
    );
  }

  return (
    <UpdatePanel
      info={update.info}
      policy={policy}
      onPolicyChange={handlePolicyChange}
      onApply={() => void update.applyAndRestart()}
    />
  );
}

/**
 * App-injected settings panels, appended after pdomain-ui's built-in
 * Appearance tab. The "jobs" panel lets the user choose where new OCR jobs
 * are stored (env > pref > default resolution lives in the backend).
 * "compute" provides app-specific device controls backed by /api/suite/device.
 * "updates" comes from pdomain-ui.
 * "models" exposes local OCR checkpoint cache status and precache.
 * "api-token" (#398) lets the user view/set/clear the `pdomain.apiToken`
 * localStorage key that apiFetch.ts reads — no backend endpoint involved.
 */
export const settingsPanels: SettingsPanelDescriptor[] = [
  {
    id: "jobs",
    label: "Jobs",
    content: <JobsLocationSettings />,
  },
  {
    id: "compute",
    label: "Compute",
    content: <ComputePanelContent />,
  },
  {
    id: "models",
    label: "Models",
    content: <ModelCacheSettings />,
  },
  {
    id: "updates",
    label: "Updates",
    content: <UpdatePanelContent />,
  },
  {
    id: "api-token",
    label: "API Token",
    content: <ApiTokenSettings />,
  },
];

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

/**
 * Minimal UIPrefs config — reads/writes from /api/prefs app prefs.
 *
 * Exported so App.test.tsx can drive persistApp/persistCommon directly and
 * assert the PUT body shape (the AppShell mock never invokes these).
 */
export const uiPrefsConfig: UIPrefsConfig = {
  load: async () => {
    try {
      const res = await apiFetch("/api/prefs");
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
    // `ui_prefs` is a REAL field on the backend AppPrefs model (the common
    // theme/density/fontScale slice), so this object shape is correct — do
    // NOT unwrap it. The backend read-modify-merges this partial body, so
    // sending only ui_prefs no longer resets sibling app prefs to defaults.
    const res = await apiFetch("/api/prefs", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ui_prefs: prefs }),
    });
    if (!res.ok) {
      throw new Error(`PUT /api/prefs failed: ${res.status}`);
    }
  },
  persistApp: async (appPrefs) => {
    // Send the app-pref slice as FLAT fields — the backend PUT /api/prefs
    // expects a flat AppPrefs body, NOT an `{app_prefs: ...}` wrapper. The
    // wrapper key was silently ignored by Pydantic (extra=ignore), so the
    // backend saw an all-defaults body and clobbered every saved pref. The
    // backend now read-modify-merges partial bodies, so sending only the
    // changed app fields is safe and preserves siblings.
    const res = await apiFetch("/api/prefs", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(appPrefs),
    });
    if (!res.ok) {
      throw new Error(`PUT /api/prefs failed: ${res.status}`);
    }
  },
};

/** Minimal suite siblings fetcher — discovers installed pd-* apps. */
const fetchInstalled = async (): Promise<InstalledApp[]> => {
  try {
    const res = await apiFetch("/api/suite/installed");
    if (!res.ok) return [];
    return (await res.json()) as InstalledApp[];
  } catch {
    return [];
  }
};

const postLaunch = async (id: string): Promise<LaunchResult> => {
  try {
    const res = await apiFetch("/api/suite/launch", {
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
 * simple-gui has no cancel or pause API (ocr-container-meta#395: the
 * backend's cancel transition was unreachable and has been removed), so
 * cancelable is always false.
 * onJobOpen navigates to /jobs/:id via the caller's useNavigate hook.
 */
function useActiveJobs(): ActiveJobsResult {
  const { data } = useQuery<RawJob[]>({
    queryKey: ["active-jobs"],
    queryFn: async () => {
      const res = await apiFetch("/api/jobs");
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
 * UpdateBadgeHeaderWrapper — renders the UpdateBadge when an update is available.
 * Calls useUpdateCheck inside the component tree (hooks must be inside React components).
 */
function UpdateBadgeHeaderWrapper() {
  const update = useUpdateCheck(_updateConfig);
  const available = Boolean(update.info?.update_available);
  return <UpdateBadge available={available} />;
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
      {/* Flexible spacer — keeps brand left-aligned and actions right-aligned
          now that the header has no middle affordance. */}
      <div aria-hidden />
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
        <UpdateBadgeHeaderWrapper />
      </div>
    </header>
  );
}

/**
 * ConfigErrorBanner — surfaces a failed GET /api/config (ConfigContext's
 * useConfigStatus) as a dismissible inline banner above the routed content,
 * instead of failing silently. Retry re-runs the fetch via reload(); a
 * successful reload clears the banner. Dismiss hides it locally without
 * retrying (it reappears if a later reload() call fails again).
 *
 * Distinct from HomePage's own `home-config-error` banner, which is driven
 * by jobCreationMachine's own /api/config load. Both banners now share the
 * same fetch site (`api/config.ts`'s `fetchRuntimeConfig()`, deduplicated
 * per ocr-container-meta#396) but stay separate UI surfaces on purpose —
 * one lives in AppShell, the other inline on HomePage.
 */
function ConfigErrorBanner() {
  const { error, reload } = useConfigStatus();
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (error) setDismissed(false);
  }, [error]);

  if (!error || dismissed) return null;

  return (
    <div
      role="alert"
      data-testid="app-config-error-banner"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        padding: "8px 16px",
        background: "var(--color-danger-bg, #fdecea)",
        color: "var(--color-danger, #b3261e)",
        borderBottom: "1px solid var(--border-1)",
        fontSize: 13,
      }}
    >
      <span>
        Could not load app configuration — some options are hidden.{" "}
        <button
          type="button"
          onClick={() => void reload()}
          style={{
            color: "inherit",
            textDecoration: "underline",
            background: "none",
            border: "none",
            padding: 0,
            font: "inherit",
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      </span>
      <button
        type="button"
        aria-label="Dismiss"
        onClick={() => setDismissed(true)}
        style={{
          color: "inherit",
          background: "none",
          border: "none",
          cursor: "pointer",
          font: "inherit",
          lineHeight: 1,
        }}
      >
        ×
      </button>
    </div>
  );
}

function AppShellWithHeader() {
  const { pill, dock } = useActiveJobs();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  /**
   * deleteJob — calls DELETE /api/jobs/{id} then invalidates the active-jobs
   * query so the dock refreshes and the deleted row disappears.
   *
   * pdomain-ui 0.6.0: AppShellJobsProps.onJobDelete renders a trash button on
   * finished/failed job rows. This wires that button to the backend purge
   * endpoint (same one used by the e2e fixture cleanup script).
   */
  async function deleteJob(id: string): Promise<void> {
    try {
      await apiFetch(`/api/jobs/${id}`, { method: "DELETE" });
    } finally {
      await queryClient.invalidateQueries({ queryKey: ["active-jobs"] });
    }
  }

  /**
   * onJobOpen — opens the ResultsPage for a completed job.
   * simple-gui has no cancel/pause API (ocr-container-meta#395), so those
   * callbacks are omitted.
   */
  const jobsProps: AppShellJobsProps = {
    activeJobs: dock,
    onJobOpen: (jobId: string) => {
      navigate(`/jobs/${jobId}`);
    },
    onJobDelete: (jobId: string) => {
      void deleteJob(jobId);
    },
  };

  return (
    <>
      <ComputeStateWarmup />
      <AppShell
        appId="pdomain-ocr-simple-gui"
        appDisplayName="OCR Simple GUI"
        appIconUrl="/api/self/icons/32"
        deployMode="local"
        launcherSlot="header"
        uiPrefsConfig={uiPrefsConfig}
        settingsPanels={settingsPanels}
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
        main={
          <>
            <ConfigErrorBanner />
            <AppRoutes />
          </>
        }
      />
    </>
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
