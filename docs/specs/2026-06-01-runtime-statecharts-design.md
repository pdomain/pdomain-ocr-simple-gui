# Runtime statecharts for job creation and job lifecycle

- **Date:** 2026-06-01
- **Repo:** pdomain-ocr-simple-gui
- **Status:** draft

## 1. Problem

`pdomain-ocr-simple-gui` has a small user surface, but its behavior is spread
across React state, hooks, route handlers, background tasks, and behavior docs.
The user-visible flow is easy to describe:

1. Load runtime config.
2. Choose a source.
3. Configure OCR.
4. Submit a job.
5. Watch the job move through its lifecycle.

The current code mostly works, but the workflow rules are implicit. Examples:

- Home page source options depend on whether the app is running as local host,
  local container, or managed server.
- Upload, path input, clear-source, and submit states are controlled by local
  component state.
- Backend job status writes can set `ProjectStatus.state` directly.
- Behavior docs and tests describe what should happen, but the runtime does not
  expose a single executable model for those expectations.

This spec makes statecharts first-class runtime logic. The first slice focuses
on job creation and backend job lifecycle. Results polling and page-view editing
are separate future slices.

## 2. Goals

- Use a library-backed TypeScript statechart to drive the Home job-creation
  flow.
- Use a library-backed Python statechart to validate backend job lifecycle
  transitions before persisting state.
- Keep the existing UI, API payloads, routes, styling, and test IDs.
- Model runtime source capability differences explicitly.
- Connect runtime machines to the behavior coverage system.
- Start a migration path where statecharts become the source of truth for
  executable behavior.

## 3. Non-goals

- Rebuild the UI or change user-facing layout.
- Replace results polling, page-view save/rerun, or suite launcher behavior in
  this slice.
- Generate diagrams or use a browser-based visual companion.
- Remove behavior docs in this slice.
- Add a backend event stream, WebSocket, or cancellation endpoint.

## 4. Library choices

### 4.1 TypeScript

Add `xstate` and `@xstate/react`.

Use XState v5 typed machines with `setup(...)`. React components use
`useMachine`, `useActor`, or selectors from `@xstate/react`.

Rationale:

- XState is the strongest current TypeScript statechart option.
- It supports typed context, events, guards, actions, invoked actors, and
  metadata.
- The official React package fits the existing React app without changing the
  component model.

### 4.2 Python

Add `python-statemachine`.

Use its `StateChart` support behind a local adapter module. The adapter exposes
small functions used by routes and pipeline code.

Rationale:

- The project is mature and actively maintained.
- It supports runtime statechart execution in Python.
- Keeping it behind a local adapter limits future churn if the library API
  changes.

## 5. Frontend statechart

### 5.1 Location

New files:

- `frontend/src/statecharts/jobCreationMachine.ts`
- `frontend/src/statecharts/jobCreationTypes.ts`
- `frontend/src/statecharts/jobCreationBehavior.ts`
- `frontend/src/statecharts/__tests__/jobCreationMachine.test.ts`

### 5.2 Runtime profile

`/api/config` is the first invoked actor. Its result maps to a runtime profile:

```ts
type RuntimeProfile =
  | { kind: "local-host"; canUpload: true; canUsePath: true }
  | {
      kind: "local-container";
      canUpload: true;
      canUsePath: true;
      pathHint: "container";
    }
  | { kind: "managed-server"; canUpload: true; canUsePath: false };
```

This profile controls the active source-selection branch and the allowed
events. Components should render from `snapshot.context.profile`, not duplicate
`mode === "local"` checks.

### 5.3 States

The first machine has these top-level states:

```text
loadingConfig
configFailed
choosingSource
  localHost
  localContainer
  managedServer
uploading
sourceChosen
configuringJob
submittingJob
submitted
failed
```

`choosingSource.*` is a compound state. Returning to source selection must return
to the branch that matches the runtime profile.

`failed` is reserved for unrecoverable machine faults. Recoverable config,
upload, and submit failures use `configFailed`, `uploadError`, or
`submitError` so the user can retry without losing context.

### 5.4 Events

The machine accepts these events:

```text
CONFIG_RETRY
CONFIG_LOADED
CONFIG_FAILED
FILES_SELECTED
UPLOAD_DONE
UPLOAD_FAILED
PATH_CHOSEN
CLEAR_SOURCE
JOB_FORM_CHANGED
SUBMIT_JOB
JOB_CREATED
JOB_CREATE_FAILED
```

`PATH_CHOSEN` is guarded by `profile.canUsePath`. `FILES_SELECTED` is guarded by
`profile.canUpload`. UI code should normally prevent invalid events, but the
machine must still reject them.

### 5.5 Context

The machine context stores:

- `config`: raw `/api/config` response.
- `profile`: derived runtime profile.
- `source`: path or upload source.
- `uploadId`: staged upload id.
- `jobForm`: current job configuration values.
- `uploadError`: last upload error, if any.
- `submitError`: last submit error, if any.
- `submittedProjectId`: project id returned by `/api/jobs`.
- `behaviorTrace`: behavior IDs reached during the current machine run.

`behaviorTrace` is for tests and coverage reporting. It should not drive UI.

### 5.6 Invoked actors

The machine invokes three async actors:

- `loadConfig`: `GET /api/config`.
- `uploadFiles`: `POST /api/uploads`.
- `createJob`: `POST /api/jobs`.

Actor implementations live next to the machine or in a small API helper module.
Tests can replace them with deterministic fakes through machine `provide(...)`.

### 5.7 React integration

`HomePage` owns `useMachine(jobCreationMachine)`.

`SourcePicker` remains presentational. It sends source events upward:

