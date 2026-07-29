"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { MetricComparisonList } from "./compare/metric-comparison-list";
import { VideoCompareCard } from "./compare/video-compare-card";
import { PerformanceLabelBadge } from "./performance-label-badge";
import { VideoPicker } from "./video-picker";
import { VideoTable } from "./video-table";
import { downloadCsv } from "../lib/csv-export";
import type { YoutubeChannelVideo } from "../lib/youtube-api";
import {
  MIN_VIDEOS_FOR_SCORE,
  computeCompositeScores,
  median,
  nextSortState,
  sortVideos,
  truncateTitle,
  withDerivedMetrics,
  type ScoredVideo,
  type TableSort,
} from "../lib/youtube-metrics";

function winnerBy(items: ScoredVideo[], selector: (item: ScoredVideo) => number): ScoredVideo | null {
  if (items.length === 0) return null;
  return [...items].sort((a, b) => selector(b) - selector(a))[0];
}

function WinnerLabel({ winner }: { winner: ScoredVideo | null }) {
  if (!winner) return <strong>—</strong>;
  return (
    <Link href={`/youtube/videos/${winner.youtube_video_id}`} title={winner.title}>
      <strong>{truncateTitle(winner.title, 30)}</strong>
    </Link>
  );
}

type CompareView = "cards" | "table";

