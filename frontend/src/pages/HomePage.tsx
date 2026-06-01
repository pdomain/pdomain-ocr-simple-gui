// HomePage — renders input affordances based on mode/container matrix from /api/config.
// After a source is chosen, an inline JobConfigInline form appears progressively
// below the SourcePicker(s); no modal dialog.
import { useState, useMemo, useCallback } from "react";
import { useConfig, useConfigStatus } from "../runtime/ConfigContext";
import { SourcePicker } from "../components/SourcePicker";
import { RecentProjectsList } from "../components/RecentProjectsList";
import {
  JobConfigInline,
  type ChosenSource,
} from "../components/JobConfigInline";
import { APP_TEST_IDS } from "../lib/testids";
import { useShortcuts } from "@pdomain/pdomain-ui/hooks";
import type { ShortcutBinding } from "@pdomain/pdomain-ui/hooks";

export function HomePage() {
  const cfg = useConfig();
  const { error: configError, reload } = useConfigStatus();
  const [chosen, setChosen] = useState<ChosenSource | null>(null);

  function handleCancel() {
    setChosen(null);
  }

  // B-SHELL-013: Register a home-route keyboard shortcut so the cheatsheet
  // is not empty when the user opens it from the home page.
  // "n" → focus the source path input (if present in current mode).
  // useCallback + useMemo: stable references prevent infinite re-registration
  // via ShortcutsContext (allBindings changes cause Provider re-render →
  // new bindings array → new registration → loop).
  const focusPathInput = useCallback(() => {
    const el = document.querySelector<HTMLElement>(
      `[data-testid="${APP_TEST_IDS.sourcePickerPathInput}"]`,
    );
    el?.focus();
  }, []);

  const homeShortcuts = useMemo<ShortcutBinding[]>(
    () => [
      {
        keys: "n",
        label: "Focus source path input",
        group: "Home",
        handler: focusPathInput,
      },
    ],
    [focusPathInput],
  );

  useShortcuts(homeShortcuts);

  // B-HOME-014 (Regression): when /api/config fails, surface the error +
  // a retry instead of hanging on "Loading…" forever.
  if (configError) {
    return (
      <div data-testid={APP_TEST_IDS.homePage} className="home-page">
        <div role="alert" data-testid="home-config-error">
          <p>
            Could not load app configuration. The server may be unavailable.
          </p>
          <button
            type="button"
            data-testid="home-config-retry"
            onClick={() => void reload()}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!cfg) return <div>Loading…</div>;

  const mode = cfg.mode;
  const containerized = cfg.is_containerized;
  const clearChosen = () => setChosen(null);

  return (
    <div data-testid={APP_TEST_IDS.homePage} className="home-page">
      {mode === "managed" && (
        <SourcePicker
          allowDrop
          allowPathInput={false}
          onUploadComplete={(id) => setChosen({ kind: "upload", uploadId: id })}
          onPathChosen={() => {}}
          onClear={clearChosen}
        />
      )}
      {mode === "local" && containerized && (
        <>
          {/* Hide the upload picker once a path source is chosen, and vice versa.
              Both pickers are visible when no source is chosen (chosen === null).
              Once one source is chosen, only that source is visible. Clearing
              (onClear → clearChosen) restores chosen to null → both reappear. */}
          {chosen === null || chosen.kind === "upload" ? (
            <>
              <h3 className="heading-13">Upload</h3>
              <SourcePicker
                allowDrop
                allowPathInput={false}
                onUploadComplete={(id) =>
                  setChosen({ kind: "upload", uploadId: id })
                }
                onPathChosen={() => {}}
                onClear={clearChosen}
              />
            </>
          ) : null}
          {chosen === null || chosen.kind === "path" ? (
            <>
              <h3 className="heading-13">Existing folder or zip</h3>
              <SourcePicker
                allowDrop={false}
                allowPathInput
                pathHint="Paths refer to the container filesystem (bind-mount your scans dir if needed)."
                onUploadComplete={() => {}}
                onPathChosen={(p) => setChosen({ kind: "path", path: p })}
                onClear={clearChosen}
              />
            </>
          ) : null}
        </>
      )}
      {mode === "local" && !containerized && (
        <SourcePicker
          allowDrop
          allowPathInput
          pathHint="Folder, image, or zip path on this machine."
          onUploadComplete={(id) => setChosen({ kind: "upload", uploadId: id })}
          onPathChosen={(p) => setChosen({ kind: "path", path: p })}
          onClear={clearChosen}
        />
      )}
      {chosen !== null && (
        <JobConfigInline source={chosen} mode={mode} onCancel={handleCancel} />
      )}
      <RecentProjectsList />
    </div>
  );
}
