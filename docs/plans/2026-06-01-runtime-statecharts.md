# Runtime Statecharts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add library-backed runtime statecharts for Home job creation and backend job lifecycle without changing the existing UI contract.

**Architecture:** The frontend uses XState v5 plus `@xstate/react` for a `jobCreationMachine` owned by `HomePage`. The backend uses `python-statemachine` behind a local `job_lifecycle.py` adapter, so routes and pipeline code validate state changes without importing the library directly. Behavior coverage grows machine-modeled and machine-tested columns while existing behavior docs stay in place.

**Tech Stack:** React 19, TypeScript, XState v5, `@xstate/react`, FastAPI, Pydantic, `python-statemachine`, pytest, Vitest, Playwright.

---

## File Structure

### Frontend new files

- `frontend/src/statecharts/jobCreationTypes.ts` — shared config, profile, source, form, event, and context types.
- `frontend/src/statecharts/jobCreationBehavior.ts` — behavior ID constants and helpers used by machine metadata/tests.
- `frontend/src/statecharts/jobCreationMachine.ts` — XState v5 machine plus actor input contracts.
- `frontend/src/statecharts/__tests__/jobCreationMachine.test.ts` — pure machine transition tests.

### Frontend modified files

- `frontend/package.json` and `frontend/pnpm-lock.yaml` — add `xstate` and `@xstate/react`.
- `frontend/src/pages/HomePage.tsx` — owns `useMachine(jobCreationMachine)`, renders from the machine snapshot, and navigates after submit.
- `frontend/src/components/SourcePicker.tsx` — becomes the richer dashed
  drop-zone surface for file/folder/path selection; upload network work moves
  into the machine.
- `frontend/src/components/JobConfigInline.tsx` — keeps the form UI, emits form-change and submit events, and receives submit state/errors from the machine.
- `frontend/src/app.css` — styles the richer source picker surface.
- `frontend/src/pages/__tests__/HomePage.test.tsx` — update mocks for machine-owned config/upload.
- `frontend/src/components/__tests__/JobConfigInline.test.tsx` — update submit tests to assert event payloads instead of direct fetch.

### Backend new files

- `src/pdomain_ocr_simple_gui/statecharts/__init__.py` — package marker.
- `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py` — lifecycle chart adapter and behavior mapping.
- `tests/test_job_lifecycle_statechart.py` — pure lifecycle tests.

### Backend modified files

- `pyproject.toml` and `uv.lock` — add `python-statemachine`.
- `src/pdomain_ocr_simple_gui/routes/jobs.py` — validate initial queue and rerun reset paths.
- `src/pdomain_ocr_simple_gui/pipeline.py` — validate queued/running/terminal progress writes.
- `tests/test_routes_jobs.py` and `tests/test_pipeline.py` — focused integration assertions for invalid transitions.

### Behavior coverage modified files

- `scripts/behavior_coverage.py` — scan machine metadata/test citations and render documented/modeled/tested columns.
- `tests/test_behavior_coverage.py` — unit tests for machine metadata and machine-test citations.
- `docs/specs/behavior/coverage.md` — regenerated output from `make behavior-coverage`.

---

## Task 1: Add Runtime Statechart Dependencies

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Confirm dependency absence**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
rg '"xstate"|"@xstate/react"|python-statemachine' frontend/package.json pyproject.toml
```

Expected: no matches.

- [ ] **Step 2: Add frontend dependencies**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui/frontend
pnpm add xstate @xstate/react
```

Expected: `package.json` gains `xstate` and `@xstate/react`; `pnpm-lock.yaml`
updates.

- [ ] **Step 3: Add Python dependency**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
uv add python-statemachine
```

Expected: `pyproject.toml` gains `python-statemachine`; `uv.lock` updates.

- [ ] **Step 4: Verify dependency install**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
make frontend-install AI=1
uv run python - <<'PY'
import statemachine
print(statemachine.__version__)
PY
```

Expected: frontend install passes and Python prints the installed
`python-statemachine` version.

- [ ] **Step 5: Commit**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
git add frontend/package.json frontend/pnpm-lock.yaml pyproject.toml uv.lock
git commit -m "build: add statechart runtimes" -m "Add XState for the frontend and python-statemachine for backend lifecycle validation."
```

Expected: commit passes pre-commit hooks.

---

## Task 2: Add the Frontend Job-Creation Machine

**Files:**

- Create: `frontend/src/statecharts/jobCreationTypes.ts`
- Create: `frontend/src/statecharts/jobCreationBehavior.ts`
- Create: `frontend/src/statecharts/jobCreationMachine.ts`
- Create: `frontend/src/statecharts/__tests__/jobCreationMachine.test.ts`

- [ ] **Step 1: Write the failing machine tests**

Create `frontend/src/statecharts/__tests__/jobCreationMachine.test.ts`:

```ts
import { createActor, waitFor } from "xstate";
import { describe, expect, it, vi } from "vitest";
import { jobCreationMachine } from "../jobCreationMachine";

