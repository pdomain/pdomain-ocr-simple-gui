// SourcePicker — A6.2
// Drop zone + file picker + path input affordances.
// Props control which affordances are active; all POST to /api/uploads.
import { useRef, useState } from "react";
import { Button, Field, Input } from "@pdomain/pdomain-ui/primitives";
import { APP_TEST_IDS } from "../lib/testids";

export interface SourcePickerProps {
  allowDrop: boolean;
  allowFilePick: boolean;
  allowPathInput: boolean;
  pathHint?: string;
  onUploadComplete: (uploadId: string) => void;
  onPathChosen: (path: string) => void;
}

async function uploadFiles(files: File[]): Promise<string> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await fetch("/api/uploads", { method: "POST", body: form });
  if (!res.ok) throw new Error(`upload failed: ${res.status}`);
  const body = (await res.json()) as { upload_id: string };
  return body.upload_id;
}

type UploadStatus = "idle" | "uploading" | "error";

// Inline sr-only style — accessible-but-visually-hidden pattern.
const SR_ONLY_STYLE: React.CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0, 0, 0, 0)",
  whiteSpace: "nowrap",
  border: 0,
};

export function SourcePicker(props: SourcePickerProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [pathDraft, setPathDraft] = useState("");
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [dragActive, setDragActive] = useState(false);

  const handleFiles = async (files: File[]) => {
    if (!files.length) return;
    setUploadStatus("uploading");
    setErrorMessage("");
    try {
      const id = await uploadFiles(files);
      setUploadStatus("idle");
      props.onUploadComplete(id);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Upload failed. Please try again.";
      setUploadStatus("error");
      setErrorMessage(msg);
    }
  };

  const uploading = uploadStatus === "uploading";

  const dropBackground = dragActive ? "var(--bg-raised)" : "transparent";
  const dropBorderColor = dragActive ? "var(--accent)" : "var(--border-3)";

  return (
    <div>
      {props.allowDrop && (
        <div
          data-testid={APP_TEST_IDS.sourcePickerDropZone}
          data-drag-active={dragActive ? "true" : "false"}
          onDragOver={(e) => e.preventDefault()}
          onDragEnter={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            setDragActive(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            setDragActive(false);
            void handleFiles(Array.from(e.dataTransfer.files));
          }}
          style={{
            padding: 24,
            minHeight: 120,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            border: `2px dashed ${dropBorderColor}`,
            borderRadius: 8,
            background: dropBackground,
            color: "var(--fg, inherit)",
            transition: "background 120ms ease, border-color 120ms ease",
          }}
        >
          {dragActive
            ? "Release to upload."
            : "Drop an image, multiple images, a folder, or a .zip here."}
        </div>
      )}
      {props.allowFilePick && (
        <div style={{ marginTop: 12 }}>
          <input
            ref={fileInput}
            data-testid={APP_TEST_IDS.sourcePickerFilePick}
            className="sr-only"
            type="file"
            multiple
            accept="image/*,.zip"
            disabled={uploading}
            style={SR_ONLY_STYLE}
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              void handleFiles(files);
            }}
          />
          <Button
            type="button"
            variant="primary"
            disabled={uploading}
            onClick={() => fileInput.current?.click()}
          >
            Choose files
          </Button>
          {uploading && (
            <span style={{ marginLeft: 12 }} aria-live="polite">
              Uploading…
            </span>
          )}
        </div>
      )}
      {uploadStatus === "error" && (
        <div
          data-testid="source-picker-error"
          role="alert"
          style={{
            marginTop: 12,
            padding: "8px 12px",
            borderRadius: 6,
            border: "1px solid var(--mismatch)",
            color: "var(--mismatch)",
            background: "var(--bg-raised)",
          }}
        >
          {errorMessage || "Upload failed. Please try again."}
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
