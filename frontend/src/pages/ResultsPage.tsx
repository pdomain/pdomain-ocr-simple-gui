// Results page — M4 task #230, M6 task #233
// Screen 3: live polling job status + page list
// A7.2: download button for managed output mode.
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
import { useNavigate, useParams } from "react-router-dom";
import { Progress, JobStatusPip, Button } from "@pdomain/pdomain-ui/primitives";
import { useOcrJob } from "../api/useOcrJob";
import { APP_TEST_IDS } from "../lib/testids";

const POLL_INTERVAL_MS = 1000;

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [rerunPending, setRerunPending] = useState(false);
  const [pathCopied, setPathCopied] = useState(false);

  // rerunKey is bumped after a successful rerun POST so useOcrJob sees a new
  // jobId and restarts polling (useLongJob stops when state reaches done/error).
  const [rerunKey, setRerunKey] = useState(0);

  // Encode rerunKey in jobId to force useOcrJob/useLongJob reset after rerun.
  const effectiveJobId = id ? `${id}:${rerunKey}` : null;

  const { longJobStatus, progress, jobData } = useOcrJob(effectiveJobId, {
    pollIntervalMs: POLL_INTERVAL_MS,
  });

  async function handleRerunAll() {
    if (!id) return;
    setRerunPending(true);
    try {
      const res = await fetch(`/api/jobs/${id}/rerun`, { method: "POST" });
      if (res.ok) {
        // Bump rerunKey so effectiveJobId changes, forcing useLongJob to
        // restart its polling loop (it stops when it reaches a terminal state).
        setRerunKey((k) => k + 1);
      }
    } catch {
      // ignore — user can retry
    } finally {
      setRerunPending(false);
    }
  }

  // Loading: jobId present but no data yet and not in error
  const isLoading =
    id !== undefined && jobData === null && longJobStatus !== "error";

  if (isLoading) {
    return (
      <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
        <p className="results-page__loading">Loading…</p>
      </div>
    );
  }

  if (longJobStatus === "error" || jobData === null) {
    return (
      <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
        <p role="alert" className="results-page__error">
          {longJobStatus === "error"
            ? "Error fetching job status."
            : "Job not found."}
        </p>
      </div>
    );
  }

  const {
    name,
    state,
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

      {showDownload && (
        <div className="results-page__download">
          <Button
            variant="primary"
            data-testid={APP_TEST_IDS.downloadResultsButton}
            onClick={() => {
              window.location.assign(
                `/api/jobs/${id ?? ""}/download?include=text,json`,
              );
            }}
          >
            Download results (.zip)
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
