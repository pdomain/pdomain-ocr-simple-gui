// Tests for settingsPanels includes Compute, Models, and Updates entries.
// Unit-tests the exported settingsPanels array from App.tsx.
// Here we verify simple-gui wires the descriptors correctly.

import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, it, expect, vi } from "vitest";

const fetchDeviceMock = vi.fn(async () => ({
  mode: "local",
  available: [{ id: "cpu", label: "CPU", available: true, kind: "cpu" }],
  current: "cpu",
  effective_source: "auto",
}));
const setDeviceMock = vi.fn();
const clearDeviceMock = vi.fn();
let deviceInfoState = {
  info: {
    mode: "local",
    available: [{ id: "cpu", label: "CPU" }],
    current: "cpu",
    effective_source: "auto",
  },
  loading: false,
  error: null as unknown,
  setDevice: setDeviceMock,
  clearDevice: clearDeviceMock,
};

// Mock @pdomain/pdomain-ui/shell — avoids real fetch calls and zustand stores
// in this unit test. We only care that the exported descriptors use the right IDs.
vi.mock("@pdomain/pdomain-ui/shell", () => ({
  AppShell: vi.fn(),
  JobsPill: vi.fn(),
  SuiteSiblingsProvider: vi.fn(),
  ShortcutsHelpButton: vi.fn(),
  SettingsSlot: vi.fn(),
  useUtilityDock: () => ({ toggle: vi.fn() }),
  ComputeTargetPanel: ({
    children,
    cudaDocsUrl,
  }: {
    children?: ReactNode;
    cudaDocsUrl?: string;
  }) => (
    <div
      data-testid="compute-target-panel-mock"
      data-cuda-docs-url={cudaDocsUrl}
    >
      {children}
    </div>
  ),
  UpdatePanel: vi.fn().mockReturnValue(null),
  UpdateBadge: vi.fn().mockReturnValue(null),
  createApiDeviceConfig: vi.fn().mockReturnValue({
    fetchDevice: fetchDeviceMock,
    putDevice: vi.fn(),
    clearDevice: vi.fn(),
  }),
  useUpdateCheck: vi.fn().mockReturnValue({ info: null, loading: false }),
  createApiUpdateConfig: vi.fn().mockReturnValue({
    fetchUpdate: vi.fn(),
    applyUpdate: vi.fn(),
  }),
}));

vi.mock("@pdomain/pdomain-ui/hooks", () => ({
  ShortcutsProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@pdomain/pdomain-ui/stores", () => ({
  useDeviceInfo: vi.fn(() => deviceInfoState),
  useUpdateCheck: vi.fn().mockReturnValue({ info: null, loading: false }),
}));

vi.mock("@pdomain/pdomain-ui/stages/PageWorkbench", () => ({
  ArtifactViewer: vi.fn(),
}));

vi.mock("@pdomain/pdomain-ui/canvas", () => ({
  PageImageCanvas: vi.fn(),
}));

vi.mock("../components/ModelCacheSettings", () => ({
  ModelCacheSettings: () => <div data-testid="model-cache-settings-mock" />,
}));

vi.mock("../components/CudaSetupGuidance", () => ({
  CudaSetupGuidance: () => <div data-testid="cuda-setup-guidance-mock" />,
}));

describe("settingsPanels", () => {
  afterEach(() => {
    deviceInfoState = {
      info: {
        mode: "local",
        available: [{ id: "cpu", label: "CPU" }],
        current: "cpu",
        effective_source: "auto",
      },
      loading: false,
      error: null,
      setDevice: setDeviceMock,
      clearDevice: clearDeviceMock,
    };
  });

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

  it("includes a models panel descriptor", async () => {
    const { settingsPanels } = await import("../App");
    const models = settingsPanels.find((p) => p.id === "models");
    expect(models?.label).toBe("Models");
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

  it("renders the shared compute target panel with the repo CUDA docs URL", async () => {
    const { settingsPanels } = await import("../App");
    const compute = settingsPanels.find((p) => p.id === "compute");

    render(<>{compute?.content}</>);

    expect(screen.getByTestId("compute-target-panel-mock")).toHaveAttribute(
      "data-cuda-docs-url",
      "/docs/runbooks/cuda-setup.md",
    );
  });

  it("starts a background compute-state fetch at app startup", async () => {
    const { ComputeStateWarmup } = await import("../App");

    render(<ComputeStateWarmup />);

    await waitFor(() => expect(fetchDeviceMock).toHaveBeenCalledTimes(1));
  });

  it("renders CUDA setup guidance inside the Compute settings panel", async () => {
    const { settingsPanels } = await import("../App");
    const compute = settingsPanels.find((p) => p.id === "compute");

    render(<>{compute?.content}</>);

    expect(screen.getByTestId("cuda-setup-guidance-mock")).toBeInTheDocument();
  });

  it("keeps CUDA setup guidance visible while compute devices are loading", async () => {
    deviceInfoState = {
      ...deviceInfoState,
      info: null,
      loading: true,
    };
    const { settingsPanels } = await import("../App");
    const compute = settingsPanels.find((p) => p.id === "compute");

    render(<>{compute?.content}</>);

    expect(screen.getByText(/Checking compute devices/i)).toBeInTheDocument();
    expect(screen.getByTestId("cuda-setup-guidance-mock")).toBeInTheDocument();
  });
});
