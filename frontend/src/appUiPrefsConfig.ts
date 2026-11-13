import type { UIPrefsConfig } from "@pdomain/pdomain-ui/shell";
import { toast } from "sonner";
import { apiFetch } from "./api/apiFetch";

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
        ui_prefs?: { theme?: string; density?: string; font_scale?: number };
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
          typeof ui.font_scale === "number"
            ? Math.min(1.4, Math.max(0.8, ui.font_scale))
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
    // theme/density/font_scale slice), so this object shape is correct — do
    // NOT unwrap it. The backend read-modify-merges this partial body, so
    // sending only ui_prefs no longer resets sibling app prefs to defaults.
    // The backend field is snake_case and it ignores unknown keys.
    const { fontScale, ...rest } = prefs;
    const res = await apiFetch("/api/prefs", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ui_prefs: { ...rest, font_scale: fontScale } }),
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
