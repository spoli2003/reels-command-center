import Link from "next/link";
import { notFound } from "next/navigation";

import { AiSummaryPlaceholder } from "../../../../../components/ai-summary-placeholder";
import { AppShell } from "../../../../../components/app-shell";
import { ChartCard } from "../../../../../components/charts/chart-card";
import { LineChartViz } from "../../../../../components/charts/line-chart";
import { CopyLinkButton } from "../../../../../components/copy-link-button";
import { ExpandableDescription } from "../../../../../components/expandable-description";
import { ExternalLink } from "../../../../../components/external-link";
import { PlatformCommentThreadCard } from "../../../../../components/platform-comment-thread-card";
import { PlatformSectionNav } from "../../../../../components/platform-section-nav";
import { ScoreBreakdownDetails } from "../../../../../components/score-breakdown";
import { StatCard, StatsGrid } from "../../../../../components/stat-card";
import { createPlatformApi, PLATFORM_LABELS, type PlatformKey } from "../../../../../lib/platform-api";
import { computePlatformCompositeScores, MIN_VIDEOS_FOR_SCORE, withDerivedMetrics } from "../../../../../lib/platform-metrics";
import { performanceStatus } from "../../../../../lib/youtube-metrics";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
const REAL_PLATFORMS: PlatformKey[] = ["youtube", "facebook", "instagram"];

function formatNumber(value: number) {
  return new Intl.NumberFormat("pl-PL").format(value);
}

