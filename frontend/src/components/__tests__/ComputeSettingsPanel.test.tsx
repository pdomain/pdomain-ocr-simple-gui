import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ComputeSettingsPanel } from "../ComputeSettingsPanel";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const gpuInfo = {
  mode: "local",
  current: "cuda:0",
  effective_source: "auto",
  available: [
    { id: "cpu", label: "CPU", available: true, kind: "cpu" },
    {
      id: "cuda:0",
      label: "NVIDIA RTX 4090",
      available: true,
      kind: "cuda",
      vram_total_mb: 24576,
      vram_free_mb: 20000,
    },
    {
      id: "nvidia:1",
      label: "NVIDIA GTX 1080",
      available: false,
      kind: "nvidia",
      reason: "NVIDIA GPU detected, but PyTorch CUDA is not available.",
    },
  ],
};

describe("ComputeSettingsPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders selectable devices, unavailable NVIDIA hardware, and CUDA docs", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(gpuInfo)));
    vi.stubGlobal("fetch", fetchMock);

    render(<ComputeSettingsPanel cudaDocsUrl="/docs/runbooks/cuda-setup.md" />);

    expect(
      await screen.findByRole("radio", { name: "CPU" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /NVIDIA RTX 4090/ }),
    ).toBeChecked();
    expect(
      screen.getByText("24576 MB VRAM (20000 MB free)"),
    ).toBeInTheDocument();
    expect(screen.getByText("NVIDIA GTX 1080")).toBeInTheDocument();
    expect(
      screen.getByText(
        "NVIDIA GPU detected, but PyTorch CUDA is not available.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("radio", { name: /NVIDIA GTX 1080/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "CUDA setup guide" }),
    ).toHaveAttribute("href", "/docs/runbooks/cuda-setup.md");
    expect(fetchMock).toHaveBeenCalledWith("/api/suite/device");
  });

  it("selects an app device with PUT and updates state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(gpuInfo))
      .mockResolvedValueOnce(
        jsonResponse({
          ...gpuInfo,
          current: "cpu",
          effective_source: "app",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ComputeSettingsPanel />);

    await userEvent.click(await screen.findByLabelText("CPU"));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/suite/device", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: "app", device: "cpu" }),
      }),
    );
    expect(
      await screen.findByText("CPU forced for this app"),
    ).toBeInTheDocument();
  });

  it("forces CPU from a non-CPU current device", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(gpuInfo))
      .mockResolvedValueOnce(
        jsonResponse({
          ...gpuInfo,
          current: "cpu",
          effective_source: "app",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ComputeSettingsPanel />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Force CPU" }),
    );

    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith("/api/suite/device", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: "app", device: "cpu" }),
      }),
    );
  });

  it("resets an app-forced CPU preference to auto", async () => {
    const cpuForcedInfo = {
      ...gpuInfo,
      current: "cpu",
      effective_source: "app",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(cpuForcedInfo))
      .mockResolvedValueOnce(
        jsonResponse({
          ...gpuInfo,
          current: "cuda:0",
          effective_source: "auto",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ComputeSettingsPanel />);

    expect(
      await screen.findByText("CPU forced for this app"),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Reset to auto" }),
    );

    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith("/api/suite/device", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: "app", device: "" }),
      }),
    );
  });

  it("shows an alert for GET and PUT errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse({}, 500))),
    );

    const { unmount } = render(<ComputeSettingsPanel />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "GET /api/suite/device failed: 500",
    );
    unmount();

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(gpuInfo))
      .mockResolvedValueOnce(jsonResponse({}, 503));
    vi.stubGlobal("fetch", fetchMock);

    render(<ComputeSettingsPanel />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Force CPU" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "PUT /api/suite/device failed: 503",
    );
  });
});
