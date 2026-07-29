import Link from "next/link";
import { notFound } from "next/navigation";

import { AppShell } from "../../../../components/app-shell";
import { PlatformSubNav } from "../../../../components/platform-sub-nav";
import { StatCard, StatsGrid } from "../../../../components/stat-card";
import { ChartCard } from "../../../../components/charts/chart-card";
import { LineChartViz } from "../../../../components/charts/line-chart";
import { AiSummaryPlaceholder } from "../../../../components/ai-summary-placeholder";
import { ChannelBaselineView } from "../../../../components/channel-baseline";
import { CommentThreadCard } from "../../../../components/comment-thread-card";
import { CopyLinkButton } from "../../../../components/copy-link-button";
import { ExpandableDescription } from "../../../../components/expandable-description";
import { ExternalLink, youtubeWatchUrl } from "../../../../components/external-link";
import { InsightsList } from "../../../../components/insights-list";
import { PerformanceLabelBadge } from "../../../../components/performance-label-badge";
import { RankedVideoList } from "../../../../components/ranked-video-list";
import { SyncStatusLine } from "../../../../components/sync-status-line";
import { UnavailableMetricsCard } from "../../../../components/unavailable-metrics-card";
import { VideoNavKeyboard } from "../../../../components/video-nav-keyboard";
import { createYoutubeApi } from "../../../../lib/youtube-api";
import {
  MIN_VIDEOS_FOR_SCORE,
  buildChannelBaseline,
  buildVideoInsights,
  computeCompositeScores,
  dayWord,
  findRelatedVideosByKeywords,
  performanceStatus,
  withDerivedMetrics,
} from "../../../../lib/youtube-metrics";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

function formatNumber(value: number) {
  return new Intl.NumberFormat("pl-PL").format(value);
}

function formatSigned(value: number | null) {
  if (value === null) return "Brak danych";
  return `${value > 0 ? "+" : ""}${formatNumber(value)}`;
}