function formatDateTime(value: string | null) {
  if (!value) return "Brak danych";
  return new Intl.DateTimeFormat("pl-PL", { day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export default async function PlatformVideoDetailPage({
  params,
}: {
  params: Promise<{ platform: string; externalId: string }>;
}) {
  const { platform, externalId } = await params;
  if (!REAL_PLATFORMS.includes(platform as PlatformKey)) notFound();
  const key = platform as PlatformKey;

  const api = createPlatformApi(INTERNAL_API_URL, key);
  const [detail, history, allVideos, commentInbox, quickReplies] = await Promise.all([
    api.getVideoDetail(externalId),
    api.getVideoHistory(externalId),
    api.getVideos(),
    api.getComments({ video: externalId, sort: "priority" }),
    api.getQuickReplies(),
  ]);

  if (!detail) notFound();

  const derived = allVideos.map((video) => withDerivedMetrics(video));
  const targetDerived = derived.find((v) => v.external_id === externalId) ?? withDerivedMetrics(detail);
  const hasEnoughForScore = derived.length >= MIN_VIDEOS_FOR_SCORE;
  const scored = hasEnoughForScore ? computePlatformCompositeScores(derived) : [];
  const targetScored = scored.find((v) => v.external_id === externalId) ?? null;

  const byPublishedDesc = [...allVideos].sort((a, b) => +new Date(b.published_at ?? 0) - +new Date(a.published_at ?? 0));
  const currentIndex = byPublishedDesc.findIndex((video) => video.external_id === externalId);
  const prevVideo = currentIndex > 0 ? byPublishedDesc[currentIndex - 1] : null;
  const nextVideo = currentIndex >= 0 && currentIndex < byPublishedDesc.length - 1 ? byPublishedDesc[currentIndex + 1] : null;

  const historyRows = history.points.map((point, index) => {
    const previous = index > 0 ? history.points[index - 1] : null;
    return {
      captured_at: point.captured_at,
      views: point.views,
      likes: point.likes,
      comments: point.comments,
      viewsDelta: previous ? point.views - previous.views : null,
    };
  });
  const historyRowsNewestFirst = [...historyRows].reverse();
  const bucketChartData = history.buckets.map((bucket) => ({ label: bucket.label, views: bucket.views, likes: bucket.likes, comments: bucket.comments }));

  return (
    <AppShell active="/platforms">
      <div className="videoNavRow">
        <Link className="backLink" href={`/platforms/${key}/videos`}>
          ← Wróć do listy materiałów
        </Link>
        <div className="videoQuickNav">
          {prevVideo ? (
            <Link href={`/platforms/${key}/videos/${prevVideo.external_id}`} className="button secondary">
              ← Poprzedni
            </Link>
          ) : (
            <span className="button secondary disabled">← Poprzedni</span>
          )}
          {nextVideo ? (
            <Link href={`/platforms/${key}/videos/${nextVideo.external_id}`} className="button secondary">
              Następny →
            </Link>
          ) : (
            <span className="button secondary disabled">Następny →</span>
          )}
        </div>
      </div>

      <PlatformSectionNav platform={key} active="videos" />

      <section className="videoHero">
        {detail.thumbnail_url ? (
          <img className="largeThumb" src={detail.thumbnail_url} alt="" style={{ objectFit: "cover" }} />
        ) : (
          <div className="largeThumb">{detail.title.slice(0, 1).toUpperCase()}</div>
        )}
        <div>
          <p className="eyebrow">{PLATFORM_LABELS[key].toUpperCase()}</p>
          <h1>{detail.title}</h1>
          <ExpandableDescription text={detail.description} />
          <div className="metaLine">
            <span>{formatDateTime(detail.published_at)}</span>
          </div>
          {detail.url ? (
            <div className="videoActions">
              <ExternalLink href={detail.url} label="Otwórz oryginał" variant="button" />
              <CopyLinkButton url={detail.url} />
            </div>
          ) : null}
        </div>
      </section>

      <div className="statsGroupLabel">Dane z {PLATFORM_LABELS[key]}</div>
      <StatsGrid>
        <StatCard label="Wyświetlenia" value={formatNumber(detail.views)} hint="z ostatniej synchronizacji" featured />
        <StatCard label="Polubienia" value={formatNumber(detail.likes)} hint="z ostatniej synchronizacji" />
        <StatCard label="Komentarze" value={formatNumber(detail.comments)} hint="z ostatniej synchronizacji" />
        {detail.shares > 0 ? <StatCard label="Udostępnienia" value={formatNumber(detail.shares)} hint="z ostatniej synchronizacji" /> : null}
        {detail.saves > 0 ? <StatCard label="Zapisania" value={formatNumber(detail.saves)} hint="z ostatniej synchronizacji" /> : null}
        {detail.reach !== null ? <StatCard label="Zasięg" value={formatNumber(detail.reach)} hint="unikalni odbiorcy" /> : null}
        {detail.impressions !== null ? <StatCard label="Wyświetlenia (impressions)" value={formatNumber(detail.impressions)} hint="łącznie z powtórzeniami" /> : null}
      </StatsGrid>

      <div className="statsGroupLabel">Wskaźniki obliczone przez RCC</div>
      <StatsGrid>
        <StatCard label="Wyświetlenia / dzień" value={formatNumber(targetDerived.views_per_day)} hint="wyświetlenia ÷ dni od publikacji" />
        <StatCard
          label="Engagement rate"
          value={`${detail.engagement_rate.toFixed(2)}%`}
          hint="(polubienia + komentarze) ÷ wyświetlenia"
          tooltip="Wyliczenie: (polubienia + komentarze) ÷ wyświetlenia × 100."
        />
        <StatCard
          label="Wynik względny"
          value={targetScored ? `${Math.round(targetScored.performance_score)}/100` : "Brak danych"}
          hint={
            targetScored
              ? `${performanceStatus(targetScored.performance_score).label} · na tle wszystkich materiałów ${PLATFORM_LABELS[key]}`
              : `Za mało materiałów (min. ${MIN_VIDEOS_FOR_SCORE})`
          }
          tooltip="Wyliczenie: 50% znorm. wyświetleń/dzień + 30% znorm. engagementu + 20% znorm. wyświetleń, znormalizowane względem wszystkich materiałów tej platformy. Wynik względny, nie uniwersalny."
        />
      </StatsGrid>

      {targetScored ? (
        <section className="libraryPanel scoreDetailPanel">
          <div className="libraryHeading">
            <div>
              <p className="eyebrow">PUNKTACJA</p>
              <h2>Co zbudowało wynik {Math.round(targetScored.performance_score)}/100?</h2>
            </div>
          </div>
          <ScoreBreakdownDetails breakdown={targetScored.score_breakdown} defaultOpen />
        </section>
      ) : null}

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">HISTORIA</p>
            <h2>Wzrost od publikacji</h2>
            <p className="muted">
              {history.granularity === "daily"
                ? "Dane pogrupowane dziennie (materiał młodszy niż 30 dni)."
                : history.granularity === "weekly"
                  ? "Dane pogrupowane tygodniowo (materiał w wieku 30–180 dni)."
                  : "Dane pogrupowane miesięcznie (materiał starszy niż 180 dni)."}
            </p>
          </div>
        </div>
        <ChartCard
          title="Wyświetlenia w czasie"
          isEmpty={history.insufficient}
          emptyMessage="Potrzeba co najmniej dwóch synchronizacji, aby pokazać trend."
        >
          <LineChartViz data={bucketChartData} xKey="label" series={[{ key: "views", label: "Wyświetlenia" }]} />
        </ChartCard>
        {historyRowsNewestFirst.length > 0 ? (
          <div className="dataTableWrap" style={{ marginTop: 16 }}>
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Data synchronizacji</th>
                  <th style={{ textAlign: "right" }}>Wyświetlenia</th>
                  <th style={{ textAlign: "right" }}>Zmiana</th>
                  <th style={{ textAlign: "right" }}>Polubienia</th>
                  <th style={{ textAlign: "right" }}>Komentarze</th>
                </tr>
              </thead>
              <tbody>
                {historyRowsNewestFirst.slice(0, 20).map((row) => (
                  <tr key={row.captured_at}>
                    <td>{new Date(row.captured_at).toLocaleString("pl-PL")}</td>
                    <td style={{ textAlign: "right" }}>{formatNumber(row.views)}</td>
                    <td style={{ textAlign: "right" }}>{row.viewsDelta !== null ? `+${formatNumber(row.viewsDelta)}` : "—"}</td>
                    <td style={{ textAlign: "right" }}>{formatNumber(row.likes)}</td>
                    <td style={{ textAlign: "right" }}>{formatNumber(row.comments)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <AiSummaryPlaceholder />

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">SPOŁECZNOŚĆ</p>
            <h2>Komentarze do tego materiału</h2>
          </div>
        </div>
        {commentInbox.threads.length === 0 ? (
          <div className="emptyState">
            <h3>Brak komentarzy</h3>
            <p>Ten materiał nie ma jeszcze zsynchronizowanych komentarzy.</p>
          </div>
        ) : (
          <div className="commentList">
            {commentInbox.threads.map((row) => (
              <PlatformCommentThreadCard key={row.platform_thread_id} platform={key} row={row} quickReplies={quickReplies} showVideo={false} />
            ))}
          </div>
        )}
      </section>
    </AppShell>
  );
}
