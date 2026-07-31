import { Suspense } from "react";

import { AppShell } from "../../components/app-shell";
import { UnifiedVideoLibrary } from "../../components/unified-video-library";
import { createPlatformApi, createPlatformOverviewApi } from "../../lib/platform-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export default async function VideosPage() {
  const [videos, platforms] = await Promise.all([
    createPlatformApi(INTERNAL_API_URL, "all").getVideos(),
    createPlatformOverviewApi(INTERNAL_API_URL).listPlatforms(),
  ]);
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
        <UnifiedVideoLibrary initialVideos={videos} platforms={platforms} />
      </Suspense>
    </AppShell>
  );
}
