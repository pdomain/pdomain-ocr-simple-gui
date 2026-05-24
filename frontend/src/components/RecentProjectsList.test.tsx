// Tests for RecentProjectsList component — TDD first pass
// Issue #228

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { RecentProjectsList } from "./RecentProjectsList";

// Mock react-router navigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Sample prefs response with recent_projects
const mockPrefsWithProjects = {
  recent_projects: [
    {
      project_id: "proj-1",
      name: "My Book Scans",
      last_opened_at: "2026-05-17T10:00:00Z",
      page_count: 12,
      engine: "doctr",
      status: "done",
    },
    {
      project_id: "proj-2",
      name: "Old Newspaper",
      last_opened_at: "2026-05-16T08:30:00Z",
      page_count: 3,
      engine: "tesseract",
      status: "running",
    },
    {
      project_id: "proj-3",
      name: "Another Project",
      last_opened_at: "2026-05-15T12:00:00Z",
      page_count: 8,
      engine: "doctr",
      status: "queued",
    },
  ],
};

const mockPrefsEmpty = { recent_projects: [] };

beforeEach(() => {
  vi.clearAllMocks();
  mockNavigate.mockClear();
});

describe("RecentProjectsList", () => {
  it("shows 'No recent projects' when prefs has empty list", async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockPrefsEmpty,
    });

    render(
      <MemoryRouter>
        <RecentProjectsList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/no recent projects/i)).toBeInTheDocument();
    });
  });

  it("renders project rows from prefs response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockPrefsWithProjects,
    });

    render(
      <MemoryRouter>
        <RecentProjectsList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("My Book Scans")).toBeInTheDocument();
      expect(screen.getByText("Old Newspaper")).toBeInTheDocument();
      expect(screen.getByText("Another Project")).toBeInTheDocument();
    });
  });

  it("shows status chip for each project", async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockPrefsWithProjects,
    });

    render(
      <MemoryRouter>
        <RecentProjectsList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("done")).toBeInTheDocument();
    });
  });

  it("navigates to /jobs/:project_id on row click", async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockPrefsWithProjects,
    });

    render(
      <MemoryRouter>
        <RecentProjectsList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("My Book Scans")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText("My Book Scans"));
    expect(mockNavigate).toHaveBeenCalledWith("/jobs/proj-1");
  });

  it("shows empty state when fetch fails", async () => {
    globalThis.fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("network error"));

    render(
      <MemoryRouter>
        <RecentProjectsList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/no recent projects/i)).toBeInTheDocument();
    });
  });

  it("limits display to 10 projects", async () => {
    const manyProjects = Array.from({ length: 15 }, (_, i) => ({
      project_id: `proj-${i}`,
      name: `Project ${i}`,
      last_opened_at: "2026-05-17T10:00:00Z",
      page_count: i,
      engine: "doctr",
      status: "done",
    }));

    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ recent_projects: manyProjects }),
    });

    render(
      <MemoryRouter>
        <RecentProjectsList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      // Only 10 rows should be shown
      const rows = screen.getAllByRole("row");
      // rows includes header row, so max 11 (1 header + 10 data)
      expect(rows.length).toBeLessThanOrEqual(11);
    });
  });
});
