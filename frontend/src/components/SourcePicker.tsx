// SourcePicker is a presentational source-entry surface. Runtime work such as
// uploads is owned by HomePage's jobCreationMachine.
import { useRef, useState } from "react";
import { Button, Field, Input } from "@pdomain/pdomain-ui/primitives";
import { APP_TEST_IDS } from "../lib/testids";

export interface SourcePickerProps {
  allowDrop: boolean;
  allowPathInput: boolean;
  allowFolderBrowse?: boolean;
  recentPaths?: string[];
  pathHint?: string;
  uploadError?: string | null;
  onFilesSelected: (files: File[]) => void;
  onPathChosen: (path: string) => void;
  onClear?: () => void;
}

interface ChosenDescription {
  folder: string | null;
  names: string[];
}

function describeFiles(files: File[]): ChosenDescription {
  const firstRel =
    (files[0] as File & { webkitRelativePath?: string })?.webkitRelativePath ??
    "";
  const folder = firstRel.includes("/") ? firstRel.split("/")[0]! : null;
  return {
    folder,
    names: files.map((file) => file.name),
  };
}

export function SourcePicker(props: SourcePickerProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [pathDraft, setPathDraft] = useState("");
  const [chosen, setChosen] = useState<ChosenDescription | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const allowFolderBrowse = props.allowFolderBrowse ?? props.allowDrop;

  const handleFiles = (files: File[]) => {
    if (!files.length) return;
    setChosen(describeFiles(files));
    props.onFilesSelected(files);
  };

  const openFilePicker = () => {
    fileInput.current?.click();
  };

  const openFolderPicker = () => {
    folderInput.current?.click();
  };

  const handleClear = () => {
    setChosen(null);
    if (fileInput.current) fileInput.current.value = "";
    if (folderInput.current) folderInput.current.value = "";
    props.onClear?.();
  };

  return (
    <div className="source-picker">
      {props.allowDrop && (
        <div
          data-testid={APP_TEST_IDS.sourcePickerDropZone}
          className={`source-picker__drop${dragActive ? " source-picker__drop--active" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragActive(false);
            handleFiles(Array.from(event.dataTransfer.files));
          }}
        >
          <input
            ref={fileInput}
            data-testid={APP_TEST_IDS.sourcePickerFilePick}
            type="file"
            multiple
            accept="image/*,.pdf,.tif,.tiff,.jp2,.zip"
            className="source-picker__hidden-input"
            tabIndex={-1}
            onChange={(event) =>
              handleFiles(Array.from(event.target.files ?? []))
            }
          />
          <input
            ref={folderInput}
            type="file"
            multiple
            className="source-picker__hidden-input"
            tabIndex={-1}
            {...({ webkitdirectory: "" } as Record<string, string>)}
            onChange={(event) =>
              handleFiles(Array.from(event.target.files ?? []))
            }
          />

          <div aria-label="Source type" className="source-picker__mode-tabs">
            <span aria-hidden="true">DIR</span>
            <span aria-hidden="true">FILE</span>
            <span aria-hidden="true">ZIP</span>
          </div>

          {chosen === null ? (
            <>
              <h2>Drop a file or folder to start OCR</h2>
              <p>
                PDF, multi-page TIFF, or a folder of images. Pages are queued
                and OCR&apos;d in the background.
              </p>
              <div className="source-picker__actions">
                {allowFolderBrowse ? (
                  <Button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      openFolderPicker();
                    }}
                  >
                    Browse folder...
                  </Button>
                ) : null}
                <Button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    openFilePicker();
                  }}
                >
                  Choose file...
                </Button>
              </div>
              <p className="source-picker__formats">
                PDF | TIFF | JP2 | PNG | JPG | max 5 GB
              </p>
            </>
          ) : (
            <div
              className="source-picker__chosen"
              data-testid="source-picker-chosen"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="source-picker__chosen-header">
                <strong>
                  {chosen.folder !== null
                    ? chosen.folder
                    : chosen.names.length === 1
                      ? chosen.names[0]
                      : `${chosen.names.length} files`}
                </strong>
                <Button
                  variant="ghost"
                  size="sm"
                  data-testid="source-picker-clear"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleClear();
                  }}
                  aria-label="Clear selection"
                >
                  Clear
                </Button>
              </div>
              {chosen.names.length > 1 && (
                <ul>
                  {chosen.names.map((name, index) => (
                    <li key={`${name}-${index}`}>{name}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {props.uploadError !== null && props.uploadError !== undefined && (
            <div
              role="alert"
              data-testid="source-picker-upload-error"
              style={{
                color: "var(--error-9, red)",
                fontSize: 13,
                marginTop: 8,
              }}
            >
              {props.uploadError}
            </div>
          )}
        </div>
      )}

      {props.allowPathInput && (
        <>
          <div className="source-picker__path-divider">OR PASTE A PATH</div>
          <form
            className="source-picker__path-form"
            onSubmit={(event) => {
              event.preventDefault();
              const path = pathDraft.trim();
              if (path) props.onPathChosen(path);
            }}
          >
            <Field label="Path">
              <Input
                data-testid={APP_TEST_IDS.sourcePickerPathInput}
                value={pathDraft}
                onChange={(event) => setPathDraft(event.target.value)}
                placeholder={
                  props.pathHint ?? "/path/to/folder-or-image-or.zip"
                }
              />
            </Field>
            <Button type="submit">Open</Button>
          </form>
          {props.recentPaths?.length ? (
            <div className="source-picker__recent">
              <span>Recent:</span>
              {props.recentPaths.map((path) => (
                <button
                  type="button"
                  key={path}
                  onClick={() => props.onPathChosen(path)}
                >
                  {path}
                </button>
              ))}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
