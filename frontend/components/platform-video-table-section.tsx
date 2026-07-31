"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { VideoTable } from "./video-table";
import type { PlatformVideo } from "../lib/platform-api";
import {
  isPlatformSortDirection,
  isPlatformSortKey,
  filterPlatformByDateRange,
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

function publishedDate(value: string) {
  return new Intl.DateTimeFormat("pl-PL", { timeZone: "Europe/Warsaw" }).format(new Date(value));
}

/** Filterable/sortable video table shared by the generic Dashboard and Videos
 * pages (Part 5) — URL-backed filters, same 3-state header-click sort cycle
 * VideoTable already supports for YouTube (component itself is unmodified). */
export function PlatformVideoTableSection({ videos }: { videos: PlatformVideo[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const dateRange: DateRangeKey = isDateRangeKey(searchParams.get("range")) ? (searchParams.get("range") as DateRangeKey) : "all";
  const search = searchParams.get("q") ?? "";
  const sortKey: PlatformSortKey = isPlatformSortKey(searchParams.get("sort")) ? (searchParams.get("sort") as PlatformSortKey) : "published_at";
  const sortDirection: PlatformSortDirection = isPlatformSortDirection(searchParams.get("dir"))
    ? (searchParams.get("dir") as PlatformSortDirection)
    : "desc";
  const sort: PlatformTableSort = useMemo(() => ({ key: sortKey, direction: sortDirection }), [sortKey, sortDirection]);

  function updateUrl(next: { range?: DateRangeKey; q?: string; sort?: PlatformSortKey; dir?: PlatformSortDirection }) {
    const params = new URLSearchParams(searchParams.toString());
    if (next.range !== undefined) params.set("range", next.range);
    if (next.q !== undefined) {
      if (next.q) params.set("q", next.q);
      else params.delete("q");
    }
    if (next.sort !== undefined) params.set("sort", next.sort);
    if (next.dir !== undefined) params.set("dir", next.dir);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  const derived = useMemo(() => videos.map((video) => withDerivedMetrics(video)), [videos]);
  const dateFiltered = useMemo(() => filterPlatformByDateRange(derived, dateRange), [derived, dateRange]);
  const filtered = useMemo(() => filterBySearch(dateFiltered, search), [dateFiltered, search]);
  const sorted = useMemo(() => sortPlatformVideos(filtered, sort), [filtered, sort]);

  const activeLabel = DATE_RANGE_OPTIONS.find((option) => option.key === dateRange)?.label ?? "Cały okres";

  return (
    <>
      <div className="filterBar">
        <div className="filterBarRow">
          <select value={dateRange} onChange={(event) => updateUrl({ range: event.target.value as DateRangeKey })} aria-label="Zakres dat">
            {DATE_RANGE_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            className="searchInput"
            placeholder="Szukaj po tytule…"
            value={search}
            onChange={(event) => updateUrl({ q: event.target.value })}
            aria-label="Szukaj po tytule"
          />
          <select value={sortKey} onChange={(event) => updateUrl({ sort: event.target.value as PlatformSortKey })} aria-label="Sortowanie">
            {PLATFORM_SORT_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>
                Sortuj: {option.label}
              </option>
            ))}
          </select>
          <select value={sortDirection} onChange={(event) => updateUrl({ dir: event.target.value as PlatformSortDirection })} aria-label="Kierunek sortowania">
            <option value="desc">Malejąco</option>
            <option value="asc">Rosnąco</option>
          </select>
        </div>
        <p className="filterBarActive">
          Aktywny zakres: <strong>{activeLabel}</strong> · {sorted.length} {sorted.length === 1 ? "pozycja" : "pozycji"}
        </p>
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
              <Link href={`/platforms/${video.platform}/videos/${video.external_id}`} title={video.title} className="tableFilmCell">
                {video.thumbnail_url ? <img className="tableFilmThumb" src={video.thumbnail_url} alt="" /> : <div className="tableFilmThumb placeholder" />}
                <span>{truncateTitle(video.title, 46)}</span>
              </Link>
            ),
          },
          { label: "Platforma", render: (video) => <span className="micro">{video.platform}</span> },
          {
            label: "Data publikacji",
            sortKey: "published_at",
            render: (video) => (video.published_at ? publishedDate(video.published_at) : "—"),
          },
          { label: "Wyświetlenia", align: "right", sortKey: "views", render: (video) => compact(video.views) },
          { label: "Wyśw./dzień", align: "right", sortKey: "views_per_day", render: (video) => video.views_per_day.toLocaleString("pl-PL") },
          { label: "ER", align: "right", sortKey: "engagement", render: (video) => `${video.engagement_rate.toFixed(2)}%` },
        ]}
      />
    </>
  );
}
