// App root — AppShell + React Router routing skeleton
// Issues #225 (scaffold), #226 (shell)

import { BrowserRouter, Routes, Route } from "react-router-dom";
import {
  AppShell,
  SuiteSiblingsProvider,
  TopNav,
  LauncherSlot,
} from "@concavetrillion/pd-ui/shell";

function AppHeader() {
  return (
    <TopNav>
      <img
        src="/api/self/icons/32"
        alt=""
        width={20}
        height={20}
        style={{ borderRadius: 4, flexShrink: 0 }}
      />
      <span
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: "var(--ink-1)",
          letterSpacing: "-0.01em",
          whiteSpace: "nowrap",
        }}
      >
        OCR Simple GUI
      </span>
      <div style={{ flex: 1 }} />
      <LauncherSlot />
    </TopNav>
  );
}
import type { UIPrefsConfig, InstalledApp, LaunchResult } from "@concavetrillion/pd-ui/shell";
import HomePage from "./pages/HomePage";
import ResultsPage from "./pages/ResultsPage";
import PageViewPage from "./pages/PageViewPage";

/** Minimal UIPrefs config — reads/writes from /api/prefs app prefs. */
const uiPrefsConfig: UIPrefsConfig = {
  load: async () => {
    try {
      const res = await fetch("/api/prefs");
      if (!res.ok) return { theme: "dark" as const, density: "normal" as const };
      const data = (await res.json()) as { ui_prefs?: { theme?: string; density?: string } };
      const ui = data.ui_prefs ?? {};
      return {
        theme: (ui.theme === "light" ? "light" : "dark") as "dark" | "light",
        density: (
          ["compact", "normal", "comfortable"].includes(ui.density ?? "")
            ? ui.density
            : "normal"
        ) as "compact" | "normal" | "comfortable",
      };
    } catch {
      return { theme: "dark" as const, density: "normal" as const };
    }
  },
  persistCommon: async (_prefs) => {
    // TODO: wire to PUT /api/prefs in M7
  },
  persistApp: async (_appPrefs) => {
    // TODO: wire to PUT /api/prefs in M7
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
          header={<AppHeader />}
          main={<AppRoutes />}
        />
      </SuiteSiblingsProvider>
    </BrowserRouter>
  );
}
