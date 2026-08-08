// ConfigContext — A6.1
// Fetches /api/config on mount and provides mode + is_containerized to the tree.
//
// B-HOME-014 (Regression): a failed /api/config fetch previously left cfg=null
// forever, so HomePage hung on "Loading…" with no error or recovery. The
// provider now tracks an explicit error state and exposes a reload() so the UI
// can surface the failure and offer a retry instead of an infinite spinner.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { fetchRuntimeConfig, type RuntimeConfig } from "../api/config";

export type { RuntimeConfig, OcrEngineConfig } from "../api/config";

export interface ConfigStatus {
  /** True once a fetch has failed (non-ok response or network error). */
  error: boolean;
  /** Re-run the /api/config fetch (clears the error on success). */
  reload: () => Promise<void>;
}

const ConfigCtx = createContext<RuntimeConfig | null>(null);
const StatusCtx = createContext<ConfigStatus>({
  error: false,
  reload: async () => {},
});

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  const [error, setError] = useState<boolean>(false);

  const load = useCallback(async () => {
    try {
      const body = await fetchRuntimeConfig();
      setCfg(body);
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <ConfigCtx.Provider value={cfg}>
      <StatusCtx.Provider value={{ error, reload: load }}>
        {children}
      </StatusCtx.Provider>
    </ConfigCtx.Provider>
  );
}

export function useConfig(): RuntimeConfig | null {
  return useContext(ConfigCtx);
}

export function useConfigStatus(): ConfigStatus {
  return useContext(StatusCtx);
}
