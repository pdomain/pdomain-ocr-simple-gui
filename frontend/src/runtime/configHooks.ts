import { useContext } from "react";
import type { RuntimeConfig } from "../api/config";
import { ConfigCtx, StatusCtx, type ConfigStatus } from "./configState";

export function useConfig(): RuntimeConfig | null {
  return useContext(ConfigCtx);
}

export function useConfigStatus(): ConfigStatus {
  return useContext(StatusCtx);
}