- files selected or dropped
- path chosen
- clear source

`JobConfigInline` keeps its current form layout. It receives machine context and
sends `JOB_FORM_CHANGED` plus `SUBMIT_JOB`. It no longer owns submit-side
network state.

Navigation stays in `HomePage` as a small React effect. When the machine reaches
`submitted`, it navigates to `/jobs/{submittedProjectId}`.

The UI should keep existing test IDs from `frontend/src/lib/testids.ts`.

### 5.8 Error handling

- Config failure enters `configFailed` and keeps the current retry UI.
- Upload failure returns to the current `choosingSource.*` branch and exposes
  `uploadError`.
- Submit failure returns to `configuringJob`, preserves source and form data,
  and exposes `submitError`.
- Clear source removes the selected source and deletes staged upload data
  best-effort.

## 6. Backend statechart

### 6.1 Location

New files:

- `src/pdomain_ocr_simple_gui/statecharts/__init__.py`
- `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py`
- `tests/test_job_lifecycle_statechart.py`

### 6.2 States

The backend lifecycle chart has these states:

```text
new
queued
running
succeeded
failed
cancelled
```

`new` is a transient chart start state. It is not persisted and is not exposed
through the API. The first persisted state remains `queued`, matching the
current `ProjectStatus.state` enum.

Allowed transitions:

```text
new -> queued
queued -> running
queued -> failed
running -> succeeded
running -> failed
running -> cancelled
```

Terminal states reject further progress.

### 6.3 Adapter API

The local adapter should expose a small API:

```python
def transition_job_state(current: JobState, event: JobLifecycleEvent) -> JobState: ...
def assert_job_transition(current: JobState, event: JobLifecycleEvent) -> JobState: ...
```

`transition_job_state` returns the next state or raises a project-local error.
Route and pipeline code should not import `python-statemachine` directly.

### 6.4 Persistence integration

`ProjectStatus.state` remains the persisted source of truth.

Before writing a status state change, code calls the lifecycle adapter. The
adapter validates the transition, then the existing `write_project(...)` path
persists the resulting `ProjectStatus`.

This slice updates only job create and pipeline status writes. Rerun behavior
can reset a terminal job back to `queued` through a separate explicit
`rerun_requested` path, not through normal forward progress.

## 7. Behavior coverage integration

The existing behavior docs stay in place for now. Runtime machines become
first-class behavior artifacts.

### 7.1 Machine metadata

Each frontend state or transition that represents a documented behavior gets
metadata:

```ts
meta: {
  behaviorIds: ["B-HOME-001", "F-UPLOAD-001"]
}
```

The Python lifecycle adapter uses a small behavior mapping table:

```python
BehaviorTransition(
    event="queue",
    source="new",
    target="queued",
    behavior_ids=("B-HOME-001",),
)
```

Behavior IDs in machine metadata must refer to IDs already documented under
`docs/specs/behavior/*`, unless the same implementation slice also adds the new
behavior ID to those docs.

### 7.2 Coverage rules

Extend `scripts/behavior_coverage.py` so a behavior ID can be reported in three
columns:

- documented in `docs/specs/behavior/*`
- modeled by a runtime machine
- executed by a machine test or browser test

Metadata alone is not enough to count as tested. A behavior ID counts as
machine-tested only when a test drives the relevant machine state or transition.

### 7.3 Migration path

Long term, statecharts should become the canonical executable behavior model.
Behavior docs can then shrink into generated indexes or reference reports.

Do not remove the behavior docs in this slice. First prove that machine metadata
and tests cover the same contract.

## 8. Testing

### 8.1 Frontend tests

Add pure machine tests for:

- config load success for each runtime profile
- config failure and retry
- upload success and failure
- path source allowed in local host and local container
- path source rejected in managed server
- clear-source returns to the active profile branch
- submit success stores project id
- submit failure preserves source and form context
- behavior IDs are emitted for covered transitions

Update component tests only where they currently assert local state behavior.
Prefer testing the machine directly for transition logic.

### 8.2 Backend tests

Add Python tests for:

- each valid lifecycle transition
- invalid transitions from terminal states
- invalid skips, such as `new -> running`
- route or pipeline helpers rejecting contradictory status writes
- behavior mapping coverage for lifecycle transitions

### 8.3 E2E tests

Keep Playwright tests stable. Existing selectors, routes, and user-visible copy
should not need broad changes.

E2E still proves the UI is wired to the machine. Machine tests prove the
transition model itself.

## 9. Rollout

1. Add dependencies and lockfile updates.
2. Add frontend machine and pure tests.
3. Refactor Home job creation to use the machine without changing UI.
4. Add Python lifecycle adapter and tests.
5. Wire lifecycle validation into job creation and pipeline writes.
6. Extend behavior coverage reporting.
7. Run focused tests, then full repo CI.

## 10. Risks

- **Dependency churn.** XState v5 and `python-statemachine` both have active
  release streams. Local adapter boundaries reduce the impact.
- **Over-modeling.** Only job creation and lifecycle are in scope. Other flows
  wait until this pattern proves useful.
- **Behavior ID drift.** Machine metadata could become stale if tests do not
  execute it. The coverage script must report modeled-but-untested IDs.
- **UI regressions.** Keeping test IDs and rendering structure stable limits
  this risk. Playwright remains the final UI wiring check.

## 11. References

- XState docs: <https://stately.ai/docs/xstate>
- XState React docs: <https://stately.ai/docs/xstate-react>
- XState setup docs: <https://stately.ai/docs/setup>
- python-statemachine docs: <https://python-statemachine.readthedocs.io/>
- statecharts.dev usage guide: <https://statecharts.dev/how-to-use-statecharts.html>
