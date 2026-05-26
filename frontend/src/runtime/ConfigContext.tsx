// ConfigContext — A6.1
// Fetches /api/config on mount and provides mode + is_containerized to the tree.
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export interface RuntimeConfig {
  mode: "local" | "managed";
  is_containerized: boolean;
}

const Ctx = createContext<RuntimeConfig | null>(null);

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  useEffect(() => {
    let aborted = false;
    void (async () => {
      try {
        const res = await fetch("/api/config");
        if (!res.ok) return;
        const body = (await res.json()) as RuntimeConfig;
        if (!aborted) setCfg(body);
      } catch {
        // non-fatal — keep null (loading state)
      }
    })();
    return () => {
      aborted = true;
    };
  }, []);
  return <Ctx.Provider value={cfg}>{children}</Ctx.Provider>;
}

export function useConfig(): RuntimeConfig | null {
  return useContext(Ctx);
}
