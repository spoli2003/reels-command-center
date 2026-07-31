"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { PlatformBadge } from "./platform-badge";
import { VideoTable } from "./video-table";
import {
  PLATFORM_LABELS,
  type PlatformKey,
  type PlatformKeyOrAll,
  type PlatformSummary,
  type PlatformVideo,
} from "../lib/platform-api";
import {
  filterPlatformByDateRange,
  isPlatformSortDirection,
  isPlatformSortKey,
  nextPlatformSortState,
  PLATFORM_SORT_OPTIONS,
  sortPlatformVideos,
  withDerivedMetrics,
  type DerivedPlatformVideo,
  type PlatformSortDirection,
  type PlatformSortKey,
  type PlatformTableSort,
} from "../lib/platform-metrics";
import { DATE_RANGE_OPTIONS, filterBySearch, isDateRangeKey, truncateTitle, type DateRangeKey } from "../lib/youtube-metrics";

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function isPlatformFilter(value: string | null): value is PlatformKeyOrAll {
  return value === "all" || value === "youtube" || value === "facebook" || value === "instagram";
}

function detailPath(video: PlatformVideo, returnPath: string) {
  const base = video.platform === "youtube"
    ? `/youtube/videos/${video.external_id}`
    : `/platforms/${video.platform}/videos/${video.external_id}`;
  return `${base}?from=${encodeURIComponent(returnPath)}`;
}

