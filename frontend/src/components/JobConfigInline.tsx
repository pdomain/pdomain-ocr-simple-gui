// JobConfigInline — replaces JobConfigDialog modal with an inline form on HomePage.
// Renders progressively after a source is chosen. Submits the same POST /api/jobs
// payload shape that JobConfigDialog produced. OutputConfigPanel is the sole
// output-destination control; there is no separate outputDir field.

import {
  useState,
  useEffect,
  useMemo,
  type ChangeEvent,
  type FormEvent,
} from "react";
import {
  Button,
  Input,
  Field,
  Toggle,
  Segmented,
} from "@pdomain/pdomain-ui/primitives";
import { OutputConfigPanel, type OutputConfigValue } from "./OutputConfigPanel";
import { APP_TEST_IDS } from "../lib/testids";
import type {
  ChosenSource,
  JobForm,
  RuntimeConfig,
} from "../statecharts/jobCreationTypes";
import {
  availableEngineOptions,
  normalizeEngine,
  normalizeEngineLanguage,
} from "../runtime/ocrEngines";

interface PrefsResponse {
  // AppPrefs (GET /api/prefs) exposes default_engine / default_language —
  // NOT engine / language. Reading the wrong keys silently no-op'd saved
  // defaults (B-HOME-006 regression).
  default_engine?: string;
  default_language?: string;
}

export type { ChosenSource } from "../statecharts/jobCreationTypes";

export interface JobConfigInlineProps {
  /** Structured source; null means options are editable but submit is blocked. */
  source: ChosenSource | null;
  mode?: "local" | "managed";
  runtimeConfig?: RuntimeConfig | null;
  submitError?: string | null;
  submitting?: boolean;
  onCancel?: () => void;
  onFormChanged?: (patch: Partial<JobForm>) => void;
  onSubmitJob?: (form: JobForm) => void;
}

function defaultOutputMode(
  source: ChosenSource | null,
  mode: "local" | "managed",
): OutputConfigValue {
  if (source?.kind === "path" && mode === "local") {
    return { mode: "next_to_source" };
  }
  return { mode: "managed" };
}

/** Derive a sensible project-name default from the source. */
export function defaultProjectName(source: ChosenSource): string {
  if (source.kind === "path") {
    // basename of path, stripping trailing slashes
    const trimmed = source.path.replace(/[/\\]+$/, "");
    const idx = Math.max(trimmed.lastIndexOf("/"), trimmed.lastIndexOf("\\"));
    const base = idx >= 0 ? trimmed.slice(idx + 1) : trimmed;
    return base || "ocr-job";
  }
  // upload: short uploadId
  const short = source.uploadId.slice(0, 8);
  return `ocr-job-${short}`;
}

