import { Suspense } from "react";

import { AppShell } from "../../components/app-shell";
import { VideoLibrary } from "../../components/video-library";
import { createYoutubeApi } from "../../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export default async function VideosPage() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const videos = await api.getVideos();
  return (
    <AppShell active="/videos">
      <header className="topbar">
        <div>
          <p className="eyebrow">REELS COMMAND CENTER</p>
          <h1>Biblioteka filmów</h1>
        </div>
        <div className="topActions">
          <span className="localBadge">LOCAL</span>
        </div>
      </header>
      <Suspense fallback={null}>
        <VideoLibrary initialVideos={videos} />
      </Suspense>
    </AppShell>
  );
}
