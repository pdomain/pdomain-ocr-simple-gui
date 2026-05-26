// testids.ts — A6.2
// Re-exports pdomain-ui testids and defines app-local testid constants.
//
// Note: @pdomain/pdomain-ui/testids exports individual named constants
// (e.g. APP_SHELL, JOB_ROW) — NOT a TEST_IDS object. We re-export the
// entire namespace as PD_UI_TEST_IDS for callers who want the full catalog.
// The APP_TEST_IDS object below defines constants local to this app.
export * as PD_UI_TEST_IDS from "@pdomain/pdomain-ui/testids";

export const APP_TEST_IDS = {
  homePage: "home-page",
  sourcePickerDropZone: "source-picker-drop",
  sourcePickerFilePick: "source-picker-file-pick",
  sourcePickerPathInput: "source-picker-path-input",
  outputConfigPanel: "output-config-panel",
  outputModeNextToSource: "output-mode-next-to-source",
  outputModeSpecified: "output-mode-specified",
  outputModeManaged: "output-mode-managed",
  outputSpecifiedPath: "output-specified-path",
  downloadResultsButton: "download-results-button",
  runOcrButton: "run-ocr-button",
  pageRow: "page-row",
  pageViewPage: "page-view-page",
  pageImageCanvas: "page-image-canvas",
  resultsPage: "results-page",
  recentProjectsList: "recent-projects-list",
  engineSelect: "engine-select",
  languageInput: "language-input",
} as const;
