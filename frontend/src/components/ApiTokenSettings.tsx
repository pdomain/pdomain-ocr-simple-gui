// ApiTokenSettings — app-injected SettingsModal panel.
//
// Lets the user view (masked), set, update, and clear the `pdomain.apiToken`
// localStorage key that apiFetch.ts already reads on every API call. No
// backend endpoint — the token lives only in localStorage, so the input is
// seeded synchronously from `localStorage.getItem` rather than via a
// `useEffect` load: there is nothing async to race, unlike
// JobsLocationSettings' `/api/prefs` fetch.
//
// Saving an empty value clears the key rather than storing `""` — an empty
// string would still satisfy apiFetch's truthy check (apiFetch.ts:22) and
// attach an empty bearer token.

import { useState } from "react";
import { Button, Input } from "@pdomain/pdomain-ui/primitives";
import { TOKEN_STORAGE_KEY } from "../api/apiFetch";
import { APP_TEST_IDS } from "../lib/testids";

export function ApiTokenSettings() {
  const [value, setValue] = useState<string>(
    () => localStorage.getItem(TOKEN_STORAGE_KEY) ?? "",
  );
  const [isSet, setIsSet] = useState<boolean>(
    () => localStorage.getItem(TOKEN_STORAGE_KEY) !== null,
  );
  const [revealed, setRevealed] = useState<boolean>(false);
  const [savedOk, setSavedOk] = useState<boolean>(false);

  function handleSave() {
    const trimmed = value.trim();
    if (trimmed) {
      localStorage.setItem(TOKEN_STORAGE_KEY, trimmed);
    } else {
      // Empty Save clears the key rather than storing "" (see file header).
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    setValue(trimmed);
    setIsSet(trimmed !== "");
    setSavedOk(true);
  }

  function handleClear() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setValue("");
    setIsSet(false);
    setSavedOk(false);
  }

  return (
    <div data-testid="api-token-settings">
      <p className="label" style={{ marginBottom: "4px" }}>
        API token
      </p>
      <p
        style={{
          fontSize: "0.85em",
          opacity: 0.8,
          marginBottom: "8px",
        }}
      >
        Sent as an <code>Authorization: Bearer</code> header on every API call
        when the server requires <code>PDOMAIN_API_TOKEN</code>. Stored only in
        this browser.
      </p>

      <p style={{ fontSize: "0.85em", marginBottom: "4px" }}>
        Status:{" "}
        <code data-testid={APP_TEST_IDS.settingsApiTokenStatus}>
          {isSet ? "set" : "not set"}
        </code>
      </p>

      <Input
        type={revealed ? "text" : "password"}
        data-testid={APP_TEST_IDS.settingsApiTokenInput}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setSavedOk(false);
        }}
        placeholder="Leave empty for no token"
        style={{ marginBottom: "8px" }}
      />

      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <Button
          data-testid={APP_TEST_IDS.settingsApiTokenSave}
          onClick={handleSave}
        >
          Save
        </Button>
        <Button
          variant="ghost"
          data-testid={APP_TEST_IDS.settingsApiTokenClear}
          onClick={handleClear}
        >
          Clear
        </Button>
        <Button
          variant="ghost"
          data-testid={APP_TEST_IDS.settingsApiTokenReveal}
          onClick={() => setRevealed((r) => !r)}
        >
          {revealed ? "Hide" : "Show"}
        </Button>
        {savedOk && (
          <span
            data-testid={APP_TEST_IDS.settingsApiTokenSaved}
            style={{ fontSize: "0.85em", opacity: 0.8 }}
          >
            Saved
          </span>
        )}
      </div>
    </div>
  );
}
