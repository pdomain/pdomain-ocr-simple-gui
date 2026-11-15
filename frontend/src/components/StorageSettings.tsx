import { useState, type ReactElement } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Input } from "@pdomain/pdomain-ui/primitives";
import { apiFetch } from "../api/apiFetch";

interface Locations {
  paths: Record<string, string>;
  overrides: Record<string, string>;
  installation: Record<string, string>;
  model_paths: Record<string, string>;
  legacy_data_present: boolean;
  migration_in_progress: boolean;
  requested_model_cache: string;
  model_cache_restart_required: boolean;
}
interface Preview {
  destination: string;
  projects: string[];
  retained_items: string[];
}
const queryKey = ["locations"];
const dataRoots = ["data", "projects", "uploads", "outputs", "jobs"];

function stringMap(value: unknown): value is Record<string, string> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((item: unknown) => typeof item === "string")
  );
}
function strings(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.every((item: unknown) => typeof item === "string")
  );
}
async function responseJson(response: Response): Promise<unknown> {
  const body: unknown = await response.json();
  if (!response.ok) {
    const message =
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
        ? body.detail
        : "The app could not complete this request.";
    throw new Error(message);
  }
  return body;
}
async function readLocations(signal: AbortSignal): Promise<Locations> {
  const body = await responseJson(await apiFetch("/api/locations", { signal }));
  if (
    typeof body !== "object" ||
    body === null ||
    !("paths" in body) ||
    !stringMap(body.paths) ||
    !("overrides" in body) ||
    !stringMap(body.overrides) ||
    !("installation" in body) ||
    !stringMap(body.installation) ||
    !("model_paths" in body) ||
    !stringMap(body.model_paths) ||
    !("legacy_data_present" in body) ||
    typeof body.legacy_data_present !== "boolean" ||
    !("migration_in_progress" in body) ||
    typeof body.migration_in_progress !== "boolean" ||
    !("requested_model_cache" in body) ||
    typeof body.requested_model_cache !== "string" ||
    !("model_cache_restart_required" in body) ||
    typeof body.model_cache_restart_required !== "boolean"
  )
    throw new Error("The app returned invalid location information.");
  return {
    paths: body.paths,
    overrides: body.overrides,
    installation: body.installation,
    model_paths: body.model_paths,
    legacy_data_present: body.legacy_data_present,
    migration_in_progress: body.migration_in_progress,
    requested_model_cache: body.requested_model_cache,
    model_cache_restart_required: body.model_cache_restart_required,
  };
}
async function previewMove(destination: string): Promise<Preview> {
  const body = await responseJson(
    await apiFetch("/api/locations/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ destination }),
    }),
  );
  if (
    typeof body !== "object" ||
    body === null ||
    !("destination" in body) ||
    typeof body.destination !== "string" ||
    !("projects" in body) ||
    !strings(body.projects) ||
    !("retained_items" in body) ||
    !strings(body.retained_items)
  ) {
    throw new Error("The app returned an invalid move preview.");
  }
  return {
    destination: body.destination,
    projects: body.projects,
    retained_items: body.retained_items,
  };
}

