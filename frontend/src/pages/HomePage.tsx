// Home screen — DropZone + RecentProjectsList + JobConfigDialog (M3/M4)
// Issues #227 (DropZone), #228 (RecentProjectsList), #229 (JobConfigDialog)

import { useState } from "react";
import { DropZone } from "../components/DropZone";
import { RecentProjectsList } from "../components/RecentProjectsList";
import { JobConfigDialog } from "../components/JobConfigDialog";

export default function HomePage() {
  const [dialogSource, setDialogSource] = useState<string | null>(null);

  function handleValidPath(path: string) {
    setDialogSource(path);
  }

  function handleDialogClose() {
    setDialogSource(null);
  }

  return (
    <div data-testid="home-page" className="home-page">
      <DropZone onValidPath={handleValidPath} />
      <RecentProjectsList />
      <JobConfigDialog
        open={dialogSource !== null}
        sourcePath={dialogSource ?? ""}
        onClose={handleDialogClose}
      />
    </div>
  );
}
