import { notFound } from "next/navigation";

import { AppShell } from "../../../../components/app-shell";
import { PlatformExperienceHeader } from "../../../../components/platform-experience-header";
import { PlatformVideoTableSection } from "../../../../components/platform-video-table-section";
import { StatCard, StatsGrid } from "../../../../components/stat-card";
import { createPlatformApi, createPlatformOverviewApi, PLATFORM_LABELS, type PlatformKeyOrAll } from "../../../../lib/platform-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
const VALID_PLATFORMS = ["all", "youtube", "facebook", "instagram"];

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export default async function PlatformVideosPage({ params }: { params: Promise<{ platform: string }> }) {
  const { platform } = await params;
  if (!VALID_PLATFORMS.includes(platform)) notFound();
  const key = platform as PlatformKeyOrAll;

  const overviewApi = createPlatformOverviewApi(INTERNAL_API_URL);
  const summaries = await overviewApi.listPlatforms();
  const connected: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const summary of summaries) connected[summary.platform] = summary.connected;

  const api = createPlatformApi(INTERNAL_API_URL, key);
  const videos = await api.getVideos();

  const needsConnect = key !== "all" && key !== "youtube" && connected[key] === false;
  const totalViews = videos.reduce((sum, v) => sum + v.views, 0);
  const totalInteractions = videos.reduce((sum, v) => sum + v.likes + v.comments, 0);

  return (
    <AppShell active="/platforms">
      <PlatformExperienceHeader platform={key} section="videos" connected={connected} title={`Materiały — ${PLATFORM_LABELS[key]}`} description="Biblioteka zsynchronizowanych publikacji i ich aktualnych wyników." />

      {needsConnect ? (
        <div className="emptyState"><h3>{PLATFORM_LABELS[key]} nie jest połączony</h3><p>Połącz konto w sekcji Synchronizacja, aby zobaczyć materiały.</p></div>
      ) : videos.length === 0 ? (
        <div className="emptyState">
          <h3>Brak materiałów</h3>
          <p>Połącz i zsynchronizuj {key === "all" ? "co najmniej jedną platformę" : PLATFORM_LABELS[key]}, aby zobaczyć tu bibliotekę.</p>
        </div>
      ) : (
        <>
          <StatsGrid>
            <StatCard label="Materiały" value={String(videos.length)} hint={`w bibliotece (${PLATFORM_LABELS[key]})`} />
            <StatCard label="Wyświetlenia" value={compact(totalViews)} hint="suma" />
            <StatCard label="Interakcje" value={compact(totalInteractions)} hint="polubienia + komentarze" />
          </StatsGrid>
          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">CONTENT LIBRARY</p>
                <h2>Wszystkie materiały</h2>
              </div>
            </div>
            <PlatformVideoTableSection videos={videos} />
          </section>
        </>
      )}
    </AppShell>
  );
}
