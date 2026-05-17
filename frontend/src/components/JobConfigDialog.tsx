// JobConfigDialog — M4 task #229
// Screen 2: user configures project before running OCR

import { useState, useEffect, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  Button,
  Input,
  Field,
} from "@concavetrillion/pd-ui/primitives";

interface PrefsResponse {
  engine?: string;
  language?: string;
  output_dir?: string;
}

export interface JobConfigDialogProps {
  /** Whether the dialog is open. */
  open: boolean;
  /** Source path selected in the DropZone. */
  sourcePath: string;
  /** Called when the dialog should close (cancel or after successful submit). */
  onClose: () => void;
}

function basename(path: string): string {
  const trimmed = path.replace(/\/$/, "");
  const idx = Math.max(trimmed.lastIndexOf("/"), trimmed.lastIndexOf("\\"));
  return idx >= 0 ? trimmed.slice(idx + 1) : trimmed;
}

export function JobConfigDialog({ open, sourcePath, onClose }: JobConfigDialogProps) {
  const navigate = useNavigate();

  const [projectName, setProjectName] = useState<string>(() => basename(sourcePath));
  const [engine, setEngine] = useState<string>("doctr");
  const [language, setLanguage] = useState<string>("eng");
  const [outputDir, setOutputDir] = useState<string>("");
  const [saveJson, setSaveJson] = useState<boolean>(true);
  const [combinedTxt, setCombinedTxt] = useState<boolean>(true);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Pre-fill name from source path
  useEffect(() => {
    setProjectName(basename(sourcePath));
  }, [sourcePath]);

  // Load defaults from prefs
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
        if (data.output_dir) setOutputDir(data.output_dir);
      })
      .catch(() => {
        // Network error — keep defaults
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  function validate(): string | null {
    if (!sourcePath.trim()) {
      return "Source path is required.";
    }
    if (!outputDir.trim()) {
      return "Output directory is required.";
    }
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const err = validate();
    if (err) {
      setValidationError(err);
      return;
    }
    setValidationError(null);
    setSubmitting(true);

    try {
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
        setValidationError(`Server error: ${text}`);
        return;
      }

      const data = (await res.json()) as { project_id: string };
      onClose();
      navigate(`/jobs/${data.project_id}`);
    } catch (err) {
      setValidationError("Network error — please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New OCR Job</DialogTitle>
          <DialogDescription>
            Configure the job settings before running OCR.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate>
          {validationError && (
            <p role="alert" className="job-config-dialog__error">
              {validationError}
            </p>
          )}

          <Field htmlFor="jcd-project-name" label="Project name">
            <Input
              id="jcd-project-name"
              type="text"
              value={projectName}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setProjectName(e.target.value)
              }
              placeholder="my-scans"
            />
          </Field>

          <Field htmlFor="jcd-engine" label="Engine">
            <select
              id="jcd-engine"
              value={engine}
              onChange={(e: ChangeEvent<HTMLSelectElement>) =>
                setEngine(e.target.value)
              }
              className="job-config-dialog__select"
              aria-label="Engine"
            >
              <option value="doctr">DocTR</option>
              <option value="tesseract">Tesseract</option>
            </select>
          </Field>

          <Field htmlFor="jcd-language" label="Language">
            <Input
              id="jcd-language"
              type="text"
              value={language}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setLanguage(e.target.value)
              }
              placeholder="eng"
            />
          </Field>

          <Field htmlFor="jcd-output-dir" label="Output directory">
            <Input
              id="jcd-output-dir"
              type="text"
              value={outputDir}
              onChange={(e: ChangeEvent<HTMLInputElement>) => {
                setOutputDir(e.target.value);
                if (validationError && e.target.value.trim()) {
                  setValidationError(null);
                }
              }}
              placeholder="/home/user/ocr-output"
              aria-describedby={validationError ? "jcd-error" : undefined}
              aria-invalid={validationError ? true : undefined}
            />
          </Field>

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

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? "Running…" : "Run OCR →"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
