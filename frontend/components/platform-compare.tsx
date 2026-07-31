"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { PlatformMetricComparisonList } from "./compare/platform-metric-comparison-list";
import { PlatformVideoCompareCard } from "./compare/platform-video-compare-card";
import { PlatformVideoPicker } from "./platform-video-picker";
import { VideoTable } from "./video-table";
import { downloadCsv } from "../lib/csv-export";
import type { PlatformKey, PlatformVideo } from "../lib/platform-api";
import {
  computePlatformCompositeScores,
  MIN_VIDEOS_FOR_SCORE,
  nextPlatformSortState,
  sortPlatformVideos,
  withDerivedMetrics,
  type PlatformScoredVideo,
  type PlatformSortKey,
  type PlatformTableSort,
} from "../lib/platform-metrics";
import { truncateTitle } from "../lib/youtube-metrics";
import { emptyScoreBreakdown } from "../lib/content-score";

function winnerBy(items: PlatformScoredVideo[], selector: (item: PlatformScoredVideo) => number): PlatformScoredVideo | null {
  if (items.length === 0) return null;
  return [...items].sort((a, b) => selector(b) - selector(a))[0];
}

function WinnerLabel({ platform, winner }: { platform: PlatformKey; winner: PlatformScoredVideo | null }) {
  if (!winner) return <strong>—</strong>;
  return (
    <Link href={`/platforms/${platform}/videos/${winner.external_id}`} title={winner.title}>
      <strong>{truncateTitle(winner.title, 30)}</strong>
    </Link>
  );
}

type CompareView = "cards" | "table";

/** Mirrors components/youtube-compare.tsx (same layout/classes/CSV export) for
 * Facebook/Instagram — no duration/like-ratio fields since Meta's data doesn't
 * carry those the way YouTube does; the comparison set is honest about that. */
