import { AppShell } from "../../../components/app-shell";
import { PlatformSubNav } from "../../../components/platform-sub-nav";
import { YoutubeCompare } from "../../../components/youtube-compare";
import { createYoutubeApi } from "../../../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export default async function YoutubeComparePage() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const videos = await api.getVideos();

  return (
    <AppShell active="/youtube">
      <header className="topbar">
        <div>
          <p className="eyebrow">YOUTUBE / PORÓWNANIE</p>
          <h1>Porównanie filmów</h1>
          <p className="muted">Zestaw do 6 filmów, aby porównać wyniki obok siebie.</p>
        </div>
      </header>

      <PlatformSubNav
        active="/youtube/compare"
        tabs={[
          { href: "/youtube", label: "Dashboard" },
          { href: "/youtube/compare", label: "Porównanie" },
          { href: "/youtube/intelligence", label: "Co dalej?" },
        ]}
      />

      {videos.length === 0 ? (
        <div className="emptyState">
          <h3>Brak filmów</h3>
          <p>Zsynchronizuj kanał YouTube ze strony głównej, aby móc porównywać filmy.</p>
        </div>
      ) : (
        <YoutubeCompare videos={videos} />
      )}
    </AppShell>
  );
}
