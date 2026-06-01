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
