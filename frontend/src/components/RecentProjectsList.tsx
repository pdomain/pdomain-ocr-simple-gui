// RecentProjectsList — fetches GET /api/prefs and shows recent projects
// Issue #228 — migrated to shared jobs-table CSS (issue #255)
//
// TODO(A9.2): pdomain-ui worklist exports (WordList, LineList, PageList) do not fit
// this use case. WordList/LineList expect OCR word/block items; PageList expects
// {page_index, name, width, height}. RecentProject rows carry {project_id, name,
// last_opened_at, page_count, engine, status}. No generic tabular Worklist exists
// in pdomain-ui@0.2.1. Keeping the hand-rolled <table>.

import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { JobStatusPip } from "@pdomain/pdomain-ui/primitives";
import type { JobState } from "@pdomain/pdomain-ui/types";
import { apiFetch } from "../api/apiFetch";
import { APP_TEST_IDS } from "../lib/testids";

interface RecentProject {
  project_id: string;
  name: string;
  last_opened_at: string;
  page_count: number;
  engine: string;
  status: JobState;
}

interface PrefsResponse {
  recent_projects?: RecentProject[];
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function RecentProjectsList() {
  const navigate = useNavigate();

  const { data, isLoading } = useQuery<RecentProject[]>({
    queryKey: ["recent-projects"],
    queryFn: async () => {
      const res = await apiFetch("/api/prefs");
      if (!res.ok) return [];
      const body = (await res.json()) as PrefsResponse;
      return body.recent_projects ?? [];
    },
    // Network error or unexpected shape → treat as empty list (non-fatal).
    throwOnError: false,
  });

  if (isLoading) {
    return (
      <div
        data-testid={APP_TEST_IDS.recentProjectsList}
        className="recent-projects"
      >
        <p className="recent-projects__loading">Loading…</p>
      </div>
    );
  }

  const displayedProjects = (data ?? []).slice(0, 10);

  if (displayedProjects.length === 0) {
    return (
      <div
        data-testid={APP_TEST_IDS.recentProjectsList}
        className="recent-projects"
      >
        <p className="recent-projects__empty">No recent projects</p>
      </div>
    );
  }

  return (
    <div
      data-testid={APP_TEST_IDS.recentProjectsList}
      className="recent-projects"
    >
      <table className="jobs-table" aria-label="Recent projects">
        <thead>
          <tr>
            <th scope="col" className="jobs-table__th">
              Name
            </th>
            <th scope="col" className="jobs-table__th">
              Last opened
            </th>
            <th scope="col" className="jobs-table__th">
              Pages
            </th>
            <th scope="col" className="jobs-table__th">
              Engine
            </th>
            <th scope="col" className="jobs-table__th">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {displayedProjects.map((project) => (
            <tr
              key={project.project_id}
              className="jobs-table__row"
              onClick={() => navigate(`/jobs/${project.project_id}`)}
              style={{ cursor: "pointer" }}
              tabIndex={0}
              role="row"
              data-testid={APP_TEST_IDS.recentProjectRow}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  navigate(`/jobs/${project.project_id}`);
                }
              }}
              aria-label={`Open project ${project.name}`}
            >
              <td className="jobs-table__name">{project.name}</td>
              <td className="jobs-table__date">
                {formatDate(project.last_opened_at)}
              </td>
              <td className="jobs-table__meta">{project.page_count}</td>
              <td className="jobs-table__meta">{project.engine}</td>
              <td>
                <JobStatusPip state={project.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
