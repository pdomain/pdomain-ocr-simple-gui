/**
 * useOcrJob — thin adapter wrapping useLongJob for simple-gui's backend.
 *
 * Strategy A: frontend adapter only (no backend changes).
 *
 * The backend can receive the canonical pd-suite JobState enum:
 *   queued | running | succeeded | failed | cancelled
 * This app's backend statechart never sends `cancelled` — the unreachable
 * `cancel` transition was stripped (ocr-container-meta#395). The value stays
 * in the wire type only for compatibility with the shared
 * `@pdomain/pdomain-ui` `JobState` type, so this frontend can still parse a
 * `cancelled` state without a runtime error if it ever appears. That is a
 * schema-compatibility guard, not license to re-add a cancel transition.
 *
 * useLongJob (from @pdomain/pdomain-ui/stores) expects its own internal
 * LongJobStatus enum:
 *   idle | pending | running | done | error | cancelled
 *
 * This adapter:
 *   1. Wraps apiFetch('/api/jobs/:id') in a pollFn passed to useLongJob.
 *   2. Maps backend JobState → LongJobStatus inside the pollFn.
 *   3. Stores the raw backend response in React state so callers can
 *      access extra fields (pages, output_dir, output_mode, name, page_count).
 *   4. Derives the progress fraction from pages_done / page_count.
 *
 * The hook returns a flat object combining useLongJob's state with the raw
 * backend data. Callers never touch useLongJob directly.
 */

import * as React from "react";
import { useLongJob } from "@pdomain/pdomain-ui/stores";
import type { LongJobStatus } from "@pdomain/pdomain-ui/stores";
import type { JobState } from "@pdomain/pdomain-ui/types";
import { apiFetch } from "./apiFetch";

/**
 * Error thrown by the job-status fetch carrying the HTTP status code.
 *
 * The status code is load-bearing: useOcrJob uses it to distinguish a
 * **terminal** 404 ("job not found" — stop polling, show a distinct message)
 * from a **transient** 5xx / network failure (keep polling, surface a
 * recoverable banner). Without the code, both collapse into the generic
 * "error" status and a deleted job reads the same as a server hiccup
 * (B-RESULTS-011 / B-RESULTS-012).
 */
export class JobFetchError extends Error {
  /** HTTP status code, or 0 for a network-level failure (no response). */
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "JobFetchError";
    this.status = status;
  }
}

interface OcrJobPage {
  page_idx: number;
  page_name: string;
  state: JobState;
  text_preview: string;
}

export interface OcrJobData {
  project_id: string;
  name: string;
  state: JobState;
  pages_done: number;
  page_count: number;
  output_dir?: string;
  output_mode?: "next_to_source" | "specified" | "managed";
  /**
   * Failure detail set by the backend when state is "failed" (e.g. the
   * "No supported image files found…" message). Surfaced on the ResultsPage
   * failed-state banner rather than swallowed (B-RESULTS-004).
   */
  error?: string | null;
  pages: OcrJobPage[];
  /**
   * Human-readable progress message stamped by the backend pipeline
   * (e.g. "Processing page 2/5 — img.png"). Optional/nullable so older
   * backends and post-terminal states omit it cleanly.
   */
  progress_message?: string | null;
}

export interface UseOcrJobOptions {
  /**
   * Optional fetch function — defaults to window.fetch. Injected for tests.
   * Receives jobId and returns the raw backend OcrJobData payload.
   */
  fetchFn?: (jobId: string) => Promise<OcrJobData>;
  /** Polling interval in ms (default 1000). */
  pollIntervalMs?: number;
}

export interface UseOcrJobResult {
  /** Status in LongJobStatus terms (useLongJob's own enum). */
  longJobStatus: LongJobStatus;
  /** 0–1 progress fraction derived from pages_done/page_count, or null. */
  progress: number | null;
  /** Raw backend payload — null until first poll resolves. */
  jobData: OcrJobData | null;
  /**
   * True when the status fetch returned 404 — the job does not exist (never
   * existed, or was deleted). This is a TERMINAL condition: polling stops and
   * the UI shows a distinct "Job not found" message rather than the generic
   * fetch-error banner (B-RESULTS-011).
   */
  notFound: boolean;
  /**
   * True when the most recent poll failed with a RETRYABLE error (5xx or a
   * network-level failure) rather than a terminal 404. Polling continues; the
   * UI can show a non-fatal "retrying" banner. Cleared on the next successful
   * poll (B-RESULTS-012).
   */
  transientError: boolean;
}

