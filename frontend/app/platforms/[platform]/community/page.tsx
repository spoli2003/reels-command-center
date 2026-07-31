import { notFound } from "next/navigation";

import { AppShell } from "../../../../components/app-shell";
import { PlatformCommunityInbox } from "../../../../components/platform-community-inbox";
import { PlatformExperienceHeader } from "../../../../components/platform-experience-header";
import { createPlatformApi, createPlatformOverviewApi, PLATFORM_LABELS, type PlatformKey, type PlatformKeyOrAll } from "../../../../lib/platform-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
const REAL_PLATFORMS: PlatformKey[] = ["youtube", "facebook", "instagram"];

export default async function PlatformCommunityPage({ params }: { params: Promise<{ platform: string }> }) {
  const { platform } = await params;
  if (!REAL_PLATFORMS.includes(platform as PlatformKey)) notFound();
  const key = platform as PlatformKey;

  const overviewApi = createPlatformOverviewApi(INTERNAL_API_URL);
  const summaries = await overviewApi.listPlatforms();
  const connected: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const summary of summaries) connected[summary.platform] = summary.connected;

  const api = createPlatformApi(INTERNAL_API_URL, key);
  const [videos, quickReplies] = await Promise.all([api.getVideos(), api.getQuickReplies()]);
  const needsConnect = key !== "youtube" && connected[key] === false;

  return (
    <AppShell active="/platforms">
      <PlatformExperienceHeader platform={key} section="community" connected={connected} title={`Skrzynka komentarzy — ${PLATFORM_LABELS[key]}`} description="Przeglądaj, oceniaj priorytet i odpowiadaj bez opuszczania RCC." />

      {needsConnect ? (
        <div className="emptyState"><h3>{PLATFORM_LABELS[key]} nie jest połączony</h3><p>Połącz konto w sekcji Synchronizacja, aby zobaczyć komentarze.</p></div>
      ) : videos.length === 0 ? (
        <div className="emptyState">
          <h3>Brak zsynchronizowanych materiałów</h3>
          <p>Połącz i zsynchronizuj {PLATFORM_LABELS[key]}, aby zacząć synchronizować komentarze.</p>
        </div>
      ) : (
        <PlatformCommunityInbox platform={key} videos={videos} initialQuickReplies={quickReplies} />
      )}
    </AppShell>
  );
}