export function PlatformCompare({ platform, videos }: { platform: PlatformKey; videos: PlatformVideo[] }) {
  const [selected, setSelected] = useState<string[]>(() => videos.slice(0, 3).map((video) => video.external_id));
  const [view, setView] = useState<CompareView>("cards");
  const [tableSort, setTableSort] = useState<PlatformTableSort>(null);

  function toggle(externalId: string) {
    setSelected((current) => (current.includes(externalId) ? current.filter((id) => id !== externalId) : [...current, externalId]));
  }

  const selectedVideos = useMemo(() => videos.filter((video) => selected.includes(video.external_id)), [videos, selected]);
  const derived = useMemo(() => selectedVideos.map((video) => withDerivedMetrics(video)), [selectedVideos]);
  const hasEnoughForScore = derived.length >= MIN_VIDEOS_FOR_SCORE;
  const scored = useMemo(() => (hasEnoughForScore ? computePlatformCompositeScores(derived) : []), [derived, hasEnoughForScore]);
  const cards: PlatformScoredVideo[] = hasEnoughForScore
    ? scored
    : derived.map((video) => ({ ...video, performance_score: 0, score_breakdown: emptyScoreBreakdown() }));

  const overallWinner = winnerBy(scored, (v) => v.performance_score);
  const viewsWinner = winnerBy(cards, (v) => v.views);
  const vpdWinner = winnerBy(cards, (v) => v.views_per_day);
  const erWinner = winnerBy(cards, (v) => v.engagement_rate);
  const commentsWinner = winnerBy(cards, (v) => v.comments);

  const tableRows = useMemo(() => sortPlatformVideos(cards, tableSort), [cards, tableSort]);

  function exportCsv() {
    downloadCsv(
      "porownanie-materialow.csv",
      ["Tytuł", "Data publikacji", "Wyświetlenia", "Wyśw./dzień", "Polubienia", "Komentarze", "Engagement %", "Wynik złożony"],
      cards.map((v) => [
        v.title,
        v.published_at ? new Date(v.published_at).toLocaleDateString("pl-PL") : "",
        v.views,
        v.views_per_day,
        v.likes,
        v.comments,
        v.engagement_rate.toFixed(2),
        Math.round(v.performance_score),
      ]),
    );
  }

  return (
    <>
      <div className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">WYBÓR</p>
            <h2>Wybierz materiały do porównania</h2>
          </div>
        </div>
        <PlatformVideoPicker platform={platform} videos={videos} selected={selected} onToggle={toggle} max={6} />
      </div>

      {derived.length === 0 ? (
        <div className="emptyState">
          <h3>Wybierz materiały</h3>
          <p>Zaznacz co najmniej jedną pozycję z listy powyżej, aby zobaczyć porównanie.</p>
        </div>
      ) : (
        <>
          <section className="compareSummary">
            <div className="summaryBadge">
              <span>Zwycięzca ogólny</span>
              {overallWinner ? (
                <WinnerLabel platform={platform} winner={overallWinner} />
              ) : (
                <small className="muted">Wybierz min. {MIN_VIDEOS_FOR_SCORE} pozycje, aby obliczyć wynik złożony</small>
              )}
            </div>
            <div className="summaryBadge">
              <span>Wyświetlenia</span>
              <WinnerLabel platform={platform} winner={viewsWinner} />
            </div>
            <div className="summaryBadge">
              <span>Wyświetlenia/dzień</span>
              <WinnerLabel platform={platform} winner={vpdWinner} />
            </div>
            <div className="summaryBadge">
              <span>Engagement</span>
              <WinnerLabel platform={platform} winner={erWinner} />
            </div>
            <div className="summaryBadge">
              <span>Najwięcej komentarzy</span>
              <WinnerLabel platform={platform} winner={commentsWinner} />
            </div>
          </section>
          <p className="muted">
            Zwycięzcy obliczani tylko w obrębie {derived.length} porównywanych pozycji. Wynik złożony (50% wyśw./dzień + 30% engagement +
            20% wyświetlenia) wymaga minimum {MIN_VIDEOS_FOR_SCORE} wybranych pozycji.
          </p>

          <div className="compareViewToggle">
            <button type="button" className={`quickFilterButton${view === "cards" ? " active" : ""}`} onClick={() => setView("cards")}>
              Karty
            </button>
            <button type="button" className={`quickFilterButton${view === "table" ? " active" : ""}`} onClick={() => setView("table")}>
              Tabela
            </button>
          </div>

          <div className="compareExportRow">
            <button type="button" className="button secondary" onClick={exportCsv}>
              Eksportuj CSV
            </button>
          </div>

          {view === "cards" ? (
            <section className="compareCardsGrid">
              {cards.map((video) => (
                <PlatformVideoCompareCard key={video.external_id} video={video} showScore={hasEnoughForScore} />
              ))}
            </section>
          ) : (
            <VideoTable<PlatformScoredVideo, PlatformSortKey>
              rows={tableRows}
              keyField={(video) => video.external_id}
              sort={tableSort}
              onSortChange={(key) => setTableSort(nextPlatformSortState(tableSort, key))}
              columns={[
                {
                  label: "Materiał",
                  sortKey: "title",
                  render: (video) => <Link href={`/platforms/${platform}/videos/${video.external_id}`}>{truncateTitle(video.title, 40)}</Link>,
                },
                {
                  label: "Data publikacji",
                  sortKey: "published_at",
                  render: (video) => (video.published_at ? new Date(video.published_at).toLocaleDateString("pl-PL") : "—"),
                },
                { label: "Wyświetlenia", align: "right", sortKey: "views", render: (video) => video.views.toLocaleString("pl-PL") },
                { label: "Wyśw./dzień", align: "right", sortKey: "views_per_day", render: (video) => video.views_per_day.toLocaleString("pl-PL") },
                { label: "Polubienia", align: "right", sortKey: "likes", render: (video) => video.likes.toLocaleString("pl-PL") },
                { label: "Komentarze", align: "right", sortKey: "comments", render: (video) => video.comments.toLocaleString("pl-PL") },
                { label: "ER", align: "right", sortKey: "engagement", render: (video) => `${video.engagement_rate.toFixed(2)}%` },
                { label: "Wynik", align: "right", sortKey: "score", render: (video) => (hasEnoughForScore ? Math.round(video.performance_score) : "—") },
              ]}
            />
          )}

          <section className="metricComparisonsGrid">
            <PlatformMetricComparisonList
              platform={platform}
              title="Wyświetlenia"
              explanation="Licznik wyświetleń z ostatniej synchronizacji."
              items={cards.map((v) => ({ external_id: v.external_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.views }))}
              formatValue={(value) => value.toLocaleString("pl-PL")}
            />
            <PlatformMetricComparisonList
              platform={platform}
              title="Wyświetlenia / dzień"
              explanation="Wyświetlenia ÷ dni od publikacji."
              items={cards.map((v) => ({ external_id: v.external_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.views_per_day }))}
              formatValue={(value) => value.toLocaleString("pl-PL")}
            />
            <PlatformMetricComparisonList
              platform={platform}
              title="Engagement rate"
              explanation="(Polubienia + komentarze) ÷ wyświetlenia × 100."
              items={cards.map((v) => ({ external_id: v.external_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.engagement_rate }))}
              formatValue={(value) => `${value.toFixed(2)}%`}
            />
            <PlatformMetricComparisonList
              platform={platform}
              title="Polubienia"
              explanation="Licznik polubień z ostatniej synchronizacji."
              items={cards.map((v) => ({ external_id: v.external_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.likes }))}
              formatValue={(value) => value.toLocaleString("pl-PL")}
            />
            <PlatformMetricComparisonList
              platform={platform}
              title="Komentarze"
              explanation="Licznik komentarzy z ostatniej synchronizacji."
              items={cards.map((v) => ({ external_id: v.external_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.comments }))}
              formatValue={(value) => value.toLocaleString("pl-PL")}
            />
          </section>
        </>
      )}
    </>
  );
}
