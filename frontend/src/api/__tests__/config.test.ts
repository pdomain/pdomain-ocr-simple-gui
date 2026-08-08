/**
 * Tests for fetchRuntimeConfig — the single place that fetches and parses
 * GET /api/config. Both ConfigContext (React) and jobCreationMachine
 * (xstate actor) delegate to this so the fetch + parse + error contract
 * exists in exactly one place (#396).
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchRuntimeConfig } from "../config";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchRuntimeConfig", () => {
  it("fetches and parses /api/config", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          mode: "local",
          is_containerized: true,
          detected_device: "cpu",
          gpu_available: false,
        }),
        { status: 200 },
      ),
    );

    const config = await fetchRuntimeConfig();

    expect(config).toEqual({
      mode: "local",
      is_containerized: true,
      detected_device: "cpu",
      gpu_available: false,
    });
  });

  it("throws on a non-ok (500) response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 500 }),
    );

    await expect(fetchRuntimeConfig()).rejects.toThrow(
      "GET /api/config failed: 500",
    );
  });

  it("propagates a network error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Network error"));

    await expect(fetchRuntimeConfig()).rejects.toThrow("Network error");
  });
});
