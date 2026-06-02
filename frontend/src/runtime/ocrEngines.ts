export type EngineId = "doctr" | "tesseract";

interface RuntimeOcrConfig {
  ocr_engines?: {
    id: EngineId;
    label: string;
    available: boolean;
    reason: string | null;
  }[];
}

export function engineIsAvailable(
  config: RuntimeOcrConfig | null | undefined,
  engine: EngineId,
): boolean {
  if (engine === "doctr") return true;
  return (
    config?.ocr_engines?.some(
      (entry) => entry.id === engine && entry.available,
    ) ?? false
  );
}

export function availableEngineOptions(
  config: RuntimeOcrConfig | null | undefined,
) {
  const engines = config?.ocr_engines ?? [
    { id: "doctr" as const, label: "DocTR", available: true, reason: null },
  ];
  return engines.filter((engine) => engine.available);
}

export function normalizeEngine(
  config: RuntimeOcrConfig | null | undefined,
  engine: EngineId,
): EngineId {
  return engineIsAvailable(config, engine) ? engine : "doctr";
}

export function normalizeEngineLanguage(
  engine: EngineId,
  language: string,
): string {
  const trimmed = language.trim();
  if (engine === "tesseract" && trimmed.toLowerCase() === "en") {
    return "eng";
  }
  return trimmed;
}
