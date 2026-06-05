import { Fragment, useEffect, useState } from "react";
import { Button } from "@pdomain/pdomain-ui/primitives";

interface ModelCacheFile {
  filename: string;
  cached: boolean;
  path?: string | null;
}

interface ModelCacheStatus {
  repo: string;
  cache_root: string;
  cached: boolean;
  files: ModelCacheFile[];
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function ModelCacheSettings() {
  const [status, setStatus] = useState<ModelCacheStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [precaching, setPrecaching] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError("");
      try {
        const res = await fetch("/api/models/cache");
        if (!res.ok) {
          throw new Error(`GET /api/models/cache failed: ${res.status}`);
        }
        const data = (await res.json()) as ModelCacheStatus;
        if (!cancelled) setStatus(data);
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

  async function handlePrecache() {
    setPrecaching(true);
    setError("");
    try {
      const res = await fetch("/api/models/precache", { method: "POST" });
      if (!res.ok) {
        throw new Error(`POST /api/models/precache failed: ${res.status}`);
      }
      setStatus((await res.json()) as ModelCacheStatus);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPrecaching(false);
    }
  }

  return (
    <div data-testid="model-cache-settings">
      <p className="label" style={{ marginBottom: "4px" }}>
        OCR model cache
      </p>

      {loading && (
        <p key="loading" style={{ fontSize: "0.85em", opacity: 0.8 }}>
          Checking model cache
        </p>
      )}

      {status && (
        <Fragment key="status">
          <p style={{ fontSize: "0.85em", marginBottom: "4px" }}>
            {status.cached
              ? "OCR models are cached in "
              : "OCR models will be cached in "}
            <code>{status.cache_root}</code>
          </p>
          <p style={{ fontSize: "0.85em", marginBottom: "8px" }}>
            Repository: <code>{status.repo}</code>
          </p>
          <ul
            style={{
              margin: "0 0 8px",
              paddingLeft: "1.2rem",
              fontSize: "0.85em",
            }}
          >
            {status.files.map((file) => (
              <li key={file.filename}>
                <code>{file.filename}</code>:{" "}
                {file.cached ? "cached" : "not cached"}
              </li>
            ))}
          </ul>
        </Fragment>
      )}

      <Button
        key="precache"
        onClick={() => void handlePrecache()}
        disabled={precaching}
      >
        <span key="label">
          {precaching ? "Precaching OCR models" : "Precache OCR models"}
        </span>
      </Button>

      {error && (
        <p
          key="error"
          role="alert"
          style={{ color: "var(--color-danger, #c0392b)", marginTop: "8px" }}
        >
          {error}
        </p>
      )}
    </div>
  );
}
