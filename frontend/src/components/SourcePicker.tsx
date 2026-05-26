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

export function SourcePicker(props: SourcePickerProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [pathDraft, setPathDraft] = useState("");

  const handleFiles = async (files: File[]) => {
    if (!files.length) return;
    const id = await uploadFiles(files);
    props.onUploadComplete(id);
  };

  return (
    <div>
      {props.allowDrop && (
        <div
          data-testid={APP_TEST_IDS.sourcePickerDropZone}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            void handleFiles(Array.from(e.dataTransfer.files));
          }}
          style={{ padding: 24, border: "2px dashed var(--pd-border)" }}
        >
          Drop an image, multiple images, a folder, or a .zip here.
        </div>
      )}
      {props.allowFilePick && (
        <div>
          <input
            ref={fileInput}
            data-testid={APP_TEST_IDS.sourcePickerFilePick}
            type="file"
            multiple
            accept="image/*,.zip"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              void handleFiles(files);
            }}
          />
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
