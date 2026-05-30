// JobConfigInline — replaces JobConfigDialog modal with an inline form on HomePage.
// Renders progressively after a source is chosen. Submits the same POST /api/jobs
// payload shape that JobConfigDialog produced. OutputConfigPanel is the sole
// output-destination control; there is no separate outputDir field.

import { useState, useEffect, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Input,
  Field,
  Toggle,
  Segmented,
} from "@pdomain/pdomain-ui/primitives";
import { OutputConfigPanel, type OutputConfigValue } from "./OutputConfigPanel";
import { useConfig } from "../runtime/ConfigContext";
import { APP_TEST_IDS } from "../lib/testids";

interface PrefsResponse {
  // AppPrefs (GET /api/prefs) exposes default_engine / default_language —
  // NOT engine / language. Reading the wrong keys silently no-op'd saved
  // defaults (B-HOME-006 regression).
  default_engine?: string;
  default_language?: string;
}

export type ChosenSource =
  | { kind: "path"; path: string }
  | { kind: "upload"; uploadId: string };

export interface JobConfigInlineProps {
  /** Structured source — required (form is only rendered when a source is chosen). */
  source: ChosenSource;
  /** Current runtime mode from ConfigContext. */
  mode?: "local" | "managed";
  /** Called when user clicks "Use different files" to clear the chosen source. */
  onCancel?: () => void;
}

function defaultOutputMode(
  source: ChosenSource,
  mode: "local" | "managed",
): OutputConfigValue {
  if (source.kind === "path" && mode === "local") {
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
  onCancel,
}: JobConfigInlineProps) {
  const navigate = useNavigate();
  const cfg = useConfig();
  const gpuAvailable = cfg?.gpu_available ?? false;

  const [projectName, setProjectName] = useState<string>(() =>
    defaultProjectName(source),
  );
  const [engine, setEngine] = useState<string>("doctr");
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
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const sourceIsFolder = source.kind === "path";
  const [outputConfig, setOutputConfig] = useState<OutputConfigValue>(() =>
    defaultOutputMode(source, mode),
  );

  // Reset output config + project name when source/mode changes
  useEffect(() => {
    setOutputConfig(defaultOutputMode(source, mode));
    setProjectName(defaultProjectName(source));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    source.kind,
    mode,
    sourceIsFolder
      ? (source as { path: string }).path
      : (source as { uploadId: string }).uploadId,
  ]);

  // Load engine/language defaults from prefs on mount
  useEffect(() => {
    let cancelled = false;
    fetch("/api/prefs")
      .then(async (res) => {
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as PrefsResponse;
        if (cancelled) return;
        if (data.default_engine) setEngine(data.default_engine);
        if (data.default_language) setLanguage(data.default_language);
      })
      .catch(() => {
        // Network error — keep defaults
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!projectName.trim()) {
      setError("Project name is required.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const baseBody: Record<string, unknown> = {
        name: projectName,
        engine,
        language,
        // No save_json / combined_txt knob — the server always writes per-page
        // sidecars + combined.txt (B-HOME-011 cleanup).
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

      if (source.kind === "upload") {
        baseBody.upload_id = source.uploadId;
      } else {
        baseBody.source_path = source.path;
      }

      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(baseBody),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Server error: ${text}`);
      }
      const data = (await res.json()) as { project_id: string };
      navigate(`/jobs/${data.project_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred.");
    } finally {
      setSubmitting(false);
    }
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
        {onCancel && (
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
        {error !== null && (
          <p role="alert" className="job-config-inline__error">
            {error}
          </p>
        )}

        <Field htmlFor="jci-name" label="Project name">
          <Input
            id="jci-name"
            type="text"
            value={projectName}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setProjectName(e.target.value)
            }
            aria-label="Project name"
          />
        </Field>

        <Field htmlFor="jci-engine" label="Engine">
          <select
            id="jci-engine"
            value={engine}
            onChange={(e: ChangeEvent<HTMLSelectElement>) =>
              setEngine(e.target.value)
            }
            className="input"
            aria-label="Engine"
            data-testid={APP_TEST_IDS.engineSelect}
          >
            <option value="doctr">DocTR</option>
            <option value="tesseract">Tesseract</option>
          </select>
        </Field>

        <Field htmlFor="jci-language" label="Language">
          <Input
            id="jci-language"
            type="text"
            value={language}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setLanguage(e.target.value)
            }
            placeholder="en"
            data-testid={APP_TEST_IDS.languageInput}
          />
        </Field>

        <Toggle
          id="jci-straight-quotes"
          label="Convert curly quotes to straight"
          checked={straightQuotes}
          onCheckedChange={setStraightQuotes}
          data-testid={APP_TEST_IDS.toggleStraightQuotes}
        />
        <Toggle
          id="jci-em-dash"
          label="Convert em-dashes (—) to double hyphens (--)"
          checked={emDashDoubleHyphen}
          onCheckedChange={setEmDashDoubleHyphen}
          data-testid={APP_TEST_IDS.toggleEmDash}
        />
        <Toggle
          id="jci-illustration-placeholders"
          label="Emit [illustration] placeholders for figures"
          checked={emitIllustrationPlaceholders}
          onCheckedChange={setEmitIllustrationPlaceholders}
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
              onChange={(v) => setDevice(v as "auto" | "gpu" | "cpu")}
            />
            <p
              style={{
                margin: "6px 0 0",
                fontSize: 12,
                color: "var(--ink-3)",
              }}
            >
              {gpuAvailable
                ? `GPU detected (${cfg?.detected_device}). Auto uses it.`
                : "No GPU detected — OCR will run on CPU (slower)."}
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
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setBatchPages(e.target.value)
            }
            placeholder="auto"
            data-testid={APP_TEST_IDS.batchPagesInput}
          />
        </Field>

        <OutputConfigPanel
          mode={mode}
          sourceIsFolder={sourceIsFolder}
          value={outputConfig}
          onChange={setOutputConfig}
        />

        <div className="job-config-inline__actions">
          <Button
            type="submit"
            variant="primary"
            disabled={submitting || !projectName.trim()}
            data-testid={APP_TEST_IDS.runOcrButton}
          >
            {submitting ? "Run OCR →…" : "Run OCR →"}
          </Button>
        </div>
      </form>
    </section>
  );
}