export function JobConfigInline({
  source,
  mode = "local",
  runtimeConfig = null,
  submitError = null,
  submitting = false,
  onCancel,
  onFormChanged,
  onSubmitJob,
}: JobConfigInlineProps) {
  const gpuAvailable = runtimeConfig?.gpu_available ?? false;
  const engineOptions = availableEngineOptions(runtimeConfig);
  const tesseractAvailable = engineOptions.some(
    (option) => option.id === "tesseract",
  );

  const [projectName, setProjectName] = useState<string>(() =>
    source === null ? "" : defaultProjectName(source),
  );
  const [projectNameTouched, setProjectNameTouched] = useState(false);
  const [engine, setEngine] = useState<JobForm["engine"]>("doctr");
  const [language, setLanguage] = useState<string>("en");
  const [straightQuotes, setStraightQuotes] = useState<boolean>(true);
  const [emDashDoubleHyphen, setEmDashDoubleHyphen] = useState<boolean>(true);
  const [emitIllustrationPlaceholders, setEmitIllustrationPlaceholders] =
    useState<boolean>(false);
  // Device choice: default to "auto" (follow detection). Force "cpu" when no
  // GPU is available so the disabled GPU option is never the active value.
  const [device, setDevice] = useState<"auto" | "gpu" | "cpu">("auto");
  const [showGpuHelp, setShowGpuHelp] = useState<boolean>(false);
  // Blank = default batch size (8); a positive int overrides.
  const [batchPages, setBatchPages] = useState<string>("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const sourceKind = source?.kind ?? null;
  const sourceIsFolder = sourceKind === "path";
  const sourceId =
    source?.kind === "path" ? source.path : (source?.uploadId ?? "");
  const sourceKey = sourceKind === null ? "none" : `${sourceKind}:${sourceId}`;
  const sourceForDefaults = useMemo<ChosenSource | null>(
    () =>
      sourceKind === null
        ? null
        : sourceKind === "path"
          ? { kind: "path", path: sourceId }
          : { kind: "upload", uploadId: sourceId },
    [sourceId, sourceKind],
  );
  const [outputConfig, setOutputConfig] = useState<OutputConfigValue>(() =>
    defaultOutputMode(source, mode),
  );
  const [outputTouched, setOutputTouched] = useState(false);

  // Reset output config + project name when source/mode changes
  useEffect(() => {
    if (sourceForDefaults === null) return;
    const output = defaultOutputMode(sourceForDefaults, mode);
    const name = defaultProjectName(sourceForDefaults);
    const patch: Partial<JobForm> = {};
    if (!outputTouched) {
      setOutputConfig(output);
      patch.output = output;
    }
    if (!projectNameTouched) {
      setProjectName(name);
      patch.name = name;
    }
    if (Object.keys(patch).length > 0) onFormChanged?.(patch);
  }, [
    mode,
    onFormChanged,
    outputTouched,
    projectNameTouched,
    sourceForDefaults,
    sourceKey,
  ]);

  useEffect(() => {
    const nextEngine = normalizeEngine(runtimeConfig, engine);
    if (nextEngine !== engine) {
      setEngine(nextEngine);
      onFormChanged?.({ engine: nextEngine });
    }
  }, [engine, onFormChanged, runtimeConfig]);

  // Load engine/language defaults from prefs on mount
  useEffect(() => {
    let cancelled = false;
    fetch("/api/prefs")
      .then(async (res) => {
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as PrefsResponse;
        if (cancelled) return;
        if (data.default_engine) {
          const nextEngine = normalizeEngine(
            runtimeConfig,
            data.default_engine as JobForm["engine"],
          );
          setEngine(nextEngine);
          onFormChanged?.({ engine: nextEngine });
        }
        if (data.default_language) {
          setLanguage(data.default_language);
          onFormChanged?.({ language: data.default_language });
        }
      })
      .catch(() => {
        // Network error — keep defaults
      });
    return () => {
      cancelled = true;
    };
  }, [onFormChanged, runtimeConfig]);

  function buildForm(): JobForm {
    return {
      name: projectName,
      engine,
      language: normalizeEngineLanguage(engine, language),
      straight_quotes: straightQuotes,
      em_dash_to_double_hyphen: emDashDoubleHyphen,
      emit_illustration_placeholders: emitIllustrationPlaceholders,
      device: !gpuAvailable && device === "gpu" ? "cpu" : device,
      batch_pages:
        batchPages.trim() === ""
          ? null
          : Math.max(1, parseInt(batchPages, 10) || 1),
      output: outputConfig,
    };
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (source === null) {
      setValidationError("Choose a source first.");
      return;
    }
    if (!projectName.trim()) {
      setValidationError("Project name is required.");
      return;
    }
    setValidationError(null);
    onSubmitJob?.(buildForm());
  }

  return (
    <section
      data-testid="job-config-inline"
      className="job-config-inline"
      aria-labelledby="job-config-inline-heading"
    >
      <div className="job-config-inline__header">
        <h3 id="job-config-inline-heading" className="heading-13">
          Configure OCR job
        </h3>
        {source !== null && onCancel && (
          <Button
            variant="ghost"
            type="button"
            onClick={onCancel}
            data-testid="job-config-inline-cancel"
          >
            Use different files
          </Button>
        )}
      </div>

      <form
        data-testid="job-config-inline-form"
        onSubmit={(e) => {
          void handleSubmit(e);
        }}
        noValidate
      >
        {(validationError !== null || submitError !== null) && (
          <p role="alert" className="job-config-inline__error">
            {validationError ?? submitError}
          </p>
        )}

        <Field htmlFor="jci-name" label="Project name">
          <Input
            id="jci-name"
            type="text"
            value={projectName}
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              setProjectNameTouched(true);
              setProjectName(e.target.value);
              onFormChanged?.({ name: e.target.value });
            }}
            aria-label="Project name"
          />
        </Field>

        <Field htmlFor="jci-engine" label="Engine">
          <select
            id="jci-engine"
            value={engine}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => {
              const nextEngine = e.target.value as JobForm["engine"];
              setEngine(nextEngine);
              onFormChanged?.({ engine: nextEngine });
            }}
            className="input"
            aria-label="Engine"
            data-testid={APP_TEST_IDS.engineSelect}
          >
            {engineOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>

        <Field htmlFor="jci-language" label="Language">
          <Input
            id="jci-language"
            type="text"
            value={language}
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              setLanguage(e.target.value);
              onFormChanged?.({ language: e.target.value });
            }}
            placeholder="en"
            data-testid={APP_TEST_IDS.languageInput}
          />
          {engine === "tesseract" ? (
            <p className="job-config-inline__field-note">
              English only for now. The app sends Tesseract code{" "}
              <code>eng</code>.
            </p>
          ) : null}
        </Field>

        <Toggle
          id="jci-straight-quotes"
          label="Convert curly quotes to straight"
          checked={straightQuotes}
          onCheckedChange={(checked) => {
            setStraightQuotes(checked);
            onFormChanged?.({ straight_quotes: checked });
          }}
          data-testid={APP_TEST_IDS.toggleStraightQuotes}
        />
        <Toggle
          id="jci-em-dash"
          label="Convert em-dashes (—) to double hyphens (--)"
          checked={emDashDoubleHyphen}
          onCheckedChange={(checked) => {
            setEmDashDoubleHyphen(checked);
            onFormChanged?.({ em_dash_to_double_hyphen: checked });
          }}
          data-testid={APP_TEST_IDS.toggleEmDash}
        />
        <Toggle
          id="jci-illustration-placeholders"
          label="Emit [illustration] placeholders for figures"
          checked={emitIllustrationPlaceholders}
          onCheckedChange={(checked) => {
            setEmitIllustrationPlaceholders(checked);
            onFormChanged?.({ emit_illustration_placeholders: checked });
          }}
          data-testid={APP_TEST_IDS.toggleIllustrationPlaceholders}
        />

        <Field label="Processing device">
          <div data-testid={APP_TEST_IDS.deviceChooser}>
            <Segmented
              options={
                gpuAvailable
                  ? [
                      { value: "auto", label: "Auto" },
                      { value: "gpu", label: "GPU" },
                      { value: "cpu", label: "CPU" },
                    ]
                  : [
                      { value: "auto", label: "Auto" },
                      { value: "cpu", label: "CPU" },
                    ]
              }
              value={device}
              onChange={(v) => {
                const nextDevice = v as JobForm["device"];
                setDevice(nextDevice);
                onFormChanged?.({ device: nextDevice });
              }}
            />
            <p
              style={{
                margin: "6px 0 0",
                fontSize: 12,
                color: "var(--ink-3)",
              }}
            >
              {gpuAvailable
                ? `GPU detected (${runtimeConfig?.detected_device}). Auto uses it.`
                : "No GPU detected - OCR will run on CPU (slower)."}
              {!gpuAvailable && (
                <>
                  {" "}
                  <button
                    type="button"
                    data-testid={APP_TEST_IDS.gpuHelpToggle}
                    onClick={() => setShowGpuHelp((v) => !v)}
                    style={{
                      background: "none",
                      border: "none",
                      padding: 0,
                      color: "var(--accent)",
                      cursor: "pointer",
                      font: "inherit",
                      textDecoration: "underline",
                    }}
                  >
                    Why is GPU unavailable?
                  </button>
                </>
              )}
            </p>
            {!gpuAvailable && showGpuHelp && (
              <div
                data-testid={APP_TEST_IDS.gpuHelp}
                style={{
                  marginTop: 8,
                  padding: "8px 12px",
                  border: "1px solid var(--border-2)",
                  borderRadius: 6,
                  background: "var(--bg-sunk)",
                  fontSize: 12,
                  color: "var(--ink-2)",
                }}
              >
                <strong>Enabling GPU acceleration</strong>
                <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                  <li>
                    Confirm an NVIDIA GPU + driver: <code>nvidia-smi</code>{" "}
                    should list a device.
                  </li>
                  <li>
                    Install a CUDA-enabled PyTorch build (the CPU-only wheel
                    won&apos;t see the GPU).
                  </li>
                  <li>
                    In a container, start it with <code>--gpus all</code> (or
                    the Compose <code>deploy.resources</code> GPU reservation).
                  </li>
                  <li>
                    Restart the app after changing drivers/toolkit so detection
                    re-runs.
                  </li>
                </ul>
              </div>
            )}
          </div>
        </Field>

        <Field htmlFor="jci-batch-pages" label="Pages per batch (blank = auto)">
          <Input
            id="jci-batch-pages"
            type="number"
            min={1}
            value={batchPages}
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              setBatchPages(e.target.value);
              onFormChanged?.({
                batch_pages:
                  e.target.value.trim() === ""
                    ? null
                    : Math.max(1, parseInt(e.target.value, 10) || 1),
              });
            }}
            placeholder="auto"
            data-testid={APP_TEST_IDS.batchPagesInput}
          />
        </Field>

        <OutputConfigPanel
          mode={mode}
          sourceIsFolder={sourceIsFolder}
          value={outputConfig}
          onChange={(nextOutput) => {
            setOutputTouched(true);
            setOutputConfig(nextOutput);
            onFormChanged?.({ output: nextOutput });
          }}
        />

        <div className="job-config-inline__actions">
          <Button
            type="submit"
            variant="primary"
            disabled={submitting || source === null || !projectName.trim()}
            data-testid={APP_TEST_IDS.runOcrButton}
          >
            {submitting ? "Run OCR →…" : "Run OCR →"}
          </Button>
        </div>
        {!tesseractAvailable ? (
          <p className="job-config-inline__help-link">
            <a href="/help/tesseract">Want to use Tesseract?</a>
          </p>
        ) : null}
      </form>
    </section>
  );
}