export function UnifiedVideoLibrary({ initialVideos, platforms }: { initialVideos: PlatformVideo[]; platforms: PlatformSummary[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const dateRange: DateRangeKey = isDateRangeKey(searchParams.get("range")) ? (searchParams.get("range") as DateRangeKey) : "all";
  const platform: PlatformKeyOrAll = isPlatformFilter(searchParams.get("platform")) ? (searchParams.get("platform") as PlatformKeyOrAll) : "all";
  const search = searchParams.get("q") ?? "";
  const sortKey: PlatformSortKey = isPlatformSortKey(searchParams.get("sort")) ? (searchParams.get("sort") as PlatformSortKey) : "published_at";
  const sortDirection: PlatformSortDirection = isPlatformSortDirection(searchParams.get("dir"))
    ? (searchParams.get("dir") as PlatformSortDirection)
    : "desc";
  const sort: PlatformTableSort = useMemo(() => ({ key: sortKey, direction: sortDirection }), [sortKey, sortDirection]);
  const viewsAvailability = useMemo(
    () => new Map<PlatformKey, boolean>(platforms.map((item) => [item.platform, item.views_available])),
    [platforms],
  );

  function updateUrl(next: { range?: DateRangeKey; platform?: PlatformKeyOrAll; q?: string; sort?: PlatformSortKey; dir?: PlatformSortDirection }) {
    const params = new URLSearchParams(searchParams.toString());
    if (next.range !== undefined) params.set("range", next.range);
    if (next.platform !== undefined) params.set("platform", next.platform);
    if (next.q !== undefined) {
      if (next.q) params.set("q", next.q);
      else params.delete("q");
    }
    if (next.sort !== undefined) params.set("sort", next.sort);
    if (next.dir !== undefined) params.set("dir", next.dir);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  const derived = useMemo(() => initialVideos.map((video) => withDerivedMetrics(video)), [initialVideos]);
  const platformFiltered = useMemo(
    () => (platform === "all" ? derived : derived.filter((video) => video.platform === platform)),
    [derived, platform],
  );
  const dateFiltered = useMemo(() => filterPlatformByDateRange(platformFiltered, dateRange), [platformFiltered, dateRange]);
  const filtered = useMemo(() => filterBySearch(dateFiltered, search), [dateFiltered, search]);
  const sorted = useMemo(() => sortPlatformVideos(filtered, sort), [filtered, sort]);

  const totalViews = filtered.reduce(
    (sum, video) => sum + (viewsAvailability.get(video.platform) === false ? 0 : video.views),
    0,
  );
  const totalInteractions = filtered.reduce((sum, video) => sum + video.likes + video.comments + video.shares + video.saves, 0);
  const platformCount = new Set(filtered.map((video) => video.platform)).size;
  const unavailableViews = filtered.some((video) => viewsAvailability.get(video.platform) === false);
  const returnPath = `${pathname}?${searchParams.toString()}`;

  function viewsAvailable(video: PlatformVideo) {
    return viewsAvailability.get(video.platform) !== false;
  }

  return (
    <>
      <section className="statsGrid">
        <article className="metricCard"><span>Materiały</span><strong>{filtered.length}</strong><small>{initialVideos.length} w całej bibliotece</small></article>
        <article className="metricCard"><span>Wyświetlenia</span><strong>{compact(totalViews)}</strong><small>{unavailableViews ? "Instagram bez Insights pominięty" : "suma wybranych platform"}</small></article>
        <article className="metricCard"><span>Interakcje</span><strong>{compact(totalInteractions)}</strong><small>polubienia + komentarze + udostępnienia</small></article>
        <article className="metricCard"><span>Platformy</span><strong>{platformCount}</strong><small>YouTube · Facebook · Instagram</small></article>
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">CONTENT LIBRARY</p>
            <h2>Wszystkie materiały</h2>
            <p className="muted">YouTube, Facebook i Instagram w jednej, wspólnej bibliotece.</p>
          </div>
        </div>

        <div className="filterBar">
          <div className="filterBarRow">
            <select value={platform} onChange={(event) => updateUrl({ platform: event.target.value as PlatformKeyOrAll })} aria-label="Platforma">
              {(Object.keys(PLATFORM_LABELS) as PlatformKeyOrAll[]).map((key) => <option key={key} value={key}>{PLATFORM_LABELS[key]}</option>)}
            </select>
            <select value={dateRange} onChange={(event) => updateUrl({ range: event.target.value as DateRangeKey })} aria-label="Zakres dat">
              {DATE_RANGE_OPTIONS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
            </select>
            <input className="searchInput" placeholder="Szukaj materiału po tytule…" value={search} onChange={(event) => updateUrl({ q: event.target.value })} aria-label="Szukaj po tytule" />
            <select value={sortKey} onChange={(event) => updateUrl({ sort: event.target.value as PlatformSortKey })} aria-label="Sortowanie">
              {PLATFORM_SORT_OPTIONS.map((option) => <option key={option.key} value={option.key}>Sortuj: {option.label}</option>)}
            </select>
            <select value={sortDirection} onChange={(event) => updateUrl({ dir: event.target.value as PlatformSortDirection })} aria-label="Kierunek sortowania">
              <option value="desc">Malejąco</option><option value="asc">Rosnąco</option>
            </select>
          </div>
          <p className="filterBarActive">{sorted.length} {sorted.length === 1 ? "materiał" : "materiałów"} · {PLATFORM_LABELS[platform]}</p>
        </div>

        <VideoTable<DerivedPlatformVideo, PlatformSortKey>
          rows={sorted}
          keyField={(video) => `${video.platform}:${video.external_id}`}
          emptyMessage="Brak materiałów pasujących do wybranych filtrów."
          sort={sort}
          onSortChange={(key) => {
            const next = nextPlatformSortState(sort, key);
            updateUrl({ sort: next?.key ?? "published_at", dir: next?.direction ?? "desc" });
          }}
          columns={[
            {
              label: "Materiał",
              sortKey: "title",
              render: (video) => (
                <Link href={detailPath(video, returnPath)} title={video.title} className="tableFilmCell">
                  {video.thumbnail_url ? <img className="tableFilmThumb" src={video.thumbnail_url} alt="" /> : <div className="tableFilmThumb placeholder" />}
                  <span>{truncateTitle(video.title, 52)}</span>
                </Link>
              ),
            },
            { label: "Platforma", render: (video) => <PlatformBadge platform={video.platform} /> },
            { label: "Data publikacji", sortKey: "published_at", render: (video) => video.published_at ? new Date(video.published_at).toLocaleDateString("pl-PL") : "—" },
            { label: "Wyświetlenia", align: "right", sortKey: "views", render: (video) => viewsAvailable(video) ? compact(video.views) : <span className="metricUnavailable">Brak danych</span> },
            { label: "Wyśw./dzień", align: "right", sortKey: "views_per_day", render: (video) => viewsAvailable(video) ? video.views_per_day.toLocaleString("pl-PL") : "—" },
            { label: "Polubienia", align: "right", sortKey: "likes", render: (video) => compact(video.likes) },
            { label: "Komentarze", align: "right", sortKey: "comments", render: (video) => compact(video.comments) },
            { label: "ER", align: "right", sortKey: "engagement", render: (video) => viewsAvailable(video) ? `${video.engagement_rate.toFixed(2)}%` : "—" },
          ]}
        />
      </section>
    </>
  );
}
