import { notFound } from "next/navigation";

import { AppShell } from "../../../components/app-shell";
import { PlatformDashboard } from "../../../components/platform-dashboard";
import { PlatformExperienceHeader } from "../../../components/platform-experience-header";
import { createPlatformApi, createPlatformOverviewApi, PLATFORM_LABELS, type PlatformKeyOrAll } from "../../../lib/platform-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
const VALID_PLATFORMS = ["all", "youtube", "facebook", "instagram"];

export default async function PlatformDashboardPage({ params }: { params: Promise<{ platform: string }> }) {
  const { platform } = await params;
  if (!VALID_PLATFORMS.includes(platform)) notFound();
  const key = platform as PlatformKeyOrAll;

  const overviewApi = createPlatformOverviewApi(INTERNAL_API_URL);
  const summaries = await overviewApi.listPlatforms();
  const connected: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const summary of summaries) connected[summary.platform] = summary.connected;

  const api = createPlatformApi(INTERNAL_API_URL, key);
  const [videos, status] = await Promise.all([api.getVideos(), key === "all" ? Promise.resolve(null) : api.getStatus()]);

  const needsConnect = key !== "all" && key !== "youtube" && connected[key] === false;

  return (
    <AppShell active="/platforms">
      <PlatformExperienceHeader
        platform={key}
        section=""
        connected={connected}
        title={PLATFORM_LABELS[key]}
        description={key === "all" ? "Zbiorczy widok wszystkich połączonych platform." : `Wyniki i materiały z ${PLATFORM_LABELS[key]}.`}
      />

      {needsConnect ? (
        <div className="emptyState"><h3>{PLATFORM_LABELS[key]} nie jest połączony</h3><p>Przejdź do sekcji Synchronizacja, aby połączyć konto i pobrać pierwsze dane.</p></div>
      ) : videos.length === 0 ? (
        <div className="emptyState">
          <h3>Brak zsynchronizowanych danych</h3>
          <p>
            {key === "all"
              ? "Połącz i zsynchronizuj co najmniej jedną platformę, aby zobaczyć tu dane."
              : `Połącz i zsynchronizuj ${PLATFORM_LABELS[key]}, aby zobaczyć tu dane.`}
          </p>
        </div>
      ) : (
        <PlatformDashboard videos={videos} viewsAvailable={status?.platform !== "instagram" || !status.missing_optional_permissions.includes("instagram_manage_insights")} />
      )}

    </AppShell>
  );
}