export function StorageSettings(): ReactElement {
  const client = useQueryClient();
  const locations = useQuery({
    queryKey,
    queryFn: ({ signal }) => readLocations(signal),
  });
  const [destination, setDestination] = useState("");
  const [modelDraft, setModelDraft] = useState<string | null>(null);
  const preview = useMutation({ mutationFn: previewMove });
  const move = useMutation({
    mutationFn: async (target: string) => {
      const result = await responseJson(
        await apiFetch("/api/locations/migrate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ destination: target }),
        }),
      );
      if (
        typeof result !== "object" ||
        result === null ||
        !("originals_preserved" in result) ||
        result.originals_preserved !== true
      )
        throw new Error("The app returned an invalid migration result.");
      return result;
    },
    onSuccess: () => client.invalidateQueries(),
  });
  const model = useMutation({
    mutationFn: async (value: string) =>
      responseJson(
        await apiFetch("/api/prefs", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model_cache_location: value }),
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey }),
  });
  if (locations.isPending)
    return <p role="status">Loading storage locations…</p>;
  if (locations.error) return <p role="alert">{locations.error.message}</p>;
  const data = locations.data;
  const overridden = dataRoots.some((name) => name in data.overrides);
  const busy = move.isPending || data.migration_in_progress;
  return (
    <section className="storage-settings">
      <h3>App data</h3>
      <dl>
        {Object.entries(data.paths).map(([name, path]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>
              <code>{path}</code>
              {data.overrides[name] && <small> {data.overrides[name]}</small>}
            </dd>
          </div>
        ))}
      </dl>
      {data.legacy_data_present && (
        <p>
          Existing data remains at earlier locations. Moving keeps the
          originals.
        </p>
      )}
      {overridden && (
        <p>
          Data locations are controlled by environment variables. Change those
          overrides before moving data.
        </p>
      )}
      <label htmlFor="new-data-folder">New data folder</label>
      <Input
        id="new-data-folder"
        value={destination}
        disabled={busy}
        onChange={(event) => {
          setDestination(event.target.value);
          preview.reset();
          move.reset();
        }}
        placeholder={data.paths.data}
      />
      <Button
        disabled={
          overridden || busy || !destination.trim() || preview.isPending
        }
        onClick={() => preview.mutate(destination)}
      >
        Review data move
      </Button>
      {preview.data && !move.isSuccess && (
        <div>
          <p>
            Move {preview.data.projects.length} jobs to{" "}
            <code>{preview.data.destination}</code>. Source scans and original
            files stay where they are.
          </p>
          {preview.data.retained_items.length > 0 && (
            <details>
              <summary>Files staying in the old location</summary>
              <ul>
                {preview.data.retained_items.map((path) => (
                  <li key={path}>
                    <code>{path}</code>
                  </li>
                ))}
              </ul>
            </details>
          )}
          <Button
            disabled={busy}
            onClick={() => move.mutate(preview.data.destination)}
          >
            Move data
          </Button>
        </div>
      )}
      {busy && (
        <p role="status">Moving and verifying data. Keep the app open.</p>
      )}
      {move.isSuccess && (
        <p role="status">Data move completed. Original files were kept.</p>
      )}
      {(preview.error || move.error) && (
        <p role="alert">{(preview.error ?? move.error)?.message}</p>
      )}
      <h3>Model caches</h3>
      <dl>
        {Object.entries(data.model_paths).map(([name, path]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>
              <code>{path}</code>
            </dd>
          </div>
        ))}
      </dl>
      <label htmlFor="model-cache-folder">Model cache folder</label>
      <Input
        id="model-cache-folder"
        value={modelDraft ?? data.requested_model_cache}
        onChange={(event) => setModelDraft(event.target.value)}
        placeholder="Use existing provider defaults"
      />
      <Button
        disabled={model.isPending || modelDraft === null}
        onClick={() => model.mutate(modelDraft ?? "")}
      >
        Save model location
      </Button>
      <p>
        Changes apply after restarting. Existing caches are kept. Environment
        overrides take precedence.
      </p>
      {data.model_cache_restart_required && (
        <p role="status">Restart the app to apply the new model location.</p>
      )}
      {model.error && <p role="alert">{model.error.message}</p>}
      <details>
        <summary>Installed files</summary>
        <dl>
          {Object.entries(data.installation).map(([name, path]) => (
            <div key={name}>
              <dt>{name}</dt>
              <dd>
                <code>{path || "Not available"}</code>
              </dd>
            </div>
          ))}
        </dl>
        <p>
          The installer manages these locations. Uninstall keeps app data and
          shared dependencies.
        </p>
      </details>
    </section>
  );
}
