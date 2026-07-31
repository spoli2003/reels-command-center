"use client";

import Link from "next/link";
import { useMemo } from "react";

import { AudienceGain } from "./audience-gain";
import { ExternalLink } from "./external-link";
import { PlatformBadge } from "./platform-badge";
import { PlatformVideoTableSection } from "./platform-video-table-section";
import { RankedVideoList } from "./ranked-video-list";
import { ScoreBreakdownDetails } from "./score-breakdown";
import { StatCard, StatsGrid } from "./stat-card";
import type { PlatformVideo } from "../lib/platform-api";
import { computePlatformCompositeScores, MIN_VIDEOS_FOR_SCORE, withDerivedMetrics } from "../lib/platform-metrics";

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

/** Generic Dashboard shared by Facebook/Instagram (and directly reachable for
 * bridged YouTube data too) — same StatsGrid/RankedVideoList/VideoTable shapes
 * as YoutubeDashboard, without the YouTube-only channel-wide timeseries charts
 * (Facebook/Instagram Graph API doesn't expose an equivalent channel-history
 * endpoint the way YouTube's Data API snapshots do — honestly omitted rather
 * than faked). `videos` may span multiple platforms at once (the "all" pseudo-
 * platform on the Platform Switcher) — every link is built from each video's
 * OWN `platform` field, never a single fixed one. */
