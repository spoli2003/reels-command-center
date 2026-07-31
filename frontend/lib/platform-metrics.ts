// Generic per-video derived metrics for Facebook/Instagram (and bridged
// YouTube) videos — Release 0.8.0. Deliberately smaller than youtube-metrics.ts:
// composite score, sorting, and range/search filtering are reused/mirrored, but
// the deep YouTube-only features (attention lists, title-pattern suggestions,
// channel baseline, keyword-related videos) stay exclusive to the /youtube/*
// deep-dive pages — the generic /platforms/* surfaces get their equivalent
// (winning/attention/topics/publishing) from the Creator Intelligence report
// instead, which is honest reuse rather than fabricating YouTube-shaped
// metadata the backend doesn't compute for these platforms.

import { median, filterByDateRange, type DateRangeKey } from "./youtube-metrics";
import { computeExplainableScores, type ScoreBreakdown } from "./content-score";
import type { PlatformVideo } from "./platform-api";

export type DerivedPlatformVideo = PlatformVideo & { views_per_day: number };

export function withDerivedMetrics(video: PlatformVideo, now: number = Date.now()): DerivedPlatformVideo {
  const publishedAtMs = video.published_at ? new Date(video.published_at).getTime() : now;
  const daysSincePublished = Math.max(1, (now - publishedAtMs) / 86_400_000);
  return { ...video, views_per_day: Math.round(video.views / daysSincePublished) };
}

/** Facebook/Instagram videos can genuinely lack a known publish date (unlike
 * YouTube, which always has one) — filterByDateRange requires a non-null date,
 * so undated videos are honestly excluded from any specific range rather than
 * defaulting them to "now" and silently misplacing them. */
export function filterPlatformByDateRange<T extends { published_at: string | null }>(
  videos: T[],
  range: DateRangeKey,
  now: number = Date.now(),
): T[] {
  if (range === "all") return videos;
  const dated = videos.filter((video): video is T & { published_at: string } => video.published_at !== null);
  return filterByDateRange(dated, range, now);
}

export type PlatformSortKey = "published_at" | "views" | "views_per_day" | "engagement" | "likes" | "comments" | "title" | "score";

export const PLATFORM_SORT_OPTIONS: { key: PlatformSortKey; label: string }[] = [
  { key: "published_at", label: "Data publikacji" },
  { key: "views", label: "Wyświetlenia" },
  { key: "views_per_day", label: "Wyśw./dzień" },
  { key: "engagement", label: "Engagement" },
  { key: "likes", label: "Polubienia" },
  { key: "comments", label: "Komentarze" },
  { key: "title", label: "Tytuł" },
];

export function isPlatformSortKey(value: string | null): value is PlatformSortKey {
  return !!value && PLATFORM_SORT_OPTIONS.some((option) => option.key === value) ;
}

export type PlatformSortDirection = "asc" | "desc";
export type PlatformTableSort = { key: PlatformSortKey; direction: PlatformSortDirection } | null;

export function isPlatformSortDirection(value: string | null): value is PlatformSortDirection {
  return value === "asc" || value === "desc";
}

/** Same 3-state header-click cycle as nextSortState in youtube-metrics.ts (desc -> asc -> unsorted). */
export function nextPlatformSortState(current: PlatformTableSort, key: PlatformSortKey): PlatformTableSort {
  if (!current || current.key !== key) return { key, direction: "desc" };
  if (current.direction === "desc") return { key, direction: "asc" };
  return null;
}

function sortValue(video: DerivedPlatformVideo & { performance_score?: number }, key: PlatformSortKey): number | string {
  switch (key) {
    case "views":
      return video.views;
    case "views_per_day":
      return video.views_per_day;
    case "engagement":
      return video.engagement_rate;
    case "likes":
      return video.likes;
    case "comments":
      return video.comments;
    case "title":
      return video.title.toLowerCase();
    case "score":
      return video.performance_score ?? 0;
    case "published_at":
    default:
      return video.published_at ? new Date(video.published_at).getTime() : 0;
  }
}

export function sortPlatformVideos<T extends DerivedPlatformVideo & { performance_score?: number }>(videos: T[], sort: PlatformTableSort): T[] {
  if (!sort) return [...videos].sort((a, b) => +new Date(b.published_at ?? 0) - +new Date(a.published_at ?? 0));
  const factor = sort.direction === "asc" ? 1 : -1;
  return [...videos].sort((a, b) => {
    const av = sortValue(a, sort.key);
    const bv = sortValue(b, sort.key);
    if (typeof av === "string" || typeof bv === "string") return factor * String(av).localeCompare(String(bv));
    return factor * (av - bv);
  });
}

// --- Composite performance score — identical 50/30/20 formula as youtube-metrics.ts ---

export const MIN_VIDEOS_FOR_SCORE = 3;

export type PlatformScoredVideo = DerivedPlatformVideo & { performance_score: number; score_breakdown: ScoreBreakdown };

export function computePlatformCompositeScores(videos: DerivedPlatformVideo[]): PlatformScoredVideo[] {
  return computeExplainableScores(videos);
}

export { median };
