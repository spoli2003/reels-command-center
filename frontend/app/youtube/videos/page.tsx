import { Suspense } from "react";

import { AppShell } from "../../../components/app-shell";
import { PlatformExperienceHeader } from "../../../components/platform-experience-header";
import { VideoLibrary } from "../../../components/video-library";
import { createPlatformOverviewApi, type PlatformKeyOrAll } from "../../../lib/platform-api";
import { createYoutubeApi } from "../../../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export default async function YoutubeVideosPage() {
  const [videos, summaries] = await Promise.all([
    createYoutubeApi(INTERNAL_API_URL).getVideos(),
    createPlatformOverviewApi(INTERNAL_API_URL).listPlatforms(),
  ]);
  const connected: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const item of summaries) connected[item.platform] = item.connected;

  return (
    <AppShell active="/youtube">
      <PlatformExperienceHeader platform="youtube" section="videos" connected={connected} title="Materiały — YouTube" description="Biblioteka zsynchronizowanych filmów i Shortsów." />
      <Suspense fallback={null}><VideoLibrary initialVideos={videos} /></Suspense>
    </AppShell>
  );
}
