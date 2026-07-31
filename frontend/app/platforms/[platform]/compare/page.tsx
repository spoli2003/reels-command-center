import { notFound } from "next/navigation";

import { AppShell } from "../../../../components/app-shell";
import { PlatformCompare } from "../../../../components/platform-compare";
import { PlatformExperienceHeader } from "../../../../components/platform-experience-header";
import { createPlatformApi, createPlatformOverviewApi, PLATFORM_LABELS, type PlatformKey, type PlatformKeyOrAll } from "../../../../lib/platform-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
const REAL_PLATFORMS: PlatformKey[] = ["youtube", "facebook", "instagram"];

export default async function PlatformComparePage({ params }: { params: Promise<{ platform: string }> }) {
  const { platform } = await params;
  if (!REAL_PLATFORMS.includes(platform as PlatformKey)) notFound();
  const key = platform as PlatformKey;

  const overviewApi = createPlatformOverviewApi(INTERNAL_API_URL);
  const summaries = await overviewApi.listPlatforms();
  const connected: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const summary of summaries) connected[summary.platform] = summary.connected;

  const api = createPlatformApi(INTERNAL_API_URL, key);
  const videos = await api.getVideos();
  const needsConnect = key !== "youtube" && connected[key] === false;

  return (
    <AppShell active="/platforms">
      <PlatformExperienceHeader platform={key} section="compare" connected={connected} title={`Porównanie — ${PLATFORM_LABELS[key]}`} description="Zestaw do 6 materiałów, aby porównać wyniki obok siebie." />

      {needsConnect ? (
        <div className="emptyState"><h3>{PLATFORM_LABELS[key]} nie jest połączony</h3><p>Połącz konto w sekcji Synchronizacja, aby porównywać materiały.</p></div>
      ) : videos.length === 0 ? (
        <div className="emptyState">
          <h3>Brak materiałów</h3>
          <p>Zsynchronizuj {PLATFORM_LABELS[key]}, aby móc porównywać materiały.</p>
        </div>
      ) : (
        <PlatformCompare platform={key} videos={videos} />
      )}
    </AppShell>
  );
}
