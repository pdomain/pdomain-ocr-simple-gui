import type { SettingsPanelDescriptor } from "@pdomain/pdomain-ui/shell";
import { JobsLocationSettings } from "./components/JobsLocationSettings";
import { ModelCacheSettings } from "./components/ModelCacheSettings";
import { ApiTokenSettings } from "./components/ApiTokenSettings";
import { ComputePanelContent, UpdatePanelContent } from "./appSettingsPanels";

/**
 * App-injected settings panels, appended after pdomain-ui's built-in
 * Appearance tab. The "jobs" panel lets the user choose where new OCR jobs
 * are stored (env > pref > default resolution lives in the backend).
 * "compute" provides app-specific device controls backed by /api/suite/device.
 * "updates" comes from pdomain-ui.
 * "models" exposes local OCR checkpoint cache status and precache.
 * "api-token" (#398) lets the user view/set/clear the `pdomain.apiToken`
 * localStorage key that apiFetch.ts reads — no backend endpoint involved.
 */
export const settingsPanels: SettingsPanelDescriptor[] = [
  {
    id: "jobs",
    label: "Jobs",
    content: <JobsLocationSettings />,
  },
  {
    id: "compute",
    label: "Compute",
    content: <ComputePanelContent />,
  },
  {
    id: "models",
    label: "Models",
    content: <ModelCacheSettings />,
  },
  {
    id: "updates",
    label: "Updates",
    content: <UpdatePanelContent />,
  },
  {
    id: "api-token",
    label: "API Token",
    content: <ApiTokenSettings />,
  },
];
