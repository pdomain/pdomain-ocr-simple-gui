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
import { useOcrJob } from "../useOcrJob";
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
});
