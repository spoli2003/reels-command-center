import type { YoutubeChannelVideo } from "./youtube-api";

export type DerivedVideo = YoutubeChannelVideo & {
  days_since_published: number;
  views_per_day: number;
  like_ratio: number;
  comment_ratio: number;
  engagement_rate: number;
};

const DAY_MS = 86_400_000;

export function withDerivedMetrics(video: YoutubeChannelVideo, now: number = Date.now()): DerivedVideo {
  const rawDays = Math.floor((now - new Date(video.published_at).getTime()) / DAY_MS);
  const daysSincePublished = Math.max(0, rawDays);
  const divisor = Math.max(1, daysSincePublished);
  return {
    ...video,
    days_since_published: daysSincePublished,
    views_per_day: Math.round(video.views / divisor),
    like_ratio: video.views ? (video.likes / video.views) * 100 : 0,
    comment_ratio: video.views ? (video.comments / video.views) * 100 : 0,
    engagement_rate: video.views ? ((video.likes + video.comments) / video.views) * 100 : 0,
  };
}

export function truncateTitle(title: string, maxLength = 42): string {
  return title.length > maxLength ? `${title.slice(0, maxLength - 1)}…` : title;
}

// ---------------------------------------------------------------------------
// Filtering & sorting
// ---------------------------------------------------------------------------

export type DateRangeKey = "all" | "7d" | "30d" | "90d" | "365d";

export const DATE_RANGE_OPTIONS: { key: DateRangeKey; label: string }[] = [
  { key: "all", label: "Cały okres" },
  { key: "7d", label: "Ostatnie 7 dni" },
  { key: "30d", label: "Ostatnie 30 dni" },
  { key: "90d", label: "Ostatnie 90 dni" },
  { key: "365d", label: "Ostatnie 365 dni" },
];

const RANGE_DAYS: Record<DateRangeKey, number | null> = { all: null, "7d": 7, "30d": 30, "90d": 90, "365d": 365 };

export function isDateRangeKey(value: string | null): value is DateRangeKey {
  return !!value && DATE_RANGE_OPTIONS.some((option) => option.key === value);
}

export function filterByDateRange<T extends { published_at: string }>(videos: T[], range: DateRangeKey, now: number = Date.now()): T[] {
  const days = RANGE_DAYS[range];
  if (days === null) return videos;
  const cutoff = now - days * DAY_MS;
  return videos.filter((video) => new Date(video.published_at).getTime() >= cutoff);
}

export function filterBySearch<T extends { title: string }>(videos: T[], query: string): T[] {
  const normalized = query.trim().toLocaleLowerCase("pl");
  if (!normalized) return videos;
  return videos.filter((video) => video.title.toLocaleLowerCase("pl").includes(normalized));
}

export type SortKey =
  | "views"
  | "views_per_day"
  | "engagement"
  | "likes"
  | "comments"
  | "published_at"
  | "score"
  | "age"
  | "duration"
  | "title";

export const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "published_at", label: "Data publikacji" },
  { key: "views", label: "Wyświetlenia" },
  { key: "views_per_day", label: "Wyświetlenia/dzień" },
  { key: "likes", label: "Polubienia" },
  { key: "comments", label: "Komentarze" },
  { key: "engagement", label: "Engagement" },
  { key: "score", label: "Wynik względny" },
  { key: "age", label: "Wiek filmu" },
  { key: "duration", label: "Długość" },
  { key: "title", label: "Tytuł" },
];

export function isSortKey(value: string | null): value is SortKey {
  return !!value && SORT_OPTIONS.some((option) => option.key === value);
}

/** A video row that MAY have a composite score merged in (only true when the
 * caller has run computeCompositeScores over the same set — see "score" sort key). */
export type SortableVideo = DerivedVideo & { performance_score?: number };

export type SortDirection = "asc" | "desc";

/** null = default order (newest-first by published_at) — the pre-Sprint-5 behavior. */
export type TableSort = { key: SortKey; direction: SortDirection } | null;

