import { AppShell } from "../../../components/app-shell";
import { CommunityInbox } from "../../../components/community-inbox";
import { PlatformExperienceHeader } from "../../../components/platform-experience-header";
import { createPlatformOverviewApi, type PlatformKeyOrAll } from "../../../lib/platform-api";
import { createYoutubeApi } from "../../../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export default async function YoutubeCommunityPage() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const [videos, quickReplies, summaries] = await Promise.all([api.getVideos(), api.getQuickReplies(), createPlatformOverviewApi(INTERNAL_API_URL).listPlatforms()]);
  const connected: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const item of summaries) connected[item.platform] = item.connected;

  return (
    <AppShell active="/youtube">
      <PlatformExperienceHeader platform="youtube" section="community" connected={connected} title="Skrzynka komentarzy — YouTube" description="Przeglądaj, oceniaj priorytet i odpowiadaj na komentarze bez opuszczania RCC." />

      {videos.length === 0 ? (
        <div className="emptyState">
          <h3>Brak zsynchronizowanych filmów</h3>
          <p>Połącz i zsynchronizuj kanał YouTube ze strony głównej, aby zacząć synchronizować komentarze.</p>
        </div>
      ) : (
        <CommunityInbox videos={videos} initialQuickReplies={quickReplies} />
      )}
    </AppShell>
  );
}
