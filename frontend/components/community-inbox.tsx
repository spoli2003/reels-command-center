"use client";

import { useEffect, useMemo, useState } from "react";

import { CommentThreadCard } from "./comment-thread-card";
import { QuickReplyManager } from "./quick-reply-manager";
import type {
  CommentInboxRead,
  CommentQuickFilter,
  CommentSort,
  CommentSyncStatus,
  QuickReplyTemplate,
  YoutubeChannelVideo,
} from "../lib/youtube-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const QUICK_FILTERS: { key: CommentQuickFilter; label: string }[] = [
  { key: "all", label: "Wszystkie" },
  { key: "waiting", label: "🟡 Czekają" },
  { key: "new", label: "🔵 Nowe" },
  { key: "resolved", label: "🟢 Rozwiązane" },
  { key: "closed", label: "⚪ Zamknięte" },
  { key: "questions", label: "Pytania" },
  { key: "recent", label: "Ostatnie" },
  { key: "with_replies", label: "Z odpowiedziami" },
  { key: "highly_liked", label: "Wysoko oceniane" },
];

const SORT_OPTIONS: { key: CommentSort; label: string }[] = [
  { key: "newest", label: "Najnowsze" },
  { key: "oldest", label: "Najstarsze" },
  { key: "recently_active", label: "Ostatnia aktywność" },
  { key: "most_liked", label: "Najbardziej polubione" },
  { key: "most_replies", label: "Najwięcej odpowiedzi" },
  { key: "priority", label: "Priorytet" },
];

const SYNC_STATUS_LABELS: Record<string, string> = { success: "Udana", partial: "Częściowo udana", failed: "Nieudana" };

