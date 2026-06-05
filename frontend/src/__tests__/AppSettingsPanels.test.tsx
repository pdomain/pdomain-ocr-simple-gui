// Tests for F5: settingsPanels includes Compute and Updates entries.
// Unit-tests the exported settingsPanels array from App.tsx.
// These panels arrive from @pdomain/pdomain-ui/shell at runtime;
// here we verify simple-gui wires them correctly.

import { describe, it, expect, vi } from "vitest";

// Mock @pdomain/pdomain-ui/shell — avoids real fetch calls and zustand stores
// in this unit test. We only care that the exported descriptors use the right IDs.
vi.mock("@pdomain/pdomain-ui/shell", () => ({
  AppShell: vi.fn(),
  JobsPill: vi.fn(),
  SuiteSiblingsProvider: vi.fn(),
  ShortcutsHelpButton: vi.fn(),
  SettingsSlot: vi.fn(),
  useUtilityDock: () => ({ toggle: vi.fn() }),
  ComputeTargetPanel: vi.fn().mockReturnValue(null),
  UpdatePanel: vi.fn().mockReturnValue(null),
  UpdateBadge: vi.fn().mockReturnValue(null),
  useDeviceInfo: vi.fn().mockReturnValue({ info: null, loading: false }),
  useUpdateCheck: vi.fn().mockReturnValue({ info: null, loading: false }),
  createApiDeviceConfig: vi.fn().mockReturnValue({
    fetchDevice: vi.fn(),
    putDevice: vi.fn(),
  }),
  createApiUpdateConfig: vi.fn().mockReturnValue({
    fetchUpdate: vi.fn(),
    applyUpdate: vi.fn(),
  }),
}));

vi.mock("@pdomain/pdomain-ui/hooks", () => ({
  ShortcutsProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

vi.mock("@pdomain/pdomain-ui/stores", () => ({
  useDeviceInfo: vi.fn().mockReturnValue({ info: null, loading: false }),
  useUpdateCheck: vi.fn().mockReturnValue({ info: null, loading: false }),
}));

vi.mock("@pdomain/pdomain-ui/stages/PageWorkbench", () => ({
  ArtifactViewer: vi.fn(),
}));

vi.mock("@pdomain/pdomain-ui/canvas", () => ({
  PageImageCanvas: vi.fn(),
}));

describe("settingsPanels", () => {
  it("includes a compute panel descriptor", async () => {
    const { settingsPanels } = await import("../App");
    const ids = settingsPanels.map((p) => p.id);
    expect(ids).toContain("compute");
  });

  it("includes an updates panel descriptor", async () => {
    const { settingsPanels } = await import("../App");
    const ids = settingsPanels.map((p) => p.id);
    expect(ids).toContain("updates");
  });

  it("compute panel has a label", async () => {
    const { settingsPanels } = await import("../App");
    const compute = settingsPanels.find((p) => p.id === "compute");
    expect(compute?.label).toBeTruthy();
  });

  it("updates panel has a label", async () => {
    const { settingsPanels } = await import("../App");
    const updates = settingsPanels.find((p) => p.id === "updates");
    expect(updates?.label).toBeTruthy();
  });
});
