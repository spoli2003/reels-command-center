import { AppShell } from "../../../components/app-shell";
import { PlatformExperienceHeader } from "../../../components/platform-experience-header";
import { YoutubeCompare } from "../../../components/youtube-compare";
import { createPlatformOverviewApi, type PlatformKeyOrAll } from "../../../lib/platform-api";
import { createYoutubeApi } from "../../../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export default async function YoutubeComparePage() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const [videos, summaries] = await Promise.all([api.getVideos(), createPlatformOverviewApi(INTERNAL_API_URL).listPlatforms()]);
  const connected: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const item of summaries) connected[item.platform] = item.connected;

  return (
    <AppShell active="/youtube">
      <PlatformExperienceHeader platform="youtube" section="compare" connected={connected} title="Porównanie — YouTube" description="Zestaw do 6 filmów, aby porównać wyniki obok siebie." />

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
