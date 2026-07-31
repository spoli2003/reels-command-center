import { AppShell } from "../../components/app-shell";
import { PlatformExperienceHeader } from "../../components/platform-experience-header";
import { YoutubeDashboard } from "../../components/youtube-dashboard";
import { createPlatformOverviewApi, type PlatformKeyOrAll } from "../../lib/platform-api";
import { createYoutubeApi } from "../../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export default async function YoutubeDashboardPage() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const [summary, videos, viewsSeries, likesSeries, commentsSeries, channelHistory, summaries] = await Promise.all([
    api.getSummary(),
    api.getVideos(),
    api.getTimeseries("views"),
    api.getTimeseries("likes"),
    api.getTimeseries("comments"),
    api.getChannelHistory(),
    createPlatformOverviewApi(INTERNAL_API_URL).listPlatforms(),
  ]);
  const connectedPlatforms: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const item of summaries) connectedPlatforms[item.platform] = item.connected;

  const hasConnectedData = summary !== null && videos.length > 0;

  return (
    <AppShell active="/youtube">
      <PlatformExperienceHeader platform="youtube" section="" connected={connectedPlatforms} title="YouTube" description={summary?.channel_title ?? "Kanał niepołączony"} />

      {!hasConnectedData || !summary ? (
        <div className="emptyState">
          <h3>Brak zsynchronizowanych danych</h3>
          <p>
            Połącz i zsynchronizuj kanał YouTube w sekcji Synchronizacja, aby zobaczyć tu pełną analitykę.
          </p>
        </div>
      ) : (
        <YoutubeDashboard
          summary={summary}
          videos={videos}
          viewsSeries={viewsSeries}
          likesSeries={likesSeries}
          commentsSeries={commentsSeries}
          channelHistory={channelHistory}
        />
      )}
    </AppShell>
  );
}
