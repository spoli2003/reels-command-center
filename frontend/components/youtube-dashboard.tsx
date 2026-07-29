"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { ChartCard } from "./charts/chart-card";
import { LineChartViz } from "./charts/line-chart";
import { DashboardFilterBar } from "./dashboard-filter-bar";
import { ExternalLink, youtubeWatchUrl } from "./external-link";
import { PerformanceLabelBadge } from "./performance-label-badge";
import { RankedVideoList } from "./ranked-video-list";
import { StatCard, StatsGrid } from "./stat-card";
import { SuggestionsList } from "./suggestions-list";
import { VideoTable } from "./video-table";
import type { YoutubeChannelHistory, YoutubeChannelVideo, YoutubeSummary, YoutubeTimeseriesPoint } from "../lib/youtube-api";
import {
  ATTENTION_DEFAULT_WINDOW_DAYS,
  DATE_RANGE_OPTIONS,
  MIN_COMPARABLE_FOR_ATTENTION,
  MIN_VIDEOS_FOR_SCORE,
  SORT_OPTIONS,
  TOO_NEW_DAYS,
  applyQuickFilter,
  buildAttentionList,
  buildBestPerformerSuggestion,
  buildKeywordSuggestion,
  buildWeekdaySuggestion,
  computeCompositeScores,
  explainRanking,
  filterByDateRange,
  filterBySearch,
  filterByViewsRange,
  isDateRangeKey,
  isQuickFilter,
  isSortDirection,
  isSortKey,
  median,
  nextSortState,
  performanceStatus,
  sortVideos,
  truncateTitle,
  withDerivedMetrics,
  type DateRangeKey,
  type QuickFilter,
  type SortDirection,
  type SortKey,
  type TableSort,
} from "../lib/youtube-metrics";

const RANGE_DAY_COUNTS: Record<DateRangeKey, number | null> = { all: null, "7d": 7, "30d": 30, "90d": 90, "365d": 365 };

function attentionWindowDays(range: DateRangeKey): number {
  const days = RANGE_DAY_COUNTS[range];
  if (days === null) return ATTENTION_DEFAULT_WINDOW_DAYS;
  return Math.min(days, ATTENTION_DEFAULT_WINDOW_DAYS);
}

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function shortDate(value: string) {
  return new Intl.DateTimeFormat("pl-PL", { day: "2-digit", month: "short" }).format(new Date(value));
}

