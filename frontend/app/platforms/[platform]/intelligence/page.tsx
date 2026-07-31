import { notFound } from "next/navigation";

import { AppShell } from "../../../../components/app-shell";
import { PlatformExperienceHeader } from "../../../../components/platform-experience-header";
import { PlatformRecommendationList } from "../../../../components/platform-recommendation-card";
import { PlatformTopicCard } from "../../../../components/platform-topic-card";
import { StatCard, StatsGrid } from "../../../../components/stat-card";
import {
  createPlatformApi,
  createPlatformOverviewApi,
  PLATFORM_LABELS,
  type PlatformKey,
  type PlatformKeyOrAll,
} from "../../../../lib/platform-api";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
const REAL_PLATFORMS: PlatformKey[] = ["youtube", "facebook", "instagram"];

function compact(value: number) {
  return new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export default async function PlatformIntelligencePage({ params }: { params: Promise<{ platform: string }> }) {
  const { platform } = await params;
  if (!REAL_PLATFORMS.includes(platform as PlatformKey)) notFound();
  const key = platform as PlatformKey;

  const overviewApi = createPlatformOverviewApi(INTERNAL_API_URL);
  const summaries = await overviewApi.listPlatforms();
  const connected: Partial<Record<PlatformKeyOrAll, boolean>> = {};
  for (const summary of summaries) connected[summary.platform] = summary.connected;

  const api = createPlatformApi(INTERNAL_API_URL, key);
  const report = await api.getIntelligence();
  const needsConnect = key !== "youtube" && connected[key] === false;

  return (
    <AppShell active="/platforms">
      <PlatformExperienceHeader platform={key} section="intelligence" connected={connected} title={`Co dalej? — ${PLATFORM_LABELS[key]}`} description="Rekomendacje oparte wyłącznie na Twoich danych historycznych — bez AI i bez porównań z konkurencją." />

      {needsConnect ? (
        <div className="emptyState"><h3>{PLATFORM_LABELS[key]} nie jest połączony</h3><p>Połącz konto w sekcji Synchronizacja, aby zobaczyć rekomendacje.</p></div>
      ) : !report ? (
        <div className="emptyState">
          <h3>Brak danych</h3>
          <p>Połącz i zsynchronizuj {PLATFORM_LABELS[key]}, aby zobaczyć rekomendacje.</p>
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
                tooltip="Suma przyrostu wyświetleń wszystkich materiałów między najnowszą synchronizacją a najbliższą sprzed 24h."
                featured
              />
              <StatCard label="Materiały wymagające uwagi" value={String(report.daily_brief.attention_video_count)} hint="zobacz sekcję poniżej" />
              <StatCard
                label="Dni od ostatniej publikacji"
                value={report.daily_brief.days_since_last_upload !== null ? String(report.daily_brief.days_since_last_upload) : "Brak danych"}
              />
            </StatsGrid>
            {report.daily_brief.no_upload_warning ? <div className="alert">{report.daily_brief.no_upload_warning}</div> : null}
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">WYRÓŻNIONE</p>
                <h2>Najlepsze materiały — dlaczego wygrywają</h2>
              </div>
            </div>
            <PlatformRecommendationList platform={key} recommendations={report.winning_videos} emptyMessage="Za mało materiałów, aby wskazać zwycięzców." />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">JAKOŚĆ</p>
                <h2>Materiały wymagające uwagi</h2>
                {report.too_new_count > 0 ? <p className="muted">{report.too_new_count} pominięto — zbyt nowe, by rzetelnie ocenić.</p> : null}
              </div>
            </div>
            <PlatformRecommendationList
              platform={key}
              recommendations={report.attention_videos}
              emptyMessage="Żaden materiał nie odstaje istotnie od mediany — dobra robota."
            />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">POMYSŁY</p>
                <h2>Warto kontynuować</h2>
              </div>
            </div>
            <PlatformRecommendationList
              platform={key}
              recommendations={report.follow_up_opportunities}
              emptyMessage="Za mało danych, aby wskazać kandydatów do kontynuacji."
            />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">TEMATY</p>
                <h2>Inteligencja tematyczna</h2>
                <p className="muted">Tematy wykrywane automatycznie na podstawie powtarzających się słów kluczowych w tytułach.</p>
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
                  <PlatformTopicCard key={topic.keyword} platform={key} topic={topic} />
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
            <PlatformRecommendationList platform={key} recommendations={report.title_patterns} emptyMessage="Za mało danych, aby porównać wzorce tytułów." />
          </section>

          <section className="libraryPanel">
            <div className="libraryHeading">
              <div>
                <p className="eyebrow">SYNTEZA</p>
                <h2>Rekomendacje treściowe</h2>
              </div>
            </div>
            <PlatformRecommendationList
              platform={key}
              recommendations={report.content_recommendations}
              emptyMessage="Za mało danych, aby wygenerować rekomendacje."
            />
          </section>
        </>
      )}
    </AppShell>
  );
}