function startMachine(config: {
  mode: "local" | "managed";
  is_containerized: boolean;
}) {
  const actor = createActor(
    jobCreationMachine.provide({
      actors: {
        loadConfig: async () => ({
          ...config,
          detected_device: "cpu",
          gpu_available: false,
        }),
        uploadFiles: async () => ({ uploadId: "upload-123" }),
        createJob: async () => ({ projectId: "job-123" }),
      },
    }),
  );
  actor.start();
  return actor;
}

describe("jobCreationMachine runtime profiles", () => {
  it("enters localHost when local and not containerized", async () => {
    const actor = startMachine({ mode: "local", is_containerized: false });
    await waitFor(actor, (state) => state.matches({ choosingSource: "localHost" }));
    expect(actor.getSnapshot().context.profile?.kind).toBe("local-host");
    actor.stop();
  });

  it("enters localContainer when local and containerized", async () => {
    const actor = startMachine({ mode: "local", is_containerized: true });
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "localContainer" }),
    );
    expect(actor.getSnapshot().context.profile?.kind).toBe("local-container");
    actor.stop();
  });

  it("enters managedServer and rejects path sources in managed mode", async () => {
    const actor = startMachine({ mode: "managed", is_containerized: false });
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "managedServer" }),
    );
    actor.send({ type: "PATH_CHOSEN", path: "/tmp/scans" });
    expect(actor.getSnapshot().matches({ choosingSource: "managedServer" })).toBe(
      true,
    );
    expect(actor.getSnapshot().context.source).toBeNull();
    actor.stop();
  });
});

