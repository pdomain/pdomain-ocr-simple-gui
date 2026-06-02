// SourcePicker is a presentational source-entry surface. Runtime work such as
// uploads is owned by HomePage's jobCreationMachine.
import { useEffect, useRef, useState } from "react";
import { Button, Field, Input } from "@pdomain/pdomain-ui/primitives";
import { FileArchive, FileText, FolderOpen } from "lucide-react";
import { APP_TEST_IDS } from "../lib/testids";

export interface SourcePickerProps {
  allowDrop: boolean;
  allowPathInput: boolean;
  allowFolderBrowse?: boolean;
  recentPaths?: string[];
  pathHint?: string;
  uploadError?: string | null;
  resetToken?: unknown;
  onFilesSelected: (files: File[]) => void;
  onPathChosen: (path: string) => void;
  onClear?: () => void;
}

interface ChosenDescription {
  kind: "folder" | "files" | "archive";
  folder: string | null;
  files: File[];
}

function describeFiles(files: File[]): ChosenDescription {
  const firstRel =
    (files[0] as File & { webkitRelativePath?: string })?.webkitRelativePath ??
    "";
  const folder = firstRel.includes("/") ? firstRel.split("/")[0]! : null;
  const kind =
    folder !== null
      ? "folder"
      : files.length === 1 && files[0]?.name.toLowerCase().endsWith(".zip")
        ? "archive"
        : "files";
  return {
    kind,
    folder,
    files,
  };
}

function selectedKind(chosen: ChosenDescription | null) {
  return chosen?.kind ?? null;
}

function chosenTitle(chosen: ChosenDescription): string {
  if (chosen.kind === "folder") return chosen.folder ?? "Folder selected";
  if (chosen.kind === "archive")
    return chosen.files[0]?.name ?? "Archive selected";
  const count = chosen.files.length;
  return `${count} file${count === 1 ? "" : "s"} selected`;
}

export function SourcePicker(props: SourcePickerProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [pathDraft, setPathDraft] = useState("");
  const [chosen, setChosen] = useState<ChosenDescription | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const allowFolderBrowse = props.allowFolderBrowse ?? props.allowDrop;

  useEffect(() => {
    setChosen(null);
    if (fileInput.current) fileInput.current.value = "";
    if (folderInput.current) folderInput.current.value = "";
  }, [props.resetToken]);

  const handleFiles = (files: File[]) => {
    if (!files.length) return;
    const nextSelection = describeFiles(files);
    const nextFiles =
      chosen?.kind === "files" && nextSelection.kind === "files"
        ? [...chosen.files, ...files]
        : files;
    const next = describeFiles(nextFiles);
    setChosen(next);
    props.onFilesSelected(next.files);
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

  const removeFileAt = (index: number) => {
    if (chosen === null || chosen.kind !== "files") return;
    const nextFiles = chosen.files.filter(
      (_, fileIndex) => fileIndex !== index,
    );
    if (!nextFiles.length) {
      handleClear();
      return;
    }
    const next = describeFiles(nextFiles);
    setChosen(next);
    props.onFilesSelected(next.files);
  };

  const currentKind = selectedKind(chosen);

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
            <span
              aria-label="Folder source"
              data-selected={currentKind === "folder" ? "true" : "false"}
            >
              <FolderOpen aria-hidden="true" size={18} strokeWidth={1.8} />
            </span>
            <span
              aria-label="File source"
              data-selected={currentKind === "files" ? "true" : "false"}
            >
              <FileText aria-hidden="true" size={18} strokeWidth={1.8} />
            </span>
            <span
              aria-label="Archive source"
              data-selected={currentKind === "archive" ? "true" : "false"}
            >
              <FileArchive aria-hidden="true" size={18} strokeWidth={1.8} />
            </span>
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
                <strong>{chosenTitle(chosen)}</strong>
                <div className="source-picker__chosen-actions">
                  {chosen.kind === "files" ? (
                    <Button
                      type="button"
                      size="sm"
                      onClick={(event) => {
                        event.stopPropagation();
                        openFilePicker();
                      }}
                    >
                      Add files...
                    </Button>
                  ) : null}
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
              </div>
              {chosen.kind === "files" ? (
                <ul className="source-picker__file-list">
                  {chosen.files.map((file, index) => (
                    <li key={`${file.name}-${file.size}-${index}`}>
                      <span className="source-picker__file-name">
                        {file.name}
                      </span>
                      <button
                        type="button"
                        aria-label={`Remove ${file.name}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          removeFileAt(index);
                        }}
                      >
                        X
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
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

      {props.allowPathInput && chosen === null && (
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
