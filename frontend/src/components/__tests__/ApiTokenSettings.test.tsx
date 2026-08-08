// Tests for ApiTokenSettings — the app-injected settings panel that lets the
// user view (masked), set, update, and clear the `pdomain.apiToken`
// localStorage key that apiFetch.ts consumes. No backend endpoint; the token
// lives only in localStorage, so there is nothing async to mock here.

import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiTokenSettings } from "../ApiTokenSettings";
import { renderWithProviders } from "../../test/test-utils";
import { APP_TEST_IDS } from "../../lib/testids";
import { TOKEN_STORAGE_KEY } from "../../api/apiFetch";

describe("ApiTokenSettings", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("shows 'not set' status and a masked empty input when no key is stored", () => {
    renderWithProviders(<ApiTokenSettings />);

    expect(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenStatus),
    ).toHaveTextContent("not set");
    const input = screen.getByTestId(
      APP_TEST_IDS.settingsApiTokenInput,
    ) as HTMLInputElement;
    expect(input.type).toBe("password");
    expect(input.value).toBe("");
  });

  it("seeds the input from an existing stored key, still masked", () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, "secret-token");

    renderWithProviders(<ApiTokenSettings />);

    expect(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenStatus),
    ).toHaveTextContent("set");
    const input = screen.getByTestId(
      APP_TEST_IDS.settingsApiTokenInput,
    ) as HTMLInputElement;
    expect(input.type).toBe("password");
    expect(input.value).toBe("secret-token");
  });

  it("typing then Save writes the key and shows the Saved confirmation", async () => {
    renderWithProviders(<ApiTokenSettings />);

    const input = screen.getByTestId(APP_TEST_IDS.settingsApiTokenInput);
    await userEvent.type(input, "new-token");
    await userEvent.click(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenSave),
    );

    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe("new-token");
    expect(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenSaved),
    ).toHaveTextContent("Saved");
  });

  it("the reveal toggle flips the input type to text", async () => {
    renderWithProviders(<ApiTokenSettings />);

    const input = screen.getByTestId(
      APP_TEST_IDS.settingsApiTokenInput,
    ) as HTMLInputElement;
    expect(input.type).toBe("password");

    await userEvent.click(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenReveal),
    );
    expect(input.type).toBe("text");

    await userEvent.click(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenReveal),
    );
    expect(input.type).toBe("password");
  });

  it("Clear removes the key and empties the input", async () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, "secret-token");
    renderWithProviders(<ApiTokenSettings />);

    const input = screen.getByTestId(
      APP_TEST_IDS.settingsApiTokenInput,
    ) as HTMLInputElement;
    expect(input.value).toBe("secret-token");

    await userEvent.click(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenClear),
    );

    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    expect(input.value).toBe("");
    expect(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenStatus),
    ).toHaveTextContent("not set");
  });

  it("saving an empty value clears the key rather than storing an empty string", async () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, "secret-token");
    renderWithProviders(<ApiTokenSettings />);

    const input = screen.getByTestId(APP_TEST_IDS.settingsApiTokenInput);
    await userEvent.clear(input);
    await userEvent.click(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenSave),
    );

    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    expect(
      screen.getByTestId(APP_TEST_IDS.settingsApiTokenStatus),
    ).toHaveTextContent("not set");
  });
});
