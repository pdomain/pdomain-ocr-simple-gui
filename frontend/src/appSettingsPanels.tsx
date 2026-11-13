import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  UpdatePanel,
  UpdateBadge,
  ComputeTargetPanel,
  createApiDeviceConfig,
  createApiUpdateConfig,
} from "@pdomain/pdomain-ui/shell";
import type { UpdatePolicy } from "@pdomain/pdomain-ui/shell";
import { useDeviceInfo, useUpdateCheck } from "@pdomain/pdomain-ui/stores";
import { toast } from "sonner";
import { CudaSetupGuidance } from "./components/CudaSetupGuidance";
import { apiFetch } from "./api/apiFetch";

/**
 * API-backed update config for UpdatePanel.
 * createApiUpdateConfig reads/writes /api/suite/update.
 */
const _updateConfig = createApiUpdateConfig();
const _deviceConfig = createApiDeviceConfig();
let _computeStateWarmupStarted = false;

export function ComputeStateWarmup() {
  useEffect(() => {
    if (_computeStateWarmupStarted) return;
    _computeStateWarmupStarted = true;
    // Fire-and-forget warmup: tolerate a fetchDevice() that returns a
    // non-promise (e.g. test mocks) so it can never crash the app shell.
    void Promise.resolve(_deviceConfig.fetchDevice()).catch(() => undefined);
  }, []);
  return null;
}

/** Inner component for the Compute panel — calls hooks inside the component tree. */
export function ComputePanelContent() {
  const device = useDeviceInfo(_deviceConfig);

  let body: ReactNode;
  if (device.loading && !device.info) {
    body = (
      <p key="compute-loading" style={{ margin: 0 }}>
        Checking compute devices
      </p>
    );
  } else if (device.error && !device.info) {
    body = (
      <p
        key="compute-error"
        role="alert"
        style={{ margin: 0, color: "var(--color-danger)" }}
      >
        {device.error instanceof Error
          ? device.error.message
          : String(device.error)}
      </p>
    );
  } else {
    body = (
      <ComputeTargetPanel
        key="compute-target"
        info={device.info}
        onSelect={(deviceId) => void device.setDevice("app", deviceId)}
        onClear={(scope) => void device.clearDevice(scope)}
        cudaDocsUrl="https://github.com/pdomain/pdomain-ocr-simple-gui/blob/master/docs/runbooks/cuda-setup.md"
      />
    );
  }

  return (
    <div>
      {body}
      <CudaSetupGuidance key="cuda-guidance" />
    </div>
  );
}

/** Shape of the `common` slice of GET/PUT /api/suite/prefs (partial — we
 * only read/write the fields we know about; unknown fields must survive a
 * read-modify-write round trip, so this stays a loose record). */
type SuiteCommonPrefs = Record<string, unknown> & {
  update_policy?: UpdatePolicy | null;
};

/**
 * Inner component for the Updates panel — calls hooks inside the component
 * tree.
 *
 * The update-policy selector is backed by suite prefs, not local state:
 * `GET /api/suite/prefs` supplies `common.update_policy` on mount, and each
 * selector change re-reads `common` fresh and PUTs the WHOLE object back to
 * `/api/suite/prefs/common` — that route replaces `common` wholesale, so a
 * partial body would blank sibling fields (theme, density, ...).
 */
export function UpdatePanelContent() {
  const update = useUpdateCheck(_updateConfig);
  const [policy, setPolicy] = useState<UpdatePolicy>("notify");
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch("/api/suite/prefs");
        if (!res.ok) {
          if (!cancelled) {
            setLoadError(`GET /api/suite/prefs failed: ${res.status}`);
          }
          return;
        }
        const data = (await res.json()) as { common?: SuiteCommonPrefs };
        if (!cancelled) {
          setPolicy(data.common?.update_policy ?? "notify");
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : String(err));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handlePolicyChange = useCallback((next: UpdatePolicy): void => {
    void (async () => {
      try {
        const getRes = await apiFetch("/api/suite/prefs");
        if (!getRes.ok) {
          throw new Error(`GET /api/suite/prefs failed: ${getRes.status}`);
        }
        const data = (await getRes.json()) as { common?: SuiteCommonPrefs };
        const common: SuiteCommonPrefs = {
          ...(data.common ?? {}),
          update_policy: next,
        };
        const putRes = await apiFetch("/api/suite/prefs/common", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(common),
        });
        if (!putRes.ok) {
          throw new Error(
            `PUT /api/suite/prefs/common failed: ${putRes.status}`,
          );
        }
        setPolicy(next);
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        toast.error("Update policy not saved — server error", {
          description: detail,
        });
      }
    })();
  }, []);

  if (loadError) {
    return (
      <p role="alert" style={{ margin: 0, color: "var(--color-danger)" }}>
        {loadError}
      </p>
    );
  }

  return (
    <UpdatePanel
      info={update.info}
      policy={policy}
      onPolicyChange={handlePolicyChange}
      onApply={() => void update.applyAndRestart()}
    />
  );
}

/**
 * UpdateBadgeHeaderWrapper — renders the UpdateBadge when an update is available.
 * Calls useUpdateCheck inside the component tree (hooks must be inside React components).
 */
export function UpdateBadgeHeaderWrapper() {
  const update = useUpdateCheck(_updateConfig);
  const available = Boolean(update.info?.update_available);
  return <UpdateBadge available={available} />;
}
