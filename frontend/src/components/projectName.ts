import type { ChosenSource } from "../statecharts/jobCreationTypes";

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
