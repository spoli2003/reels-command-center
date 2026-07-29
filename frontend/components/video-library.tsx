"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { DashboardFilterBar } from "./dashboard-filter-bar";
import { PerformanceLabelBadge } from "./performance-label-badge";
import { VideoTable } from "./video-table";
import type { YoutubeChannelVideo } from "../lib/youtube-api";
import {
  DATE_RANGE_OPTIONS,
  applyQuickFilter,
  filterByDateRange,
  filterBySearch,
  filterByViewsRange,
  isDateRangeKey,
  isQuickFilter,
  isSortDirection,
  isSortKey,
  nextSortState,
  sortVideos,
  truncateTitle,
  withDerivedMetrics,
  type DateRangeKey,
  type QuickFilter,
  type SortDirection,
  type SortKey,
  type TableSort,
} from "../lib/youtube-metrics";

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function VideoLibrary({ initialVideos }: { initialVideos: YoutubeChannelVideo[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const dateRange: DateRangeKey = isDateRangeKey(searchParams.get("range")) ? (searchParams.get("range") as DateRangeKey) : "all";
  const search = searchParams.get("q") ?? "";
  const sortKey: SortKey = isSortKey(searchParams.get("sort")) ? (searchParams.get("sort") as SortKey) : "published_at";
  const sortDirection: SortDirection = isSortDirection(searchParams.get("dir")) ? (searchParams.get("dir") as SortDirection) : "desc";
  const sort: TableSort = { key: sortKey, direction: sortDirection };
  const minViews = searchParams.get("minViews") ? Number(searchParams.get("minViews")) : null;
  const maxViews = searchParams.get("maxViews") ? Number(searchParams.get("maxViews")) : null;
  const quickFilter: QuickFilter = isQuickFilter(searchParams.get("quick")) ? (searchParams.get("quick") as QuickFilter) : "all";

  function updateUrl(next: {
    range?: DateRangeKey;
    q?: string;
    sort?: SortKey;
    dir?: SortDirection;
    minViews?: number | null;
    maxViews?: number | null;
    quick?: QuickFilter;
  }) {
    const params = new URLSearchParams(searchParams.toString());
    if (next.range !== undefined) params.set("range", next.range);
    if (next.q !== undefined) {
      if (next.q) params.set("q", next.q);
      else params.delete("q");
    }
    if (next.sort !== undefined) params.set("sort", next.sort);
    if (next.dir !== undefined) params.set("dir", next.dir);
    if (next.minViews !== undefined) {
      if (next.minViews === null) params.delete("minViews");
      else params.set("minViews", String(next.minViews));
    }
    if (next.maxViews !== undefined) {
      if (next.maxViews === null) params.delete("maxViews");
      else params.set("maxViews", String(next.maxViews));
    }
    if (next.quick !== undefined) params.set("quick", next.quick);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  const derived = useMemo(() => initialVideos.map((video) => withDerivedMetrics(video)), [initialVideos]);
  const dateFiltered = useMemo(() => filterByDateRange(derived, dateRange), [derived, dateRange]);
  const searchFiltered = useMemo(() => filterBySearch(dateFiltered, search), [dateFiltered, search]);
  const filtered = useMemo(() => filterByViewsRange(searchFiltered, minViews, maxViews), [searchFiltered, minViews, maxViews]);
  const scoreById = useMemo(() => new Map(filtered.map((v) => [v.youtube_video_id, v.performance_score])), [filtered]);
  const quickFiltered = useMemo(() => applyQuickFilter(filtered, scoreById, quickFilter), [filtered, scoreById, quickFilter]);
  const sorted = useMemo(() => sortVideos(quickFiltered, sort), [quickFiltered, sort]);

  const activeLabel = DATE_RANGE_OPTIONS.find((option) => option.key === dateRange)?.label ?? "Cały okres";
  const totalViews = filtered.reduce((sum, video) => sum + video.views, 0);
  const totalInteractions = filtered.reduce((sum, video) => sum + video.likes + video.comments, 0);

  return (
    <>
      <section className="statsGrid">
        <article className="metricCard">
          <span>Filmy</span>
          <strong>{initialVideos.length}</strong>
          <small>w bibliotece (YouTube)</small>
        </article>
        <article className="metricCard">
          <span>Wyświetlenia</span>
          <strong>{compact(totalViews)}</strong>
          <small>w wybranym zakresie</small>
        </article>
        <article className="metricCard">
          <span>Interakcje</span>
          <strong>{compact(totalInteractions)}</strong>
          <small>polubienia + komentarze</small>
        </article>
        <article className="metricCard">
          <span>Platformy</span>
          <strong>1</strong>
          <small>YouTube — więcej wkrótce</small>
        </article>
      </section>

      <div className="alert informational">
        Ta biblioteka obejmuje obecnie filmy z <strong>YouTube</strong>. Wsparcie dla Facebook, Instagram i TikTok pojawi się po integracji
        Unified Content.
      </div>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">CONTENT LIBRARY</p>
            <h2>Wszystkie filmy</h2>
            <p className="muted">Jedna rolka, wszystkie publikacje i wspólny wynik.</p>
          </div>
        </div>

        <DashboardFilterBar
          dateRange={dateRange}
          onDateRangeChange={(value) => updateUrl({ range: value })}
          search={search}
          onSearchChange={(value) => updateUrl({ q: value })}
          sortKey={sortKey}
          sortDirection={sortDirection}
          onSortChange={(key, direction) => updateUrl({ sort: key, dir: direction })}
          minViews={minViews}
          onMinViewsChange={(value) => updateUrl({ minViews: value })}
          maxViews={maxViews}
          onMaxViewsChange={(value) => updateUrl({ maxViews: value })}
          quickFilter={quickFilter}
          onQuickFilterChange={(value) => updateUrl({ quick: value })}
          resultCount={sorted.length}
          activeLabel={activeLabel}
        />

        <VideoTable
          rows={sorted}
          keyField={(video) => video.youtube_video_id}
          emptyMessage="Brak filmów pasujących do wybranych filtrów."
          sort={sort}
          onSortChange={(key) => {
            const next = nextSortState(sort, key);
            updateUrl({ sort: next?.key ?? "published_at", dir: next?.direction ?? "desc" });
          }}
          columns={[
            {
              label: "Film",
              sortKey: "title",
              render: (video) => (
                <Link
                  href={`/youtube/videos/${video.youtube_video_id}?from=${encodeURIComponent(`${pathname}?${searchParams.toString()}`)}`}
                  title={video.title}
                  className="tableFilmCell"
                >
                  {video.thumbnail_url ? (
                    <img className="tableFilmThumb" src={video.thumbnail_url} alt="" />
                  ) : (
                    <div className="tableFilmThumb placeholder" />
                  )}
                  <span>{truncateTitle(video.title, 46)}</span>
                </Link>
              ),
            },
            { label: "Etykieta", render: (video) => <PerformanceLabelBadge label={video.performance_label} /> },
            { label: "Data publikacji", sortKey: "published_at", render: (video) => new Date(video.published_at).toLocaleDateString("pl-PL") },
            { label: "Wyświetlenia", align: "right", sortKey: "views", render: (video) => compact(video.views) },
            { label: "Wyśw./dzień", align: "right", sortKey: "views_per_day", render: (video) => video.views_per_day.toLocaleString("pl-PL") },
            { label: "ER", align: "right", sortKey: "engagement", render: (video) => `${video.engagement_rate.toFixed(2)}%` },
            { label: "Wynik", align: "right", sortKey: "score", render: (video) => Math.round(video.performance_score) },
          ]}
        />
      </section>
    </>
  );
}
