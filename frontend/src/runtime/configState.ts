import { createContext } from "react";
import type { RuntimeConfig } from "../api/config";

export interface ConfigStatus {
  error: boolean;
  reload: () => Promise<void>;
}

export const ConfigCtx = createContext<RuntimeConfig | null>(null);
export const StatusCtx = createContext<ConfigStatus>({
  error: false,
  reload: async () => {},
});