export function CommunityInbox({ videos, initialQuickReplies }: { videos: YoutubeChannelVideo[]; initialQuickReplies: QuickReplyTemplate[] }) {
  const [inbox, setInbox] = useState<CommentInboxRead | null>(null);
  const [syncStatus, setSyncStatus] = useState<CommentSyncStatus | null>(null);
  const [quickReplies, setQuickReplies] = useState(initialQuickReplies);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState("");

  const [quick, setQuick] = useState<CommentQuickFilter>("all");
  const [videoFilter, setVideoFilter] = useState("");
  const [authorFilter, setAuthorFilter] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<CommentSort>("newest");

  async function load() {
    setError("");
    try {
      const params = new URLSearchParams();
      if (quick !== "all") params.set("quick", quick);
      if (videoFilter) params.set("video", videoFilter);
      if (authorFilter) params.set("author", authorFilter);
      if (search) params.set("q", search);
      params.set("sort", sort);
      const [inboxResponse, statusResponse] = await Promise.all([
        fetch(`${API_URL}/api/integrations/youtube/comments?${params.toString()}`, { cache: "no-store" }),
        fetch(`${API_URL}/api/integrations/youtube/comments/sync-status`, { cache: "no-store" }),
      ]);
      if (inboxResponse.ok) setInbox(await inboxResponse.json());
      if (statusResponse.ok) setSyncStatus(await statusResponse.json());
    } catch {
      setError("Backend nie odpowiada. Sprawdź, czy Docker działa.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setLoading(true);
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quick, videoFilter, authorFilter, search, sort]);

  async function synchronize(mode: "incremental" | "full") {
    setSyncing(true);
    setError("");
    setSyncFeedback("");
    try {
      const response = await fetch(`${API_URL}/api/integrations/youtube/comments/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? "Synchronizacja komentarzy nie powiodła się.");
      }
      const result = await response.json();
      setSyncFeedback(
        `Wątki: ${result.threads_discovered}, nowe komentarze: ${result.comments_imported}, nowe odpowiedzi: ${result.replies_imported}.`,
      );
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Synchronizacja komentarzy nie powiodła się.");
    } finally {
      setSyncing(false);
    }
  }

  const videoOptions = useMemo(() => [...videos].sort((a, b) => +new Date(b.published_at) - +new Date(a.published_at)), [videos]);

  return (
    <>
      {syncStatus !== null && !syncStatus.comments_scope_granted ? (
        <div className="alert informational">
          To konto nie ma jeszcze uprawnienia do komentarzy. Połącz konto ponownie z poziomu strony głównej, aby włączyć Skrzynkę
          komentarzy.
        </div>
      ) : null}

      <section className="statsGrid">
        <article className="metricCard featured">
          <span>Wymagają uwagi</span>
          <strong>{inbox?.summary.awaiting_reply_count ?? 0}</strong>
          <small>nowe + czekające na odpowiedź</small>
        </article>
        <article className="metricCard">
          <span>🟡 Czekają</span>
          <strong>{inbox?.summary.waiting_count ?? 0}</strong>
          <small>widz odpowiedział ponownie</small>
        </article>
        <article className="metricCard">
          <span>🔵 Nowe</span>
          <strong>{inbox?.summary.new_count ?? 0}</strong>
          <small>brak odpowiedzi kanału</small>
        </article>
        <article className="metricCard">
          <span>🟢 Rozwiązane</span>
          <strong>{inbox?.summary.resolved_count ?? 0}</strong>
          <small>ostatnie słowo należy do kanału</small>
        </article>
        <article className="metricCard">
          <span>Prawdopodobne pytania</span>
          <strong>{inbox?.summary.questions_count ?? 0}</strong>
          <small>wykryte heurystycznie</small>
        </article>
        <article className="metricCard">
          <span>Ostatnie (7 dni)</span>
          <strong>{inbox?.summary.recent_count ?? 0}</strong>
          <small>nowe komentarze</small>
        </article>
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">SYNCHRONIZACJA KOMENTARZY</p>
            <h2>Status synchronizacji</h2>
          </div>
          <div className="actions">
            <button className="button" onClick={() => synchronize("incremental")} disabled={syncing}>
              {syncing ? "Synchronizuję…" : "Synchronizuj komentarze"}
            </button>
            <button className="button secondary" onClick={() => synchronize("full")} disabled={syncing}>
              Pełne odświeżenie
            </button>
          </div>
        </div>
        {error && <div className="alert">{error}</div>}
        {syncFeedback && !error ? <div className="syncFeedback">✓ {syncFeedback}</div> : null}
        {syncStatus ? (
          <div className="syncDetails">
            <div className="syncDetailRow">
              <span>Ostatnia synchronizacja komentarzy</span>
              <strong>{syncStatus.last_synced_at ? new Date(syncStatus.last_synced_at).toLocaleString("pl-PL") : "jeszcze nie wykonano"}</strong>
            </div>
            {syncStatus.last_sync_status ? (
              <div className="syncDetailRow">
                <span>Status</span>
                <strong className={`syncStatusTag ${syncStatus.last_sync_status}`}>
                  {SYNC_STATUS_LABELS[syncStatus.last_sync_status] ?? syncStatus.last_sync_status}
                </strong>
              </div>
            ) : null}
            <div className="syncDetailRow">
              <span>Wątki / nowe komentarze / nowe odpowiedzi</span>
              <strong>
                {syncStatus.last_sync_threads_discovered ?? 0} / {syncStatus.last_sync_comments_imported ?? 0} /{" "}
                {syncStatus.last_sync_replies_imported ?? 0}
              </strong>
            </div>
            {syncStatus.last_sync_error ? (
              <div className="syncDetailRow">
                <span>Błąd</span>
                <strong className="syncStatusTag failed">{syncStatus.last_sync_error}</strong>
              </div>
            ) : null}
            <div className="syncDetailRow">
              <span>Harmonogram automatyczny</span>
              <strong className={`syncStatusTag ${syncStatus.automatic_sync_enabled ? "success" : ""}`}>
                {syncStatus.automatic_sync_enabled ? "Aktywny (razem z synchronizacją filmów)" : "Wyłączony"}
              </strong>
            </div>
          </div>
        ) : null}
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">SKRZYNKA</p>
            <h2>Komentarze</h2>
          </div>
        </div>

        <div className="filterBar">
          <div className="filterBarRow">
            <input className="searchInput" placeholder="Szukaj po treści lub autorze…" value={search} onChange={(event) => setSearch(event.target.value)} />
            <input
              className="viewsRangeInput"
              placeholder="Filtruj po autorze…"
              value={authorFilter}
              onChange={(event) => setAuthorFilter(event.target.value)}
            />
            <select value={videoFilter} onChange={(event) => setVideoFilter(event.target.value)}>
              <option value="">Wszystkie filmy</option>
              {videoOptions.map((video) => (
                <option key={video.youtube_video_id} value={video.youtube_video_id}>
                  {video.title}
                </option>
              ))}
            </select>
            <select value={sort} onChange={(event) => setSort(event.target.value as CommentSort)}>
              {SORT_OPTIONS.map((option) => (
                <option key={option.key} value={option.key}>
                  Sortuj: {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="filterBarRow">
            <div className="quickFilterGroup">
              {QUICK_FILTERS.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className={`quickFilterButton${quick === option.key ? " active" : ""}`}
                  onClick={() => setQuick(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          <QuickReplyManager templates={quickReplies} onChange={setQuickReplies} />
        </div>

        {loading ? (
          <div className="emptyState">
            <h3>Wczytuję…</h3>
          </div>
        ) : !inbox || inbox.threads.length === 0 ? (
          <div className="emptyState">
            <h3>Brak komentarzy</h3>
            <p>Żaden komentarz nie pasuje do wybranych filtrów, albo synchronizacja komentarzy nie została jeszcze uruchomiona.</p>
          </div>
        ) : (
          <div className="commentList">
            {inbox.threads.map((row) => (
              <CommentThreadCard key={row.platform_thread_id} row={row} quickReplies={quickReplies} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
