// SourcePicker — A6.2
// Drop zone (also click-to-browse) + path input affordances.
// The dropzone IS the entire input affordance — there is no separate
// "Choose files" button. Drop into it, or click it to open the file picker.
// After a drop/select, the dropzone shows what was chosen plus a clear button.
import { useRef, useState } from "react";
import { Button, Field, Input } from "@pdomain/pdomain-ui/primitives";
import { APP_TEST_IDS } from "../lib/testids";

export interface SourcePickerProps {
  allowDrop: boolean;
  allowPathInput: boolean;
  pathHint?: string;
  onUploadComplete: (uploadId: string) => void;
  onPathChosen: (path: string) => void;
  /**
   * Called when the user clicks the dropzone's clear/cancel button.
   * Lets the parent reset any chosen-source state (e.g. hide a config form
   * that was revealed after onUploadComplete).
   */
  onClear?: () => void;
}

async function uploadFiles(files: File[]): Promise<string> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await fetch("/api/uploads", { method: "POST", body: form });
  if (!res.ok) throw new Error(`upload failed: ${res.status}`);
  const body = (await res.json()) as { upload_id: string };
  return body.upload_id;
}

function describeFiles(files: File[]): string {
  if (files.length === 0) return "";
  const first = files[0]?.name ?? "(file)";
  if (files.length === 1) return first;
  return `${first} (+${files.length - 1} more)`;
}

export function SourcePicker(props: SourcePickerProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [pathDraft, setPathDraft] = useState("");
  const [chosenLabel, setChosenLabel] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFiles = async (files: File[]) => {
    if (!files.length) return;
    setChosenLabel(describeFiles(files));
    const id = await uploadFiles(files);
    props.onUploadComplete(id);
  };

  const openPicker = () => {
    fileInput.current?.click();
  };

  const handleClear = () => {
    setChosenLabel(null);
    if (fileInput.current) fileInput.current.value = "";
    props.onClear?.();
  };

  return (
    <div>
      {props.allowDrop && (
        <div
          data-testid={APP_TEST_IDS.sourcePickerDropZone}
          role="button"
          tabIndex={0}
          onClick={openPicker}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              openPicker();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragActive(false);
            void handleFiles(Array.from(e.dataTransfer.files));
          }}
          style={{
            padding: 24,
            border: `2px dashed ${dragActive ? "var(--accent-9)" : "var(--border-3)"}`,
            background: dragActive ? "var(--surface-2)" : "transparent",
            cursor: "pointer",
            borderRadius: 8,
            minHeight: 120,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            textAlign: "center",
          }}
        >
          <input
            ref={fileInput}
            data-testid={APP_TEST_IDS.sourcePickerFilePick}
            type="file"
            multiple
            accept="image/*,.zip"
            style={{
              position: "absolute",
              width: 1,
              height: 1,
              padding: 0,
              margin: -1,
              overflow: "hidden",
              clip: "rect(0,0,0,0)",
              whiteSpace: "nowrap",
              border: 0,
            }}
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              void handleFiles(files);
            }}
          />
          {chosenLabel === null ? (
            <>
              <div>Drop an image, multiple images, a folder, or a .zip here.</div>
              <div style={{ fontSize: 12, opacity: 0.7 }}>or click to browse</div>
            </>
          ) : (
            <div
              style={{ display: "flex", alignItems: "center", gap: 12 }}
              data-testid="source-picker-chosen"
            >
              <span>{chosenLabel}</span>
              <Button
                variant="ghost"
                size="sm"
                data-testid="source-picker-clear"
                onClick={(e) => {
                  e.stopPropagation();
                  handleClear();
                }}
                aria-label="Clear selection"
              >
                × Clear
              </Button>
            </div>
          )}
        </div>
      )}
      {props.allowPathInput && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (pathDraft.trim()) props.onPathChosen(pathDraft.trim());
          }}
        >
          <Field label="Path">
            <Input
              data-testid={APP_TEST_IDS.sourcePickerPathInput}
              value={pathDraft}
              onChange={(e) => setPathDraft(e.target.value)}
              placeholder={props.pathHint ?? "/path/to/folder-or-image-or.zip"}
            />
          </Field>
          <Button type="submit">Use this path</Button>
        </form>
      )}
    </div>
  );
}
