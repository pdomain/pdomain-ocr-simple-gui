// JobConfigDialog — M4 task #229
// Screen 2: user configures project before running OCR
// Migrated to BaseJobConfigDialog shell (issue #256)
// A7.1: embed OutputConfigPanel; detect upload: sentinel; wire output field.

import { useState, useEffect, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  BaseJobConfigDialog,
  Input,
  Field,
  Toggle,
} from "@pdomain/pdomain-ui/primitives";
import type { BaseJobConfig } from "@pdomain/pdomain-ui/primitives";
import { OutputConfigPanel, type OutputConfigValue } from "./OutputConfigPanel";
import { APP_TEST_IDS } from "../lib/testids";

interface PrefsResponse {
  engine?: string;
  language?: string;
}

type ChosenSource =
  | { kind: "path"; path: string }
  | { kind: "upload"; uploadId: string };

export interface JobConfigDialogProps {
  /** Whether the dialog is open. */
  open: boolean;
  /** Source path selected in the DropZone (legacy sentinel or real path). */
  sourcePath: string;
  /** Called when the dialog should close (cancel or after successful submit). */
  onClose: () => void;
  /** Structured source — preferred over sourcePath when provided. */
  source?: ChosenSource;
  /** Current runtime mode from ConfigContext. */
  mode?: "local" | "managed";
}

/** Parse a ChosenSource from the legacy sourcePath sentinel string. */
function parseSource(sourcePath: string, source?: ChosenSource): ChosenSource {
  if (source) return source;
  if (sourcePath.startsWith("upload:")) {
    return { kind: "upload", uploadId: sourcePath.slice(7) };
  }
  return { kind: "path", path: sourcePath };
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

export function JobConfigDialog({
  open,
  sourcePath,
  onClose,
  source,
  mode = "local",
}: JobConfigDialogProps) {
  const navigate = useNavigate();

  const [engine, setEngine] = useState<string>("doctr");
  const [language, setLanguage] = useState<string>("en");
  const [saveJson, setSaveJson] = useState<boolean>(true);
  const [combinedTxt, setCombinedTxt] = useState<boolean>(true);

  const parsedSource = parseSource(sourcePath, source);
  const sourceIsFolder = parsedSource.kind === "path";

  const [outputConfig, setOutputConfig] = useState<OutputConfigValue>(() =>
    defaultOutputMode(parsedSource, mode),
  );

  // Reset output config when source/mode changes
  useEffect(() => {
    setOutputConfig(defaultOutputMode(parsedSource, mode));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourcePath, mode, source?.kind]);

  // Load engine/language defaults from prefs on open
  useEffect(() => {
    if (!open) return;
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
  }, [open]);

  async function handleSubmit({ projectName, outputDir }: BaseJobConfig) {
    // Build the job body based on source type
    const baseBody: Record<string, unknown> = {
      name: projectName,
      engine,
      language,
      output_dir: outputDir,
      save_json: saveJson,
      combined_txt: combinedTxt,
      output: outputConfig,
    };

    if (parsedSource.kind === "upload") {
      baseBody.upload_id = parsedSource.uploadId;
    } else {
      baseBody.source_path = parsedSource.path;
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
    onClose();
    navigate(`/jobs/${data.project_id}`);
  }

  return (
    <BaseJobConfigDialog
      open={open}
      title="New OCR Job"
      description="Configure the job settings before running OCR."
      sourcePath={sourcePath}
      onClose={onClose}
      onSubmit={handleSubmit}
      submitLabel="Run OCR →"
    >
      {/* Engine select */}
      <Field htmlFor="jcd-engine" label="Engine">
        <select
          id="jcd-engine"
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

      {/* Language */}
      <Field htmlFor="jcd-language" label="Language">
        <Input
          id="jcd-language"
          type="text"
          value={language}
          onChange={(e: ChangeEvent<HTMLInputElement>) =>
            setLanguage(e.target.value)
          }
          placeholder="en"
          data-testid={APP_TEST_IDS.languageInput}
        />
      </Field>

      {/* Boolean toggles */}
      <Toggle
        id="jcd-save-json"
        label="Save JSON sidecar"
        checked={saveJson}
        onCheckedChange={setSaveJson}
      />
      <Toggle
        id="jcd-combined-txt"
        label="Save combined .txt"
        checked={combinedTxt}
        onCheckedChange={setCombinedTxt}
      />

      {/* Output destination */}
      <OutputConfigPanel
        mode={mode}
        sourceIsFolder={sourceIsFolder}
        value={outputConfig}
        onChange={setOutputConfig}
      />

      {/* E2e sentinel: run-ocr-button testid marks that the dialog is open.
          BaseJobConfigDialog renders its own submit button without a testid,
          so we expose a 1x1 visible marker here for Playwright assertions.
          aria-hidden keeps it out of the accessibility tree. */}
      <div
        data-testid={APP_TEST_IDS.runOcrButton}
        aria-hidden="true"
        style={{
          display: "block",
          height: "1px",
          width: "1px",
          overflow: "hidden",
        }}
      />
    </BaseJobConfigDialog>
  );
}