function formatDuration(seconds: number | null) {
  if (!seconds) return "Brak danych";
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("pl-PL", { day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(
    new Date(value),
  );
}

const GROWTH_CATEGORY_LABELS: Record<string, string> = {
  accelerating: "Przyspiesza",
  growing: "Rośnie",
  slowing: "Zwalnia",
  declining: "Spada",
  unknown: "Brak danych",
};

const ENGAGEMENT_CATEGORY_LABELS: Record<string, string> = {
  excellent: "Doskonały",
  good: "Dobry",
  average: "Przeciętny",
  low: "Niski",
};

export default async function YoutubeVideoDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ youtubeVideoId: string }>;
  searchParams: Promise<{ from?: string }>;
}) {
  const { youtubeVideoId } = await params;
  const { from } = await searchParams;
  const api = createYoutubeApi(INTERNAL_API_URL);
  const [detail, history, summary, status, allVideosRaw, commentInbox, quickReplies] = await Promise.all([
    api.getVideoDetail(youtubeVideoId),
    api.getVideoHistory(youtubeVideoId),
    api.getSummary(),
    api.getStatus(),
    api.getVideos(),
    api.getComments({ video: youtubeVideoId, sort: "newest" }),
    api.getQuickReplies(),
  ]);

  if (!detail) notFound();

  const allDerived = allVideosRaw.map((video) => withDerivedMetrics(video));
  const targetVideo = allDerived.find((video) => video.youtube_video_id === detail.youtube_video_id) ?? withDerivedMetrics(detail);

  const hasEnoughForScore = allDerived.length >= MIN_VIDEOS_FOR_SCORE;
  const scored = hasEnoughForScore ? computeCompositeScores(allDerived) : [];
  const targetScored = scored.find((video) => video.youtube_video_id === targetVideo.youtube_video_id) ?? null;

  const baseline = buildChannelBaseline(targetVideo, allDerived);
  const related = findRelatedVideosByKeywords(targetVideo, allDerived, 5);
  const insights = buildVideoInsights(targetVideo, allDerived, history.points);

  // Previous/next navigation (Sprint 5 / Part 3) — newest-first, matching the
  // default browsing order everywhere else in the app.
  const byPublishedDesc = [...allVideosRaw].sort((a, b) => +new Date(b.published_at) - +new Date(a.published_at));
  const currentIndex = byPublishedDesc.findIndex((video) => video.youtube_video_id === youtubeVideoId);
  const prevVideo = currentIndex > 0 ? byPublishedDesc[currentIndex - 1] : null;
  const nextVideo = currentIndex >= 0 && currentIndex < byPublishedDesc.length - 1 ? byPublishedDesc[currentIndex + 1] : null;
  const fromSuffix = from ? `?from=${encodeURIComponent(from)}` : "";
  const prevHref = prevVideo ? `/youtube/videos/${prevVideo.youtube_video_id}${fromSuffix}` : null;
  const nextHref = nextVideo ? `/youtube/videos/${nextVideo.youtube_video_id}${fromSuffix}` : null;
  const backHref = from && from.startsWith("/") ? from : "/youtube";

  const historyRows = history.points.map((point, index) => {
    const previous = index > 0 ? history.points[index - 1] : null;
    return {
      captured_at: point.captured_at,
      views: point.views,
      likes: point.likes,
      comments: point.comments,
      viewsDelta: previous ? point.views - previous.views : null,
      likesDelta: previous ? point.likes - previous.likes : null,
      commentsDelta: previous ? point.comments - previous.comments : null,
      viewsPctChange: previous && previous.views > 0 ? Math.round(((point.views - previous.views) / previous.views) * 100) : null,
    };
  });
  const historyRowsNewestFirst = [...historyRows].reverse();

  // Bucketed, video-age-anchored chart data (Sprint 5/6 Part 5/9) — the X axis
  // represents days/weeks/months since publish, never raw sync timestamps.
  const bucketChartData = history.buckets.map((bucket) => ({ label: bucket.label, views: bucket.views, likes: bucket.likes, comments: bucket.comments }));
  const granularityNote: Record<string, string> = {
    daily: "Dane pogrupowane dziennie (film młodszy niż 30 dni) — jeden punkt na dzień od publikacji.",
    weekly: "Dane pogrupowane tygodniowo (film w wieku 30–180 dni) — jeden punkt na tydzień od publikacji.",
    monthly: "Dane pogrupowane miesięcznie (film starszy niż 180 dni) — jeden punkt na miesiąc od publikacji.",
  };

  const watchUrl = youtubeWatchUrl(detail.youtube_video_id);

  return (
    <AppShell active="/youtube">
      <VideoNavKeyboard prevHref={prevHref} nextHref={nextHref} />

      <div className="videoNavRow">
        <Link className="backLink" href={backHref}>
          ← {from ? "Wróć do listy" : "Wróć do dashboardu YouTube"}
        </Link>
        <div className="videoQuickNav">
          {prevHref ? (
            <Link href={prevHref} className="button secondary" title="Poprzedni film (strzałka w lewo)">
              ← Poprzedni
            </Link>
          ) : (
            <span className="button secondary disabled">← Poprzedni</span>
          )}
          {nextHref ? (
            <Link href={nextHref} className="button secondary" title="Następny film (strzałka w prawo)">
              Następny →
            </Link>
          ) : (
            <span className="button secondary disabled">Następny →</span>
          )}
        </div>
      </div>

      <PlatformSubNav
        active="/youtube"
        tabs={[
          { href: "/youtube", label: "Dashboard" },
          { href: "/youtube/compare", label: "Porównanie" },
          { href: "/youtube/intelligence", label: "Co dalej?" },
          { href: "/youtube/community", label: "Komentarze" },
        ]}
      />

      <section className="videoHero">
        {detail.thumbnail_url ? (
          <img className="largeThumb" src={detail.thumbnail_url} alt="" style={{ objectFit: "cover" }} />
        ) : (
          <div className="largeThumb">{detail.title.slice(0, 1).toUpperCase()}</div>
        )}
        <div>
          <p className="eyebrow">{detail.is_short_candidate ? "SHORT" : "FILM"}</p>
          <h1>{detail.title}</h1>
          <div className="heroBadgeRow">
            <PerformanceLabelBadge label={detail.performance_label} />
          </div>
          <ExpandableDescription text={detail.description} />
          <div className="metaLine">
            <span>{formatDateTime(detail.published_at)}</span>
            <span>{formatDuration(detail.duration_seconds)}</span>
            <span>{summary?.channel_title ?? "Brak danych"}</span>
            <span title="Widoczność filmu nie jest obecnie zapisywana przez RCC">Widoczność: Brak danych</span>
            <SyncStatusLine status={status} />
          </div>
          <div className="videoActions">
            <ExternalLink href={watchUrl} label="Obejrzyj na YouTube" variant="button" />
            <CopyLinkButton url={watchUrl} />
          </div>
        </div>
      </section>

      <div className="statsGroupLabel">Dane z YouTube</div>
      <StatsGrid>
        <StatCard
          label="Wyświetlenia"
          value={formatNumber(detail.views)}
          hint="publiczny licznik z ostatniej synchronizacji"
          tooltip="Wartość pobrana bezpośrednio z YouTube podczas ostatniej synchronizacji — nie jest wyliczana przez RCC."
          featured
        />
        <StatCard
          label="Polubienia"
          value={formatNumber(detail.likes)}
          hint="publiczny licznik z ostatniej synchronizacji"
          tooltip="Wartość pobrana bezpośrednio z YouTube podczas ostatniej synchronizacji."
        />
        <StatCard
          label="Komentarze"
          value={formatNumber(detail.comments)}
          hint="publiczny licznik z ostatniej synchronizacji"
          tooltip="Wartość pobrana bezpośrednio z YouTube podczas ostatniej synchronizacji."
        />
      </StatsGrid>

      <div className="statsGroupLabel">Wskaźniki obliczone przez RCC</div>
      <StatsGrid>
        <StatCard
          label="Wyświetlenia / dzień"
          value={formatNumber(targetVideo.views_per_day)}
          hint="wyświetlenia ÷ dni od publikacji"
          tooltip={`Wyliczenie: ${formatNumber(detail.views)} wyświetleń ÷ ${targetVideo.days_since_published} ${dayWord(targetVideo.days_since_published)} od publikacji.`}
        />
        <StatCard
          label="Engagement rate"
          value={`${targetVideo.engagement_rate.toFixed(2)}%`}
          hint="(polubienia + komentarze) ÷ wyświetlenia"
          tooltip="Wyliczenie: (polubienia + komentarze) ÷ wyświetlenia × 100."
        />
        <StatCard
          label="Wskaźnik polubień"
          value={`${targetVideo.like_ratio.toFixed(2)}%`}
          hint="polubienia ÷ wyświetlenia"
          tooltip="Wyliczenie: polubienia ÷ wyświetlenia × 100."
        />
        <StatCard
          label="Wskaźnik komentarzy"
          value={`${targetVideo.comment_ratio.toFixed(2)}%`}
          hint="komentarze ÷ wyświetlenia"
          tooltip="Wyliczenie: komentarze ÷ wyświetlenia × 100."
        />
        <StatCard
          label="Wynik względny"
          value={targetScored ? `${Math.round(targetScored.performance_score)}/100` : "Brak danych"}
          hint={targetScored ? `${performanceStatus(targetScored.performance_score).label} · na tle całego kanału` : `Za mało filmów w kanale (min. ${MIN_VIDEOS_FOR_SCORE})`}
          tooltip="Wyliczenie: 50% znorm. wyświetleń/dzień + 30% znorm. engagementu + 20% znorm. wyświetleń, znormalizowane względem wszystkich filmów kanału. Wynik względny, nie uniwersalny."
        />
        <StatCard
          label="Wiek filmu"
          value={`${targetVideo.days_since_published} ${dayWord(targetVideo.days_since_published)}`}
          hint="od daty publikacji"
          tooltip="Liczba pełnych dni od daty publikacji do teraz."
        />
      </StatsGrid>

      <div className="statsGroupLabel">Wzrost w czasie</div>
      <StatsGrid>
        <StatCard
          label="Zysk 24h"
          value={formatSigned(detail.views_gained_24h)}
          hint="wyświetlenia"
          tooltip="Różnica wyświetleń względem najbliższego pomiaru sprzed ~24h. Brak danych, jeśli historia nie sięga tak daleko wstecz."
        />
        <StatCard label="Zysk 7 dni" value={formatSigned(detail.views_gained_7d)} hint="wyświetlenia" />
        <StatCard label="Zysk 30 dni" value={formatSigned(detail.views_gained_30d)} hint="wyświetlenia" />
        <StatCard
          label="Prędkość (velocity)"
          value={detail.velocity !== null ? `${formatSigned(Math.round(detail.velocity))}/dzień` : "Brak danych"}
          hint="tempo wzrostu między dwoma ostatnimi pomiarami"
          tooltip="Wyliczenie: (wyświetlenia najnowsze − poprzednie) ÷ liczba dni między pomiarami."
        />
        <StatCard
          label="Przyspieszenie"
          value={detail.acceleration !== null ? formatSigned(Math.round(detail.acceleration)) : "Brak danych"}
          hint="zmiana tempa względem poprzedniego interwału"
          tooltip="Wyliczenie: bieżąca prędkość − prędkość z poprzedniego interwału. Wartość dodatnia = przyspiesza."
        />
        <StatCard
          label="Kategoria wzrostu"
          value={GROWTH_CATEGORY_LABELS[detail.growth_category] ?? detail.growth_category}
          hint="deterministyczna kategoria trendu"
        />
      </StatsGrid>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">KONTEKST</p>
            <h2>Na tle kanału</h2>
          </div>
        </div>
        <ChannelBaselineView baseline={baseline} />
      </section>

      <section className="chartsGrid">
        <ChartCard
          title="Wyświetlenia w czasie"
          subtitle={granularityNote[history.granularity]}
          isEmpty={history.insufficient}
          emptyMessage="Za mało okresów w historii, aby pokazać sensowny trend. Wykres pojawi się, gdy zbierzemy więcej synchronizacji rozłożonych w czasie."
        >
          <LineChartViz data={bucketChartData} xKey="label" series={[{ key: "views", label: "Wyświetlenia" }]} />
        </ChartCard>
        <ChartCard
          title="Zaangażowanie w czasie"
          subtitle={granularityNote[history.granularity]}
          isEmpty={history.insufficient}
          emptyMessage="Za mało okresów w historii, aby pokazać sensowny trend."
        >
          <LineChartViz
            data={bucketChartData}
            xKey="label"
            series={[
              { key: "likes", label: "Polubienia" },
              { key: "comments", label: "Komentarze" },
            ]}
          />
        </ChartCard>
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">OŚ CZASU</p>
            <h2>Chronologia filmu</h2>
          </div>
        </div>
        <ol className="videoTimeline">
          <li>
            <strong>Publikacja</strong>
            <span>{formatDateTime(detail.published_at)}</span>
          </li>
          <li>
            <strong>Pierwsza synchronizacja</strong>
            <span>{history.points[0] ? formatDateTime(history.points[0].captured_at) : "Brak danych"}</span>
          </li>
          <li>
            <strong>Zebrane pomiary</strong>
            <span>
              {detail.snapshot_count} {detail.snapshot_count === 1 ? "pomiar" : "pomiarów"}
            </span>
          </li>
          <li>
            <strong>Ostatnia synchronizacja</strong>
            <span>
              {history.points.length ? formatDateTime(history.points[history.points.length - 1].captured_at) : "Brak danych"}
            </span>
          </li>
        </ol>
      </section>

      {historyRows.length > 0 ? (
        <section className="libraryPanel">
          <div className="libraryHeading">
            <div>
              <p className="eyebrow">HISTORIA</p>
              <h2>Historia synchronizacji</h2>
              <p className="muted">Zmiana (Δ) i procent liczone względem poprzedniej synchronizacji — puste pole oznacza brak poprzedniego pomiaru.</p>
            </div>
          </div>
          {(detail.peak_growth_date || detail.largest_slowdown_date) ? (
            <p className="muted historySummaryStrip">
              {detail.peak_growth_date ? (
                <span>
                  Najlepszy przyrost: <strong>{formatSigned(detail.peak_growth_views)}</strong> ({new Date(detail.peak_growth_date).toLocaleDateString("pl-PL")})
                </span>
              ) : null}
              {detail.largest_slowdown_date ? (
                <span>
                  Największe spowolnienie: <strong>{formatSigned(detail.largest_slowdown_views)}</strong> ({new Date(detail.largest_slowdown_date).toLocaleDateString("pl-PL")})
                </span>
              ) : null}
            </p>
          ) : null}
          <div className="dataTableWrap">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Data i godzina</th>
                  <th style={{ textAlign: "right" }}>Wyświetlenia</th>
                  <th style={{ textAlign: "right" }}>Δ wyświetleń</th>
                  <th style={{ textAlign: "right" }}>Polubienia</th>
                  <th style={{ textAlign: "right" }}>Δ polubień</th>
                  <th style={{ textAlign: "right" }}>Komentarze</th>
                  <th style={{ textAlign: "right" }}>Δ komentarzy</th>
                </tr>
              </thead>
              <tbody>
                {historyRowsNewestFirst.map((row) => (
                  <tr key={row.captured_at}>
                    <td>{new Date(row.captured_at).toLocaleString("pl-PL")}</td>
                    <td style={{ textAlign: "right" }}>{formatNumber(row.views)}</td>
                    <td style={{ textAlign: "right" }}>
                      {row.viewsDelta === null
                        ? "—"
                        : `${row.viewsDelta > 0 ? "+" : ""}${formatNumber(row.viewsDelta)}${row.viewsPctChange !== null ? ` (${row.viewsPctChange > 0 ? "+" : ""}${row.viewsPctChange}%)` : ""}`}
                    </td>
                    <td style={{ textAlign: "right" }}>{formatNumber(row.likes)}</td>
                    <td style={{ textAlign: "right" }}>{row.likesDelta === null ? "—" : `${row.likesDelta > 0 ? "+" : ""}${formatNumber(row.likesDelta)}`}</td>
                    <td style={{ textAlign: "right" }}>{formatNumber(row.comments)}</td>
                    <td style={{ textAlign: "right" }}>
                      {row.commentsDelta === null ? "—" : `${row.commentsDelta > 0 ? "+" : ""}${formatNumber(row.commentsDelta)}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">ANALIZA</p>
            <h2>Wnioski dotyczące tego filmu</h2>
            <p className="muted">Wnioski deterministyczne na podstawie danych powyżej — nie generowane przez AI i nie dowodzą związku przyczynowego.</p>
          </div>
        </div>
        <InsightsList insights={insights} />
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">SPOŁECZNOŚĆ</p>
            <h2>Komentarze</h2>
            <p className="muted">
              {commentInbox.summary.total_visible} zaimportowanych · {commentInbox.summary.unanswered_count} bez odpowiedzi ·{" "}
              {commentInbox.summary.questions_count} prawdopodobnych pytań
            </p>
          </div>
          <Link className="textLink" href={`/youtube/community?video=${detail.youtube_video_id}`}>
            Otwórz w Skrzynce komentarzy →
          </Link>
        </div>
        {commentInbox.threads.length === 0 ? (
          <div className="emptyState">
            <h3>Brak zaimportowanych komentarzy</h3>
            <p>Uruchom synchronizację komentarzy w Skrzynce komentarzy, aby zobaczyć je tutaj.</p>
          </div>
        ) : (
          <div className="commentList">
            {commentInbox.threads.slice(0, 3).map((row) => (
              <CommentThreadCard key={row.platform_thread_id} row={row} quickReplies={quickReplies} showVideo={false} />
            ))}
          </div>
        )}
      </section>

      <AiSummaryPlaceholder />
      <UnavailableMetricsCard />

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">METADANE</p>
            <h2>Metadane techniczne</h2>
            <p className="muted">Ustrukturyzowane, deterministyczne dane przygotowane jako wejście dla przyszłego silnika AI (patrz docs/AI_ENGINE.md).</p>
          </div>
        </div>
        <div className="techMetadataGrid">
          <div>
            <span>Trend</span>
            <strong>{detail.trend}</strong>
          </div>
          <div>
            <span>Kategoria zaangażowania</span>
            <strong>{ENGAGEMENT_CATEGORY_LABELS[detail.engagement_category] ?? detail.engagement_category}</strong>
          </div>
          <div>
            <span>Kategoria wzrostu</span>
            <strong>{GROWTH_CATEGORY_LABELS[detail.growth_category] ?? detail.growth_category}</strong>
          </div>
          <div>
            <span>Etykieta wydajności</span>
            <strong>{detail.performance_label}</strong>
          </div>
          <div>
            <span>Liczba pomiarów</span>
            <strong>{detail.snapshot_count}</strong>
          </div>
          <div>
            <span>Słowa kluczowe tematu</span>
            <strong>{detail.topic_keywords.length ? detail.topic_keywords.join(", ") : "Brak"}</strong>
          </div>
        </div>
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">POWIĄZANE</p>
            <h2>Podobne filmy na Twoim kanale</h2>
            <p className="muted">Dopasowanie na podstawie wspólnych słów kluczowych w tytule — nie na podstawie treści czy kategorii.</p>
          </div>
        </div>
        <RankedVideoList
          items={related}
          emptyMessage="Brak filmów o wystarczająco podobnym tytule w tym kanale."
          renderMetrics={(video) => (
            <>
              <span>{formatNumber(video.views)} wyśw.</span>
              <span>{video.views_per_day.toLocaleString("pl-PL")}/dzień</span>
              <span>{video.engagement_rate.toFixed(2)}% ER</span>
            </>
          )}
          renderActions={(video) => <ExternalLink href={youtubeWatchUrl(video.youtube_video_id)} label="Obejrzyj na YouTube" />}
        />
      </section>
    </AppShell>
  );
}
