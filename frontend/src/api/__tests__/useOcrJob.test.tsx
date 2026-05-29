/**
 * Tests for useOcrJob — the adapter hook wrapping useLongJob for simple-gui.
 *
 * Strategy A: frontend adapter only. Maps backend JobState enum
 * (queued | running | succeeded | failed | cancelled) → LongJobStatus
 * (idle | pending | running | done | error | cancelled) inside the pollFn
 * passed to useLongJob. Backend is untouched.
 */

import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useOcrJob, JobFetchError } from "../useOcrJob";
import type { OcrJobData } from "../useOcrJob";

function makeBackendResponse(
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled",
  overrides: Partial<OcrJobData> = {},
): OcrJobData {
  return {
    project_id: "proj-1",
    name: "my-project",
    state,
    pages_done: 2,
    page_count: 5,
    output_dir: "/tmp/out",
    output_mode: undefined,
    pages: [],
    ...overrides,
  };
}

describe("useOcrJob", () => {
  it("starts idle with no job data when jobId is null", () => {
    const { result } = renderHook(() => useOcrJob(null));
    expect(result.current.longJobStatus).toBe("idle");
    expect(result.current.jobData).toBeNull();
  });

  it("maps backend 'queued' → LongJobStatus 'pending'", async () => {
    const fetchFn = vi.fn().mockResolvedValue(makeBackendResponse("queued"));
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 100 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.longJobStatus).toBe("pending");
    expect(result.current.jobData?.state).toBe("queued");
  });

  it("maps backend 'running' → LongJobStatus 'running'", async () => {
    const fetchFn = vi.fn().mockResolvedValue(makeBackendResponse("running"));
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 100 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.longJobStatus).toBe("running");
    expect(result.current.jobData?.state).toBe("running");
  });

  it("maps backend 'succeeded' → LongJobStatus 'done'", async () => {
    const fetchFn = vi.fn().mockResolvedValue(makeBackendResponse("succeeded"));
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 100 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.longJobStatus).toBe("done");
    expect(result.current.jobData?.state).toBe("succeeded");
  });

  it("maps backend 'failed' → LongJobStatus 'error'", async () => {
    const fetchFn = vi.fn().mockResolvedValue(makeBackendResponse("failed"));
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 100 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.longJobStatus).toBe("error");
    expect(result.current.jobData?.state).toBe("failed");
  });

  it("maps backend 'cancelled' → LongJobStatus 'cancelled'", async () => {
    const fetchFn = vi.fn().mockResolvedValue(makeBackendResponse("cancelled"));
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 100 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.longJobStatus).toBe("cancelled");
    expect(result.current.jobData?.state).toBe("cancelled");
  });

  it("exposes progress as fraction of pages_done / page_count", async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValue(
        makeBackendResponse("running", { pages_done: 3, page_count: 6 }),
      );
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 100 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.progress).toBeCloseTo(0.5);
  });

  it("surfaces extra fields (output_dir, output_mode, pages, name) via jobData", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      makeBackendResponse("succeeded", {
        output_dir: "/home/user/out",
        output_mode: "managed",
        name: "special-book",
        pages: [
          {
            page_idx: 0,
            page_name: "p1.png",
            state: "succeeded",
            text_preview: "hi",
          },
        ],
      }),
    );
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 100 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.jobData?.output_dir).toBe("/home/user/out");
    expect(result.current.jobData?.output_mode).toBe("managed");
    expect(result.current.jobData?.name).toBe("special-book");
    expect(result.current.jobData?.pages).toHaveLength(1);
  });

  it("stops polling when state reaches succeeded", async () => {
    let callCount = 0;
    const fetchFn = vi.fn().mockImplementation(async () => {
      callCount++;
      return makeBackendResponse("succeeded");
    });
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 50 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 120));
    });
    // Should have polled once (done → stop)
    expect(callCount).toBe(1);
    expect(result.current.longJobStatus).toBe("done");
  });

  it("resets to idle when jobId changes to null", async () => {
    const fetchFn = vi.fn().mockResolvedValue(makeBackendResponse("running"));
    let jobId: string | null = "proj-1";
    const { result, rerender } = renderHook(() =>
      useOcrJob(jobId, { fetchFn, pollIntervalMs: 5000 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.longJobStatus).toBe("running");

    jobId = null;
    act(() => {
      rerender();
    });
    expect(result.current.longJobStatus).toBe("idle");
    expect(result.current.jobData).toBeNull();
  });

  it("uses the default fetch when fetchFn is not provided (stub — verifies no crash)", () => {
    const { result } = renderHook(() => useOcrJob("proj-1"));
    // Without fetchFn, the hook should not crash. It will poll via window.fetch.
    // In jsdom with no fetch mock, this will go to error — that's acceptable.
    // The test verifies the hook initialises without throwing.
    expect(result.current).toBeDefined();
  });

  // ---------------------------------------------------------------------------
  // Bad-case tests (M4 strengthening)
  // ---------------------------------------------------------------------------

  it("returns null progress when page_count is zero (division-by-zero guard)", async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValue(
        makeBackendResponse("running", { pages_done: 0, page_count: 0 }),
      );
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 100 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.progress).toBeNull();
  });

  it("surfaces undefined extra fields gracefully when API omits them", async () => {
    // Backend response without output_dir / output_mode — hook must not crash.
    const minimal = {
      project_id: "proj-1",
      name: "proj",
      state: "succeeded" as const,
      pages_done: 1,
      page_count: 1,
      pages: [],
    };
    const fetchFn = vi.fn().mockResolvedValue(minimal);
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 100 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(result.current.longJobStatus).toBe("done");
    expect(result.current.jobData?.output_dir).toBeUndefined();
    expect(result.current.jobData?.output_mode).toBeUndefined();
  });

  // ---------------------------------------------------------------------------
  // 404 (terminal not-found) vs transient (retry) distinction — B-RESULTS-011/-012
  // ---------------------------------------------------------------------------

  it("flags notFound and goes terminal when the fetch throws a 404 JobFetchError", async () => {
    // B-RESULTS-011: a 404 is a terminal "job not found" — stop polling, set notFound.
    let callCount = 0;
    const fetchFn = vi.fn().mockImplementation(async () => {
      callCount++;
      throw new JobFetchError("not found", 404);
    });
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 50 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 200));
    });
    expect(result.current.notFound).toBe(true);
    expect(result.current.longJobStatus).toBe("error");
    // Polling must STOP on a 404 (terminal) — only the first poll fires.
    expect(callCount).toBe(1);
  });

  it("keeps polling (does NOT go terminal) on a transient network error", async () => {
    // B-RESULTS-012: a generic network failure is retryable — keep polling,
    // do not set notFound, surface a transient-error flag instead.
    let callCount = 0;
    const fetchFn = vi.fn().mockImplementation(async () => {
      callCount++;
      throw new Error("Network failure");
    });
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 50 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 200));
    });
    expect(result.current.notFound).toBe(false);
    expect(result.current.transientError).toBe(true);
    // Polling must CONTINUE through transient errors → more than one poll.
    expect(callCount).toBeGreaterThan(1);
    // The hook must not be terminal — useLongJob keeps re-arming.
    expect(result.current.longJobStatus).not.toBe("error");
  });

  it("keeps polling on a transient 5xx JobFetchError", async () => {
    // B-RESULTS-012: a 5xx is retryable, distinct from a terminal 404.
    let callCount = 0;
    const fetchFn = vi.fn().mockImplementation(async () => {
      callCount++;
      throw new JobFetchError("server error", 503);
    });
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 50 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 200));
    });
    expect(result.current.notFound).toBe(false);
    expect(result.current.transientError).toBe(true);
    expect(callCount).toBeGreaterThan(1);
  });

  it("clears the transientError flag after a poll recovers", async () => {
    // B-RESULTS-012: once a poll succeeds again, the transient flag clears.
    let callCount = 0;
    const fetchFn = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) throw new Error("Network blip");
      return makeBackendResponse("running");
    });
    const { result } = renderHook(() =>
      useOcrJob("proj-1", { fetchFn, pollIntervalMs: 50 }),
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 250));
    });
    expect(result.current.transientError).toBe(false);
    expect(result.current.jobData?.state).toBe("running");
  });
});