export function PlatformDashboard({ videos, viewsAvailable = true }: { videos: PlatformVideo[]; viewsAvailable?: boolean }) {
  const derived = useMemo(() => videos.map((video) => withDerivedMetrics(video)), [videos]);
  const hasEnoughForScore = viewsAvailable && derived.length >= MIN_VIDEOS_FOR_SCORE;
  const scored = useMemo(() => (hasEnoughForScore ? computePlatformCompositeScores(derived) : []), [derived, hasEnoughForScore]);
  const bestVideos = useMemo(() => [...scored].sort((a, b) => b.performance_score - a.performance_score).slice(0, 10), [scored]);

  const totalViews = derived.reduce((sum, v) => sum + v.views, 0);
  const totalLikes = derived.reduce((sum, v) => sum + v.likes, 0);
  const totalComments = derived.reduce((sum, v) => sum + v.comments, 0);
  const totalShares = derived.reduce((sum, v) => sum + v.shares, 0);
  const totalSaves = derived.reduce((sum, v) => sum + v.saves, 0);
  const reachValues = derived.filter((v) => v.reach !== null).map((v) => v.reach as number);
  const totalReach = reachValues.reduce((sum, value) => sum + value, 0);
  const avgVpd = derived.length ? Math.round(derived.reduce((sum, v) => sum + v.views_per_day, 0) / derived.length) : 0;
  const avgEr = derived.length ? derived.reduce((sum, v) => sum + v.engagement_rate, 0) / derived.length : 0;

  return (
    <>
      {!viewsAvailable ? (
        <div className="alert informational">
          <strong>Instagram nie udostępnił statystyk wyświetleń.</strong>{" "}
          Liczby wyświetleń, tempo wzrostu, engagement i ranking są ukryte, zamiast pokazywać mylące zera. Dodaj uprawnienie
          <code> instagram_manage_insights</code> do aktywnej konfiguracji Meta i połącz konto ponownie.
        </div>
      ) : null}
      <StatsGrid>
        <StatCard label="Materiały" value={String(derived.length)} hint="wszystkie zsynchronizowane" tooltip="Liczba publikacji zwróconych przez połączone platformy i zapisanych w RCC." featured />
        <StatCard label="Wyświetlenia" value={viewsAvailable ? compact(totalViews) : "Brak danych"} hint={viewsAvailable ? "suma" : "brak uprawnienia Insights"} tooltip="Suma liczników views/plays zwróconych przez platformę. Zasięg nie jest traktowany jako wyświetlenia." />
        {reachValues.length > 0 ? <StatCard label="Zasięg" value={compact(totalReach)} hint={`${reachValues.length} materiałów`} tooltip="Suma unikalnego zasięgu tylko dla materiałów, dla których platforma udostępniła metrykę reach." /> : null}
        <StatCard label="Polubienia" value={compact(totalLikes)} hint="suma" tooltip="Suma publicznych liczników polubień z ostatnich migawek." />
        <StatCard label="Komentarze" value={compact(totalComments)} hint="suma" tooltip="Suma liczników komentarzy z ostatnich migawek." />
        {totalShares > 0 ? <StatCard label="Udostępnienia" value={compact(totalShares)} hint="suma" tooltip="Suma udostępnień zwróconych w dostępnych insights." /> : null}
        {totalSaves > 0 ? <StatCard label="Zapisy" value={compact(totalSaves)} hint="suma" tooltip="Suma zapisów zwróconych w dostępnych insights." /> : null}
        <StatCard label="Śr. wyśw./dzień" value={viewsAvailable ? compact(avgVpd) : "Brak danych"} hint={viewsAvailable ? "na materiał" : "wymaga Insights"} tooltip="Średnia z: liczba wyświetleń materiału ÷ liczba dni od publikacji (minimum jeden dzień)." />
        <StatCard label="Śr. engagement" value={viewsAvailable ? `${avgEr.toFixed(2)}%` : "Brak danych"} hint={viewsAvailable ? "(polubienia + komentarze) ÷ wyświetlenia" : "bez wyświetleń nie da się policzyć"} tooltip="Średnia arytmetyczna wskaźnika (polubienia + komentarze) ÷ wyświetlenia × 100 dla materiałów w bieżącym zestawie." />
      </StatsGrid>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">RANKING</p>
            <h2>Najlepsze materiały</h2>
            <p className="muted">
              Wynik = 50% znorm. wyświetleń/dzień + 30% znorm. engagementu + 20% znorm. wyświetleń.{" "}
              <strong>Wynik względny w tym zestawie materiałów.</strong>
            </p>
          </div>
          <Link href="/faq/punktacja" className="buttonLink">Jak działa punktacja? →</Link>
        </div>
        <RankedVideoList
          items={bestVideos.map((video) => ({
            ...video,
            youtube_video_id: video.external_id,
            ranking_key: `${video.platform}:${video.external_id}`,
          }))}
          highlightTopN={3}
          hrefBuilder={(item) => `/platforms/${item.platform}/videos/${item.youtube_video_id}`}
          emptyMessage={
            !viewsAvailable
              ? "Ranking pojawi się po udostępnieniu statystyk wyświetleń."
              : hasEnoughForScore ? "Brak materiałów." : `Za mało materiałów (min. ${MIN_VIDEOS_FOR_SCORE}), aby obliczyć wiarygodny ranking.`
          }
          renderMeta={(video) => <PlatformBadge platform={video.platform} />}
          renderMetrics={(video) => (
            <>
              <span>{compact(video.views)} wyśw.</span>
              <span>{video.views_per_day.toLocaleString("pl-PL")}/dzień</span>
              <span>{video.engagement_rate.toFixed(2)}% ER</span>
              <AudienceGain platform={video.platform} value={video.followers_gained} />
            </>
          )}
          renderBadge={(video) => (
            <span className="performanceBadge good" title="Wynik względny w bieżącym zestawie materiałów">
              {Math.round(video.performance_score)}/100
            </span>
          )}
          renderExtra={(video) => <ScoreBreakdownDetails breakdown={video.score_breakdown} />}
          renderActions={(video) => (video.url ? <ExternalLink href={video.url} label="Otwórz oryginał" /> : null)}
        />
      </section>

      <section className="libraryPanel">
        <div className="libraryHeading">
          <div>
            <p className="eyebrow">PRZEGLĄD</p>
            <h2>Wszystkie materiały</h2>
            <p className="muted">Kliknij nagłówek kolumny, aby zmienić sortowanie.</p>
          </div>
        </div>
        <PlatformVideoTableSection videos={videos} />
      </section>
    </>
  );
}