export function YoutubeCompare({ videos }: { videos: YoutubeChannelVideo[] }) {
  const [selected, setSelected] = useState<string[]>(() => videos.slice(0, 3).map((video) => video.youtube_video_id));
  const [view, setView] = useState<CompareView>("cards");
  const [tableSort, setTableSort] = useState<TableSort>(null);

  function toggle(youtubeVideoId: string) {
    setSelected((current) =>
      current.includes(youtubeVideoId) ? current.filter((id) => id !== youtubeVideoId) : [...current, youtubeVideoId],
    );
  }

  const allDerived = useMemo(() => videos.map((video) => withDerivedMetrics(video)), [videos]);
  const selectedVideos = useMemo(() => videos.filter((video) => selected.includes(video.youtube_video_id)), [videos, selected]);
  const derived = useMemo(() => selectedVideos.map((video) => withDerivedMetrics(video)), [selectedVideos]);
  const hasEnoughForScore = derived.length >= MIN_VIDEOS_FOR_SCORE;
  const scored = useMemo(() => (hasEnoughForScore ? computeCompositeScores(derived) : []), [derived, hasEnoughForScore]);
  const cards = hasEnoughForScore ? scored : derived.map((video) => ({ ...video, performance_score: 0, score_breakdown: { views: 0, views_per_day: 0, engagement: 0 } }));

  const overallWinner = winnerBy(scored, (v) => v.performance_score);
  const viewsWinner = winnerBy(cards, (v) => v.views);
  const vpdWinner = winnerBy(cards, (v) => v.views_per_day);
  const erWinner = winnerBy(cards, (v) => v.engagement_rate);
  const commentsWinner = winnerBy(cards, (v) => v.comments);

  // Whole-channel baselines (Sprint 5 / Part 5) — median/average/best-ever, not
  // limited to the compared set, so "how good is this vs. the channel" is answerable.
  const channelBaselines = useMemo(
    () => ({
      views: {
        median: median(allDerived.map((v) => v.views)) ?? 0,
        average: allDerived.length ? allDerived.reduce((sum, v) => sum + v.views, 0) / allDerived.length : 0,
        best: allDerived.length ? Math.max(...allDerived.map((v) => v.views)) : 0,
      },
      views_per_day: {
        median: median(allDerived.map((v) => v.views_per_day)) ?? 0,
        average: allDerived.length ? allDerived.reduce((sum, v) => sum + v.views_per_day, 0) / allDerived.length : 0,
        best: allDerived.length ? Math.max(...allDerived.map((v) => v.views_per_day)) : 0,
      },
      engagement_rate: {
        median: median(allDerived.map((v) => v.engagement_rate)) ?? 0,
        average: allDerived.length ? allDerived.reduce((sum, v) => sum + v.engagement_rate, 0) / allDerived.length : 0,
        best: allDerived.length ? Math.max(...allDerived.map((v) => v.engagement_rate)) : 0,
      },
      likes: {
        median: median(allDerived.map((v) => v.likes)) ?? 0,
        average: allDerived.length ? allDerived.reduce((sum, v) => sum + v.likes, 0) / allDerived.length : 0,
        best: allDerived.length ? Math.max(...allDerived.map((v) => v.likes)) : 0,
      },
      comments: {
        median: median(allDerived.map((v) => v.comments)) ?? 0,
        average: allDerived.length ? allDerived.reduce((sum, v) => sum + v.comments, 0) / allDerived.length : 0,
        best: allDerived.length ? Math.max(...allDerived.map((v) => v.comments)) : 0,
      },
    }),
    [allDerived],
  );

  const tableRows = useMemo(() => sortVideos(cards, tableSort), [cards, tableSort]);

  function exportCsv() {
    downloadCsv(
      "porownanie-filmow.csv",
      ["Tytuł", "Data publikacji", "Wyświetlenia", "Wyśw./dzień", "Polubienia", "Komentarze", "Engagement %", "Wynik złożony", "Etykieta"],
      cards.map((v) => [
        v.title,
        new Date(v.published_at).toLocaleDateString("pl-PL"),
        v.views,
        v.views_per_day,
        v.likes,
        v.comments,
        v.engagement_rate.toFixed(2),
        Math.round(v.performance_score),
        v.performance_label,
      ]),
    );
  }

  return (
    <>
      <div className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">WYBÓR</p>
            <h2>Wybierz filmy do porównania</h2>
          </div>
        </div>
        <VideoPicker videos={videos} selected={selected} onToggle={toggle} max={6} />
      </div>

      {derived.length === 0 ? (
        <div className="emptyState">
          <h3>Wybierz filmy</h3>
          <p>Zaznacz co najmniej jeden film z listy powyżej, aby zobaczyć porównanie.</p>
        </div>
      ) : (
        <>
          <section className="compareSummary">
            <div className="summaryBadge">
              <span>Zwycięzca ogólny</span>
              {overallWinner ? (
                <WinnerLabel winner={overallWinner} />
              ) : (
                <small className="muted">Wybierz min. {MIN_VIDEOS_FOR_SCORE} filmy, aby obliczyć wynik złożony</small>
              )}
            </div>
            <div className="summaryBadge">
              <span>Wyświetlenia</span>
              <WinnerLabel winner={viewsWinner} />
            </div>
            <div className="summaryBadge">
              <span>Wyświetlenia/dzień</span>
              <WinnerLabel winner={vpdWinner} />
            </div>
            <div className="summaryBadge">
              <span>Engagement</span>
              <WinnerLabel winner={erWinner} />
            </div>
            <div className="summaryBadge">
              <span>Najwięcej komentarzy</span>
              <WinnerLabel winner={commentsWinner} />
            </div>
          </section>
          <p className="muted">
            Zwycięzcy obliczani tylko w obrębie {derived.length} porównywanych filmów, nie całego kanału. Wynik złożony (50% wyśw./dzień
            + 30% engagement + 20% wyświetlenia) wymaga minimum {MIN_VIDEOS_FOR_SCORE} wybranych filmów.
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
                <VideoCompareCard key={video.youtube_video_id} video={video} showScore={hasEnoughForScore} />
              ))}
            </section>
          ) : (
            <VideoTable
              rows={tableRows}
              keyField={(video) => video.youtube_video_id}
              sort={tableSort}
              onSortChange={(key) => setTableSort(nextSortState(tableSort, key))}
              columns={[
                { label: "Film", sortKey: "title", render: (video) => <Link href={`/youtube/videos/${video.youtube_video_id}`}>{truncateTitle(video.title, 40)}</Link> },
                { label: "Etykieta", render: (video) => <PerformanceLabelBadge label={video.performance_label} /> },
                { label: "Data publikacji", sortKey: "published_at", render: (video) => new Date(video.published_at).toLocaleDateString("pl-PL") },
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
            <MetricComparisonList
              title="Wyświetlenia"
              explanation="Publiczny licznik wyświetleń z ostatniej synchronizacji YouTube."
              items={cards.map((v) => ({ youtube_video_id: v.youtube_video_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.views }))}
              formatValue={(value) => value.toLocaleString("pl-PL")}
              channelMedian={channelBaselines.views.median}
              channelAverage={channelBaselines.views.average}
              channelBest={channelBaselines.views.best}
            />
            <MetricComparisonList
              title="Wyświetlenia / dzień"
              explanation="Wyświetlenia ÷ dni od publikacji."
              items={cards.map((v) => ({ youtube_video_id: v.youtube_video_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.views_per_day }))}
              formatValue={(value) => value.toLocaleString("pl-PL")}
              channelMedian={channelBaselines.views_per_day.median}
              channelAverage={channelBaselines.views_per_day.average}
              channelBest={channelBaselines.views_per_day.best}
            />
            <MetricComparisonList
              title="Engagement rate"
              explanation="(Polubienia + komentarze) ÷ wyświetlenia × 100."
              items={cards.map((v) => ({ youtube_video_id: v.youtube_video_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.engagement_rate }))}
              formatValue={(value) => `${value.toFixed(2)}%`}
              channelMedian={channelBaselines.engagement_rate.median}
              channelAverage={channelBaselines.engagement_rate.average}
              channelBest={channelBaselines.engagement_rate.best}
            />
            <MetricComparisonList
              title="Polubienia"
              explanation="Publiczny licznik polubień z ostatniej synchronizacji YouTube."
              items={cards.map((v) => ({ youtube_video_id: v.youtube_video_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.likes }))}
              formatValue={(value) => value.toLocaleString("pl-PL")}
              channelMedian={channelBaselines.likes.median}
              channelAverage={channelBaselines.likes.average}
              channelBest={channelBaselines.likes.best}
            />
            <MetricComparisonList
              title="Komentarze"
              explanation="Publiczny licznik komentarzy z ostatniej synchronizacji YouTube."
              items={cards.map((v) => ({ youtube_video_id: v.youtube_video_id, title: v.title, thumbnail_url: v.thumbnail_url, value: v.comments }))}
              formatValue={(value) => value.toLocaleString("pl-PL")}
              channelMedian={channelBaselines.comments.median}
              channelAverage={channelBaselines.comments.average}
              channelBest={channelBaselines.comments.best}
            />
          </section>
        </>
      )}
    </>
  );
}
