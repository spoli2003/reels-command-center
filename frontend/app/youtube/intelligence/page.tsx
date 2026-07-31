import Link from "next/link";

import { AppShell } from "../../../components/app-shell";
import { PlatformExperienceHeader } from "../../../components/platform-experience-header";
import { RecommendationList } from "../../../components/recommendation-card";
import { StatCard, StatsGrid } from "../../../components/stat-card";
import { TopicCard } from "../../../components/topic-card";
import { createPlatformOverviewApi, type PlatformKeyOrAll } from "../../../lib/platform-api";
import { createYoutubeApi } from "../../../lib/youtube-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export default async function CreatorIntelligencePage() {
  const api = createYoutubeApi(INTERNAL_API_URL);
  const [report, summaries] = await Promise.all([api.getIntelligence(), createPlatformOverviewApi(INTERNAL_API_URL).listPlatforms()]);
  const connected: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const item of summaries) connected[item.platform] = item.connected;

  return (
    <AppShell active="/youtube">
      <PlatformExperienceHeader platform="youtube" section="intelligence" connected={connected} title="Co dalej? — YouTube" description="Rekomendacje oparte wyłącznie na Twoich danych historycznych — bez AI i bez porównań z konkurencją." />

      {!report ? (
        <div className="emptyState">
          <h3>Brak danych</h3>
          <p>Połącz i zsynchronizuj kanał YouTube ze strony głównej, aby zobaczyć rekomendacje.</p>
        </div>
      ) : (
        <>
          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">DZIŚ</p>
                <h2>Codzienny brief</h2>
              </div>
            </div>
            <StatsGrid>
              <StatCard
                label="Wyświetlenia (24h)"
                value={report.daily_brief.views_gained_24h !== null ? `+${compact(report.daily_brief.views_gained_24h)}` : "Brak danych"}
                tooltip="Suma przyrostu wyświetleń wszystkich filmów między najnowszą synchronizacją a najbliższą sprzed 24h. Wymaga co najmniej dwóch synchronizacji w tym oknie czasowym."
                featured
              />
              <StatCard
                label="Subskrybenci (24h)"
                value={
                  report.daily_brief.subscribers_gained_24h !== null
                    ? `${report.daily_brief.subscribers_gained_24h > 0 ? "+" : ""}${report.daily_brief.subscribers_gained_24h}`
                    : "Brak danych"
                }
                tooltip="Zmiana liczby subskrybentów w ciągu ostatnich 24h. Śledzenie subskrybentów w czasie ruszyło razem z tą funkcją — historia buduje się dopiero od teraz."
              />
              <StatCard label="Filmy wymagające uwagi" value={String(report.daily_brief.attention_video_count)} hint="zobacz sekcję poniżej" />
              <StatCard
                label="Dni od ostatniej publikacji"
                value={report.daily_brief.days_since_last_upload !== null ? String(report.daily_brief.days_since_last_upload) : "Brak danych"}
              />
            </StatsGrid>
            {report.daily_brief.no_upload_warning ? <div className="alert">{report.daily_brief.no_upload_warning}</div> : null}
            <div className="dailyBriefLinks">
              {report.daily_brief.best_growing_video ? (
                <p>
                  📈 Najlepiej rośnie:{" "}
                  <Link href={`/youtube/videos/${report.daily_brief.best_growing_video.youtube_video_id}`}>
                    {report.daily_brief.best_growing_video.title}
                  </Link>
                  {report.daily_brief.best_growing_video_gain !== null ? ` (+${compact(report.daily_brief.best_growing_video_gain)} wyświetleń)` : ""}
                </p>
              ) : null}
              {report.daily_brief.biggest_slowdown_video ? (
                <p>
                  📉 Największe spowolnienie:{" "}
                  <Link href={`/youtube/videos/${report.daily_brief.biggest_slowdown_video.youtube_video_id}`}>
                    {report.daily_brief.biggest_slowdown_video.title}
                  </Link>
                  {report.daily_brief.biggest_slowdown_delta !== null ? ` (${report.daily_brief.biggest_slowdown_delta.toFixed(0)} wyśw./dzień)` : ""}
                </p>
              ) : null}
            </div>
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">WYRÓŻNIONE</p>
                <h2>Najlepsze filmy — dlaczego wygrywają</h2>
              </div>
            </div>
            <RecommendationList recommendations={report.winning_videos} emptyMessage="Za mało filmów, aby wskazać zwycięzców." />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">JAKOŚĆ</p>
                <h2>Filmy wymagające uwagi</h2>
                {report.too_new_count > 0 ? <p className="muted">{report.too_new_count} filmów pominięto — zbyt nowe, by rzetelnie ocenić.</p> : null}
              </div>
            </div>
            <RecommendationList recommendations={report.attention_videos} emptyMessage="Żaden film nie odstaje istotnie od mediany kanału — dobra robota." />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">POMYSŁY</p>
                <h2>Warto kontynuować</h2>
              </div>
            </div>
            <RecommendationList recommendations={report.follow_up_opportunities} emptyMessage="Za mało danych, aby wskazać kandydatów do kontynuacji." />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">TEMATY</p>
                <h2>Inteligencja tematyczna</h2>
                <p className="muted">
                  Tematy wykrywane automatycznie na podstawie powtarzających się słów kluczowych w tytułach — nie z góry narzuconej listy
                  kategorii, więc dopasowują się do każdego kanału.
                </p>
              </div>
            </div>
            {report.topics.length === 0 ? (
              <div className="emptyState">
                <h3>Brak danych</h3>
                <p>Za mało powtarzających się słów kluczowych w tytułach.</p>
              </div>
            ) : (
              <div className="topicsGrid">
                {report.topics.slice(0, 12).map((topic) => (
                  <TopicCard key={topic.keyword} topic={topic} />
                ))}
              </div>
            )}
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">PUBLIKACJE</p>
                <h2>Kiedy publikować</h2>
              </div>
            </div>
            <StatsGrid>
              <StatCard
                label="Najlepszy dzień tygodnia"
                value={report.publishing.best_weekday ?? "Brak danych"}
                hint={report.publishing.best_weekday_median_vpd ? `mediana ${compact(report.publishing.best_weekday_median_vpd)} wyśw./dzień` : undefined}
              />
              <StatCard
                label="Najlepsza godzina"
                value={report.publishing.best_hour !== null ? `${report.publishing.best_hour}:00` : "Brak danych"}
                hint={report.publishing.best_hour_median_vpd ? `mediana ${compact(report.publishing.best_hour_median_vpd)} wyśw./dzień` : undefined}
              />
              <StatCard
                label="Najlepsza częstotliwość"
                value={report.publishing.best_cadence_label ?? "Brak danych"}
                hint={report.publishing.best_cadence_median_vpd ? `mediana ${compact(report.publishing.best_cadence_median_vpd)} wyśw./dzień` : undefined}
              />
            </StatsGrid>
            {report.publishing.best_streak_start ? (
              <p className="muted">
                Najlepsza seria publikacji: {report.publishing.best_streak_start} – {report.publishing.best_streak_end} (
                {report.publishing.best_streak_video_count} filmów, śr. {report.publishing.best_streak_avg_vpd?.toFixed(0)} wyśw./dzień).
              </p>
            ) : null}
            {report.publishing.worst_streak_start ? (
              <p className="muted">
                Najsłabsza seria publikacji: {report.publishing.worst_streak_start} – {report.publishing.worst_streak_end} (
                {report.publishing.worst_streak_video_count} filmów, śr. {report.publishing.worst_streak_avg_vpd?.toFixed(0)} wyśw./dzień).
              </p>
            ) : null}
            {report.publishing.insufficient_data_notes.map((note) => (
              <p key={note} className="muted">
                {note}
              </p>
            ))}
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">TYTUŁY</p>
                <h2>Inteligencja tytułów</h2>
              </div>
            </div>
            <RecommendationList recommendations={report.title_patterns} emptyMessage="Za mało danych, aby porównać wzorce tytułów." />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">SYNTEZA</p>
                <h2>Rekomendacje treściowe</h2>
              </div>
            </div>
            <RecommendationList recommendations={report.content_recommendations} emptyMessage="Za mało danych, aby wygenerować rekomendacje." />
          </section>
        </>
      )}
    </AppShell>
  );
}
