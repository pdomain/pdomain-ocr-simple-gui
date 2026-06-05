import { Fragment, useEffect, useState } from "react";

interface DeviceEntry {
  id: string;
  label: string;
  vram_total_mb?: number | null;
  vram_free_mb?: number | null;
  available?: boolean;
  kind?: string | null;
  reason?: string | null;
}

interface DeviceInfo {
  mode?: string;
  available?: DeviceEntry[];
  current?: string | null;
  effective_source?: string | null;
  cuda_docs_url?: string | null;
}

interface ComputeSettingsPanelProps {
  cudaDocsUrl?: string;
}

type DeviceScope = "app" | "suite";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function isUnavailableNvidia(device: DeviceEntry): boolean {
  return device.available === false && device.kind === "nvidia";
}

function isUsableCuda(device: DeviceEntry): boolean {
  return (
    device.available !== false &&
    (device.kind === "cuda" || device.id.startsWith("cuda:"))
  );
}

async function readDeviceInfo(): Promise<DeviceInfo> {
  const res = await fetch("/api/suite/device");
  if (!res.ok) {
    throw new Error(`GET /api/suite/device failed: ${res.status}`);
  }
  return (await res.json()) as DeviceInfo;
}

async function writeDeviceInfo(
  scope: DeviceScope,
  device: string,
): Promise<DeviceInfo> {
  const res = await fetch("/api/suite/device", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope, device }),
  });
  if (!res.ok) {
    throw new Error(`PUT /api/suite/device failed: ${res.status}`);
  }
  return (await res.json()) as DeviceInfo;
}

export function ComputeSettingsPanel({
  cudaDocsUrl,
}: ComputeSettingsPanelProps) {
  const [info, setInfo] = useState<DeviceInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError("");
      try {
        const data = await readDeviceInfo();
        if (!cancelled) setInfo(data);
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function updateDevice(scope: DeviceScope, device: string) {
    setSaving(true);
    setError("");
    try {
      setInfo(await writeDeviceInfo(scope, device));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const devices = info?.available ?? [];
  const current = info?.current ?? null;
  const effectiveSource = info?.effective_source ?? "auto";
  const showCudaGuide =
    devices.some(isUsableCuda) || devices.some(isUnavailableNvidia);
  const guideUrl =
    cudaDocsUrl ?? info?.cuda_docs_url ?? "/docs/runbooks/cuda-setup.md";
  const isAppForcedCpu = current === "cpu" && effectiveSource === "app";

  if (info && info.mode !== "local") {
    return null;
  }

  return (
    <section
      data-testid="compute-settings-panel"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3, 12px)",
        padding: "var(--space-4, 16px)",
      }}
    >
      <h3
        key="heading"
        style={{
          margin: 0,
          fontSize: "var(--text-sm, 0.9rem)",
          fontWeight: "var(--font-semibold, 600)",
        }}
      >
        Compute target
      </h3>

      {loading && (
        <p
          key="loading"
          style={{ margin: 0, fontSize: "0.85em", opacity: 0.8 }}
        >
          Checking compute devices
        </p>
      )}

      {info && (
        <Fragment key="info">
          <fieldset
            key="devices"
            disabled={saving}
            style={{
              border: "none",
              margin: 0,
              padding: 0,
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2, 8px)",
            }}
          >
            <legend key="legend" style={{ display: "none" }}>
              Select compute device
            </legend>
            {devices.map((device) => {
              if (isUnavailableNvidia(device)) {
                return (
                  <div
                    key={device.id}
                    data-testid={`compute-device-unavailable-${device.id}`}
                    style={{
                      padding: "var(--space-2, 8px) var(--space-3, 12px)",
                      border: "1px solid var(--border, #555)",
                      borderRadius: "var(--radius-sm, 4px)",
                    }}
                  >
                    <div
                      key="label"
                      style={{ fontWeight: "var(--font-semibold, 600)" }}
                    >
                      {device.label}
                    </div>
                    {device.reason && (
                      <div
                        key="reason"
                        style={{ fontSize: "0.8em", opacity: 0.75 }}
                      >
                        {device.reason}
                      </div>
                    )}
                  </div>
                );
              }

              const isCurrent = device.id === current;
              return (
                <label
                  key={device.id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                    padding: "var(--space-2, 8px) var(--space-3, 12px)",
                    border: isCurrent
                      ? "1px solid var(--accent, #5f8cff)"
                      : "1px solid var(--border, #555)",
                    borderRadius: "var(--radius-sm, 4px)",
                    cursor: "pointer",
                  }}
                >
                  <span
                    key="label"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <input
                      key="input"
                      type="radio"
                      name="compute-device"
                      value={device.id}
                      checked={isCurrent}
                      onChange={() => void updateDevice("app", device.id)}
                    />
                    <span key="name">{device.label}</span>
                  </span>
                  {device.vram_total_mb != null && (
                    <span
                      key="vram"
                      style={{ fontSize: "0.8em", opacity: 0.75 }}
                    >
                      {device.vram_total_mb} MB VRAM
                      {device.vram_free_mb != null &&
                        ` (${device.vram_free_mb} MB free)`}
                    </span>
                  )}
                </label>
              );
            })}
          </fieldset>

          <p
            key="active"
            style={{ margin: 0, fontSize: "0.8em", opacity: 0.8 }}
          >
            <span key="label">Active: </span>
            <strong key="current">{current ?? "auto"}</strong>
            {effectiveSource && (
              <span key="source"> (via {effectiveSource})</span>
            )}
          </p>

          {isAppForcedCpu && (
            <div
              key="cpu-forced"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                flexWrap: "wrap",
              }}
            >
              <span key="message" style={{ fontSize: "0.8em", opacity: 0.8 }}>
                CPU forced for this app
              </span>
              <button
                key="reset"
                type="button"
                onClick={() => void updateDevice("app", "")}
                disabled={saving}
              >
                Reset to auto
              </button>
            </div>
          )}

          {current !== null && current !== "cpu" && (
            <button
              key="force-cpu"
              type="button"
              onClick={() => void updateDevice("app", "cpu")}
              disabled={saving}
              style={{ alignSelf: "flex-start" }}
            >
              Force CPU
            </button>
          )}

          {showCudaGuide && (
            <a key="cuda-docs" href={guideUrl} style={{ fontSize: "0.85em" }}>
              CUDA setup guide
            </a>
          )}
        </Fragment>
      )}

      {error && (
        <p
          key="error"
          role="alert"
          style={{ color: "var(--color-danger, #c0392b)", margin: 0 }}
        >
          {error}
        </p>
      )}
    </section>
  );
}
