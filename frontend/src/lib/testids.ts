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
  copyPathButton: "copy-path-button",
  downloadResultsButton: "download-results-button",
  deviceChooser: "device-chooser",
  gpuHelpToggle: "gpu-help-toggle",
  gpuHelp: "gpu-help",
  pageDownloadMenu: "page-download-menu",
  pageDownloadText: "page-download-text",
  pageDownloadJson: "page-download-json",
  pageDownloadBoth: "page-download-both",
  runOcrButton: "run-ocr-button",
  pageRow: "page-row",
  pageViewPage: "page-view-page",
  pageImageCanvas: "page-image-canvas",
  resultsPage: "results-page",
  recentProjectsList: "recent-projects-list",
  engineSelect: "engine-select",
  languageInput: "language-input",
  pageZoomIn: "page-zoom-in",
  pageZoomOut: "page-zoom-out",
  pageZoomFit: "page-zoom-fit",
  pageZoom100: "page-zoom-100",
  pageZoomViewport: "page-zoom-viewport",
  jobProgressMessage: "job-progress-message",
  pageProgressMessage: "page-progress-message",
} as const;
