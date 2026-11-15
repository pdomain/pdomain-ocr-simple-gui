import type { ReactElement } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/apiFetch";

interface LifecyclePreferences {
  managed: boolean;
  keepRunning: boolean;
}
const queryKey = ["app-prefs", "desktop-lifecycle"];

async function readPreferences(
  signal: AbortSignal,
): Promise<LifecyclePreferences> {
  const bootstrap = await apiFetch("/api/lifecycle/bootstrap", {
    method: "POST",
    signal,
  });
  if (!bootstrap.ok) throw new Error("Could not read app session settings.");
  const session: unknown = await bootstrap.json();
  if (
    typeof session !== "object" ||
    session === null ||
    !("managed" in session) ||
    typeof session.managed !== "boolean"
  ) {
    throw new Error("The app returned invalid session settings.");
  }
  if (!session.managed) return { managed: false, keepRunning: true };
  const response = await apiFetch("/api/prefs", { signal });
  if (!response.ok) throw new Error("Could not read app preferences.");
  const prefs: unknown = await response.json();
  if (
    typeof prefs !== "object" ||
    prefs === null ||
    !("keep_running" in prefs) ||
    typeof prefs.keep_running !== "boolean"
  ) {
    throw new Error("The app returned invalid preferences.");
  }
  return { managed: true, keepRunning: prefs.keep_running };
}

export function LifecycleSettings(): ReactElement {
  const client = useQueryClient();
  const preferences = useQuery({
    queryKey,
    queryFn: ({ signal }) => readPreferences(signal),
  });
  const save = useMutation({
    mutationFn: async (keepRunning: boolean) => {
      const response = await apiFetch("/api/lifecycle/options", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keep_running: keepRunning }),
      });
      if (!response.ok) throw new Error("Could not save app session settings.");
    },
    onSuccess: () => client.invalidateQueries({ queryKey }),
  });
  if (preferences.isPending) return <p role="status">Loading app settings…</p>;
  if (preferences.error) return <p role="alert">{preferences.error.message}</p>;
  if (!preferences.data.managed)
    return <p>This session keeps running until it is stopped.</p>;
  return (
    <div>
      <label>
        <input
          type="checkbox"
          checked={preferences.data.keepRunning}
          disabled={save.isPending}
          onChange={(event) => save.mutate(event.target.checked)}
        />{" "}
        Keep app running after all tabs close
      </label>
      <p>
        Otherwise it stops 30 seconds after the last tab closes, once current
        work finishes.
      </p>
      {save.error && <p role="alert">{save.error.message}</p>}
    </div>
  );
}
