/**
 * Tests for apiFetch — a thin fetch wrapper that attaches a bearer token
 * from localStorage to every API call, when one has been set.
 *
 * Token source is deliberately minimal (localStorage, set via the browser
 * console — see docs/runbooks/install.md). There is no Settings UI for it
 * yet (tracked separately); this wrapper is the prerequisite plumbing so
 * that once a token is set, every mutating route (which now requires one)
 * keeps working.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "../apiFetch";

const TOKEN_KEY = "pdomain.apiToken";

afterEach(() => {
  localStorage.removeItem(TOKEN_KEY);
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("attaches bearer token from localStorage when present", async () => {
    localStorage.setItem(TOKEN_KEY, "sekrit");
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}"));

    await apiFetch("/api/jobs", { method: "POST" });

    expect(spy).toHaveBeenCalledOnce();
    const [, init] = spy.mock.calls[0];
    expect(new Headers(init?.headers).get("Authorization")).toBe(
      "Bearer sekrit",
    );
  });

  it("adds no Authorization header when token is unset", async () => {
    localStorage.removeItem(TOKEN_KEY);
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}"));

    await apiFetch("/api/jobs");

    expect(spy).toHaveBeenCalledOnce();
    const [, init] = spy.mock.calls[0];
    expect(new Headers(init?.headers).get("Authorization")).toBeNull();
  });

  it("adds no Authorization header when token is an empty string", async () => {
    localStorage.setItem(TOKEN_KEY, "");
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}"));

    await apiFetch("/api/jobs");

    expect(new Headers(spy.mock.calls[0][1]?.headers).get("Authorization")).toBeNull();
  });

  it("preserves caller-supplied headers given as a plain object", async () => {
    localStorage.setItem(TOKEN_KEY, "sekrit");
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}"));

    await apiFetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    const headers = new Headers(spy.mock.calls[0][1]?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Authorization")).toBe("Bearer sekrit");
  });

  it("preserves caller-supplied headers given as a Headers instance", async () => {
    localStorage.setItem(TOKEN_KEY, "sekrit");
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}"));

    await apiFetch("/api/jobs", {
      headers: new Headers({ "Content-Type": "application/json" }),
    });

    const headers = new Headers(spy.mock.calls[0][1]?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Authorization")).toBe("Bearer sekrit");
  });

  it("preserves caller-supplied headers given as an array of tuples", async () => {
    localStorage.setItem(TOKEN_KEY, "sekrit");
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}"));

    await apiFetch("/api/jobs", {
      headers: [["Content-Type", "application/json"]],
    });

    const headers = new Headers(spy.mock.calls[0][1]?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Authorization")).toBe("Bearer sekrit");
  });

  it("passes through unchanged (same call signature) when no token is set", async () => {
    localStorage.removeItem(TOKEN_KEY);
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}"));

    await apiFetch("/api/jobs", { method: "DELETE" });

    expect(spy).toHaveBeenCalledWith("/api/jobs", { method: "DELETE" });
  });

  it("calls fetch with a single argument when no init and no token are given", async () => {
    localStorage.removeItem(TOKEN_KEY);
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}"));

    await apiFetch("/api/jobs");

    expect(spy).toHaveBeenCalledWith("/api/jobs");
    expect(spy.mock.calls[0]).toHaveLength(1);
  });

  it("resolves with the underlying fetch Response", async () => {
    const response = new Response("hello");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response);

    const result = await apiFetch("/api/jobs");

    expect(result).toBe(response);
  });
});
