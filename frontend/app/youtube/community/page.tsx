import { AppShell } from "../../../components/app-shell";
import { CommunityInbox } from "../../../components/community-inbox";
import { PlatformSubNav } from "../../../components/platform-sub-nav";
import { SyncStatusLine } from "../../../components/sync-status-line";
import { createYoutubeApi } from "../../../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export default async function YoutubeCommunityPage() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const [videos, quickReplies, status] = await Promise.all([api.getVideos(), api.getQuickReplies(), api.getStatus()]);

  return (
    <AppShell active="/youtube">
      <header className="topbar">
        <div>
          <p className="eyebrow">YOUTUBE / KOMENTARZE</p>
          <h1>Skrzynka komentarzy</h1>
          <p className="muted">
            Przeglądaj, oceniaj priorytet i odpowiadaj na komentarze YouTube bez opuszczania RCC. <SyncStatusLine status={status} />
          </p>
        </div>
      </header>

      <PlatformSubNav
        active="/youtube/community"
        tabs={[
          { href: "/youtube", label: "Dashboard" },
          { href: "/youtube/compare", label: "Porównanie" },
          { href: "/youtube/intelligence", label: "Co dalej?" },
          { href: "/youtube/community", label: "Komentarze" },
        ]}
      />

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