export function YoutubeDashboard({
  summary,
  videos,
  viewsSeries,
  likesSeries,
  commentsSeries,
  channelHistory,
}: {
  summary: YoutubeSummary;
  videos: YoutubeChannelVideo[];
  viewsSeries: YoutubeTimeseriesPoint[];
  likesSeries: YoutubeTimeseriesPoint[];
  commentsSeries: YoutubeTimeseriesPoint[];
  channelHistory?: YoutubeChannelHistory | null;
}) {
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

  const derived = useMemo(() => videos.map((video) => withDerivedMetrics(video)), [videos]);
  const dateFiltered = useMemo(() => filterByDateRange(derived, dateRange), [derived, dateRange]);
  const searchFiltered = useMemo(() => filterBySearch(dateFiltered, search), [dateFiltered, search]);
  const filtered = useMemo(() => filterByViewsRange(searchFiltered, minViews, maxViews), [searchFiltered, minViews, maxViews]);

  const hasEnoughForScore = filtered.length >= MIN_VIDEOS_FOR_SCORE;
  const scored = useMemo(() => (hasEnoughForScore ? computeCompositeScores(filtered) : []), [filtered, hasEnoughForScore]);
  const scoreById = useMemo(() => new Map(scored.map((v) => [v.youtube_video_id, v.performance_score])), [scored]);
  const bestVideos = useMemo(() => [...scored].sort((a, b) => b.performance_score - a.performance_score).slice(0, 10), [scored]);
  const quickFiltered = useMemo(() => applyQuickFilter(filtered, scoreById, quickFilter), [filtered, scoreById, quickFilter]);

  const channelMedians = useMemo(
    () => ({
      vpd: median(filtered.map((v) => v.views_per_day)) ?? 0,
      er: median(filtered.map((v) => v.engagement_rate)) ?? 0,
    }),
    [filtered],
  );

  const attention = useMemo(() => buildAttentionList(filtered, attentionWindowDays(dateRange)), [filtered, dateRange]);

  const suggestions = useMemo(
    () => [buildBestPerformerSuggestion(filtered), buildWeekdaySuggestion(filtered), buildKeywordSuggestion(filtered)],
    [filtered],
  );

  const quickFilteredWithScore = useMemo(
    () => quickFiltered.map((v) => ({ ...v, performance_score: scoreById.get(v.youtube_video_id) ?? v.performance_score })),
    [quickFiltered, scoreById],
  );
  const generalList = useMemo(() => sortVideos(quickFilteredWithScore, sort), [quickFilteredWithScore, sort]);

  const activeLabel = DATE_RANGE_OPTIONS.find((option) => option.key === dateRange)?.label ?? "Cały okres";

  const totalViews = filtered.reduce((sum, v) => sum + v.views, 0);
  const totalLikes = filtered.reduce((sum, v) => sum + v.likes, 0);
  const totalComments = filtered.reduce((sum, v) => sum + v.comments, 0);
  const avgVpd = filtered.length ? Math.round(filtered.reduce((sum, v) => sum + v.views_per_day, 0) / filtered.length) : 0;
  const avgEr = filtered.length ? filtered.reduce((sum, v) => sum + v.engagement_rate, 0) / filtered.length : 0;

  const viewsChartData = viewsSeries.map((point) => ({ date: shortDate(point.date), views: point.value }));
  const engagementDates = Array.from(new Set([...likesSeries.map((p) => p.date), ...commentsSeries.map((p) => p.date)])).sort();
  const likesByDate = new Map(likesSeries.map((p) => [p.date, p.value]));
  const commentsByDate = new Map(commentsSeries.map((p) => [p.date, p.value]));
  const engagementChartData = engagementDates.map((date) => ({
    date: shortDate(date),
    likes: likesByDate.get(date) ?? 0,
    comments: commentsByDate.get(date) ?? 0,
  }));

  return (
    <>
      <StatsGrid>
        <StatCard
          label="Subskrybenci"
          value={compact(summary.subscriber_count)}
          hint="cały kanał, niezależnie od filtra"
          tooltip="Aktualna liczba subskrybentów kanału z ostatniej synchronizacji. Nie zależy od filtrów powyżej."
          featured
        />
        <StatCard
          label="Wyświetlenia/dzień (kanał)"
          value={summary.channel_views_per_day !== null ? compact(summary.channel_views_per_day) : "Brak danych"}
          hint="Od pierwszego analizowanego filmu"
          tooltip={
            summary.days_since_oldest_video !== null
              ? `Wyliczenie: suma wyświetleń wszystkich filmów ÷ liczba dni od najstarszego zaimportowanego filmu (${summary.days_since_oldest_video} dni). Celowo NIE używa wieku konta YouTube — kanały bywają nieaktywne przez lata, co zaniżałoby ten wskaźnik. Nie zależy od filtrów powyżej.`
              : "Brak zaimportowanych filmów z datą publikacji."
          }
        />
        <StatCard label="Filmy w zakresie" value={String(filtered.length)} hint={activeLabel} />
        <StatCard label="Wyświetlenia (zakres)" value={compact(totalViews)} hint={activeLabel} />
        <StatCard label="Polubienia (zakres)" value={compact(totalLikes)} hint={activeLabel} />
        <StatCard label="Komentarze (zakres)" value={compact(totalComments)} hint={activeLabel} />
        <StatCard
          label="Śr. wyśw./dzień na film"
          value={compact(avgVpd)}
          hint={activeLabel}
          tooltip="Średnia z indywidualnych wskaźników wyświetlenia/dzień każdego filmu w wybranym zakresie (nie to samo co tempo całego kanału obok)."
        />
        <StatCard
          label="Śr. engagement"
          value={`${avgEr.toFixed(2)}%`}
          hint={activeLabel}
          tooltip="Średnia z (polubienia + komentarze) ÷ wyświetlenia dla każdego filmu w wybranym zakresie."
        />
      </StatsGrid>

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
        resultCount={quickFiltered.length}
        activeLabel={activeLabel}
      />

      <section className="chartsGrid">
        <ChartCard
          title="Wyświetlenia w czasie"
          subtitle="Suma wyświetleń wszystkich filmów kanału w kolejnych synchronizacjach (nie podlega filtrom zakresu/wyszukiwania powyżej)."
          isEmpty={viewsChartData.length < 2}
          emptyMessage="Potrzeba co najmniej dwóch synchronizacji YouTube, aby pokazać trend."
        >
          <LineChartViz data={viewsChartData} xKey="date" series={[{ key: "views", label: "Wyświetlenia" }]} />
        </ChartCard>

        <ChartCard
          title="Zaangażowanie w czasie"
          subtitle="Polubienia i komentarze zsumowane po wszystkich filmach kanału (nie podlega filtrom powyżej)."
          isEmpty={engagementChartData.length < 2}
          emptyMessage="Potrzeba co najmniej dwóch synchronizacji YouTube, aby pokazać trend."
        >
          <LineChartViz
            data={engagementChartData}
            xKey="date"
            series={[
              { key: "likes", label: "Polubienia" },
              { key: "comments", label: "Komentarze" },
            ]}
          />
        </ChartCard>

        {channelHistory ? (
          <ChartCard
            title="Wzrost subskrybentów"
            subtitle={
              channelHistory.granularity === "daily"
                ? "Dane pogrupowane dziennie — RCC śledzi ten kanał krócej niż 30 dni."
                : channelHistory.granularity === "weekly"
                  ? "Dane pogrupowane tygodniowo — RCC śledzi ten kanał od 30 do 180 dni."
                  : "Dane pogrupowane miesięcznie — RCC śledzi ten kanał dłużej niż 180 dni."
            }
            isEmpty={channelHistory.insufficient}
            emptyMessage="Za mało okresów synchronizacji, aby pokazać trend subskrybentów. Wróć po kilku kolejnych synchronizacjach."
          >
            <LineChartViz
              data={channelHistory.buckets.map((bucket) => ({ label: bucket.label, subscribers: bucket.subscriber_count }))}
              xKey="label"
              series={[{ key: "subscribers", label: "Subskrybenci" }]}
            />
          </ChartCard>
        ) : null}
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">RANKING</p>
            <h2>Najlepsze filmy</h2>
            <p className="muted">
              Wynik = 50% znorm. wyświetleń/dzień + 30% znorm. engagementu + 20% znorm. wyświetleń.{" "}
              <strong>Wynik względny w aktualnie wybranym zestawie filmów.</strong>
            </p>
          </div>
        </div>
        <RankedVideoList
          items={bestVideos}
          highlightTopN={3}
          emptyMessage={
            hasEnoughForScore
              ? "Brak filmów pasujących do wybranych filtrów."
              : `Za mało filmów w wybranym zakresie (min. ${MIN_VIDEOS_FOR_SCORE}), aby obliczyć wiarygodny ranking.`
          }
          renderMetrics={(video) => (
            <>
              <span>{compact(video.views)} wyśw.</span>
              <span>{video.views_per_day.toLocaleString("pl-PL")}/dzień</span>
              <span>{video.engagement_rate.toFixed(2)}% ER</span>
            </>
          )}
          renderBadge={(video) => {
            const status = performanceStatus(video.performance_score);
            return (
              <span className={`performanceBadge ${status.tone}`}>
                {status.label} · {Math.round(video.performance_score)}
              </span>
            );
          }}
          renderExtra={(video) => <p className="rankedExplanation">{explainRanking(video, channelMedians)}</p>}
          renderActions={(video) => <ExternalLink href={youtubeWatchUrl(video.youtube_video_id)} label="Obejrzyj na YouTube" />}
        />
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">JAKOŚĆ</p>
            <h2>Filmy wymagające uwagi</h2>
            <p className="muted">
              Ocena ograniczona do filmów opublikowanych w ciągu ostatnich {attention.windowDays} dni — starsze filmy nie są oceniane, aby
              nie oznaczać evergreenów tylko za niskie bieżące tempo.
            </p>
          </div>
        </div>
        {attention.insufficientData ? (
          <div className="emptyState">
            <h3>Za mało danych</h3>
            <p>
              Potrzeba co najmniej {MIN_COMPARABLE_FOR_ATTENTION} porównywalnych filmów (starszych niż {TOO_NEW_DAYS} dni) w tym oknie
              czasowym, aby ocenić wydajność.
            </p>
          </div>
        ) : (
          <>
            <RankedVideoList
              items={attention.flagged}
              emptyMessage="Żaden film w tym oknie czasowym nie odstaje istotnie od mediany kanału."
              renderMetrics={(video) => (
                <>
                  <span>{video.views_per_day.toLocaleString("pl-PL")}/dzień</span>
                  <span>{video.engagement_rate.toFixed(2)}% ER</span>
                </>
              )}
              renderExtra={(video) =>
                video.reasons.map((reason) => (
                  <p key={reason} className="attentionReason">
                    {reason}
                  </p>
                ))
              }
              renderActions={(video) => <ExternalLink href={youtubeWatchUrl(video.youtube_video_id)} label="Obejrzyj na YouTube" />}
            />
            {attention.tooNewCount > 0 ? (
              <p className="muted">
                {attention.tooNewCount} {attention.tooNewCount === 1 ? "film pominięto" : "filmów pominięto"} — zbyt nowe (młodsze niż{" "}
                {TOO_NEW_DAYS} dni), by rzetelnie ocenić.
              </p>
            ) : null}
          </>
        )}
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">POMYSŁY</p>
            <h2>Sugestie na podstawie Twoich filmów</h2>
            <p className="muted">Sugestie deterministyczne na podstawie realnych danych — nie generowane przez AI i nie dowodzą związku przyczynowego.</p>
          </div>
        </div>
        <SuggestionsList suggestions={suggestions} />
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">PRZEGLĄD</p>
            <h2>Wszystkie filmy</h2>
            <p className="muted">
              Posortowano według: {SORT_OPTIONS.find((option) => option.key === sortKey)?.label} (
              {sortDirection === "asc" ? "rosnąco" : "malejąco"}) · kliknij nagłówek kolumny, aby zmienić sortowanie.
            </p>
          </div>
        </div>
        <VideoTable
          rows={generalList}
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
            {
              label: "Etykieta",
              render: (video) => <PerformanceLabelBadge label={video.performance_label} />,
            },
            { label: "Data publikacji", sortKey: "published_at", render: (video) => new Date(video.published_at).toLocaleDateString("pl-PL") },
            { label: "Wyświetlenia", align: "right", sortKey: "views", render: (video) => compact(video.views) },
            { label: "Wyśw./dzień", align: "right", sortKey: "views_per_day", render: (video) => video.views_per_day.toLocaleString("pl-PL") },
            { label: "ER", align: "right", sortKey: "engagement", render: (video) => `${video.engagement_rate.toFixed(2)}%` },
            {
              label: "Wynik",
              align: "right",
              sortKey: "score",
              render: (video) => (video.performance_score !== undefined ? Math.round(video.performance_score) : "—"),
            },
          ]}
        />
      </section>
    </>
  );
}
