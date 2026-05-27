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
} from "@pdomain/pdomain-ui/primitives";
import { OutputConfigPanel, type OutputConfigValue } from "./OutputConfigPanel";
import { APP_TEST_IDS } from "../lib/testids";

interface PrefsResponse {
  engine?: string;
  language?: string;
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

  const [projectName, setProjectName] = useState<string>(() =>
    defaultProjectName(source),
  );
  const [engine, setEngine] = useState<string>("doctr");
  const [language, setLanguage] = useState<string>("en");
  const [saveJson, setSaveJson] = useState<boolean>(true);
  const [combinedTxt, setCombinedTxt] = useState<boolean>(true);
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
  }, [source.kind, mode, sourceIsFolder ? (source as { path: string }).path : (source as { uploadId: string }).uploadId]);

  // Load engine/language defaults from prefs on mount
  useEffect(() => {
    let cancelled = false;
    fetch("/api/prefs")
      .then(async (res) => {
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as PrefsResponse;
        if (cancelled) return;
        if (data.engine) setEngine(data.engine);
        if (data.language) setLanguage(data.language);
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
        save_json: saveJson,
        combined_txt: combinedTxt,
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
          id="jci-save-json"
          label="Save JSON sidecar"
          checked={saveJson}
          onCheckedChange={setSaveJson}
        />
        <Toggle
          id="jci-combined-txt"
          label="Save combined .txt"
          checked={combinedTxt}
          onCheckedChange={setCombinedTxt}
        />

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
