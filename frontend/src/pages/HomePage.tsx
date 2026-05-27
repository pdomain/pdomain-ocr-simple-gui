// HomePage — A6.3
// Renders input affordances based on mode/container matrix from /api/config.
// Replaces legacy DropZone with SourcePicker.
import { useState } from "react";
import { useConfig } from "../runtime/ConfigContext";
import { SourcePicker } from "../components/SourcePicker";
import { RecentProjectsList } from "../components/RecentProjectsList";
import { JobConfigDialog } from "../components/JobConfigDialog";
import { APP_TEST_IDS } from "../lib/testids";

type ChosenSource =
  | { kind: "path"; path: string }
  | { kind: "upload"; uploadId: string };

/** Derive a display path from the chosen source for the legacy JobConfigDialog. */
function sourceToPath(source: ChosenSource): string {
  if (source.kind === "path") return source.path;
  // For uploads, use a sentinel so the jobs route knows to use upload_id.
  // A7 will wire OutputConfig properly; for now pass upload_id as the path.
  return `upload:${source.uploadId}`;
}

export function HomePage() {
  const cfg = useConfig();
  const [chosen, setChosen] = useState<ChosenSource | null>(null);

  function handleDialogClose() {
    setChosen(null);
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
      <RecentProjectsList />
      <JobConfigDialog
        open={chosen !== null}
        sourcePath={chosen ? sourceToPath(chosen) : ""}
        onClose={handleDialogClose}
      />
    </div>
  );
}
