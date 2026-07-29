import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { PlatformSubNav } from "../../components/platform-sub-nav";
import { YoutubeDashboard } from "../../components/youtube-dashboard";
import { createYoutubeApi } from "../../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export default async function YoutubeDashboardPage() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const [summary, videos, viewsSeries, likesSeries, commentsSeries, channelHistory] = await Promise.all([
    api.getSummary(),
    api.getVideos(),
    api.getTimeseries("views"),
    api.getTimeseries("likes"),
    api.getTimeseries("comments"),
    api.getChannelHistory(),
  ]);

  const connected = summary !== null && videos.length > 0;

  return (
    <AppShell active="/youtube">
      <header className="topbar">
        <div>
          <p className="eyebrow">YOUTUBE / ANALYTICS</p>
          <h1>Dashboard YouTube</h1>
          <p className="muted">
            {summary?.channel_title ?? "Kanał niepołączony"}
            {summary?.last_synced_at ? ` · ostatnia synchronizacja: ${new Date(summary.last_synced_at).toLocaleString("pl-PL")}` : ""}
          </p>
        </div>
        <Link className="primaryButton" href="/youtube/compare">
          Porównaj filmy
        </Link>
      </header>

      <PlatformSubNav
        active="/youtube"
        tabs={[
          { href: "/youtube", label: "Dashboard" },
          { href: "/youtube/compare", label: "Porównanie" },
          { href: "/youtube/intelligence", label: "Co dalej?" },
        ]}
      />

      {!connected || !summary ? (
        <div className="emptyState">
          <h3>Brak zsynchronizowanych danych</h3>
          <p>
            Połącz i zsynchronizuj kanał YouTube z poziomu <Link href="/">strony głównej</Link>, aby zobaczyć tu pełną analitykę.
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
