// App root — AppShell + React Router routing skeleton
// Issues #225 (scaffold), #226 (shell)

import { BrowserRouter, Routes, Route } from "react-router-dom";
import {
  AppShell,
  SuiteSiblingsProvider,
} from "@concavetrillion/pd-ui/shell";
import type { UIPrefsConfig, InstalledApp, LaunchResult } from "@concavetrillion/pd-ui/shell";
import HomePage from "./pages/HomePage";
import ResultsPage from "./pages/ResultsPage";
import PageViewPage from "./pages/PageViewPage";

/** Minimal UIPrefs config — reads/writes from /api/prefs app prefs. */
const uiPrefsConfig: UIPrefsConfig = {
  load: async () => {
    try {
      const res = await fetch("/api/prefs");
      if (!res.ok) return { theme: "dark" as const, density: "normal" as const, fontScale: 1.0 };
      const data = (await res.json()) as { ui_prefs?: { theme?: string; density?: string; fontScale?: number } };
      const ui = data.ui_prefs ?? {};
      return {
        theme: (ui.theme === "light" ? "light" : "dark") as "dark" | "light",
        density: (
          ["compact", "normal", "comfortable"].includes(ui.density ?? "")
            ? ui.density
            : "normal"
        ) as "compact" | "normal" | "comfortable",
        fontScale: typeof ui.fontScale === "number" ? Math.min(1.4, Math.max(0.8, ui.fontScale)) : 1.0,
      };
    } catch {
      return { theme: "dark" as const, density: "normal" as const, fontScale: 1.0 };
    }
  },
  persistCommon: async (prefs) => {
    try {
      await fetch("/api/prefs", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ui_prefs: prefs }),
      });
    } catch {
      // non-fatal
    }
  },
  persistApp: async (_appPrefs) => {
    // TODO: wire to PUT /api/prefs app-specific prefs in M7
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

export default function App() {
  return (
    <BrowserRouter>
      <SuiteSiblingsProvider value={{ fetchInstalled, postLaunch }}>
        <AppShell
          appId="pd-ocr-simple-gui"
          appDisplayName="OCR Simple GUI"
          appIconUrl="/api/self/icons/32"
          deployMode="local"
          launcherSlot="header"
          uiPrefsConfig={uiPrefsConfig}
          main={<AppRoutes />}
        />
      </SuiteSiblingsProvider>
    </BrowserRouter>
  );
}
