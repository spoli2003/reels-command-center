import Link from "next/link";

import { AppShell } from "../components/app-shell";
import { ExternalLink } from "../components/external-link";
import { PlatformBadge } from "../components/platform-badge";
import { PlatformStatusBar } from "../components/platform-status-bar";
import { RankedVideoList } from "../components/ranked-video-list";
import { RecommendationCard } from "../components/recommendation-card";
import { StatCard, StatsGrid } from "../components/stat-card";
import { SyncStatusLine } from "../components/sync-status-line";
import { createPlatformApi, createPlatformOverviewApi, PLATFORM_LABELS, platformPath, type PlatformKey } from "../lib/platform-api";
import { aggregateCommentInboxes, aggregatePlatformMetrics } from "../lib/dashboard-aggregation";
import { withDerivedMetrics as withPlatformDerivedMetrics } from "../lib/platform-metrics";
import { createYoutubeApi } from "../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
const META_PLATFORM_ICONS: Record<Extract<PlatformKey, "facebook" | "instagram">, string> = { facebook: "f", instagram: "◎" };

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export default async function Home() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const platformOverviewApi = createPlatformOverviewApi(INTERNAL_API_URL);
  const allPlatformsApi = createPlatformApi(INTERNAL_API_URL, "all");
  const facebookApi = createPlatformApi(INTERNAL_API_URL, "facebook");
  const instagramApi = createPlatformApi(INTERNAL_API_URL, "instagram");
  const [summary, status, report, videos, youtubeComments, facebookComments, instagramComments, platformSummaries, allPlatformVideos] = await Promise.all([
    api.getSummary(),
    api.getStatus(),
    api.getIntelligence(),
    api.getVideos(),
    api.getComments({ sort: "newest" }),
    facebookApi.getComments({ sort: "newest" }),
    instagramApi.getComments({ sort: "newest" }),
    platformOverviewApi.listPlatforms(),
    allPlatformsApi.getVideos(),
  ]);
  const metaPlatforms = platformSummaries.filter(
    (item): item is typeof item & { platform: "facebook" | "instagram" } => item.platform === "facebook" || item.platform === "instagram",
  );
  const commentInbox = aggregateCommentInboxes(youtubeComments, facebookComments, instagramComments);
  const platformMetrics = aggregatePlatformMetrics(allPlatformVideos, platformSummaries);
  const newestComment = commentInbox.threads[0] ?? null;
  const newQuestions = commentInbox.threads.filter(
    (thread) => thread.is_likely_question && (thread.conversation_state === "new" || thread.conversation_state === "waiting"),
  );
  const recentlyActive = [...commentInbox.threads].sort((a, b) => +new Date(b.last_message_at) - +new Date(a.last_message_at)).slice(0, 3);
  const discussionCountByVideo = new Map<string, { title: string; count: number; href: string }>();
  for (const thread of commentInbox.threads) {
    const key = `${thread.platform}:${thread.external_id}`;
    const existing = discussionCountByVideo.get(key);
    discussionCountByVideo.set(key, { title: thread.video_title, count: (existing?.count ?? 0) + 1, href: thread.href });
  }
  const mostDiscussedVideo = [...discussionCountByVideo.entries()].sort((a, b) => b[1].count - a[1].count)[0] ?? null;
  const synchronizedPlatformCount = new Set(allPlatformVideos.map((video) => video.platform)).size;
  const breakdown = (field: "materials" | "views" | "interactions" | "comments" | "audience") =>
    (["youtube", "facebook", "instagram"] as PlatformKey[]).map((platform) => ({
      label: PLATFORM_LABELS[platform],
      value:
        field === "views" && !platformMetrics.byPlatform[platform].viewsAvailable
          ? "Brak dostępu"
          : platformMetrics.byPlatform[platform][field] === null
            ? "Brak danych"
            : compact(platformMetrics.byPlatform[platform][field] as number),
      href: platformPath(platform),
      tone: platform,
    }));

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
      <PlatformStatusBar />

      {allPlatformVideos.length === 0 ? (
        <>
          <div className="emptyState">
            <h3>Zacznij od połączenia kanału</h3>
            <p>Połącz konto w osobnej sekcji Synchronizacja, aby odblokować dashboard, porównania i rekomendacje.</p>
            <Link className="primaryButton" href="/synchronization">Przejdź do synchronizacji →</Link>
          </div>
        </>
      ) : (
        <>
          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">WSZYSTKIE PLATFORMY</p>
                <h2>Wyniki wszystkich platform</h2>
              </div>
              <Link className="textLink" href="/platforms/all">
                Otwórz widok zbiorczy →
              </Link>
            </div>
            <StatsGrid>
              <StatCard label="Wyświetlenia" value={compact(platformMetrics.total.views)} hint="suma platform z dostępną metryką" featured breakdown={breakdown("views")} />
              <StatCard label="Społeczność" value={platformMetrics.total.audience === null ? "Brak danych" : compact(platformMetrics.total.audience)} hint="subskrybenci + obserwujący (nieunikalni)" breakdown={breakdown("audience")} />
              <StatCard label="Komentarze" value={compact(platformMetrics.total.comments)} hint="pod wszystkimi materiałami" breakdown={breakdown("comments")} />
              <StatCard label="Materiały" value={compact(platformMetrics.total.materials)} hint={`${synchronizedPlatformCount} platformy z danymi`} breakdown={breakdown("materials")} />
              <StatCard label="Interakcje" value={compact(platformMetrics.total.interactions)} hint="polubienia, komentarze, udostępnienia i zapisy" breakdown={breakdown("interactions")} />
            </StatsGrid>
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">SPOŁECZNOŚĆ</p>
                <h2>Czy są komentarze wymagające uwagi?</h2>
              </div>
              <nav className="communityPlatformLinks" aria-label="Komentarze według platformy">
                <Link href="/youtube/community">YouTube</Link>
                <Link href="/platforms/facebook/community">Facebook</Link>
                <Link href="/platforms/instagram/community">Instagram</Link>
              </nav>
            </div>
            <StatsGrid>
              <StatCard
                label="Wymagają odpowiedzi"
                value={String(commentInbox.summary.awaiting_reply_count)}
                hint={`${commentInbox.summary.new_count} nowych · ${commentInbox.summary.waiting_count} czeka`}
                featured={commentInbox.summary.awaiting_reply_count > 0}
              />
              <StatCard label="Nowe pytania" value={String(newQuestions.length)} hint="bez odpowiedzi kanału" />
              <StatCard label="Rozwiązane" value={String(commentInbox.summary.resolved_count)} hint="ostatnie słowo należy do kanału" />
              <StatCard label="Ostatnie (7 dni)" value={String(commentInbox.summary.recent_count)} hint="nowe komentarze" />
            </StatsGrid>

            {mostDiscussedVideo ? (
              <p className="muted" style={{ marginTop: 14 }}>
                Najwięcej komentarzy zebrał film{" "}
                <Link href={mostDiscussedVideo[1].href}>{mostDiscussedVideo[1].title}</Link> ({mostDiscussedVideo[1].count}{" "}
                {mostDiscussedVideo[1].count === 1 ? "wątek" : "wątków"}).
              </p>
            ) : null}

            {recentlyActive.length > 0 ? (
              <div style={{ marginTop: 14 }}>
                <p className="muted" style={{ marginBottom: 8 }}>
                  Ostatnio aktywne dyskusje:
                </p>
                <div className="dailyBriefLinks">
                  {recentlyActive.map((thread) => (
                    <p key={thread.platform_thread_id}>
                      <span className={`commentPlatformBadge ${thread.platform}`}>{META_PLATFORM_ICONS[thread.platform as "facebook" | "instagram"] ?? "▶"}</span>{" "}
                      <Link href={thread.href}>
                        {thread.text_original.length > 70 ? `${thread.text_original.slice(0, 69)}…` : thread.text_original}
                      </Link>{" "}
                      — {thread.author_display_name}
                    </p>
                  ))}
                </div>
              </div>
            ) : null}

            {newestComment ? null : (
              <p className="muted" style={{ marginTop: 14 }}>
                Brak zaimportowanych komentarzy — uruchom synchronizację komentarzy w Skrzynce komentarzy.
              </p>
            )}
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
                <RecommendationCard recommendation={report.winning_videos[0]} platform="youtube" />
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
                <RecommendationCard recommendation={report.follow_up_opportunities[0] ?? report.content_recommendations[0]} platform="youtube" />
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

          <section className="libraryPanel">
              <div className="libraryHeading">
                <div>
                  <p className="eyebrow">PLATFORMY</p>
                  <h2>Przegląd platform</h2>
                </div>
              </div>
              <div className="platformOverview">
                <Link href="/platforms/youtube" className={`platformCard${summary ? " connected" : " soon"}`}>
                  <span className="platformIcon">▶</span>
                  <div>
                    <strong>YouTube</strong>
                    <p>
                      {summary ? `${summary.total_videos} filmów · ${compact(summary.total_views)} wyświetleń` : "Połącz, aby zacząć synchronizację"}
                    </p>
                  </div>
                  <span className={`pill${summary ? " success" : ""}`}>{summary ? "Połączono" : "Połącz"}</span>
                </Link>
                {metaPlatforms.map((platformSummary) => (
                  <Link
                    key={platformSummary.platform}
                    href={platformPath(platformSummary.platform)}
                    className={`platformCard${platformSummary.connected ? " connected" : " soon"}`}
                  >
                    <span className="platformIcon">{META_PLATFORM_ICONS[platformSummary.platform]}</span>
                    <div>
                      <strong>{PLATFORM_LABELS[platformSummary.platform]}</strong>
                      <p>{platformSummary.connected ? (platformSummary.display_name ?? "Połączono") : "Połącz, aby zacząć synchronizację"}</p>
                    </div>
                    <span className={`pill${platformSummary.connected ? " success" : ""}`}>
                      {platformSummary.connected ? "Połączono" : "Połącz"}
                    </span>
                  </Link>
                ))}
                <div className="platformCard soon">
                  <span className="platformIcon">♪</span>
                  <div>
                    <strong>TikTok</strong>
                    <p>Integracja w przygotowaniu</p>
                  </div>
                  <span className="pill">Wkrótce</span>
                </div>
              </div>
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
              items={[...allPlatformVideos]
                .sort((a, b) => +new Date(b.published_at ?? 0) - +new Date(a.published_at ?? 0))
                .slice(0, 5)
                .map((video) => ({ ...withPlatformDerivedMetrics(video), youtube_video_id: video.external_id, ranking_key: `${video.platform}:${video.external_id}` }))}
              hrefBuilder={(video) => `/platforms/${video.platform}/videos/${video.youtube_video_id}`}
              emptyMessage="Brak materiałów."
              renderMeta={(video) => <PlatformBadge platform={video.platform} />}
              renderMetrics={(video) => (
                <>
                  <span>{compact(video.views)} wyśw.</span>
                  <span>{video.views_per_day.toLocaleString("pl-PL")}/dzień</span>
                  <span>{video.engagement_rate.toFixed(2)}% ER</span>
                </>
              )}
              renderActions={(video) => (video.url ? <ExternalLink href={video.url} label="Otwórz oryginał" /> : null)}
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
              <Link className="quickActionCard" href="/youtube/community">
                <strong>💬 Skrzynka komentarzy</strong>
                <span>Przeglądaj i odpowiadaj na komentarze</span>
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
