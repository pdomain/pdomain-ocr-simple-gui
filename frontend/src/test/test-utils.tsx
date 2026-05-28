/**
 * Shared frontend test utilities.
 *
 * Provides:
 *   - renderWithProviders — wraps UI in QueryClientProvider + MemoryRouter
 *   - mockFetchJson — stubs globalThis.fetch for a single URL pattern
 *   - resetFetch — clears the fetch stub after each test
 *   - fixtures — canonical in-memory data builders for common API shapes
 */

import { render, type RenderOptions } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement, ReactNode } from "react";
import { vi } from "vitest";

// ---------------------------------------------------------------------------
// renderWithProviders
// ---------------------------------------------------------------------------

export interface RenderWithProvidersOptions extends RenderOptions {
  /** Initial route path for MemoryRouter. Defaults to "/". */
  route?: string;
  /** Optional pre-configured QueryClient. A fresh no-retry client is used if omitted. */
  queryClient?: QueryClient;
}

/** Build a QueryClient suitable for tests: no retries, GC disabled. */
export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
    },
  });
}

/**
 * Render `ui` inside QueryClientProvider + MemoryRouter.
 * Covers the provider needs of every page-level spec in this repo.
 * Specs that need additional providers (ConfigProvider, etc.) can pass
 * a custom `wrapper` via RenderOptions.
 */
export function renderWithProviders(
  ui: ReactElement,
  { route = "/", queryClient, ...options }: RenderWithProvidersOptions = {},
) {
  const client = queryClient ?? makeTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...options });
}

// ---------------------------------------------------------------------------
// Fetch mock helpers
// ---------------------------------------------------------------------------

type FetchImpl = (
  url: string,
  opts?: RequestInit,
) => Promise<{
  ok: boolean;
  json?: () => Promise<unknown>;
  text?: () => Promise<string>;
}>;

/**
 * Install a simple fetch stub.
 * `handler` is called for every fetch; return the shaped response.
 * Stores the mock in a ref so tests can inspect calls via `.mock.calls`.
 */
export function installFetchMock(handler: FetchImpl): ReturnType<typeof vi.fn> {
  const mock = vi.fn().mockImplementation(handler);
  (globalThis as unknown as { fetch: unknown }).fetch = mock;
  return mock;
}

/**
 * Install a fetch stub that returns `body` as JSON for any URL matching `urlPattern`,
 * and `{ ok: false }` for everything else.
 * Returns the vi.fn so callers can assert calls.
 */
export function mockFetchJson(
  urlPattern: string | RegExp,
  body: unknown,
): ReturnType<typeof vi.fn> {
  return installFetchMock((url) => {
    const matched =
      typeof urlPattern === "string"
        ? url.includes(urlPattern)
        : urlPattern.test(url);
    if (matched) {
      return Promise.resolve({ ok: true, json: async () => body });
    }
    return Promise.resolve({ ok: false, json: async () => ({}) });
  });
}

/** Clear globalThis.fetch (call in afterEach if needed). */
export function resetFetch(): void {
  (globalThis as unknown as { fetch: unknown }).fetch = undefined;
}

// ---------------------------------------------------------------------------
// Fixture builders
// ---------------------------------------------------------------------------

export type JobState =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";
export type OutputMode = "next_to_source" | "specified" | "managed";

export interface PageRow {
  page_idx: number;
  page_name: string;
  state: string;
  text_preview: string;
}

export interface JobStatusFixture {
  project_id: string;
  name: string;
  state: JobState;
  pages_done: number;
  page_count: number;
  output_dir: string;
  output_mode?: OutputMode;
  pages: PageRow[];
  progress_message?: string;
}

export interface PageDataFixture {
  page_idx: number;
  page_name: string;
  state: string;
  text: string;
  width: number;
  height: number;
}

export const fixtures = {
  /** Minimal /api/config response. */
  config: (): { mode: string; is_containerized: boolean } => ({
    mode: "local",
    is_containerized: false,
  }),

  /** Build a JobStatus API response. */
  jobStatus: (
    state: JobState = "succeeded",
    {
      pagesDone = 3,
      pageCount = 3,
      outputMode,
      projectId = "proj-abc",
      name = "test-project",
      progressMessage,
    }: {
      pagesDone?: number;
      pageCount?: number;
      outputMode?: OutputMode;
      projectId?: string;
      name?: string;
      progressMessage?: string;
    } = {},
  ): JobStatusFixture => ({
    project_id: projectId,
    name,
    state,
    pages_done: pagesDone,
    page_count: pageCount,
    output_dir: "/tmp/out",
    ...(outputMode !== undefined ? { output_mode: outputMode } : {}),
    ...(progressMessage !== undefined
      ? { progress_message: progressMessage }
      : {}),
    pages: Array.from({ length: pageCount }, (_, i) => ({
      page_idx: i,
      page_name: `page_00${i + 1}.png`,
      state: "succeeded",
      text_preview: `Preview page ${i + 1}`,
    })),
  }),

  /** Build a single page data API response. */
  pageData: (idx = 0, text = "Sample OCR text"): PageDataFixture => ({
    page_idx: idx,
    page_name: `page_00${idx + 1}.png`,
    state: "done",
    text,
    width: 800,
    height: 1200,
  }),
};
