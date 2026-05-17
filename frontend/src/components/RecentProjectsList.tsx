// RecentProjectsList — fetches GET /api/prefs and shows recent projects
// Issue #228

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Chip } from "@concavetrillion/pd-ui/primitives";

interface RecentProject {
  project_id: string;
  name: string;
  last_opened_at: string;
  page_count: number;
  engine: string;
  status: string;
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
  const [projects, setProjects] = useState<RecentProject[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    fetch("/api/prefs")
      .then(async (res) => {
        if (!res.ok) return;
        const data = (await res.json()) as PrefsResponse;
        if (!cancelled) {
          setProjects(data.recent_projects ?? []);
        }
      })
      .catch(() => {
        // Network error — show empty state
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div data-testid="recent-projects-list" className="recent-projects">
        <p className="recent-projects__loading">Loading…</p>
      </div>
    );
  }

  const displayedProjects = projects.slice(0, 10);

  if (displayedProjects.length === 0) {
    return (
      <div data-testid="recent-projects-list" className="recent-projects">
        <p className="recent-projects__empty">No recent projects</p>
      </div>
    );
  }

  return (
    <div data-testid="recent-projects-list" className="recent-projects">
      <table className="recent-projects__table" aria-label="Recent projects">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Last opened</th>
            <th scope="col">Pages</th>
            <th scope="col">Engine</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {displayedProjects.map((project) => (
            <tr
              key={project.project_id}
              className="recent-projects__row"
              onClick={() => navigate(`/jobs/${project.project_id}`)}
              style={{ cursor: "pointer" }}
              tabIndex={0}
              role="row"
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  navigate(`/jobs/${project.project_id}`);
                }
              }}
              aria-label={`Open project ${project.name}`}
            >
              <td className="recent-projects__name">{project.name}</td>
              <td className="recent-projects__date">
                {formatDate(project.last_opened_at)}
              </td>
              <td className="recent-projects__pages">{project.page_count}</td>
              <td className="recent-projects__engine">{project.engine}</td>
              <td className="recent-projects__status">
                <Chip variant="static" className={`status-chip status-chip--${project.status}`}>
                  {project.status}
                </Chip>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
