/**
 * apiFetch — thin `fetch` wrapper that attaches a bearer token when one has
 * been set.
 *
 * Every mutating backend route can require `PDOMAIN_API_TOKEN`
 * (see `src/pdomain_ocr_simple_gui/auth.py`); without this wrapper the
 * frontend never sent the token and every protected call failed once a
 * token was configured. All API calls in `frontend/src` should go through
 * `apiFetch` instead of calling `fetch` directly.
 *
 * The token itself is read from `localStorage` under the
 * `pdomain.apiToken` key. There is deliberately no Settings UI for it yet
 * (see docs/runbooks/install.md for how to set it from the browser
 * console); that follow-up is tracked separately.
 */

export const TOKEN_STORAGE_KEY = "pdomain.apiToken";

export function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (!token) {
    // Preserve the caller's exact call signature (no token → no wrapping)
    // rather than always forwarding a second `init` argument, which would
    // change `fetch` call signatures observed by tests/mocks.
    return init === undefined ? fetch(input) : fetch(input, init);
  }

  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}
