import type { YoutubeStatus } from "../lib/youtube-api";

/**
 * The ONE place that renders "last synchronization" for a page header. Every
 * page that shows sync info (Home, Dashboard, Creator Intelligence, Video
 * Detail) must render this component fed by the same `GET /status` response —
 * never a separately-fetched/derived timestamp — so they can never disagree.
 * See docs/DECISIONS.md ADR-016.
 */
export function SyncStatusLine({ status }: { status: YoutubeStatus | null }) {
  if (!status || !status.last_synced_at) {
    return <span>Brak danych o synchronizacji</span>;
  }
  const when = new Date(status.last_synced_at).toLocaleString("pl-PL");
  if (status.last_sync_status === "failed") {
    return <span className="syncStatusTag failed">Synchronizacja nieudana ({when})</span>;
  }
  if (status.last_sync_status === "partial") {
    return <span className="syncStatusTag partial">Synchronizacja częściowa ({when})</span>;
  }
  return <span>Ostatnia synchronizacja: {when}</span>;
}
