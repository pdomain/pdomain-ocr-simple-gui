import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { apiFetch } from "../../api/apiFetch";
import { StorageSettings } from "../StorageSettings";

vi.mock("../../api/apiFetch", () => ({ apiFetch: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function report(overrides: Record<string, string> = {}) {
  return {
    paths: {
      data: "/data",
      config: "/config",
      state: "/state",
      projects: "/data/projects",
      uploads: "/data/uploads",
      outputs: "/data/outputs",
      jobs: "/data/jobs",
      cache: "/cache",
    },
    overrides,
    legacy_data_present: false,
    migration_in_progress: false,
    installation: { python: "/python", app_environment: "/tool" },
    model_paths: {
      doctr: "/shared/doctr",
      huggingface: "/shared/hf",
      torch: "/shared/torch",
    },
    requested_model_cache: "",
    model_cache_restart_required: false,
  };
}

it("shows effective paths and explains environment-controlled data", async () => {
  vi.mocked(apiFetch).mockResolvedValue(
    Response.json(report({ projects: "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT" })),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  try {
    render(
      <QueryClientProvider client={client}>
        <StorageSettings />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("/data/projects")).toBeInTheDocument();
    expect(
      screen.getByText("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Review data move" }),
    ).toBeDisabled();
  } finally {
    client.clear();
  }
});

it("requires a preview before committing a data move", async () => {
  vi.mocked(apiFetch).mockImplementation(async (path) => {
    if (path === "/api/locations") return Response.json(report());
    if (path === "/api/locations/plan")
      return Response.json({
        destination: "/new-data",
        projects: ["job-1"],
        retained_items: [],
      });
    if (path === "/api/locations/migrate")
      return Response.json({
        data_root: "/new-data",
        project_count: 1,
        originals_preserved: true,
      });
    throw new Error("Unexpected request");
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  try {
    render(
      <QueryClientProvider client={client}>
        <StorageSettings />
      </QueryClientProvider>,
    );
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText("New data folder"),
      "/new-data",
    );
    expect(
      screen.queryByRole("button", { name: "Move data" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Review data move" }));
    await user.click(await screen.findByRole("button", { name: "Move data" }));
    expect(
      await screen.findByText("Data move completed. Original files were kept."),
    ).toBeInTheDocument();
  } finally {
    client.clear();
  }
});
