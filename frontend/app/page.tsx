import Link from "next/link";

import { AppShell } from "../components/app-shell";
import { ExternalLink, youtubeWatchUrl } from "../components/external-link";
import { RankedVideoList } from "../components/ranked-video-list";
import { RecommendationCard } from "../components/recommendation-card";
import { StatCard, StatsGrid } from "../components/stat-card";
import { SyncStatusLine } from "../components/sync-status-line";
import { YoutubePanel } from "../components/youtube-panel";
import { createYoutubeApi } from "../lib/youtube-api";
import { withDerivedMetrics } from "../lib/youtube-metrics";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export default async function Home() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const [summary, status, report, videos] = await Promise.all([
    api.getSummary(),
    api.getStatus(),
    api.getIntelligence(),
    api.getVideos(),
  ]);

  return (
    <AppShell active="/">
      <header className="topbar">
        <div>
          <p className="eyebrow">359° / CENTRUM DOWODZENIA</p>
          <h1>Centrum dowodzenia</h1>
          <p className="muted">
            {summary && videos.length > 0 ? (
              <>
                {summary.channel_title} · <SyncStatusLine status={status} />
              </>
            ) : (
              "Połącz kanał YouTube poniżej, aby odblokować dashboard, porównania i rekomendacje."
            )}
          </p>
        </div>
        {summary && videos.length > 0 ? (
          <Link className="primaryButton" href="/youtube/intelligence">
            Co dalej? →
          </Link>
        ) : null}
      </header>

      {!summary || videos.length === 0 ? (
        <>
          <div className="emptyState">
            <h3>Zacznij od połączenia kanału</h3>
            <p>Połącz konto YouTube poniżej, aby odblokować dashboard, porównania i rekomendacje oparte na Twoich danych.</p>
          </div>
          <YoutubePanel />
        </>
      ) : (
        <>
          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">DZIŚ</p>
                <h2>Podsumowanie dnia</h2>
              </div>
            </div>
            <StatsGrid>
              <StatCard
                label="Wyświetlenia (24h)"
                value={
                  report?.daily_brief.views_gained_24h !== null && report?.daily_brief.views_gained_24h !== undefined
                    ? `+${compact(report.daily_brief.views_gained_24h)}`
                    : "Brak danych"
                }
                tooltip="Suma przyrostu wyświetleń wszystkich filmów między najnowszą synchronizacją a najbliższą sprzed 24h."
                featured
              />
              <StatCard label="Subskrybenci" value={compact(summary.subscriber_count)} hint="cały kanał" />
              <StatCard
                label="Filmy wymagające uwagi"
                value={String(report?.daily_brief.attention_video_count ?? 0)}
                hint="zobacz sekcję Co dalej?"
              />
              <StatCard
                label="Dni od ostatniej publikacji"
                value={
                  report?.daily_brief.days_since_last_upload !== null && report?.daily_brief.days_since_last_upload !== undefined
                    ? String(report.daily_brief.days_since_last_upload)
                    : "Brak danych"
                }
              />
            </StatsGrid>
            {report?.daily_brief.no_upload_warning ? <div className="alert">{report.daily_brief.no_upload_warning}</div> : null}
          </section>

          <section className="homeSplitGrid">
            <div className="libraryPanel">
              <div className="libraryHeading">
                <div>
                  <p className="eyebrow">WYRÓŻNIONE</p>
                  <h2>Najlepszy film</h2>
                </div>
              </div>
              {report && report.winning_videos.length > 0 ? (
                <RecommendationCard recommendation={report.winning_videos[0]} />
              ) : (
                <div className="emptyState">
                  <h3>Brak danych</h3>
                  <p>Za mało filmów, aby wskazać zwycięzcę.</p>
                </div>
              )}
            </div>
            <div className="libraryPanel">
              <div className="libraryHeading">
                <div>
                  <p className="eyebrow">SZANSA</p>
                  <h2>Największa okazja</h2>
                </div>
              </div>
              {report && (report.follow_up_opportunities[0] || report.content_recommendations[0]) ? (
                <RecommendationCard recommendation={report.follow_up_opportunities[0] ?? report.content_recommendations[0]} />
              ) : (
                <div className="emptyState">
                  <h3>Brak danych</h3>
                  <p>Za mało danych, aby wskazać okazję.</p>
                </div>
              )}
              <Link className="textLink" href="/youtube/intelligence" style={{ display: "inline-block", marginTop: 12 }}>
                Zobacz wszystkie rekomendacje →
              </Link>
            </div>
          </section>

          <section className="homeSplitGrid">
            <div className="libraryPanel">
              <div className="libraryHeading">
                <div>
                  <p className="eyebrow">PLATFORMY</p>
                  <h2>Przegląd platform</h2>
                </div>
              </div>
              <div className="platformOverview">
                <div className="platformCard connected">
                  <span className="platformIcon">▶</span>
                  <div>
                    <strong>YouTube</strong>
                    <p>
                      {summary.total_videos} filmów · {compact(summary.total_views)} wyświetleń
                    </p>
                  </div>
                  <span className="pill success">Połączono</span>
                </div>
                <div className="platformCard soon">
                  <span className="platformIcon">f</span>
                  <div>
                    <strong>Facebook</strong>
                    <p>Integracja w przygotowaniu</p>
                  </div>
                  <span className="pill">Wkrótce</span>
                </div>
                <div className="platformCard soon">
                  <span className="platformIcon">◎</span>
                  <div>
                    <strong>Instagram</strong>
                    <p>Integracja w przygotowaniu</p>
                  </div>
                  <span className="pill">Wkrótce</span>
                </div>
                <div className="platformCard soon">
                  <span className="platformIcon">♪</span>
                  <div>
                    <strong>TikTok</strong>
                    <p>Integracja w przygotowaniu</p>
                  </div>
                  <span className="pill">Wkrótce</span>
                </div>
              </div>
            </div>
            <YoutubePanel />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">OSTATNIE</p>
                <h2>Ostatnio opublikowane</h2>
              </div>
              <Link className="textLink" href="/videos">
                Zobacz bibliotekę →
              </Link>
            </div>
            <RankedVideoList
              items={[...videos]
                .sort((a, b) => +new Date(b.published_at) - +new Date(a.published_at))
                .slice(0, 5)
                .map((video) => withDerivedMetrics(video))}
              emptyMessage="Brak filmów."
              renderMetrics={(video) => (
                <>
                  <span>{compact(video.views)} wyśw.</span>
                  <span>{video.views_per_day.toLocaleString("pl-PL")}/dzień</span>
                  <span>{video.engagement_rate.toFixed(2)}% ER</span>
                </>
              )}
              renderActions={(video) => <ExternalLink href={youtubeWatchUrl(video.youtube_video_id)} label="Obejrzyj na YouTube" />}
            />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">SKRÓTY</p>
                <h2>Szybkie akcje</h2>
              </div>
            </div>
            <div className="quickActions">
              <Link className="quickActionCard" href="/youtube">
                <strong>📊 Dashboard analityczny</strong>
                <span>Pełne statystyki, wykresy i rankingi</span>
              </Link>
              <Link className="quickActionCard" href="/youtube/compare">
                <strong>⚖️ Porównaj filmy</strong>
                <span>Zestaw do 6 filmów obok siebie</span>
              </Link>
              <Link className="quickActionCard" href="/youtube/intelligence">
                <strong>💡 Co dalej?</strong>
                <span>Rekomendacje oparte na Twoich danych</span>
              </Link>
              <Link className="quickActionCard" href="/videos">
                <strong>🎞️ Biblioteka filmów</strong>
                <span>Przeglądaj i filtruj wszystkie filmy</span>
              </Link>
            </div>
          </section>
        </>
      )}
    </AppShell>
  );
}
