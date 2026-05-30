// testids.ts — A6.2
// Re-exports pdomain-ui testids and defines app-local testid constants.
//
// Note: @pdomain/pdomain-ui/testids exports individual named constants
// (e.g. APP_SHELL, JOB_ROW) — NOT a TEST_IDS object. We re-export the
// entire namespace as PD_UI_TEST_IDS for callers who want the full catalog.
// The APP_TEST_IDS object below defines constants local to this app.
//
// AppShell / shell testid notes (M6):
// Most shell elements are rendered by @pdomain/pdomain-ui internally and are
// NOT re-tagged here.  The DOM-addressable selectors are split into two groups:
//
//   Via PD_UI_TEST_IDS (pdomain-ui testids catalog):
//     PD_UI_TEST_IDS.SHORTCUTS_HELP_BUTTON = "shortcuts-help-button"
//     PD_UI_TEST_IDS.SETTINGS_SLOT_TRIGGER  = "settings-slot-trigger"
//     PD_UI_TEST_IDS.SETTINGS_MODAL         = "settings-modal"
//     PD_UI_TEST_IDS.SETTINGS_MODAL_CLOSE   = "settings-modal-close"
//     PD_UI_TEST_IDS.SETTINGS_APPEARANCE_THEME_DARK / _LIGHT
//     PD_UI_TEST_IDS.SETTINGS_APPEARANCE_DENSITY_COMPACT / _NORMAL / _COMFORTABLE
//     PD_UI_TEST_IDS.SETTINGS_APPEARANCE_FONT_SCALE_SLIDER
//     PD_UI_TEST_IDS.APP_SHELL, APP_SHELL_HEADER, APP_SHELL_MAIN, etc.
//
//   Via APP_TEST_IDS (defined below) — pdomain-ui renders these testids
//   but does NOT export them as named constants from its testids catalog:
//     appHeader         = "app-header"        (AppHeader outer <header>)
//     jobsPillCount     = "jobs-pill-count"   (active-jobs count badge)
//     jobsPillPopover   = "jobs-pill-popover" (running-jobs popover container)
//     shortcutsCheatsheet = "shortcuts-cheatsheet" (? overlay dialog)
//
//   Prefs controls (theme/density/fontScale) live entirely inside
//   pdomain-ui's AppShell.  Test via GET/PUT /api/prefs + reload or via
//   PD_UI_TEST_IDS.SETTINGS_APPEARANCE_* selectors above.
export * as PD_UI_TEST_IDS from "@pdomain/pdomain-ui/testids";

export const APP_TEST_IDS = {
  // ---- AppShell / shell (M6) -------------------------------------------------
  // Rendered by pdomain-ui; testids are hardcoded in library, not exported
  // as named constants.  Define local aliases here so test authors have one
  // stable import.
  appHeader: "app-header",
  jobsPillCount: "jobs-pill-count",
  jobsPillPopover: "jobs-pill-popover",
  shortcutsCheatsheet: "shortcuts-cheatsheet",
  // ---------------------------------------------------------------------------
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
  batchPagesInput: "batch-pages-input",
  gpuHelpToggle: "gpu-help-toggle",
  gpuHelp: "gpu-help",
  pageDownloadMenu: "page-download-menu",
  pageDownloadText: "page-download-text",
  pageDownloadJson: "page-download-json",
  pageDownloadBoth: "page-download-both",
  runOcrButton: "run-ocr-button",
  pageRow: "page-row",
  pageViewPage: "page-view-page",
  pageNotFound: "page-not-found",
  pageError: "page-error",
  pageImageCanvas: "page-image-canvas",
  resultsPage: "results-page",
  resultsLoading: "results-loading",
  resultsError: "results-error",
  resultsNotFound: "results-not-found",
  resultsBackHome: "results-back-home",
  rerunFailedButton: "rerun-failed-button",
  resultsRerunError: "results-rerun-error",
  downloadFilterText: "download-filter-text",
  downloadFilterJson: "download-filter-json",
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
  rerunAllButton: "rerun-all-button",
  recentProjectRow: "recent-project-row",
  pagePrevButton: "page-prev-button",
  pageNextButton: "page-next-button",
  pageSaveButton: "page-save-button",
  pageRerunDoctr: "page-rerun-doctr",
  pageRerunTesseract: "page-rerun-tesseract",
  toggleStraightQuotes: "toggle-straight-quotes",
  toggleEmDash: "toggle-em-dash",
  toggleIllustrationPlaceholders: "toggle-illustration-placeholders",
} as const;
