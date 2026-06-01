// HomePage renders the source-selection and job-configuration flow from the
// jobCreationMachine runtime statechart.
import { useCallback, useEffect, useMemo } from "react";
import { useMachine } from "@xstate/react";
import { useNavigate } from "react-router-dom";
import { SourcePicker } from "../components/SourcePicker";
import { RecentProjectsList } from "../components/RecentProjectsList";
import { JobConfigInline } from "../components/JobConfigInline";
import { APP_TEST_IDS } from "../lib/testids";
import { jobCreationMachine } from "../statecharts/jobCreationMachine";
import type { JobForm } from "../statecharts/jobCreationTypes";
import { useShortcuts } from "@pdomain/pdomain-ui/hooks";
import type { ShortcutBinding } from "@pdomain/pdomain-ui/hooks";

const recentPaths = [
  "~/scans/belloc-survivals/jp2/",
  "belloc-survivals.zip",
  "manuscript-fragment.pdf",
];

export function HomePage() {
  const [snapshot, send] = useMachine(jobCreationMachine);
  const navigate = useNavigate();
  const { config, profile, source, uploadError, submitError } =
    snapshot.context;

  const chooseFiles = useCallback(
    (files: File[]) => send({ type: "FILES_SELECTED", files }),
    [send],
  );
  const choosePath = useCallback(
    (path: string) => send({ type: "PATH_CHOSEN", path }),
    [send],
  );
  const clearSource = useCallback(() => send({ type: "CLEAR_SOURCE" }), [send]);
  const changeJobForm = useCallback(
    (patch: Partial<JobForm>) => send({ type: "JOB_FORM_CHANGED", patch }),
    [send],
  );
  const submitJob = useCallback(
    (form: JobForm) => {
      send({ type: "JOB_FORM_CHANGED", patch: form });
      send({ type: "SUBMIT_JOB" });
    },
    [send],
  );

  useEffect(() => {
    if (snapshot.matches("submitted") && snapshot.context.submittedProjectId) {
      navigate(`/jobs/${snapshot.context.submittedProjectId}`);
    }
  }, [navigate, snapshot]);

  // B-SHELL-013: Register a home-route keyboard shortcut so the cheatsheet
  // is not empty when the user opens it from the home page.
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

  if (snapshot.matches("configFailed")) {
    return (
      <div data-testid={APP_TEST_IDS.homePage} className="home-page">
        <div role="alert" data-testid="home-config-error">
          <p>
            Could not load app configuration. The server may be unavailable.
          </p>
          <button
            type="button"
            data-testid="home-config-retry"
            onClick={() => send({ type: "CONFIG_RETRY" })}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (profile === null || config === null) return <div>Loading...</div>;

  const mode = config.mode;
  const localPathHint =
    profile.kind === "local-container"
      ? "Paths refer to the container filesystem (bind-mount your scans dir if needed)."
      : "Folder, image, or zip path on this machine.";
  return (
    <div data-testid={APP_TEST_IDS.homePage} className="home-page">
      {profile.kind === "managed-server" && (
        <SourcePicker
          allowDrop
          allowPathInput={false}
          uploadError={uploadError}
          onFilesSelected={chooseFiles}
          onPathChosen={choosePath}
          onClear={clearSource}
        />
      )}
      {profile.kind === "local-container" && (
        <>
          {source === null || source.kind === "upload" ? (
            <>
              <h3 className="heading-13">Upload</h3>
              <SourcePicker
                allowDrop
                allowPathInput={false}
                uploadError={uploadError}
                onFilesSelected={chooseFiles}
                onPathChosen={choosePath}
                onClear={clearSource}
              />
            </>
          ) : null}
          {source === null || source.kind === "path" ? (
            <>
              <h3 className="heading-13">Existing folder or zip</h3>
              <SourcePicker
                allowDrop={false}
                allowPathInput
                pathHint={localPathHint}
                recentPaths={recentPaths}
                uploadError={uploadError}
                onFilesSelected={chooseFiles}
                onPathChosen={choosePath}
                onClear={clearSource}
              />
            </>
          ) : null}
        </>
      )}
      {profile.kind === "local-host" && (
        <SourcePicker
          allowDrop
          allowPathInput
          pathHint={localPathHint}
          recentPaths={recentPaths}
          uploadError={uploadError}
          onFilesSelected={chooseFiles}
          onPathChosen={choosePath}
          onClear={clearSource}
        />
      )}
      {source !== null && (
        <JobConfigInline
          source={source}
          mode={mode}
          runtimeConfig={config}
          submitError={submitError}
          submitting={snapshot.matches("submittingJob")}
          onCancel={clearSource}
          onFormChanged={changeJobForm}
          onSubmitJob={submitJob}
        />
      )}
      <RecentProjectsList />
    </div>
  );
}
