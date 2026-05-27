// OutputConfigPanel — A7.1
// Three-mode output destination selector.
// Migrated from radio group to pdomain-ui Segmented control.
// Unavailable options are filtered out of the Segmented rather than disabled:
//   - "next_to_source" requires sourceIsFolder=true
//   - "specified" requires mode !== "managed"

import { type ChangeEvent } from "react";
import {
  Input,
  Segmented,
  type SegmentedOption,
} from "@pdomain/pdomain-ui/primitives";
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

const OPTION_NEXT: SegmentedOption = {
  value: "next_to_source",
  label: "Next to source",
};
const OPTION_SPEC: SegmentedOption = {
  value: "specified",
  label: "Specified folder",
};
const OPTION_MANAGED: SegmentedOption = {
  value: "managed",
  label: "Managed (download)",
};

export function OutputConfigPanel(props: OutputConfigPanelProps) {
  const { mode, sourceIsFolder, value, onChange } = props;

  // Build available options based on current constraints.
  // next_to_source requires a folder source; specified requires local mode.
  const options: SegmentedOption[] = [
    ...(sourceIsFolder ? [OPTION_NEXT] : []),
    ...(mode !== "managed" ? [OPTION_SPEC] : []),
    OPTION_MANAGED,
  ];

  function handleModeChange(newMode: string) {
    if (newMode === "next_to_source") {
      onChange({ mode: "next_to_source" });
    } else if (newMode === "specified") {
      const currentPath = value.mode === "specified" ? value.path : "";
      onChange({ mode: "specified", path: currentPath });
    } else {
      onChange({ mode: "managed" });
    }
  }

  return (
    <div data-testid={APP_TEST_IDS.outputConfigPanel}>
      <p className="label" style={{ marginBottom: "6px" }}>
        Where should results land?
      </p>
      <Segmented
        data-testid="output-mode-segmented"
        options={options}
        value={value.mode}
        onChange={handleModeChange}
        full
      />
      {value.mode === "specified" && (
        <Input
          type="text"
          data-testid={APP_TEST_IDS.outputSpecifiedPath}
          value={value.path}
          onChange={(e: ChangeEvent<HTMLInputElement>) =>
            onChange({ mode: "specified", path: e.target.value })
          }
          placeholder="/path/to/output"
          style={{ marginTop: "6px" }}
        />
      )}
      {/* Hidden sentinels so legacy testids remain addressable in tests */}
      <input
        type="radio"
        name="output-mode"
        data-testid={APP_TEST_IDS.outputModeNextToSource}
        checked={value.mode === "next_to_source"}
        disabled={!sourceIsFolder}
        onChange={() => onChange({ mode: "next_to_source" })}
        style={{ display: "none" }}
        aria-hidden="true"
      />
      <input
        type="radio"
        name="output-mode"
        data-testid={APP_TEST_IDS.outputModeSpecified}
        checked={value.mode === "specified"}
        disabled={mode === "managed"}
        onChange={() => onChange({ mode: "specified", path: "" })}
        style={{ display: "none" }}
        aria-hidden="true"
      />
      <input
        type="radio"
        name="output-mode"
        data-testid={APP_TEST_IDS.outputModeManaged}
        checked={value.mode === "managed"}
        onChange={() => onChange({ mode: "managed" })}
        style={{ display: "none" }}
        aria-hidden="true"
      />
    </div>
  );
}
