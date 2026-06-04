// Results page — M4 task #230, M6 task #233
// Screen 3: live polling job status + page list
// A7.2: download button for managed output mode.
// Task 9: replaced include-filter checkboxes with two explicit download buttons.
//
// Polling is handled by useOcrJob (frontend/src/api/useOcrJob.ts), a thin
// adapter that wraps useLongJob from @pdomain/pdomain-ui/stores. The
// hand-rolled fetch loop is gone; useOcrJob owns all poll/stop/cleanup logic.
//
// TODO(A9.2): pdomain-ui PageList (from @pdomain/pdomain-ui/worklist) requires
// {page_index, name, width, height} per item. PageRow here carries {page_idx,
// page_name, state, text_preview} with no width/height. The shapes are
// incompatible. Keeping the hand-rolled <table>.

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Progress, JobStatusPip, Button } from "@pdomain/pdomain-ui/primitives";
import { useOcrJob } from "../api/useOcrJob";
import { APP_TEST_IDS } from "../lib/testids";

const POLL_INTERVAL_MS = 1000;

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [rerunPending, setRerunPending] = useState(false);
  const [rerunError, setRerunError] = useState<string | null>(null);
  const [pathCopied, setPathCopied] = useState(false);

  // rerunKey is bumped after a successful rerun POST so useOcrJob sees a new
  // jobId and restarts polling (useLongJob stops when state reaches done/error).
  const [rerunKey, setRerunKey] = useState(0);

  // Encode rerunKey in jobId to force useOcrJob/useLongJob reset after rerun.
  const effectiveJobId = id ? `${id}:${rerunKey}` : null;

  const { longJobStatus, progress, jobData, notFound, transientError } =
    useOcrJob(effectiveJobId, {
      pollIntervalMs: POLL_INTERVAL_MS,
    });

  async function handleRerunAll() {
    if (!id) return;
    setRerunPending(true);
    setRerunError(null);
    try {
      const res = await fetch(`/api/jobs/${id}/rerun`, { method: "POST" });
      if (res.ok) {
        // Bump rerunKey so effectiveJobId changes, forcing useLongJob to
        // restart its polling loop (it stops when it reaches a terminal state).
        setRerunKey((k) => k + 1);
      } else {
        // B-RESULTS-009: a non-ok rerun was previously swallowed silently.
        // Surface it so the user knows the re-run did not start.
        setRerunError(`Re-run failed (HTTP ${res.status}). Please try again.`);
      }
    } catch (err) {
      // Network-level failure — surface it rather than swallowing.
      setRerunError(
        `Re-run failed: ${err instanceof Error ? err.message : "network error"}.`,
      );
    } finally {
      setRerunPending(false);
    }
  }

  // 404 is terminal and distinct: the job does not exist (deleted / never
  // existed). Show a dedicated "not found" block with a way back home rather
  // than the generic fetch-error banner (B-RESULTS-011).
  if (notFound) {
    return (
      <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
        <div
          role="alert"
          data-testid={APP_TEST_IDS.resultsNotFound}
          className="results-page__error"
        >
          <p>Job not found. It may have been deleted.</p>
          <Link to="/" data-testid={APP_TEST_IDS.resultsBackHome}>
            Back to home
          </Link>
        </div>
      </div>
    );
  }

  // A transient error (5xx / network) keeps polling under the hood — surface a
  // non-fatal banner (B-RESULTS-012). A terminal fetch error with no data also
  // lands here. NOTE: a *job* in the "failed" state ALSO maps to
  // longJobStatus="error" via toHookStatus — but that is a legitimate terminal
  // job result (jobData is populated), handled in the main render below, not a
  // fetch failure. Only treat it as a fetch error when there is no jobData.
  if (transientError || (longJobStatus === "error" && jobData === null)) {
    return (
      <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
        <p
          role="alert"
          data-testid={APP_TEST_IDS.resultsError}
          className="results-page__error"
        >
          {transientError
            ? "Error fetching job status — retrying…"
            : "Error fetching job status."}
        </p>
      </div>
    );
  }

  // Loading: jobId present but no data yet, no error/not-found flag.
  const isLoading = id !== undefined && jobData === null;

  if (isLoading) {
    return (
      <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
        <p
          data-testid={APP_TEST_IDS.resultsLoading}
          className="results-page__loading"
        >
          Loading…
        </p>
      </div>
    );
  }

  if (jobData === null) {
    return (
      <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
        <p
          role="alert"
          data-testid={APP_TEST_IDS.resultsError}
          className="results-page__error"
        >
          Error fetching job status.
        </p>
      </div>
    );
  }

  const {
    name,
    state,
    error,
    pages_done,
    page_count,
    output_dir,
    output_mode,
    pages,
    progress_message,
  } = jobData;

  const progressValue =
    progress !== null
      ? Math.round(progress * 100)
      : page_count > 0
        ? Math.round((pages_done / page_count) * 100)
        : 0;

  const isRunning = state === "queued" || state === "running";
  const isFailed = state === "failed";
  const showDownload = state === "succeeded" && output_mode === "managed";

  return (
    <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
      <header className="results-page__header">
        <h1 className="results-page__title">{name}</h1>
        <JobStatusPip state={state} />
      </header>

      {progress_message && (
        <p
          className="results-page__progress-message"
          data-testid={APP_TEST_IDS.jobProgressMessage}
        >
          {progress_message}
        </p>
      )}

      {/* B-RESULTS-004: a failed job surfaces its error text + a rerun control,
          rather than rendering only a bare red pip. */}
      {isFailed && (
        <div className="results-page__failed">
          <p
            role="alert"
            data-testid={APP_TEST_IDS.resultsError}
            className="results-page__error"
          >
            {error ?? "The job failed. See server logs for details."}
          </p>
          <Button
            variant="primary"
            disabled={rerunPending}
            aria-label="Re-run failed job"
            data-testid={APP_TEST_IDS.rerunFailedButton}
            onClick={() => {
              void handleRerunAll();
            }}
          >
            {rerunPending ? "Re-running…" : "Re-run job"}
          </Button>
        </div>
      )}

      {/* B-RESULTS-009: a non-ok rerun is surfaced, not swallowed. */}
      {rerunError && (
        <p
          role="alert"
          data-testid={APP_TEST_IDS.resultsRerunError}
          className="results-page__error"
        >
          {rerunError}
        </p>
      )}

      {isRunning && (
        <div className="results-page__progress">
          <Progress
            value={progressValue}
            status="running"
            label={`${pages_done} of ${page_count} pages`}
          />
          <p className="results-page__progress-label">
            {pages_done} / {page_count} pages complete
          </p>
        </div>
      )}

      {/* Task 9: two explicit download buttons replace the checkbox fieldset.
          Images are always included server-side; the buttons select which
          supplementary files are added to the zip. */}
      {showDownload && (
        <div className="results-page__download">
          <Button
            variant="primary"
            data-testid="download-images-text"
            onClick={() => {
              window.location.assign(
                `/api/jobs/${id ?? ""}/download?include=text`,
              );
            }}
          >
            Download (images + text)
          </Button>
          <Button
            variant="primary"
            data-testid="download-images-text-json"
            onClick={() => {
              window.location.assign(
                `/api/jobs/${id ?? ""}/download?include=${encodeURIComponent("text,json")}`,
              );
            }}
          >
            Download (images + text + JSON)
          </Button>
        </div>
      )}

      {state === "succeeded" && output_dir && (
        <div className="results-page__actions">
          <Button
            variant="ghost"
            data-testid={APP_TEST_IDS.copyPathButton}
            aria-label="Copy output path"
            onClick={() => {
              void navigator.clipboard.writeText(output_dir).then(() => {
                setPathCopied(true);
                setTimeout(() => {
                  setPathCopied(false);
                }, 1500);
              });
            }}
          >
            {pathCopied ? "Copied!" : "Copy path"}
          </Button>
          <Button
            variant="ghost"
            disabled={rerunPending}
            aria-label="Re-run all"
            data-testid={APP_TEST_IDS.rerunAllButton}
            onClick={() => {
              void handleRerunAll();
            }}
          >
            {rerunPending ? "Re-running…" : "Re-run all"}
          </Button>
        </div>
      )}

      {pages && pages.length > 0 && (
        <table className="jobs-table" aria-label="Page results">
          <thead>
            <tr>
              <th scope="col" className="jobs-table__th">
                Page
              </th>
              <th scope="col" className="jobs-table__th">
                Status
              </th>
              <th scope="col" className="jobs-table__th">
                Preview
              </th>
            </tr>
          </thead>
          <tbody>
            {pages.map((page) => (
              <tr
                key={page.page_idx}
                className="jobs-table__row"
                style={{ cursor: "pointer" }}
                tabIndex={0}
                role="row"
                data-testid={APP_TEST_IDS.pageRow}
                onClick={() =>
                  navigate(`/jobs/${id ?? ""}/pages/${page.page_idx}`)
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    navigate(`/jobs/${id ?? ""}/pages/${page.page_idx}`);
                  }
                }}
                aria-label={`Open page ${page.page_name}`}
              >
                <td className="results-page__page-name">{page.page_name}</td>
                <td className="results-page__page-status">
                  <JobStatusPip state={page.state} />
                </td>
                <td className="results-page__page-preview">
                  {page.text_preview ? page.text_preview.slice(0, 60) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
