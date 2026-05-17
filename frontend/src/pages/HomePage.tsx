// Home screen — DropZone + RecentProjectsList (M3)
// Issues #227 (DropZone), #228 (RecentProjectsList)

import { useNavigate } from "react-router-dom";
import { DropZone } from "../components/DropZone";
import { RecentProjectsList } from "../components/RecentProjectsList";

export default function HomePage() {
  const navigate = useNavigate();

  function handleValidPath(path: string) {
    // TODO M4: open job config dialog and pass the path
    // For now navigate to a new-job route with the path encoded
    navigate(`/new-job?path=${encodeURIComponent(path)}`);
  }

  return (
    <div data-testid="home-page" className="home-page">
      <DropZone onValidPath={handleValidPath} />
      <RecentProjectsList />
    </div>
  );
}