/** 3-state header-click cycle: unsorted -> desc -> asc -> unsorted (default). */
export function nextSortState(current: TableSort, key: SortKey): TableSort {
  if (!current || current.key !== key) return { key, direction: "desc" };
  if (current.direction === "desc") return { key, direction: "asc" };
  return null;
}

function sortValue(video: SortableVideo, key: SortKey): number | string {
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
    case "published_at":
      return +new Date(video.published_at);
    case "score":
      return video.performance_score ?? 0;
    case "age":
      return video.days_since_published;
    case "duration":
      return video.duration_seconds ?? 0;
    case "title":
      return video.title.toLocaleLowerCase("pl");
    default:
      return 0;
  }
}

export function sortVideos<T extends SortableVideo>(videos: T[], sort: TableSort): T[] {
  const copy = [...videos];
  if (!sort) {
    copy.sort((a, b) => +new Date(b.published_at) - +new Date(a.published_at));
    return copy;
  }
  const { key, direction } = sort;
  const factor = direction === "asc" ? 1 : -1;
  copy.sort((a, b) => {
    const av = sortValue(a, key);
    const bv = sortValue(b, key);
    if (typeof av === "string" || typeof bv === "string") {
      return factor * String(av).localeCompare(String(bv), "pl");
    }
    return factor * (av - bv);
  });
  return copy;
}

export function isSortDirection(value: string | null): value is SortDirection {
  return value === "asc" || value === "desc";
}

// ---------------------------------------------------------------------------
// Views-range + quick filters — Sprint 5 / Part 2
// ---------------------------------------------------------------------------

export function filterByViewsRange<T extends { views: number }>(videos: T[], min: number | null, max: number | null): T[] {
  return videos.filter((video) => (min === null || video.views >= min) && (max === null || video.views <= max));
}

export type QuickFilter = "all" | "best" | "worst" | "recent" | "trending";

export const QUICK_FILTER_OPTIONS: { key: QuickFilter; label: string }[] = [
  { key: "all", label: "Wszystkie" },
  { key: "best", label: "Najlepsze" },
  { key: "worst", label: "Najsłabsze" },
  { key: "recent", label: "Ostatnie" },
  { key: "trending", label: "Na fali wzrostu" },
];

export function isQuickFilter(value: string | null): value is QuickFilter {
  return !!value && QUICK_FILTER_OPTIONS.some((option) => option.key === value);
}

const BEST_PERCENTILE = 0.7;
const WORST_PERCENTILE = 0.3;

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.floor(p * (sorted.length - 1))));
  return sorted[index];
}

/**
 * "best"/"worst" adapt to the current filtered set's own score distribution
 * (70th/30th percentile) rather than a fixed threshold. "trending" needs a
 * `trend` field per video — only present once the backend's structured
 * metadata (Sprint 5/6 Part 8/12) has been merged into the row.
 */
export function applyQuickFilter<T extends SortableVideo & { trend?: string }>(
  videos: T[],
  scoredById: Map<string, number>,
  quick: QuickFilter,
): T[] {
  if (quick === "all") return videos;
  if (quick === "recent") return videos.filter((v) => v.days_since_published <= RECENT_COHORT_DAYS);
  if (quick === "trending") return videos.filter((v) => v.trend === "accelerating" || v.trend === "growing" || v.trend === "steady");

  const scores = videos.map((v) => scoredById.get(v.youtube_video_id) ?? 0);
  if (quick === "best") {
    const threshold = percentile(scores, BEST_PERCENTILE);
    return videos.filter((v) => (scoredById.get(v.youtube_video_id) ?? 0) >= threshold);
  }
  const threshold = percentile(scores, WORST_PERCENTILE);
  return videos.filter((v) => (scoredById.get(v.youtube_video_id) ?? 0) <= threshold);
}

// ---------------------------------------------------------------------------
// Median & normalization
// ---------------------------------------------------------------------------

