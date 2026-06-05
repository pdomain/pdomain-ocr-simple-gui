import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelCacheSettings } from "../ModelCacheSettings";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ModelCacheSettings", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders cached status, cache root, repo, and per-file status from GET", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          repo: "pdomain/pdomain-ocr-models",
          cache_root: "/cache/shared-ai/huggingface/hub",
          cached: true,
          files: [
            {
              filename: "detection/pdomain-all-detection-model-finetuned.pt",
              cached: true,
              path: "/cache/det.pt",
            },
            {
              filename:
                "recognition/pdomain-all-recognition-model-finetuned.pt",
              cached: false,
              path: null,
            },
          ],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ModelCacheSettings />);

    expect(
      await screen.findByText(/OCR models are cached in/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText("/cache/shared-ai/huggingface/hub"),
    ).toBeInTheDocument();
    expect(screen.getByText("pdomain/pdomain-ocr-models")).toBeInTheDocument();
    expect(
      screen
        .getByText("detection/pdomain-all-detection-model-finetuned.pt")
        .closest("li"),
    ).toHaveTextContent("cached");
    expect(
      screen
        .getByText("recognition/pdomain-all-recognition-model-finetuned.pt")
        .closest("li"),
    ).toHaveTextContent("not cached");
    expect(fetchMock).toHaveBeenCalledWith("/api/models/cache");
  });

  it("posts precache request, disables while running, and updates status", async () => {
    let resolvePrecache: (response: Response) => void = () => undefined;
    const precacheResponse = new Promise<Response>((resolve) => {
      resolvePrecache = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          repo: "pdomain/pdomain-ocr-models",
          cache_root: "/cache/hf/hub",
          cached: false,
          files: [
            {
              filename: "detection/pdomain-all-detection-model-finetuned.pt",
              cached: false,
              path: null,
            },
          ],
        }),
      )
      .mockReturnValueOnce(precacheResponse);
    vi.stubGlobal("fetch", fetchMock);

    render(<ModelCacheSettings />);

    expect(
      await screen.findByText(/OCR models will be cached in/i),
    ).toBeInTheDocument();

    const button = screen.getByRole("button", {
      name: /precache ocr models/i,
    });
    await userEvent.click(button);

    expect(fetchMock).toHaveBeenCalledWith("/api/models/precache", {
      method: "POST",
    });
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Precaching OCR models");

    resolvePrecache(
      jsonResponse({
        repo: "pdomain/pdomain-ocr-models",
        cache_root: "/cache/hf/hub",
        cached: true,
        files: [
          {
            filename: "detection/pdomain-all-detection-model-finetuned.pt",
            cached: true,
            path: "/cache/det.pt",
          },
        ],
      }),
    );
    expect(
      await screen.findByText(/OCR models are cached in/i),
    ).toBeInTheDocument();
    expect(
      screen
        .getByText("detection/pdomain-all-detection-model-finetuned.pt")
        .closest("li"),
    ).toHaveTextContent("cached");
  });

  it("shows a role alert when GET fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse({}, 500))),
    );

    render(<ModelCacheSettings />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "GET /api/models/cache failed: 500",
    );
  });

  it("shows a role alert when POST fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          repo: "pdomain/pdomain-ocr-models",
          cache_root: "/cache/hf/hub",
          cached: false,
          files: [],
        }),
      )
      .mockResolvedValueOnce(jsonResponse({}, 503));
    vi.stubGlobal("fetch", fetchMock);

    render(<ModelCacheSettings />);

    await userEvent.click(
      await screen.findByRole("button", { name: /precache ocr models/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "POST /api/models/precache failed: 503",
    );
  });
});
