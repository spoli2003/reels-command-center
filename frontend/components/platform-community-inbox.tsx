"use client";

import { useEffect, useMemo, useState } from "react";

import { PlatformCommentThreadCard } from "./platform-comment-thread-card";
import { PlatformQuickReplyManager } from "./platform-quick-reply-manager";
import type {
  CommentQuickFilter,
  CommentSort,
  PlatformCommentInbox,
  PlatformKey,
  PlatformVideo,
  QuickReplyTemplate,
} from "../lib/platform-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const QUICK_FILTERS: { key: CommentQuickFilter; label: string }[] = [
  { key: "all", label: "Wątki odbiorców" },
  { key: "mine", label: "Moje komentarze" },
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

/** Mirrors components/community-inbox.tsx exactly (same layout/classes/quick
 * filters), driving the generic /api/platforms/{platform}/comments endpoints
 * so Facebook and Instagram share the identical Community Engine UX (Part 6). */
export function PlatformCommunityInbox({
  platform,
  videos,
  initialQuickReplies,
}: {
  platform: PlatformKey;
  videos: PlatformVideo[];
  initialQuickReplies: QuickReplyTemplate[];
}) {
  const [inbox, setInbox] = useState<PlatformCommentInbox | null>(null);
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
      const response = await fetch(`${API_URL}/api/platforms/${platform}/comments?${params.toString()}`, { cache: "no-store" });
      if (response.ok) setInbox(await response.json());
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

  async function synchronize() {
    setSyncing(true);
    setError("");
    setSyncFeedback("");
    try {
      const response = await fetch(`${API_URL}/api/platforms/${platform}/comments/sync`, { method: "POST" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? "Synchronizacja komentarzy nie powiodła się.");
      }
      const result = await response.json();
      setSyncFeedback(`Wątki: ${result.threads_discovered}, nowe komentarze: ${result.comments_imported}, nowe odpowiedzi: ${result.replies_imported}.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Synchronizacja komentarzy nie powiodła się.");
    } finally {
      setSyncing(false);
    }
  }

  const videoOptions = useMemo(
    () => [...videos].sort((a, b) => +new Date(b.published_at ?? 0) - +new Date(a.published_at ?? 0)),
    [videos],
  );

  return (
    <>
      <section className="statsGrid">
        <article className="metricCard featured">
          <span>Wymagają uwagi</span>
          <strong>{inbox?.summary.awaiting_reply_count ?? 0}</strong>
          <small>nowe + czekające na odpowiedź</small>
        </article>
        <article className="metricCard">
          <span>🟡 Czekają</span>
          <strong>{inbox?.summary.waiting_count ?? 0}</strong>
          <small>odbiorca odpowiedział ponownie</small>
        </article>
        <article className="metricCard">
          <span>🔵 Nowe</span>
          <strong>{inbox?.summary.new_count ?? 0}</strong>
          <small>brak odpowiedzi z Twojej strony</small>
        </article>
        <article className="metricCard">
          <span>🟢 Rozwiązane</span>
          <strong>{inbox?.summary.resolved_count ?? 0}</strong>
          <small>ostatnie słowo należy do Ciebie</small>
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
            <button className="button" onClick={synchronize} disabled={syncing}>
              {syncing ? "Synchronizuję…" : "Synchronizuj komentarze"}
            </button>
          </div>
        </div>
        {error && <div className="alert">{error}</div>}
        {syncFeedback && !error ? <div className="syncFeedback">✓ {syncFeedback}</div> : null}
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
              <option value="">Wszystkie materiały</option>
              {videoOptions.map((video) => (
                <option key={video.external_id} value={video.external_id}>
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
                  {option.key === "mine" && inbox ? ` (${inbox.summary.own_threads_count})` : ""}
                </button>
              ))}
            </div>
          </div>
          <p className="filterBarActive">
            {quick === "mine"
              ? "Komentarze opublikowane przez Twoje konto jako początek wątku, w tym komentarze przypięte."
              : "Wątki rozpoczęte przez odbiorców. Twoje odpowiedzi pozostają widoczne we właściwych rozmowach."}
          </p>
          <PlatformQuickReplyManager platform={platform} templates={quickReplies} onChange={setQuickReplies} />
        </div>

        {loading ? (
          <div className="emptyState">
            <h3>Wczytuję…</h3>
          </div>
        ) : !inbox || inbox.threads.length === 0 ? (
          <div className="emptyState">
            <h3>{quick === "mine" ? "Brak własnych komentarzy" : "Brak wątków odbiorców"}</h3>
            <p>
              {quick === "mine"
                ? "Nie znaleziono komentarzy opublikowanych przez Twoje konto jako początek wątku."
                : "Żaden wątek odbiorcy nie pasuje do wybranych filtrów albo synchronizacja komentarzy nie została jeszcze uruchomiona."}
            </p>
          </div>
        ) : (
          <div className="commentList">
            {inbox.threads.map((row) => (
              <PlatformCommentThreadCard key={row.platform_thread_id} platform={platform} row={row} quickReplies={quickReplies} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