export function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** Returns 100 for every value when the set has no variance (safe — doesn't distort relative order on other metrics). */
export function minMaxNormalize(value: number, min: number, max: number): number {
  if (max === min) return 100;
  return ((value - min) / (max - min)) * 100;
}

// ---------------------------------------------------------------------------
// Composite performance score — relative to whatever set it's computed over
// ---------------------------------------------------------------------------

export const MIN_VIDEOS_FOR_SCORE = 3;

export type ScoreBreakdown = { views: number; views_per_day: number; engagement: number };
export type ScoredVideo = DerivedVideo & { performance_score: number; score_breakdown: ScoreBreakdown };

export function computeCompositeScores(videos: DerivedVideo[]): ScoredVideo[] {
  if (videos.length === 0) return [];
  const viewsValues = videos.map((v) => v.views);
  const vpdValues = videos.map((v) => v.views_per_day);
  const erValues = videos.map((v) => v.engagement_rate);
  const viewsRange: [number, number] = [Math.min(...viewsValues), Math.max(...viewsValues)];
  const vpdRange: [number, number] = [Math.min(...vpdValues), Math.max(...vpdValues)];
  const erRange: [number, number] = [Math.min(...erValues), Math.max(...erValues)];

  return videos.map((video) => {
    const viewsScore = minMaxNormalize(video.views, viewsRange[0], viewsRange[1]);
    const vpdScore = minMaxNormalize(video.views_per_day, vpdRange[0], vpdRange[1]);
    const erScore = minMaxNormalize(video.engagement_rate, erRange[0], erRange[1]);
    const performance_score = vpdScore * 0.5 + erScore * 0.3 + viewsScore * 0.2;
    return { ...video, performance_score, score_breakdown: { views: viewsScore, views_per_day: vpdScore, engagement: erScore } };
  });
}

// ---------------------------------------------------------------------------
// Performance label badge — mirrors backend PERFORMANCE_LABELS (content_metrics.py)
// so the same label key always renders the same emoji/text/tone everywhere.
// ---------------------------------------------------------------------------

export type PerformanceLabelKey = "viral" | "accelerating" | "growing" | "strong" | "average" | "weak" | "dead";

export const PERFORMANCE_LABELS: Record<PerformanceLabelKey, { emoji: string; text: string; tone: string }> = {
  viral: { emoji: "🔥", text: "Viral", tone: "great" },
  accelerating: { emoji: "⚡", text: "Przyspiesza", tone: "great" },
  growing: { emoji: "📈", text: "Rośnie", tone: "good" },
  strong: { emoji: "✅", text: "Silny", tone: "good" },
  average: { emoji: "➖", text: "Przeciętny", tone: "average" },
  weak: { emoji: "⚠", text: "Słaby", tone: "weak" },
  dead: { emoji: "💀", text: "Wygasł", tone: "weak" },
};

export function isPerformanceLabelKey(value: string | undefined | null): value is PerformanceLabelKey {
  return !!value && value in PERFORMANCE_LABELS;
}

export function performanceStatus(score: number): { label: string; tone: "great" | "good" | "average" | "weak" } {
  if (score >= 70) return { label: "Świetny wynik", tone: "great" };
  if (score >= 45) return { label: "Dobry wynik", tone: "good" };
  if (score >= 25) return { label: "Przeciętny wynik", tone: "average" };
  return { label: "Słaby wynik", tone: "weak" };
}

/** One-sentence deterministic explanation of why a video scored the way it did, referencing the actual component that drove it. */
export function explainRanking(video: ScoredVideo, channelMedians: { vpd: number; er: number }): string {
  const { views, views_per_day: vpd, engagement } = video.score_breakdown;
  const vpdAboveMedian = channelMedians.vpd > 0 && video.views_per_day >= channelMedians.vpd;
  const erAboveMedian = channelMedians.er > 0 && video.engagement_rate >= channelMedians.er;

  if (vpd >= 60 && engagement >= 60) {
    return `Wysokie wyświetlenia/dzień (${video.views_per_day.toLocaleString("pl-PL")}) i engagement (${video.engagement_rate.toFixed(2)}%) — oba powyżej mediany zakresu.`;
  }
  if (vpd >= 60 && engagement < 40) {
    return `Bardzo dobre tempo wyświetleń/dzień (${video.views_per_day.toLocaleString("pl-PL")}) napędza wynik, mimo przeciętnego engagementu.`;
  }
  if (engagement >= 60 && vpd < 40) {
    return `To wysoki engagement (${video.engagement_rate.toFixed(2)}%) napędza wynik, przy przeciętnym tempie wyświetleń/dzień.`;
  }
  if (views >= 60 && vpd < 40 && engagement < 40) {
    return `Wysoka łączna liczba wyświetleń (${video.views.toLocaleString("pl-PL")}), choć bieżące tempo dzienne i engagement są przeciętne.`;
  }
  if (vpdAboveMedian && erAboveMedian) {
    return `Wyświetlenia/dzień i engagement powyżej mediany wybranego zakresu.`;
  }
  return `Zrównoważony wynik — żaden pojedynczy wskaźnik nie odstaje wyraźnie od reszty zakresu.`;
}

// ---------------------------------------------------------------------------
// Attention list — recent, comparable videos underperforming the channel median
// ---------------------------------------------------------------------------

export const TOO_NEW_DAYS = 3;
export const ATTENTION_DEFAULT_WINDOW_DAYS = 60;
export const MIN_COMPARABLE_FOR_ATTENTION = 3;
export const ATTENTION_LIST_LIMIT = 5;

export type AttentionVideo = DerivedVideo & { reasons: string[] };

/**
 * Only evaluates videos published within `windowDays` (capped at 60 by default,
 * or the active date-range filter if that's shorter) so long-tail evergreen
 * videos are never flagged just for having low current daily views.
 */
export function buildAttentionList(
  filtered: DerivedVideo[],
  windowDays: number,
): { flagged: AttentionVideo[]; tooNewCount: number; insufficientData: boolean; windowDays: number } {
  const inWindow = filtered.filter((v) => v.days_since_published <= windowDays);
  const comparable = inWindow.filter((v) => v.days_since_published >= TOO_NEW_DAYS);
  const tooNewCount = inWindow.length - comparable.length;

  if (comparable.length < MIN_COMPARABLE_FOR_ATTENTION) {
    return { flagged: [], tooNewCount, insufficientData: true, windowDays };
  }

  const medianVpd = median(comparable.map((v) => v.views_per_day)) ?? 0;
  const medianEr = median(comparable.map((v) => v.engagement_rate)) ?? 0;

  const flagged: AttentionVideo[] = [];
  for (const video of comparable) {
    const reasons: string[] = [];
    if (medianVpd > 0 && video.views_per_day <= medianVpd * 0.7) {
      const pct = Math.round((1 - video.views_per_day / medianVpd) * 100);
      reasons.push(
        `Wyświetlenia/dzień są o ${pct}% niższe od mediany kanału (${video.views_per_day.toLocaleString("pl-PL")} vs ${Math.round(medianVpd).toLocaleString("pl-PL")}).`,
      );
    }
    if (medianEr > 0 && video.engagement_rate <= medianEr * 0.5 && video.views_per_day > medianVpd * 0.7) {
      reasons.push(
        `Film ma przyzwoite wyświetlenia, ale niski poziom reakcji (ER ${video.engagement_rate.toFixed(2)}% vs mediana ${medianEr.toFixed(2)}%).`,
      );
    }
    if (reasons.length) flagged.push({ ...video, reasons });
  }
  flagged.sort((a, b) => a.views_per_day - b.views_per_day);
  return { flagged: flagged.slice(0, ATTENTION_LIST_LIMIT), tooNewCount, insufficientData: false, windowDays };
}

// ---------------------------------------------------------------------------
// Polish tokenization — lightweight, no external NLP/AI dependency
// ---------------------------------------------------------------------------

const STOPWORDS = new Set([
  "i","w","we","na","do","z","ze","że","żeby","jak","co","się","nie","to","ten","ta","te","tym","tego","tej","tych",
  "o","po","za","przez","dla","czy","jest","są","był","była","było","będzie","będą","aby","ale","lub","oraz","albo",
  "może","można","gdy","gdzie","kiedy","dlaczego","jaki","jaka","jakie","jakich","który","która","które","którzy",
  "których","bez","pod","nad","przed","między","od","u","tak","tylko","już","jeszcze","też","bardzo","właśnie",
  "czym","kim","jego","jej","ich","mój","moja","moje","twój","twoja","twoje","swój","swoja","swoje","nasz","wasz",
  "sobie","siebie","mnie","cię","ci","mi","go","ją","je","nam","wam","im","tu","tam","tutaj","teraz","zawsze",
  "nigdy","wszystko","wszyscy","każdy","każda","każde","inny","inna","inne","jeden","jedna","jedno","dwa","trzy",
  "coś","ktoś","nic","kto","której","którym","którego","niż","więc","czyli","ponieważ","zatem","a","czyż","aż",
  // Generic function/verb words that otherwise pollute keyword matching (found via real clustering output).
  "przy","mieć","mogą","wiele","tysiące","złotych","liczy","warto","trzeba","będziesz","masz",
]);

/** Strips a small set of common Polish inflectional endings to loosely group grammatical variants of the same word. */
const MULTI_CHAR_SUFFIXES = ["ami", "ach", "owi", "ów", "emu", "ego", "ymi", "imi", "iem", "om"];
const SINGLE_CHAR_SUFFIXES = ["a", "e", "i", "y", "u", "o", "ą", "ę"];
const MIN_STEM_LENGTH = 4;

export function stemWord(word: string): string {
  for (const suffix of MULTI_CHAR_SUFFIXES) {
    if (word.length - suffix.length >= MIN_STEM_LENGTH && word.endsWith(suffix)) {
      return word.slice(0, -suffix.length);
    }
  }
  for (const suffix of SINGLE_CHAR_SUFFIXES) {
    if (word.length - 1 >= MIN_STEM_LENGTH && word.endsWith(suffix)) {
      return word.slice(0, -1);
    }
  }
  return word;
}

export function tokenizeTitle(title: string): string[] {
  return title
    .toLocaleLowerCase("pl")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter((word) => word.length >= 4 && !STOPWORDS.has(word) && !/^\d+$/.test(word));
}

// ---------------------------------------------------------------------------
// Suggestions — deterministic, auditable, never framed as causal
// ---------------------------------------------------------------------------

export type Suggestion =
  | { id: "best-performer"; kind: "best-performer"; text: string; videoId: string; videoTitle: string; viewsPerDay: number }
  | { id: "weekday"; kind: "weekday"; text: string; weekday: string; weekdayMedianVpd: number; channelMedianVpd: number; sampleCount: number }
  | {
      id: "keyword";
      kind: "keyword";
      text: string;
      keyword: string;
      matchCount: number;
      keywordMedianVpd: number;
      channelMedianVpd: number;
      percentDiff: number;
      sampleVideos: { id: string; title: string }[];
    }
  | { id: string; unavailable: true; reason: string };

export function buildBestPerformerSuggestion(videos: DerivedVideo[]): Suggestion {
  if (videos.length === 0) {
    return { id: "best-performer", unavailable: true, reason: "Brak filmów w wybranym zakresie." };
  }
  const best = [...videos].sort((a, b) => b.views_per_day - a.views_per_day)[0];
  return {
    id: "best-performer",
    kind: "best-performer",
    text: `Film „${best.title}” ma obecnie najwyższy wynik wyświetleń/dzień w wybranym zakresie. Rozważ nagranie kontynuacji na podobny temat.`,
    videoId: best.youtube_video_id,
    videoTitle: best.title,
    viewsPerDay: best.views_per_day,
  };
}

const WEEKDAY_LABELS = ["niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"];
const MIN_VIDEOS_PER_WEEKDAY = 2;

export function buildWeekdaySuggestion(videos: DerivedVideo[]): Suggestion {
  const buckets = new Map<number, number[]>();
  videos.forEach((v) => {
    const day = new Date(v.published_at).getDay();
    if (!buckets.has(day)) buckets.set(day, []);
    buckets.get(day)!.push(v.views_per_day);
  });
  const eligible = Array.from(buckets.entries())
    .filter(([, vals]) => vals.length >= MIN_VIDEOS_PER_WEEKDAY)
    .map(([day, vals]) => ({ day, med: median(vals) ?? 0, count: vals.length }));

  if (eligible.length === 0) {
    return { id: "weekday", unavailable: true, reason: `Za mało filmów na jeden dzień tygodnia (min. ${MIN_VIDEOS_PER_WEEKDAY}), aby wykryć wzorzec.` };
  }
  eligible.sort((a, b) => b.med - a.med);
  const top = eligible[0];
  const overallMedian = Math.round(median(videos.map((v) => v.views_per_day)) ?? 0);
  return {
    id: "weekday",
    kind: "weekday",
    text: `Filmy publikowane w ${WEEKDAY_LABELS[top.day]} osiągają obecnie najwyższą medianę wyświetleń/dzień w wybranym zakresie.`,
    weekday: WEEKDAY_LABELS[top.day],
    weekdayMedianVpd: Math.round(top.med),
    channelMedianVpd: overallMedian,
    sampleCount: top.count,
  };
}

const MIN_KEYWORD_MATCHES = 2;
const KEYWORD_MEDIAN_UPLIFT = 1.15;

export function buildKeywordSuggestion(videos: DerivedVideo[]): Suggestion {
  const overallMedian = median(videos.map((v) => v.views_per_day)) ?? 0;
  if (overallMedian <= 0 || videos.length < MIN_KEYWORD_MATCHES) {
    return { id: "keyword", unavailable: true, reason: "Za mało filmów w wybranym zakresie, aby szukać powtarzających się tematów." };
  }

  const groups = new Map<string, { forms: Map<string, number>; videos: Map<string, DerivedVideo> }>();
  videos.forEach((video) => {
    const words = new Set(tokenizeTitle(video.title));
    words.forEach((word) => {
      const key = stemWord(word);
      if (!groups.has(key)) groups.set(key, { forms: new Map(), videos: new Map() });
      const group = groups.get(key)!;
      group.forms.set(word, (group.forms.get(word) ?? 0) + 1);
      group.videos.set(video.youtube_video_id, video);
    });
  });

  const candidates = Array.from(groups.values())
    .map((group) => {
      const matchingVideos = Array.from(group.videos.values());
      const displayWord = [...group.forms.entries()].sort((a, b) => b[1] - a[1])[0][0];
      const medianVpd = median(matchingVideos.map((v) => v.views_per_day)) ?? 0;
      return { displayWord, matchingVideos, medianVpd, count: matchingVideos.length };
    })
    .filter((candidate) => candidate.count >= MIN_KEYWORD_MATCHES && candidate.medianVpd > overallMedian * KEYWORD_MEDIAN_UPLIFT)
    .sort((a, b) => b.medianVpd - a.medianVpd);

  if (candidates.length === 0) {
    return { id: "keyword", unavailable: true, reason: "Za mało powtarzających się tematów w tytułach, aby wygenerować wiarygodną sugestię." };
  }
  const top = candidates[0];
  const percentDiff = Math.round((top.medianVpd / overallMedian - 1) * 100);
  return {
    id: "keyword",
    kind: "keyword",
    text: `Filmy zawierające słowo „${top.displayWord}” osiągały dotychczas wyższą medianę wyświetleń/dzień.`,
    keyword: top.displayWord,
    matchCount: top.count,
    keywordMedianVpd: Math.round(top.medianVpd),
    channelMedianVpd: Math.round(overallMedian),
    percentDiff,
    sampleVideos: top.matchingVideos.slice(0, 3).map((v) => ({ id: v.youtube_video_id, title: v.title })),
  };
}

// ---------------------------------------------------------------------------
// Single-video channel baseline ("Na tle kanału") — Sprint 1.2
// ---------------------------------------------------------------------------

export function dayWord(count: number): string {
  return count === 1 ? "dzień" : "dni";
}

export type BaselineMetric = {
  key: "views" | "views_per_day" | "engagement_rate" | "likes" | "comments";
  label: string;
  videoValue: number;
  channelMedian: number | null;
  percentDiff: number | null;
  interpretation: string;
};

export type ChannelBaseline =
  | { status: "too_new"; message: string }
  | { status: "insufficient_comparable"; message: string }
  | { status: "ok"; comparableCount: number; metrics: BaselineMetric[] };

const BASELINE_METRIC_DEFS: { key: BaselineMetric["key"]; label: string }[] = [
  { key: "views", label: "Wyświetlenia" },
  { key: "views_per_day", label: "Wyświetlenia/dzień" },
  { key: "engagement_rate", label: "Engagement" },
  { key: "likes", label: "Polubienia" },
  { key: "comments", label: "Komentarze" },
];

/**
 * Compares one video against the median of "comparable" channel videos —
 * other videos at least TOO_NEW_DAYS old. If the target itself is too new,
 * or too few comparable videos exist, returns an honest limited-data status
 * instead of a misleading comparison.
 */
export function buildChannelBaseline(target: DerivedVideo, allVideos: DerivedVideo[]): ChannelBaseline {
  if (target.days_since_published < TOO_NEW_DAYS) {
    return {
      status: "too_new",
      message: `Film jest zbyt nowy (${target.days_since_published} ${dayWord(target.days_since_published)} od publikacji), aby wiarygodnie porównać go z resztą kanału.`,
    };
  }

  const comparable = allVideos.filter(
    (video) => video.youtube_video_id !== target.youtube_video_id && video.days_since_published >= TOO_NEW_DAYS,
  );
  if (comparable.length < MIN_COMPARABLE_FOR_ATTENTION) {
    return {
      status: "insufficient_comparable",
      message: `Za mało porównywalnych filmów w kanale (min. ${MIN_COMPARABLE_FOR_ATTENTION} starszych niż ${TOO_NEW_DAYS} dni), aby wiarygodnie porównać.`,
    };
  }

  const metrics: BaselineMetric[] = BASELINE_METRIC_DEFS.map(({ key, label }) => {
    const channelMedian = median(comparable.map((video) => video[key]));
    const videoValue = target[key];
    const percentDiff = channelMedian && channelMedian > 0 ? Math.round((videoValue / channelMedian - 1) * 100) : null;
    let interpretation: string;
    if (percentDiff === null) interpretation = "Brak wystarczających danych do porównania.";
    else if (Math.abs(percentDiff) < 10) interpretation = "Zbliżony do mediany kanału.";
    else if (percentDiff > 0) interpretation = `${percentDiff}% powyżej mediany kanału.`;
    else interpretation = `${Math.abs(percentDiff)}% poniżej mediany kanału.`;
    return { key, label, videoValue, channelMedian, percentDiff, interpretation };
  });

  return { status: "ok", comparableCount: comparable.length, metrics };
}

// ---------------------------------------------------------------------------
// Related videos by shared title keywords — Sprint 1.2
// ---------------------------------------------------------------------------

export type RelatedVideo = DerivedVideo & { sharedKeywords: string[] };

export function findRelatedVideosByKeywords(target: DerivedVideo, allVideos: DerivedVideo[], limit = 5): RelatedVideo[] {
  const targetTokens = tokenizeTitle(target.title);
  const targetStemToWord = new Map<string, string>();
  targetTokens.forEach((word) => targetStemToWord.set(stemWord(word), word));
  if (targetStemToWord.size === 0) return [];

  const candidates = allVideos
    .filter((video) => video.youtube_video_id !== target.youtube_video_id)
    .map((video) => {
      const videoStems = new Set(tokenizeTitle(video.title).map(stemWord));
      const sharedKeywords = Array.from(targetStemToWord.keys())
        .filter((stem) => videoStems.has(stem))
        .map((stem) => targetStemToWord.get(stem)!);
      return { video, sharedKeywords };
    })
    .filter((entry) => entry.sharedKeywords.length > 0)
    .sort((a, b) => b.sharedKeywords.length - a.sharedKeywords.length || b.video.views_per_day - a.video.views_per_day);

  return candidates.slice(0, limit).map((entry) => ({ ...entry.video, sharedKeywords: entry.sharedKeywords }));
}

// ---------------------------------------------------------------------------
// Video-specific insights — Sprint 1.2
// ---------------------------------------------------------------------------

export type Insight = { id: string; text: string };

const RECENT_COHORT_DAYS = 30;

export function buildVideoInsights(target: DerivedVideo, allVideos: DerivedVideo[], history: { views: number }[]): Insight[] {
  const insights: Insight[] = [];

  if (target.days_since_published < TOO_NEW_DAYS) {
    insights.push({
      id: "too-new",
      text: `Film jest zbyt nowy (${target.days_since_published} ${dayWord(target.days_since_published)} od publikacji), aby wiarygodnie ocenić jego wydajność.`,
    });
  } else {
    const recentCohort = allVideos.filter((video) => video.days_since_published <= RECENT_COHORT_DAYS);
    if (recentCohort.length >= 2) {
      const topInCohort = [...recentCohort].sort((a, b) => b.views_per_day - a.views_per_day)[0];
      if (topInCohort.youtube_video_id === target.youtube_video_id) {
        insights.push({
          id: "top-recent",
          text: `Ten film ma najwyższe wyświetlenia/dzień (${target.views_per_day.toLocaleString("pl-PL")}) wśród ${recentCohort.length} filmów opublikowanych w ciągu ostatnich ${RECENT_COHORT_DAYS} dni.`,
        });
      }
    }

    const baseline = buildChannelBaseline(target, allVideos);
    if (baseline.status === "ok") {
      const engagementMetric = baseline.metrics.find((metric) => metric.key === "engagement_rate");
      if (engagementMetric && engagementMetric.percentDiff !== null && Math.abs(engagementMetric.percentDiff) >= 10) {
        const direction = engagementMetric.percentDiff > 0 ? "powyżej" : "poniżej";
        insights.push({
          id: "engagement-baseline",
          text: `Engagement jest ${Math.abs(engagementMetric.percentDiff)}% ${direction} mediany kanału.`,
        });
      }
    }
  }

  if (history.length >= 2) {
    const last = history[history.length - 1];
    const previous = history[history.length - 2];
    const delta = last.views - previous.views;
    if (delta > 0) {
      insights.push({ id: "snapshot-delta", text: `Od poprzedniej synchronizacji film zyskał ${delta.toLocaleString("pl-PL")} wyświetleń.` });
    } else if (delta === 0) {
      insights.push({ id: "snapshot-delta", text: "Liczba wyświetleń nie zmieniła się od poprzedniej synchronizacji." });
    } else {
      insights.push({
        id: "snapshot-delta",
        text: `Liczba wyświetleń spadła o ${Math.abs(delta).toLocaleString("pl-PL")} od poprzedniej synchronizacji (możliwa korekta danych po stronie YouTube).`,
      });
    }
  }

  if (insights.length === 0) {
    insights.push({ id: "none", text: "Brak istotnych odchyleń od typowych wyników kanału dla tego filmu." });
  }

  return insights;
}