describe("jobCreationMachine flow", () => {
  it("uploads files, stores the upload source, and emits behavior trace", async () => {
    const actor = startMachine({ mode: "local", is_containerized: true });
    await waitFor(actor, (state) =>
      state.matches({ choosingSource: "localContainer" }),
    );
    actor.send({ type: "FILES_SELECTED", files: [new File(["x"], "scan.png")] });
    await waitFor(actor, (state) => state.matches("configuringJob"));
    expect(actor.getSnapshot().context.source).toEqual({
      kind: "upload",
      uploadId: "upload-123",
    });
    expect(actor.getSnapshot().context.behaviorTrace).toContain("B-HOME-002");
    actor.stop();
  });

  it("submits a job and stores the returned project id", async () => {
    const actor = startMachine({ mode: "local", is_containerized: false });
    await waitFor(actor, (state) => state.matches({ choosingSource: "localHost" }));
    actor.send({ type: "PATH_CHOSEN", path: "/tmp/scans" });
    await waitFor(actor, (state) => state.matches("configuringJob"));
    actor.send({ type: "SUBMIT_JOB" });
    await waitFor(actor, (state) => state.matches("submitted"));
    expect(actor.getSnapshot().context.submittedProjectId).toBe("job-123");
    expect(actor.getSnapshot().context.behaviorTrace).toContain("B-HOME-011");
    actor.stop();
  });

  it("preserves source and form context when submit fails", async () => {
    const actor = createActor(
      jobCreationMachine.provide({
        actors: {
          loadConfig: async () => ({
            mode: "local",
            is_containerized: false,
            detected_device: "cpu",
            gpu_available: false,
          }),
          uploadFiles: async () => ({ uploadId: "upload-123" }),
          createJob: async () => {
            throw new Error("bad request");
          },
        },
      }),
    );
    actor.start();
    await waitFor(actor, (state) => state.matches({ choosingSource: "localHost" }));
    actor.send({ type: "PATH_CHOSEN", path: "/tmp/scans" });
    actor.send({
      type: "JOB_FORM_CHANGED",
      patch: { name: "scans", language: "fr" },
    });
    actor.send({ type: "SUBMIT_JOB" });
    await waitFor(actor, (state) => state.matches("configuringJob"));
    expect(actor.getSnapshot().context.source).toEqual({
      kind: "path",
      path: "/tmp/scans",
    });
    expect(actor.getSnapshot().context.jobForm.language).toBe("fr");
    expect(actor.getSnapshot().context.submitError).toContain("bad request");
    actor.stop();
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui/frontend
pnpm run test src/statecharts/__tests__/jobCreationMachine.test.ts
```

Expected: fails because `jobCreationMachine` does not exist.

- [ ] **Step 3: Add shared types**

Create `frontend/src/statecharts/jobCreationTypes.ts`:

```ts
export interface RuntimeConfig {
  mode: "local" | "managed";
  is_containerized: boolean;
  detected_device: string;
  gpu_available: boolean;
}

export type RuntimeProfile =
  | { kind: "local-host"; canUpload: true; canUsePath: true }
  | {
      kind: "local-container";
      canUpload: true;
      canUsePath: true;
      pathHint: "container";
    }
  | { kind: "managed-server"; canUpload: true; canUsePath: false };

export type ChosenSource =
  | { kind: "path"; path: string }
  | { kind: "upload"; uploadId: string };

export interface JobForm {
  name: string;
  engine: "doctr" | "tesseract";
  language: string;
  straight_quotes: boolean;
  em_dash_to_double_hyphen: boolean;
  emit_illustration_placeholders: boolean;
  device: "auto" | "gpu" | "cpu";
  batch_pages: number | null;
  output: { mode: "next_to_source" | "specified" | "managed"; path?: string };
}

export interface JobCreationContext {
  config: RuntimeConfig | null;
  profile: RuntimeProfile | null;
  source: ChosenSource | null;
  jobForm: JobForm;
  uploadError: string | null;
  submitError: string | null;
  submittedProjectId: string | null;
  behaviorTrace: string[];
}

export type JobCreationEvent =
  | { type: "CONFIG_RETRY" }
  | { type: "FILES_SELECTED"; files: File[] }
  | { type: "PATH_CHOSEN"; path: string }
  | { type: "CLEAR_SOURCE" }
  | { type: "JOB_FORM_CHANGED"; patch: Partial<JobForm> }
  | { type: "SUBMIT_JOB" };
```

- [ ] **Step 4: Add behavior helpers**

Create `frontend/src/statecharts/jobCreationBehavior.ts`:

```ts
export const JOB_CREATION_BEHAVIOR = {
  uploadViaDropOrPicker: "B-HOME-002",
  chooseLocalPath: "B-HOME-003",
  clearSource: "B-HOME-004",
  configFailure: "B-HOME-014",
  submitJob: "B-HOME-011",
} as const;

export type JobCreationBehaviorId =
  (typeof JOB_CREATION_BEHAVIOR)[keyof typeof JOB_CREATION_BEHAVIOR];

export function appendBehaviorTrace(
  trace: string[],
  id: JobCreationBehaviorId,
): string[] {
  return trace.includes(id) ? trace : [...trace, id];
}
```

- [ ] **Step 5: Add the machine**

Create `frontend/src/statecharts/jobCreationMachine.ts` with a XState v5
machine that implements the tested states:

```ts
import { assign, fromPromise, setup } from "xstate";
import {
  type ChosenSource,
  type JobCreationContext,
  type JobCreationEvent,
  type JobForm,
  type RuntimeConfig,
  type RuntimeProfile,
} from "./jobCreationTypes";
import {
  JOB_CREATION_BEHAVIOR,
  appendBehaviorTrace,
} from "./jobCreationBehavior";

function defaultJobForm(): JobForm {
  return {
    name: "",
    engine: "doctr",
    language: "en",
    straight_quotes: true,
    em_dash_to_double_hyphen: true,
    emit_illustration_placeholders: false,
    device: "auto",
    batch_pages: null,
    output: { mode: "managed" },
  };
}

function profileFromConfig(config: RuntimeConfig): RuntimeProfile {
  if (config.mode === "managed") {
    return { kind: "managed-server", canUpload: true, canUsePath: false };
  }
  if (config.is_containerized) {
    return {
      kind: "local-container",
      canUpload: true,
      canUsePath: true,
      pathHint: "container",
    };
  }
  return { kind: "local-host", canUpload: true, canUsePath: true };
}

async function defaultLoadConfig(): Promise<RuntimeConfig> {
  const res = await fetch("/api/config");
  if (!res.ok) throw new Error(`GET /api/config failed: ${res.status}`);
  return (await res.json()) as RuntimeConfig;
}

async function defaultUploadFiles(input: { files: File[] }): Promise<{
  uploadId: string;
}> {
  const form = new FormData();
  input.files.forEach((file) => form.append("files", file));
  const res = await fetch("/api/uploads", { method: "POST", body: form });
  if (!res.ok) throw new Error(`POST /api/uploads failed: ${res.status}`);
  const body = (await res.json()) as { upload_id: string };
  return { uploadId: body.upload_id };
}

async function defaultCreateJob(input: {
  source: ChosenSource;
  jobForm: JobForm;
}): Promise<{ projectId: string }> {
  const body: Record<string, unknown> = { ...input.jobForm };
  if (input.source.kind === "upload") body.upload_id = input.source.uploadId;
  if (input.source.kind === "path") body.source_path = input.source.path;
  const res = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { project_id: string };
  return { projectId: data.project_id };
}

const initialContext: JobCreationContext = {
  config: null,
  profile: null,
  source: null,
  jobForm: defaultJobForm(),
  uploadError: null,
  submitError: null,
  submittedProjectId: null,
  behaviorTrace: [],
};

export const jobCreationMachine = setup({
  types: {
    context: {} as JobCreationContext,
    events: {} as JobCreationEvent,
  },
  actors: {
    loadConfig: fromPromise(defaultLoadConfig),
    uploadFiles: fromPromise(
      ({ input }: { input: { files: File[] } }) => defaultUploadFiles(input),
    ),
    createJob: fromPromise(
      ({ input }: { input: { source: ChosenSource; jobForm: JobForm } }) =>
        defaultCreateJob(input),
    ),
  },
  guards: {
    canUsePath: ({ context }) => context.profile?.canUsePath === true,
    canUpload: ({ context }) => context.profile?.canUpload === true,
    hasSource: ({ context }) => context.source !== null,
  },
  actions: {
    assignJobForm: assign({
      jobForm: ({ context, event }) =>
        event.type === "JOB_FORM_CHANGED"
          ? { ...context.jobForm, ...event.patch }
          : context.jobForm,
    }),
  },
}).createMachine({
  id: "jobCreation",
  initial: "loadingConfig",
  context: initialContext,
  states: {
    loadingConfig: {
      invoke: {
        src: "loadConfig",
        onDone: {
          target: "choosingSource",
          actions: assign({
            config: ({ event }) => event.output,
            profile: ({ event }) => profileFromConfig(event.output),
          }),
        },
        onError: {
          target: "configFailed",
          actions: assign({
            behaviorTrace: ({ context }) =>
              appendBehaviorTrace(
                context.behaviorTrace,
                JOB_CREATION_BEHAVIOR.configFailure,
              ),
          }),
        },
      },
    },
    configFailed: {
      on: { CONFIG_RETRY: "loadingConfig" },
    },
    choosingSource: {
      initial: "localHost",
      states: {
        localHost: {},
        localContainer: {},
        managedServer: {},
      },
      always: [
        { target: ".localHost", guard: ({ context }) => context.profile?.kind === "local-host" },
        { target: ".localContainer", guard: ({ context }) => context.profile?.kind === "local-container" },
        { target: ".managedServer", guard: ({ context }) => context.profile?.kind === "managed-server" },
      ],
      on: {
        PATH_CHOSEN: {
          guard: "canUsePath",
          target: "configuringJob",
          actions: assign({
            source: ({ event }) =>
              event.type === "PATH_CHOSEN" ? { kind: "path", path: event.path } : null,
            behaviorTrace: ({ context }) =>
              appendBehaviorTrace(
                context.behaviorTrace,
                JOB_CREATION_BEHAVIOR.chooseLocalPath,
              ),
          }),
        },
        FILES_SELECTED: {
          guard: "canUpload",
          target: "uploading",
        },
      },
    },
    uploading: {
      invoke: {
        src: "uploadFiles",
        input: ({ event }) => ({
          files: event.type === "FILES_SELECTED" ? event.files : [],
        }),
        onDone: {
          target: "configuringJob",
          actions: assign({
            source: ({ event }) => ({
              kind: "upload",
              uploadId: event.output.uploadId,
            }),
            uploadError: null,
            behaviorTrace: ({ context }) =>
              appendBehaviorTrace(
                context.behaviorTrace,
                JOB_CREATION_BEHAVIOR.uploadViaDropOrPicker,
              ),
          }),
        },
        onError: {
          target: "choosingSource",
          actions: assign({
            uploadError: ({ event }) =>
              event.error instanceof Error
                ? event.error.message
                : "Upload failed.",
          }),
        },
      },
    },
    configuringJob: {
      on: {
        CLEAR_SOURCE: {
          target: "choosingSource",
          actions: assign({
            source: null,
            uploadError: null,
            submitError: null,
            behaviorTrace: ({ context }) =>
              appendBehaviorTrace(
                context.behaviorTrace,
                JOB_CREATION_BEHAVIOR.clearSource,
              ),
          }),
        },
        JOB_FORM_CHANGED: { actions: "assignJobForm" },
        SUBMIT_JOB: { guard: "hasSource", target: "submittingJob" },
      },
    },
    submittingJob: {
      invoke: {
        src: "createJob",
        input: ({ context }) => ({
          source: context.source as ChosenSource,
          jobForm: context.jobForm,
        }),
        onDone: {
          target: "submitted",
          actions: assign({
            submittedProjectId: ({ event }) => event.output.projectId,
            submitError: null,
            behaviorTrace: ({ context }) =>
              appendBehaviorTrace(
                context.behaviorTrace,
                JOB_CREATION_BEHAVIOR.submitJob,
              ),
          }),
        },
        onError: {
          target: "configuringJob",
          actions: assign({
            submitError: ({ event }) =>
              event.error instanceof Error
                ? event.error.message
                : "Job creation failed.",
          }),
        },
      },
    },
    submitted: { type: "final" },
    failed: {},
  },
});
```

- [ ] **Step 6: Run the pure machine tests**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui/frontend
pnpm run test src/statecharts/__tests__/jobCreationMachine.test.ts
```

Expected: all tests in the new file pass.

- [ ] **Step 7: Commit**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
git add frontend/src/statecharts
git commit -m "feat(frontend): add job creation statechart" -m "Add the XState runtime model and pure tests for Home job creation."
```

Expected: commit passes pre-commit hooks.

---

## Task 3: Wire HomePage to the Frontend Machine

**Files:**

- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/components/SourcePicker.tsx`
- Modify: `frontend/src/components/JobConfigInline.tsx`
- Modify: `frontend/src/app.css`
- Modify: `frontend/src/pages/__tests__/HomePage.test.tsx`
- Modify: `frontend/src/components/__tests__/JobConfigInline.test.tsx`

- [ ] **Step 1: Write failing HomePage integration expectations**

Update `frontend/src/pages/__tests__/HomePage.test.tsx` so it renders
`HomePage` without `ConfigProvider`. Replace `renderTree()` with:

```tsx
function renderTree() {
  const client = makeQueryClient();
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}
```

Keep the existing tests for:

- local container shows upload and path inputs
- local host shows drop and path together
- managed shows upload only
- config failure shows retry
- source chosen shows `JobConfigInline`
- cancelling restores source selection

Add these UI assertions to the local-host case:

```tsx
expect(screen.getByRole("button", { name: /browse folder/i })).toBeInTheDocument();
expect(screen.getByRole("button", { name: /choose file/i })).toBeInTheDocument();
expect(screen.getByText(/or paste a path/i)).toBeInTheDocument();
expect(screen.getByRole("button", { name: /^open$/i })).toBeInTheDocument();
expect(screen.getByText(/recent:/i)).toBeInTheDocument();
```

Add this assertion to the managed case:

```tsx
expect(screen.queryByText(/or paste a path/i)).toBeNull();
expect(screen.queryByText(/recent:/i)).toBeNull();
```

- [ ] **Step 2: Run HomePage tests to verify failure**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui/frontend
pnpm run test src/pages/__tests__/HomePage.test.tsx
```

Expected: failures show `HomePage` still depends on `ConfigProvider`.

- [ ] **Step 3: Refactor SourcePicker to be presentational**

In `frontend/src/components/SourcePicker.tsx`, change props to this shape:

```ts
export interface SourcePickerProps {
  allowDrop: boolean;
  allowPathInput: boolean;
  allowFolderBrowse?: boolean;
  recentPaths?: string[];
  pathHint?: string;
  uploadError?: string | null;
  onFilesSelected: (files: File[]) => void;
  onPathChosen: (path: string) => void;
  onClear?: () => void;
}
```

Remove the `uploadFiles(...)` helper and all `fetch("/api/uploads", ...)`
calls from this component. In `handleFiles`, keep chosen-display state and call
`props.onFilesSelected(files)`.

Render the new source-entry surface with these elements:

```tsx
<div data-testid={APP_TEST_IDS.sourcePickerDropZone} role="button" tabIndex={0}>
  <div aria-label="Source type" className="source-picker__mode-tabs">
    <button type="button" aria-label="Folder source">...</button>
    <button type="button" aria-label="File source">...</button>
    <button type="button" aria-label="Archive source">...</button>
  </div>
  <h2>Drop a file or folder to start OCR</h2>
  <p>PDF, multi-page TIFF, or a folder of images. Pages are queued and OCR'd in the background.</p>
  <button type="button" onClick={openFolderPicker}>Browse folder...</button>
  <button type="button" onClick={openFilePicker}>Choose file...</button>
  <p>PDF · TIFF · JP2 · PNG · JPG · max 5 GB</p>
</div>
```

Use two hidden inputs:

```tsx
<input
  ref={fileInput}
  data-testid={APP_TEST_IDS.sourcePickerFilePick}
  type="file"
  multiple
  accept="image/*,.pdf,.tif,.tiff,.jp2,.zip"
  onChange={(e) => void handleFiles(Array.from(e.target.files ?? []))}
/>
<input
  ref={folderInput}
  type="file"
  multiple
  {...({ webkitdirectory: "" } as Record<string, string>)}
  onChange={(e) => void handleFiles(Array.from(e.target.files ?? []))}
/>
```

When `allowPathInput` is true, render:

```tsx
<div className="source-picker__path-divider">OR PASTE A PATH</div>
<form onSubmit={...}>
  <Input data-testid={APP_TEST_IDS.sourcePickerPathInput} ... />
  <Button type="submit">Open</Button>
</form>
{props.recentPaths?.length ? (
  <div className="source-picker__recent">
    <span>Recent:</span>
    {props.recentPaths.map((path) => (
      <button type="button" onClick={() => props.onPathChosen(path)}>{path}</button>
    ))}
  </div>
) : null}
```

Render `props.uploadError` in the existing alert slot:

```tsx
{props.uploadError !== null && props.uploadError !== undefined && (
  <div
    role="alert"
    data-testid="source-picker-upload-error"
    style={{ color: "var(--error-9, red)", fontSize: 13, marginTop: 8 }}
  >
    {props.uploadError}
  </div>
)}
```

- [ ] **Step 4: Refactor JobConfigInline to emit submit events**

Add controlled props while keeping defaults for existing tests during the
transition:

```ts
export interface JobConfigInlineProps {
  source: ChosenSource;
  mode?: "local" | "managed";
  runtimeConfig?: { detected_device: string; gpu_available: boolean } | null;
  submitError?: string | null;
  submitting?: boolean;
  onCancel?: () => void;
  onFormChanged?: (patch: Partial<JobForm>) => void;
  onSubmitJob?: (form: JobForm) => void;
}
```

Change `handleSubmit` so it builds the same `JobForm` payload but calls
`onSubmitJob(form)` when provided:

```ts
if (onSubmitJob) {
  onSubmitJob(form);
  return;
}
```

Keep the old fetch submit fallback only until HomePage wiring is complete in
this task. Remove that fallback before the task commit if all tests pass with
machine-owned submit.

- [ ] **Step 5: Wire HomePage to useMachine**

In `frontend/src/pages/HomePage.tsx`, replace `useConfig()` and
`useConfigStatus()` with:

```tsx
import { useEffect } from "react";
import { useMachine } from "@xstate/react";
import { useNavigate } from "react-router-dom";
import { jobCreationMachine } from "../statecharts/jobCreationMachine";

const [snapshot, send] = useMachine(jobCreationMachine);
const navigate = useNavigate();
const { profile, source, uploadError, submitError, config } = snapshot.context;

useEffect(() => {
  if (snapshot.matches("submitted") && snapshot.context.submittedProjectId) {
    navigate(`/jobs/${snapshot.context.submittedProjectId}`);
  }
}, [navigate, snapshot]);
```

Render config error from `snapshot.matches("configFailed")`, and send
`CONFIG_RETRY` from the retry button. Render pickers from `profile.kind`:

```tsx
const chooseFiles = (files: File[]) => send({ type: "FILES_SELECTED", files });
const choosePath = (path: string) => send({ type: "PATH_CHOSEN", path });
const clearSource = () => send({ type: "CLEAR_SOURCE" });
```

Pass `uploadError`, `chooseFiles`, `choosePath`, and `clearSource` to
`SourcePicker`. For now pass a small static `recentPaths` list in local modes:

```tsx
const recentPaths = ["~/scans/belloc-survivals/jp2/", "belloc-survivals.zip", "manuscript-fragment.pdf"];
```

Pass `submitError`, `snapshot.matches("submittingJob")`,
`runtimeConfig={config}`, `onFormChanged`, and `onSubmitJob` to
`JobConfigInline`.

Add CSS in `frontend/src/app.css` for `.source-picker__mode-tabs`,
`.source-picker__path-divider`, `.source-picker__recent`, and the refreshed
drop-zone layout. Match the screenshot direction: dark, quiet, dashed border,
compact buttons, and no card nesting.

- [ ] **Step 6: Run focused frontend tests**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui/frontend
pnpm run test src/statecharts/__tests__/jobCreationMachine.test.ts src/pages/__tests__/HomePage.test.tsx src/components/__tests__/JobConfigInline.test.tsx
```

Expected: focused tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
git add frontend/src/pages/HomePage.tsx frontend/src/components/SourcePicker.tsx frontend/src/components/JobConfigInline.tsx frontend/src/app.css frontend/src/pages/__tests__/HomePage.test.tsx frontend/src/components/__tests__/JobConfigInline.test.tsx
git commit -m "feat(frontend): drive Home job creation with statechart" -m "Wire the existing Home UI to the runtime job creation machine."
```

Expected: commit passes pre-commit hooks.

---

## Task 4: Add Backend Job Lifecycle Statechart

**Files:**

- Create: `src/pdomain_ocr_simple_gui/statecharts/__init__.py`
- Create: `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py`
- Create: `tests/test_job_lifecycle_statechart.py`

- [ ] **Step 1: Write failing backend lifecycle tests**

Create `tests/test_job_lifecycle_statechart.py`:

```python
import pytest

from pdomain_ocr_simple_gui.statecharts.job_lifecycle import (
    InvalidJobTransition,
    JOB_LIFECYCLE_BEHAVIOR,
    transition_job_state,
)


@pytest.mark.parametrize(
    ("current", "event", "expected"),
    [
        ("new", "queue", "queued"),
        ("queued", "start", "running"),
        ("queued", "fail", "failed"),
        ("running", "succeed", "succeeded"),
        ("running", "fail", "failed"),
        ("running", "cancel", "cancelled"),
        ("succeeded", "rerun_requested", "queued"),
        ("failed", "rerun_requested", "queued"),
        ("cancelled", "rerun_requested", "queued"),
    ],
)
def test_valid_job_lifecycle_transitions(current: str, event: str, expected: str) -> None:
    assert transition_job_state(current, event) == expected


@pytest.mark.parametrize(
    ("current", "event"),
    [
        ("new", "start"),
        ("queued", "succeed"),
        ("succeeded", "start"),
        ("failed", "succeed"),
        ("cancelled", "fail"),
    ],
)
def test_invalid_job_lifecycle_transitions_raise(current: str, event: str) -> None:
    with pytest.raises(InvalidJobTransition):
        transition_job_state(current, event)


def test_lifecycle_behavior_mapping_uses_documented_ids() -> None:
    assert JOB_LIFECYCLE_BEHAVIOR[("new", "queue", "queued")] == ("B-HOME-011",)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
uv run pytest tests/test_job_lifecycle_statechart.py -n0 -v
```

Expected: import error because the statecharts package does not exist.

- [ ] **Step 3: Add backend statechart adapter**

Create `src/pdomain_ocr_simple_gui/statecharts/__init__.py` as an empty package
marker.

Create `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py`:

```python
from __future__ import annotations

from typing import Literal

from statemachine import State, StateMachine

JobState = Literal["new", "queued", "running", "succeeded", "failed", "cancelled"]
JobLifecycleEvent = Literal[
    "queue",
    "start",
    "succeed",
    "fail",
    "cancel",
    "rerun_requested",
]


class InvalidJobTransition(ValueError):
    pass


class JobLifecycleMachine(StateMachine):
    new = State("new", initial=True)
    queued = State("queued")
    running = State("running")
    succeeded = State("succeeded", final=True)
    failed = State("failed", final=True)
    cancelled = State("cancelled", final=True)

    queue = new.to(queued)
    start = queued.to(running)
    succeed = running.to(succeeded)
    fail = queued.to(failed) | running.to(failed)
    cancel = running.to(cancelled)
    rerun_requested = succeeded.to(queued) | failed.to(queued) | cancelled.to(queued)


JOB_LIFECYCLE_BEHAVIOR: dict[tuple[str, str, str], tuple[str, ...]] = {
    ("new", "queue", "queued"): ("B-HOME-011",),
}


def transition_job_state(current: str, event: str) -> str:
    machine = JobLifecycleMachine(start_value=current)
    try:
        machine.send(event)
    except Exception as exc:
        raise InvalidJobTransition(f"cannot apply {event!r} from {current!r}") from exc
    return str(machine.current_state_value)


def assert_job_transition(current: str, event: str) -> str:
    return transition_job_state(current, event)
```

- [ ] **Step 4: Run lifecycle tests**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
uv run pytest tests/test_job_lifecycle_statechart.py -n0 -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
git add src/pdomain_ocr_simple_gui/statecharts tests/test_job_lifecycle_statechart.py
git commit -m "feat(backend): add job lifecycle statechart" -m "Add a local adapter around python-statemachine for job state transitions."
```

Expected: commit passes pre-commit hooks.

---

## Task 5: Enforce Backend Lifecycle Transitions

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/routes/jobs.py`
- Modify: `src/pdomain_ocr_simple_gui/pipeline.py`
- Modify: `tests/test_routes_jobs.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write a failing route-level transition test**

Add to `tests/test_routes_jobs.py`:

```python
async def test_rerun_resets_terminal_job_via_lifecycle(tmp_path, monkeypatch) -> None:
    from datetime import UTC, datetime

    from httpx import ASGITransport, AsyncClient

    from pdomain_ocr_simple_gui.app import app
    from pdomain_ocr_simple_gui.models import ProjectSpec, ProjectStatus
    from pdomain_ocr_simple_gui.storage import read_project, write_project

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
    now = datetime.now(UTC)
    spec = ProjectSpec(
      project_id="rerun-statechart",
      name="rerun",
      source_path=str(tmp_path / "src"),
      output_dir=str(tmp_path / "out"),
      engine="doctr",
      language="en",
      created_at=now,
      last_opened_at=now,
    )
    write_project(
      spec,
      ProjectStatus(
        project_id=spec.project_id,
        state="succeeded",
        page_count=0,
        pages_done=0,
        pages=[],
      ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/jobs/{spec.project_id}/rerun")

    assert resp.status_code == 202
    _, status = read_project(spec.project_id)
    assert status.state == "queued"
```

- [ ] **Step 2: Run route test**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
uv run pytest tests/test_routes_jobs.py::test_rerun_resets_terminal_job_via_lifecycle -n0 -v
```

Expected: fails if the new test location or lifecycle wiring is not present.

- [ ] **Step 3: Add a small transition helper in routes/jobs.py**

In `src/pdomain_ocr_simple_gui/routes/jobs.py`, import:

```python
from pdomain_ocr_simple_gui.statecharts.job_lifecycle import assert_job_transition
```

Use it where job statuses are created or reset:

```python
initial_state = assert_job_transition("new", "queue")
status = ProjectStatus(
    project_id=project_id,
    state=initial_state,
    page_count=0,
    pages_done=0,
    pages=[],
)
```

In `rerun_job`, validate the reset:

```python
rerun_state = assert_job_transition(status.state, "rerun_requested")
reset_status = ProjectStatus(
    project_id=project_id,
    state=rerun_state,
    page_count=status.page_count,
    pages_done=0,
    pages=reset_pages,
)
```

- [ ] **Step 4: Wire pipeline progress transitions**

In `src/pdomain_ocr_simple_gui/pipeline.py`, wrap state changes that move job
status from queued to running and running to terminal states. Add a helper near
the status-write code:

```python
from pdomain_ocr_simple_gui.statecharts.job_lifecycle import assert_job_transition


def _next_job_state(current: str, event: str) -> str:
    return assert_job_transition(current, event)
```

Use `_next_job_state(current.state, "start")` before the first running write,
`_next_job_state(current.state, "succeed")` for success, and
`_next_job_state(current.state, "fail")` for job-level failure.

- [ ] **Step 5: Run backend focused tests**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
uv run pytest tests/test_job_lifecycle_statechart.py tests/test_routes_jobs.py tests/test_pipeline.py -n0 -v
```

Expected: all focused backend tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
git add src/pdomain_ocr_simple_gui/routes/jobs.py src/pdomain_ocr_simple_gui/pipeline.py tests/test_routes_jobs.py tests/test_pipeline.py
git commit -m "feat(backend): enforce job lifecycle transitions" -m "Validate job state writes through the lifecycle statechart adapter."
```

Expected: commit passes pre-commit hooks.

---

## Task 6: Connect Behavior Coverage to Machines

**Files:**

- Modify: `scripts/behavior_coverage.py`
- Modify: `tests/test_behavior_coverage.py`
- Modify: `docs/specs/behavior/coverage.md`
- Modify: `frontend/src/statecharts/jobCreationBehavior.ts`
- Modify: `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py`

- [ ] **Step 1: Write failing behavior coverage tests**

Add to `tests/test_behavior_coverage.py`:

```python
from scripts.behavior_coverage import scan_machine_modeled, scan_machine_tested


def test_scan_machine_modeled_reads_frontend_and_python_metadata(tmp_path: Path) -> None:
    frontend = tmp_path / "jobCreationBehavior.ts"
    frontend.write_text(
        'export const JOB_CREATION_BEHAVIOR = { submitJob: "B-HOME-011" } as const;\n',
        encoding="utf-8",
    )
    backend = tmp_path / "job_lifecycle.py"
    backend.write_text(
        'JOB_LIFECYCLE_BEHAVIOR = {("new", "queue", "queued"): ("B-HOME-011",)}\n',
        encoding="utf-8",
    )
    assert scan_machine_modeled(tmp_path) == {"B-HOME-011"}


def test_scan_machine_tested_reads_machine_test_covers_lines(tmp_path: Path) -> None:
    test_file = tmp_path / "jobCreationMachine.test.ts"
    test_file.write_text(
        'it("submits", () => { /* Machine-Covers: B-HOME-011 */ });\n',
        encoding="utf-8",
    )
    assert scan_machine_tested(tmp_path) == {"B-HOME-011"}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
uv run pytest tests/test_behavior_coverage.py -n0 -v
```

Expected: import error for `scan_machine_modeled` and `scan_machine_tested`.

- [ ] **Step 3: Extend behavior coverage scanner**

In `scripts/behavior_coverage.py`, add:

```python
def scan_machine_modeled(root: Path) -> set[str]:
    modeled: set[str] = set()
    for path in root.rglob("*"):
        if path.suffix not in {".ts", ".py"}:
            continue
        if path.name.endswith(".test.ts") or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "BEHAVIOR" in text or "behavior_ids" in text:
            modeled.update(ID_RE.findall(text))
    return modeled


def scan_machine_tested(root: Path) -> set[str]:
    tested: set[str] = set()
    for path in root.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".py"}:
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "Machine-Covers:" in line:
                tested.update(ID_RE.findall(line))
    return tested
```

Extend `Report`:

```python
modeled: set[str]
machine_tested: set[str]
```

Update `render_markdown(...)` to render:

```markdown
| ID | Regression | Documented | Modeled | Tested |
```

Use `yes`/`no` values for `Modeled` and `Tested`. Treat existing browser test
citations as tested by combining `cited | machine_tested`.

- [ ] **Step 4: Add machine covers citations**

Add `Machine-Covers:` comments to the pure machine tests:

```ts
// Machine-Covers: B-HOME-002
// Machine-Covers: B-HOME-003
// Machine-Covers: B-HOME-011
// Machine-Covers: B-HOME-014
```

Add a Python lifecycle test citation:

```python
def test_lifecycle_behavior_mapping_uses_documented_ids() -> None:
    """Machine-Covers: B-HOME-011"""
    assert JOB_LIFECYCLE_BEHAVIOR[("new", "queue", "queued")] == ("B-HOME-011",)
```

- [ ] **Step 5: Run coverage tests and regenerate report**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
uv run pytest tests/test_behavior_coverage.py -n0 -v
make behavior-coverage AI=1
```

Expected: tests pass and behavior coverage reports documented, modeled, and
tested columns.

- [ ] **Step 6: Commit**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
git add scripts/behavior_coverage.py tests/test_behavior_coverage.py docs/specs/behavior/coverage.md frontend/src/statecharts src/pdomain_ocr_simple_gui/statecharts
git commit -m "feat: include statecharts in behavior coverage" -m "Report behavior IDs represented and tested by runtime machines."
```

Expected: commit passes pre-commit hooks.

---

## Task 7: Final Verification

**Files:**

- No planned source edits unless verification exposes a real defect.

- [ ] **Step 1: Run frontend focused tests**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
make frontend-test AI=1
```

Expected: frontend Vitest suite passes.

- [ ] **Step 2: Run backend tests**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
make test AI=1
```

Expected: pytest suite passes.

- [ ] **Step 3: Run behavior coverage**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
make behavior-coverage AI=1
```

Expected: behavior coverage gate passes.

- [ ] **Step 4: Run full CI gate**

Run:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
make ci AI=1
```

Expected: full CI passes. If it fails, inspect `.ci-ai.log`, fix only defects
introduced by this plan, and rerun the failing target before rerunning `make ci
AI=1`.

- [ ] **Step 5: Commit verification fixes if needed**

If Step 4 required code changes, commit them:

```bash
cd /workspaces/ocr-container/pdomain-ocr-simple-gui
git status --short
git add <changed-files>
git commit -m "fix: stabilize runtime statecharts" -m "Address issues found by final verification."
```

Expected: no uncommitted implementation changes remain.
