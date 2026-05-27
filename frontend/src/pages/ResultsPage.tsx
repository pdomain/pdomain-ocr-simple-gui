// Results page — M4 task #230, M6 task #233
// Screen 3: live polling job status + page list
// A7.2: download button for managed output mode.
//
// TODO(A9.2): pdomain-ui PageList (from @pdomain/pdomain-ui/worklist) requires
// {page_index, name, width, height} per item. PageRow here carries {page_idx,
// page_name, state, text_preview} with no width/height. The shapes are
// incompatible. Keeping the hand-rolled <table>.

import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Progress, JobStatusPip, Button } from "@pdomain/pdomain-ui/primitives";
import type { JobState } from "@pdomain/pdomain-ui/types";
import { APP_TEST_IDS } from "../lib/testids";

interface PageRow {
  page_idx: number;
  page_name: string;
  state: JobState;
  text_preview: string;
}

interface JobStatus {
  project_id: string;
  name: string;
  state: JobState;
  pages_done: number;
  page_count: number;
  output_dir?: string;
  /** A7.2: output_mode returned by the backend when set at job creation. */
  output_mode?: "next_to_source" | "specified" | "managed";
  pages?: PageRow[];
}

const POLL_INTERVAL_MS = 1000;

function isTerminal(state: JobState): boolean {
  return state === "succeeded" || state === "failed" || state === "cancelled";
}

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [rerunPending, setRerunPending] = useState(false);
  const [pathCopied, setPathCopied] = useState(false);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  function clearTimer() {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  async function fetchStatus() {
    if (cancelledRef.current) return;
    try {
      const res = await fetch(`/api/jobs/${id ?? ""}`);
      if (cancelledRef.current) return;
      if (!res.ok) {
        setFetchError(`Error fetching job status: ${res.status}`);
        setLoading(false);
        return;
      }
      const data = (await res.json()) as JobStatus;
      if (cancelledRef.current) return;
      setJobStatus(data);
      setLoading(false);
      setFetchError(null);

      // Schedule next poll only if not terminal
      if (!isTerminal(data.state)) {
        timerRef.current = setTimeout(() => {
          void fetchStatus();
        }, POLL_INTERVAL_MS);
      }
    } catch {
      if (!cancelledRef.current) {
        setFetchError("Network error fetching job status.");
        setLoading(false);
      }
    }
  }

  async function handleRerunAll() {
    if (!id) return;
    setRerunPending(true);
    try {
      const res = await fetch(`/api/jobs/${id}/rerun`, { method: "POST" });
      if (res.ok) {
        // Reset local state to trigger re-polling
        setJobStatus(null);
        setLoading(true);
        cancelledRef.current = false;
        clearTimer();
        void fetchStatus();
      }
    } catch {
      // ignore — user can retry
    } finally {
      setRerunPending(false);
    }
  }

  useEffect(() => {
    cancelledRef.current = false;
    void fetchStatus();
    return () => {
      cancelledRef.current = true;
      clearTimer();
    };
    // polling effect intentionally keyed only on id; adding poll state would restart the interval
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (loading) {
    return (
      <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
        <p className="results-page__loading">Loading…</p>
      </div>
    );
  }

  if (fetchError || !jobStatus) {
    return (
      <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
        <p role="alert" className="results-page__error">
          {fetchError ?? "Job not found."}
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
  } = jobStatus;
  const progressValue =
    page_count > 0 ? Math.round((pages_done / page_count) * 100) : 0;
  const isRunning = state === "queued" || state === "running";
  const showDownload = state === "succeeded" && output_mode === "managed";

  return (
    <div data-testid={APP_TEST_IDS.resultsPage} className="results-page">
      <header className="results-page__header">
        <h1 className="results-page__title">{name}</h1>
        <JobStatusPip state={state} />
      </header>

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
            data-testid={APP_TEST_IDS.downloadResultsButton}
            onClick={() => {
              window.location.assign(`/api/jobs/${id ?? ""}/download`);
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
            onClick={() => {
              void handleRerunAll();
            }}
          >
            {rerunPending ? "Re-running…" : "Re-run all"}
          </Button>
        </div>
      )}

      {pages && pages.length > 0 && (
        <table className="results-page__table" aria-label="Page results">
          <thead>
            <tr>
              <th scope="col">Page</th>
              <th scope="col">Status</th>
              <th scope="col">Preview</th>
            </tr>
          </thead>
          <tbody>
            {pages.map((page) => (
              <tr
                key={page.page_idx}
                className="results-page__row"
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
