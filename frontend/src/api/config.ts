/**
 * fetchRuntimeConfig — the single place that fetches and parses
 * GET /api/config.
 *
 * Previously duplicated across ConfigContext.tsx (React provider) and
 * jobCreationMachine.ts (xstate actor), with divergent RuntimeConfig types.
 * This module owns the canonical superset RuntimeConfig (upload_max_bytes /
 * upload_max_files optional, required by JobConfigInline) and both call
 * sites delegate here (#396).
 */
import { apiFetch } from "./apiFetch";

export interface RuntimeConfig {
  mode: "local" | "managed";
  is_containerized: boolean;
  detected_device: string;
  gpu_available: boolean;
  ocr_engines?: OcrEngineConfig[];
  upload_max_bytes?: number;
  upload_max_files?: number;
}

export interface OcrEngineConfig {
  id: "doctr" | "tesseract";
  label: string;
  available: boolean;
  reason: string | null;
}

export async function fetchRuntimeConfig(): Promise<RuntimeConfig> {
  const res = await apiFetch("/api/config");
  if (!res.ok) throw new Error(`GET /api/config failed: ${res.status}`);
  return (await res.json()) as RuntimeConfig;
}
