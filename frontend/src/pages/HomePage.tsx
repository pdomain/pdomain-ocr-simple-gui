// HomePage — renders input affordances based on mode/container matrix from /api/config.
// After a source is chosen, an inline JobConfigInline form appears progressively
// below the SourcePicker(s); no modal dialog.
import { useState } from "react";
import { useConfig, useConfigStatus } from "../runtime/ConfigContext";
import { SourcePicker } from "../components/SourcePicker";
import { RecentProjectsList } from "../components/RecentProjectsList";
import {
  JobConfigInline,
  type ChosenSource,
} from "../components/JobConfigInline";
import { APP_TEST_IDS } from "../lib/testids";

export function HomePage() {
  const cfg = useConfig();
  const { error: configError, reload } = useConfigStatus();
  const [chosen, setChosen] = useState<ChosenSource | null>(null);

  function handleCancel() {
    setChosen(null);
  }

  // B-HOME-014 (Regression): when /api/config fails, surface the error +
  // a retry instead of hanging on "Loading…" forever.
  if (configError) {
    return (
      <div data-testid={APP_TEST_IDS.homePage} className="home-page">
        <div role="alert" data-testid="home-config-error">
          <p>Could not load app configuration. The server may be unavailable.</p>
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
