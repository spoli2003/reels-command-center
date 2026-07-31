import { AppShell } from "../../../components/app-shell";
import { SCORE_COMPONENTS } from "../../../lib/content-score";

export default function ScoringFaqPage() {
  return (
    <AppShell active="/faq/punktacja">
      <header className="topbar">
        <div>
          <p className="eyebrow">FAQ / METODOLOGIA</p>
          <h1>Jak działa punktacja?</h1>
          <p className="muted scoringFaqLead">Przejrzysty opis wyniku widocznego przy materiałach w RCC.</p>
        </div>
      </header>

      <section className="libraryPanel faqSection">
        <p className="eyebrow">WZÓR</p>
        <h2>Trzy składniki, maksymalnie 100 punktów</h2>
        <div className="scoringFormulaGrid">
          {SCORE_COMPONENTS.map((component) => (
            <article className="scoringFormulaCard" key={component.key}>
              <strong>{component.label}</strong>
              <span>{Math.round(component.weight * 100)}% wyniku</span>
            </article>
          ))}
        </div>
        <p className="formulaCode">wynik = tempo × 0,50 + engagement × 0,30 + wyświetlenia × 0,20</p>
      </section>

      <section className="libraryPanel faqSection">
        <p className="eyebrow">NORMALIZACJA</p>
        <h2>Jak różne liczby trafiają na skalę 0–100?</h2>
        <p>
          Każdą składową porównujemy z minimum i maksimum w aktualnym zestawie materiałów. Stosujemy wzór min–max:
        </p>
        <p className="formulaCode">(wartość − minimum) ÷ (maksimum − minimum) × 100</p>
        <p className="muted">
          Gdy wszystkie materiały mają identyczną wartość danej składowej, każdy otrzymuje za nią 100 punktów znormalizowanych. Nie zmienia to ich kolejności.
        </p>
      </section>

      <section className="libraryPanel faqSection">
        <p className="eyebrow">PRZYKŁAD</p>
        <h2>Skąd może się wziąć wynik 58?</h2>
        <div className="scoringExample">
          <span>Tempo: 70 × 50% = <strong>35 pkt</strong></span>
          <span>Engagement: 50 × 30% = <strong>15 pkt</strong></span>
          <span>Wyświetlenia: 40 × 20% = <strong>8 pkt</strong></span>
          <strong>Razem: 58/100</strong>
        </div>
      </section>

      <section className="libraryPanel faqSection">
        <p className="eyebrow">OGRANICZENIA</p>
        <h2>Czego ten wynik nie oznacza?</h2>
        <ul className="faqList">
          <li>Jest względny dla aktualnego zestawu i filtrów, a nie uniwersalny dla całego internetu.</li>
          <li>Nie dowodzi przyczyn sukcesu, jakości merytorycznej ani wartości biznesowej materiału.</li>
          <li>Normalizacja min–max jest wrażliwa na skrajne wyniki; ranking pokazujemy dopiero od 3 materiałów.</li>
          <li>Pozyskani obserwujący lub subskrybenci nie wpływają obecnie na punktację.</li>
          <li>Jeśli API nie udostępnia metryki dla pojedynczego materiału, RCC pokazuje „brak danych” i niczego nie szacuje.</li>
        </ul>
      </section>
    </AppShell>
  );
}
