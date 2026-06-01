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

async function defaultUploadFiles(input: {
  files: File[];
}): Promise<{ uploadId: string }> {
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

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export const jobCreationMachine = setup({
  types: {
    context: {} as JobCreationContext,
    events: {} as JobCreationEvent,
  },
  actors: {
    loadConfig: fromPromise(defaultLoadConfig),
    uploadFiles: fromPromise(({ input }: { input: { files: File[] } }) =>
      defaultUploadFiles(input),
    ),
    createJob: fromPromise(
      ({
        input,
      }: {
        input: { source: ChosenSource; jobForm: JobForm };
      }) => defaultCreateJob(input),
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
        onDone: [
          {
            target: "choosingSource.managedServer",
            guard: ({ event }) => event.output.mode === "managed",
            actions: assign({
              config: ({ event }) => event.output,
              profile: ({ event }) => profileFromConfig(event.output),
            }),
          },
          {
            target: "choosingSource.localContainer",
            guard: ({ event }) => event.output.is_containerized,
            actions: assign({
              config: ({ event }) => event.output,
              profile: ({ event }) => profileFromConfig(event.output),
            }),
          },
          {
            target: "choosingSource.localHost",
            actions: assign({
              config: ({ event }) => event.output,
              profile: ({ event }) => profileFromConfig(event.output),
            }),
          },
        ],
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
      on: {
        CONFIG_RETRY: {
          target: "loadingConfig",
          actions: assign({
            config: null,
            profile: null,
          }),
        },
      },
    },
    choosingSource: {
      initial: "localHost",
      states: {
        hist: {
          type: "history",
          history: "shallow",
        },
        localHost: {},
        localContainer: {},
        managedServer: {},
      },
      on: {
        PATH_CHOSEN: {
          guard: "canUsePath",
          target: "configuringJob",
          actions: assign({
            source: ({ event }) =>
              event.type === "PATH_CHOSEN"
                ? { kind: "path", path: event.path }
                : null,
            submitError: null,
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
            submitError: null,
            behaviorTrace: ({ context }) =>
              appendBehaviorTrace(
                context.behaviorTrace,
                JOB_CREATION_BEHAVIOR.uploadViaDropOrPicker,
              ),
          }),
        },
        onError: {
          target: "choosingSource.hist",
          actions: assign({
            uploadError: ({ event }) =>
              errorMessage(event.error, "Upload failed."),
          }),
        },
      },
    },
    configuringJob: {
      on: {
        CLEAR_SOURCE: {
          target: "choosingSource.hist",
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
        JOB_FORM_CHANGED: {
          actions: "assignJobForm",
        },
        SUBMIT_JOB: {
          guard: "hasSource",
          target: "submittingJob",
        },
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
              errorMessage(event.error, "Job creation failed."),
          }),
        },
      },
    },
    submitted: {
      type: "final",
    },
    failed: {},
  },
});
