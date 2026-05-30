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
// Step 5 — AppHeader + useActiveJobs:
// Polls GET /api/jobs every 5s, filters to state==="running", maps to
// ActiveJob shape. No search affordance yet (simple-gui has no search feature).

import { useQuery } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import {
  AppShell,
  AppHeader,
  SuiteSiblingsProvider,
  ShortcutsHelpButton,
  SettingsSlot,
} from "@pdomain/pdomain-ui/shell";
import { ShortcutsProvider } from "@pdomain/pdomain-ui/hooks";
import type {
  UIPrefsConfig,
  InstalledApp,
  LaunchResult,
  ActiveJob,
} from "@pdomain/pdomain-ui/shell";
import { toast } from "sonner";
import { ConfigProvider } from "./runtime/ConfigContext";
import { HomePage } from "./pages/HomePage";
import ResultsPage from "./pages/ResultsPage";
import PageViewPage from "./pages/PageViewPage";

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
  pages?: { state: string }[];
}

/**
 * Polls /api/jobs every 5s and maps running jobs to the ActiveJob shape
 * expected by pdomain-ui AppHeader's JobsPill. Backend uses `state` field
 * (not `status`). Returns count of running pages as pct where available.
 */
function useActiveJobs(): ActiveJob[] {
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
  return (data ?? [])
    .filter((j) => j.state === "running" || j.state === "queued")
    .map((j) => {
      const total = j.page_count ?? j.pages?.length ?? 0;
      const done = j.pages?.filter((p) => p.state === "succeeded").length ?? 0;
      const pct = total > 0 ? Math.round((done / total) * 100) : 0;
      return {
        id: j.project_id,
        title: j.name ?? j.project_id,
        phase: j.state,
        pct,
        project: j.project_id,
      };
    });
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      {/* /new-job redirects to home — the dialog opens inline on HomePage */}
      <Route path="/new-job" element={<HomePage />} />
      <Route path="/jobs/:id" element={<ResultsPage />} />
      <Route path="/jobs/:id/pages/:idx" element={<PageViewPage />} />
    </Routes>
  );
}

function AppShellWithHeader() {
  const activeJobs = useActiveJobs();
  return (
    <AppShell
      appId="pdomain-ocr-simple-gui"
      appDisplayName="OCR Simple GUI"
      appIconUrl="/api/self/icons/32"
      deployMode="local"
      launcherSlot="header"
      uiPrefsConfig={uiPrefsConfig}
      header={
        // No onSearchClick — simple-gui has no search affordance yet.
        <AppHeader
          appName="OCR Simple GUI"
          activeJobs={activeJobs}
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
