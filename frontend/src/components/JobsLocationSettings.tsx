// JobsLocationSettings — app-injected SettingsModal panel.
//
// Lets the user choose where NEW OCR jobs/projects are stored. The backend
// resolves the projects root with precedence env > pref > default; this panel
// edits the `jobs_location` pref (the middle tier).
//
// Switch-not-migrate: changing the location affects only NEW jobs — existing
// jobs in the previous location are not moved.
//
// Persistence: reads/writes the flat AppPrefs body of /api/prefs directly
// (NOT the AppShell persistApp `{app_prefs:...}` wrapper). It GETs the current
// prefs, merges in the new jobs_location, and PUTs the merged object so other
// app prefs are preserved. A 400 from the backend (non-writable location) is
// surfaced inline.

import { useEffect, useState } from "react";
import { Button, Input } from "@pdomain/pdomain-ui/primitives";
import { APP_TEST_IDS } from "../lib/testids";

/** Shape of the GET /api/prefs response we care about here. */
interface PrefsResponse {
  jobs_location?: string;
  /** Read-only resolved root the backend would use right now. */
  effective_jobs_location?: string;
  [key: string]: unknown;
}

export function JobsLocationSettings() {
  // Full prefs object kept so PUT can merge rather than clobber sibling prefs.
  const [prefs, setPrefs] = useState<PrefsResponse>({});
  const [value, setValue] = useState<string>("");
  const [effective, setEffective] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);
  const [savedOk, setSavedOk] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/api/prefs");
        if (!res.ok) return;
        const data = (await res.json()) as PrefsResponse;
        if (cancelled) return;
        setPrefs(data);
        setValue(data.jobs_location ?? "");
        setEffective(data.effective_jobs_location ?? "");
      } catch {
        // Best-effort load; leave fields empty on failure.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave() {
    setSaving(true);
    setError("");
    setSavedOk(false);
    try {
      const merged = { ...prefs, jobs_location: value };
      // effective_jobs_location is a read-only echo — don't send it back.
      delete merged.effective_jobs_location;
      const res = await fetch("/api/prefs", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(merged),
      });
      if (!res.ok) {
        let detail = `Save failed (${res.status})`;
        try {
          const body = (await res.json()) as { detail?: string };
          if (body.detail) detail = body.detail;
        } catch {
          // keep the generic message
        }
        setError(detail);
        return;
      }
      const data = (await res.json()) as PrefsResponse;
      setPrefs(data);
      setValue(data.jobs_location ?? value);
      // Re-fetch effective location so the read-only display reflects the new
      // resolution (env may still override, in which case it stays unchanged).
      try {
        const fresh = await fetch("/api/prefs");
        if (fresh.ok) {
          const freshData = (await fresh.json()) as PrefsResponse;
          setEffective(freshData.effective_jobs_location ?? effective);
        }
      } catch {
        // keep the stale effective display
      }
      setSavedOk(true);
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    setValue("");
    setError("");
    setSavedOk(false);
  }

  return (
    <div data-testid="jobs-location-settings">
      <p className="label" style={{ marginBottom: "4px" }}>
        Jobs location
      </p>
      <p
        style={{
          fontSize: "0.85em",
          opacity: 0.8,
          marginBottom: "8px",
        }}
      >
        New jobs are saved here. Existing jobs in the previous location are not
        moved.
      </p>

      <p style={{ fontSize: "0.85em", marginBottom: "4px" }}>
        Current location:{" "}
        <code data-testid={APP_TEST_IDS.settingsJobsLocationCurrent}>
          {effective || "(default)"}
        </code>
      </p>

      <Input
        type="text"
        data-testid={APP_TEST_IDS.settingsJobsLocationInput}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setError("");
          setSavedOk(false);
        }}
        placeholder="Leave empty to use the default location"
        style={{ marginBottom: "8px" }}
      />

      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <Button
          data-testid={APP_TEST_IDS.settingsJobsLocationSave}
          onClick={() => void handleSave()}
          disabled={saving}
        >
          Save
        </Button>
        <Button
          variant="ghost"
          data-testid={APP_TEST_IDS.settingsJobsLocationReset}
          onClick={handleReset}
          disabled={saving}
        >
          Use default
        </Button>
        {savedOk && (
          <span
            data-testid="settings-jobs-location-saved"
            style={{ fontSize: "0.85em", opacity: 0.8 }}
          >
            Saved
          </span>
        )}
      </div>

      {error && (
        <p
          data-testid={APP_TEST_IDS.settingsJobsLocationError}
          role="alert"
          style={{ color: "var(--color-danger, #c0392b)", marginTop: "8px" }}
        >
          {error}
        </p>
      )}
    </div>
  );
}
