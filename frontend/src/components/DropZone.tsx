// DropZone — drag-and-drop zone + path text field + Browse button
// Issue #227

import { useState, useRef, type DragEvent, type ChangeEvent, type KeyboardEvent } from "react";
import { Button, Input, Field } from "@concavetrillion/pd-ui/primitives";

export interface DropZoneProps {
  /** Called when the user has provided a valid (non-empty, non-whitespace) path. */
  onValidPath: (path: string) => void;
}

function isValidPath(value: string): boolean {
  return value.trim().length > 0;
}

export function DropZone({ onValidPath }: DropZoneProps) {
  const [path, setPath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(value: string) {
    const trimmed = value.trim();
    if (!isValidPath(trimmed)) {
      setError("Path is required. Enter a folder or file path.");
      return;
    }
    setError(null);
    onValidPath(trimmed);
  }

  function handleBlur() {
    if (!isValidPath(path)) {
      setError("Path is required. Enter a folder or file path.");
    } else {
      setError(null);
    }
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    setPath(e.target.value);
    if (error && isValidPath(e.target.value)) {
      setError(null);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      handleSubmit(path);
    }
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(true);
  }

  function handleDragLeave() {
    setDragOver(false);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);

    // Try to get the path from the first dropped file.
    // Browsers expose `path` on File objects in Electron/Node contexts;
    // in plain browser we fall back to the file name.
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0] as File & { path?: string };
      const droppedPath = file.path ?? file.name;
      setPath(droppedPath);
      setError(null);
      onValidPath(droppedPath);
    }
  }

  function handleBrowse() {
    fileInputRef.current?.click();
  }

  function handleFileInputChange(e: ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0] as File & { path?: string };
      const chosenPath = file.path ?? file.name;
      setPath(chosenPath);
      setError(null);
      onValidPath(chosenPath);
    }
  }

  return (
    <div
      data-testid="drop-zone"
      className={dragOver ? "drop-zone drop-zone--active" : "drop-zone"}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      aria-label="Drop images or a folder here"
    >
      {/* Hidden file input for Browse button */}
      <input
        ref={fileInputRef}
        type="file"
        // eslint-disable-next-line react/no-unknown-property
        {...({ webkitdirectory: "" } as Record<string, string>)}
        multiple
        style={{ display: "none" }}
        onChange={handleFileInputChange}
        tabIndex={-1}
        aria-hidden="true"
      />

      <p className="drop-zone__hint">
        Drop a folder of images here, or use Browse below.
      </p>

      <Field
        htmlFor="drop-zone-path"
        label="Folder or file path"
      >
        <Input
          id="drop-zone-path"
          type="text"
          value={path}
          onChange={handleChange}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          placeholder="/path/to/my/scans"
          aria-describedby={error ? "drop-zone-error" : undefined}
          aria-invalid={error ? true : undefined}
        />
        {error && (
          <span id="drop-zone-error" role="alert" className="drop-zone__error">
            {error}
          </span>
        )}
      </Field>

      <Button variant="ghost" onClick={handleBrowse} type="button">
        Browse…
      </Button>
    </div>
  );
}