/** Map backend JobState → useLongJob's LongJobStatus. */
function toHookStatus(state: JobState): LongJobStatus {
  switch (state) {
    case "queued":
      return "pending";
    case "running":
      return "running";
    case "succeeded":
      return "done";
    case "failed":
      return "error";
    case "cancelled":
      return "cancelled";
  }
}

/**
 * Strip an optional ":N" rerun-key suffix that callers append to force a
 * poll restart when useLongJob has already reached a terminal state.
 * e.g. "proj-abc:1" → "proj-abc".
 */
function stripRerunKey(jobId: string): string {
  const colonIdx = jobId.lastIndexOf(":");
  if (colonIdx === -1) return jobId;
  const suffix = jobId.slice(colonIdx + 1);
  // Only strip if the suffix is a numeric rerun key (not a UUID segment)
  return /^\d+$/.test(suffix) ? jobId.slice(0, colonIdx) : jobId;
}

async function defaultFetchFn(jobId: string): Promise<OcrJobData> {
  const rawId = stripRerunKey(jobId);
  // A network-level failure (server down, DNS, CORS) rejects apiFetch() before
  // a Response exists — surface it as a JobFetchError with status 0 so the
  // hook treats it as transient (retryable), not as a terminal 404.
  let res: Response;
  try {
    res = await apiFetch(`/api/jobs/${rawId}`);
  } catch (err) {
    throw new JobFetchError(
      `GET /api/jobs/${rawId} failed: ${err instanceof Error ? err.message : String(err)}`,
      0,
    );
  }
  if (!res.ok) {
    // Carry the status code so the hook can distinguish 404 (terminal) from
    // 5xx (transient) — see JobFetchError.
    throw new JobFetchError(
      `GET /api/jobs/${rawId} returned ${res.status}`,
      res.status,
    );
  }
  return (await res.json()) as OcrJobData;
}

export function useOcrJob(
  jobId: string | null,
  options: UseOcrJobOptions = {},
): UseOcrJobResult {
  const { fetchFn = defaultFetchFn, pollIntervalMs = 1000 } = options;

  const [jobData, setJobData] = React.useState<OcrJobData | null>(null);
  const [notFound, setNotFound] = React.useState(false);
  const [transientError, setTransientError] = React.useState(false);

  // Stable pollFn reference — captures the state setters and the injectable
  // fetchFn. The error handling here is the heart of the 404-vs-transient
  // distinction (B-RESULTS-011 / -012):
  //
  //   * success            → clear transientError, store data, map status.
  //   * 404 (terminal)     → set notFound, RE-THROW so useLongJob goes
  //                          terminal ("error") and STOPS polling.
  //   * 5xx / network      → set transientError, swallow the throw and return
  //                          a NON-terminal status so useLongJob re-arms the
  //                          next poll (keep polling — the server may recover).
  const pollFn = React.useCallback(
    async (id: string) => {
      try {
        const data = await fetchFn(stripRerunKey(id));
        setJobData(data);
        setTransientError(false);
        return {
          status: toHookStatus(data.state),
          progress:
            data.page_count > 0 ? data.pages_done / data.page_count : null,
        };
      } catch (err) {
        const status = err instanceof JobFetchError ? err.status : 0;
        if (status === 404) {
          // Terminal: the job does not exist. Re-throw so useLongJob stops.
          setNotFound(true);
          throw err;
        }
        // Transient (5xx / network): keep polling. Returning "pending" (a
        // non-terminal LongJobStatus) makes useLongJob re-arm the next poll.
        setTransientError(true);
        return { status: "pending" as LongJobStatus, progress: null };
      }
    },
    [fetchFn],
  );

  // Reset all derived state when jobId changes (mirrors useLongJob's own reset
  // on id change). A new job must not inherit a stale notFound/transient flag.
  React.useEffect(() => {
    setJobData(null);
    setNotFound(false);
    setTransientError(false);
  }, [jobId]);

  const { status, progress } = useLongJob(jobId, {
    pollFn,
    pollIntervalMs,
  });

  return {
    longJobStatus: status,
    progress,
    jobData,
    notFound,
    transientError,
  };
}
