// Tests for JobsLocationSettings — the app-injected settings panel that lets
// the user pick where new OCR jobs are stored (switch-not-migrate).

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { JobsLocationSettings } from "../JobsLocationSettings";
import { renderWithProviders } from "../../test/test-utils";
import { APP_TEST_IDS } from "../../lib/testids";

function mockFetchSequence(
  handlers: Array<
    (url: string, init?: RequestInit) => Response | Promise<Response>
  >,
) {
  let call = 0;
  return vi.fn((url: string, init?: RequestInit) => {
    const handler = handlers[Math.min(call, handlers.length - 1)];
    call += 1;
    return Promise.resolve(handler(url, init));
  });
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("JobsLocationSettings", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the current effective jobs location and the stored value", async () => {
    const fetchMock = mockFetchSequence([
      () =>
        jsonResponse({
          jobs_location: "/home/u/custom",
          effective_jobs_location: "/home/u/custom",
        }),
    ]);
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<JobsLocationSettings />);

    await waitFor(() => {
      expect(
        screen.getByTestId(APP_TEST_IDS.settingsJobsLocationCurrent),
      ).toHaveTextContent("/home/u/custom");
    });
    const input = screen.getByTestId(
      APP_TEST_IDS.settingsJobsLocationInput,
    ) as HTMLInputElement;
    expect(input.value).toBe("/home/u/custom");
  });

  it("persists the input via PUT /api/prefs (merging existing prefs)", async () => {
    const fetchMock = mockFetchSequence([
      // initial GET
      () =>
        jsonResponse({
          default_engine: "tesseract",
          jobs_location: "",
          effective_jobs_location: "/default/root",
        }),
      // PUT
      (_url, init) => {
        const body = JSON.parse((init?.body as string) ?? "{}");
        expect(body.jobs_location).toBe("/new/jobs");
        // existing prefs preserved in the merged payload
        expect(body.default_engine).toBe("tesseract");
        return jsonResponse({ ...body });
      },
    ]);
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<JobsLocationSettings />);
    const input = await screen.findByTestId(
      APP_TEST_IDS.settingsJobsLocationInput,
    );
    await userEvent.clear(input);
    await userEvent.type(input, "/new/jobs");
    await userEvent.click(
      screen.getByTestId(APP_TEST_IDS.settingsJobsLocationSave),
    );

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        (c) => (c[1] as RequestInit | undefined)?.method === "PUT",
      );
      expect(putCall).toBeTruthy();
    });
  });

  it("shows the backend 400 error message inline", async () => {
    const fetchMock = mockFetchSequence([
      () => jsonResponse({ jobs_location: "", effective_jobs_location: "/d" }),
      () =>
        jsonResponse(
          { detail: "jobs location is not writable: /bad/path" },
          400,
        ),
    ]);
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<JobsLocationSettings />);
    const input = await screen.findByTestId(
      APP_TEST_IDS.settingsJobsLocationInput,
    );
    await userEvent.clear(input);
    await userEvent.type(input, "/bad/path");
    await userEvent.click(
      screen.getByTestId(APP_TEST_IDS.settingsJobsLocationSave),
    );

    await waitFor(() => {
      expect(
        screen.getByTestId(APP_TEST_IDS.settingsJobsLocationError),
      ).toHaveTextContent("not writable");
    });
  });

  it("does not clobber an in-progress edit when the prefs load resolves late", async () => {
    // Regression: the async GET /api/prefs in the mount effect used to call
    // setValue() unconditionally. On a slow/contended backend the GET could
    // resolve AFTER the user typed, silently discarding their edit — and a
    // subsequent Save would then persist the stale/empty value.
    let resolveGet: (r: Response) => void = () => {};
    const getPromise = new Promise<Response>((r) => {
      resolveGet = r;
    });
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "GET") return getPromise;
      const body = JSON.parse((init?.body as string) ?? "{}");
      return Promise.resolve(jsonResponse({ ...body }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<JobsLocationSettings />);
    const input = screen.getByTestId(
      APP_TEST_IDS.settingsJobsLocationInput,
    ) as HTMLInputElement;

    // User types BEFORE the initial prefs GET has resolved.
    await userEvent.type(input, "/user/typed");
    expect(input.value).toBe("/user/typed");

    // The slow GET now resolves with a DIFFERENT stored value.
    resolveGet(
      jsonResponse({
        jobs_location: "/stored/old",
        effective_jobs_location: "/stored/old",
      }),
    );

    // The read-only "current" display reflects the load, but the user's
    // in-progress edit must be preserved.
    await waitFor(() => {
      expect(
        screen.getByTestId(APP_TEST_IDS.settingsJobsLocationCurrent),
      ).toHaveTextContent("/stored/old");
    });
    expect(input.value).toBe("/user/typed");
  });

  it("reset clears the field", async () => {
    const fetchMock = mockFetchSequence([
      () =>
        jsonResponse({
          jobs_location: "/home/u/custom",
          effective_jobs_location: "/home/u/custom",
        }),
    ]);
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<JobsLocationSettings />);
    const input = (await screen.findByTestId(
      APP_TEST_IDS.settingsJobsLocationInput,
    )) as HTMLInputElement;
    await waitFor(() => expect(input.value).toBe("/home/u/custom"));

    await userEvent.click(
      screen.getByTestId(APP_TEST_IDS.settingsJobsLocationReset),
    );
    expect(input.value).toBe("");
  });
});
