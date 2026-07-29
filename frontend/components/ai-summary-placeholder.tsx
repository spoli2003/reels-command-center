/** Sprint 5 / Parts 9 & 10 — reserved space for the future AI Engine. Never
 * generates text itself; the exact required placeholder copy only. */
export function AiSummaryPlaceholder() {
  return (
    <section className="libraryPanel">
      <div className="libraryHeading">
        <div>
          <p className="eyebrow">AI</p>
          <h2>Podsumowanie AI</h2>
        </div>
      </div>
      <div className="emptyState">
        <p>Analiza AI będzie dostępna po wdrożeniu silnika AI.</p>
        <p className="muted">
          W przyszłości ta sekcja pokaże: wyjaśnienie wyniku filmu w prostym języku, dlaczego osiągnął taki wynik, mocne i słabe strony,
          sugerowane filmy kontynuujące temat oraz pomysły na tytuły i hooki — zawsze wyłącznie na podstawie liczb obliczonych
          deterministycznie powyżej, nigdy wymyślonych.
        </p>
      </div>
    </section>
  );
}
