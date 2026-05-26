// OutputConfigPanel — A7.1
// Three-mode radio group for output destination selection.

import { type ChangeEvent } from "react";
import { APP_TEST_IDS } from "../lib/testids";

export type OutputConfigValue =
  | { mode: "next_to_source" }
  | { mode: "specified"; path: string }
  | { mode: "managed" };

export interface OutputConfigPanelProps {
  mode: "local" | "managed";
  sourceIsFolder: boolean;
  value: OutputConfigValue;
  onChange: (next: OutputConfigValue) => void;
}

export function OutputConfigPanel(props: OutputConfigPanelProps) {
  const { mode, sourceIsFolder, value, onChange } = props;
  const nextDisabled = !sourceIsFolder;
  const specDisabled = mode === "managed";
  return (
    <fieldset data-testid={APP_TEST_IDS.outputConfigPanel}>
      <legend>Where should results land?</legend>
      <label>
        <input
          type="radio"
          name="output-mode"
          data-testid={APP_TEST_IDS.outputModeNextToSource}
          disabled={nextDisabled}
          checked={value.mode === "next_to_source"}
          onChange={() => onChange({ mode: "next_to_source" })}
        />
        Next to source image
        {nextDisabled && <small> (only valid for folder sources)</small>}
      </label>
      <label>
        <input
          type="radio"
          name="output-mode"
          data-testid={APP_TEST_IDS.outputModeSpecified}
          disabled={specDisabled}
          checked={value.mode === "specified"}
          onChange={() => onChange({ mode: "specified", path: "" })}
        />
        Specified folder
        {specDisabled && <small> (not available in managed mode)</small>}
      </label>
      {value.mode === "specified" && (
        <input
          type="text"
          data-testid={APP_TEST_IDS.outputSpecifiedPath}
          value={value.path}
          onChange={(e: ChangeEvent<HTMLInputElement>) =>
            onChange({ mode: "specified", path: e.target.value })
          }
          placeholder="/path/to/output"
        />
      )}
      <label>
        <input
          type="radio"
          name="output-mode"
          data-testid={APP_TEST_IDS.outputModeManaged}
          checked={value.mode === "managed"}
          onChange={() => onChange({ mode: "managed" })}
        />
        Managed (download when done)
      </label>
    </fieldset>
  );
}
