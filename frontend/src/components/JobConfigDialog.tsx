// JobConfigDialog — M4 task #229
// Screen 2: user configures project before running OCR
// Migrated to BaseJobConfigDialog shell (issue #256)

import { useState, useEffect, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  BaseJobConfigDialog,
  Input,
  Field,
} from "@concavetrillion/pd-ui/primitives";
import type { BaseJobConfig } from "@concavetrillion/pd-ui/primitives";

interface PrefsResponse {
  engine?: string;
  language?: string;
}

export interface JobConfigDialogProps {
  /** Whether the dialog is open. */
  open: boolean;
  /** Source path selected in the DropZone. */
  sourcePath: string;
  /** Called when the dialog should close (cancel or after successful submit). */
  onClose: () => void;
}

export function JobConfigDialog({
  open,
  sourcePath,
  onClose,
}: JobConfigDialogProps) {
  const navigate = useNavigate();

  const [engine, setEngine] = useState<string>("doctr");
  const [language, setLanguage] = useState<string>("en");
  const [saveJson, setSaveJson] = useState<boolean>(true);
  const [combinedTxt, setCombinedTxt] = useState<boolean>(true);

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
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: projectName,
        source_path: sourcePath,
        engine,
        language,
        output_dir: outputDir,
        save_json: saveJson,
        combined_txt: combinedTxt,
      }),
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
          data-testid="engine-select"
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
          data-testid="language-input"
        />
      </Field>

      {/* Checkboxes */}
      <Field htmlFor="jcd-save-json" label="Save JSON sidecar">
        <input
          id="jcd-save-json"
          type="checkbox"
          checked={saveJson}
          onChange={(e: ChangeEvent<HTMLInputElement>) =>
            setSaveJson(e.target.checked)
          }
        />
      </Field>

      <Field htmlFor="jcd-combined-txt" label="Save combined .txt">
        <input
          id="jcd-combined-txt"
          type="checkbox"
          checked={combinedTxt}
          onChange={(e: ChangeEvent<HTMLInputElement>) =>
            setCombinedTxt(e.target.checked)
          }
        />
      </Field>
    </BaseJobConfigDialog>
  );
}
