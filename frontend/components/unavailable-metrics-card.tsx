const UNAVAILABLE_METRICS = [
  "Subskrybenci zyskani/utraceni (przypisani do tego filmu)",
  "Udostępnienia",
  "Ulubione",
  "Czas oglądania",
  "Średni czas oglądania",
  "CTR (kliknięcia miniatury)",
  "Wyświetlenia miniatury (impressions)",
  "Źródła ruchu",
];

/** Sprint 5 / Part 4 — never fabricate unavailable metrics; say plainly why. */
export function UnavailableMetricsCard() {
  return (
    <section className="libraryPanel">
      <div className="libraryHeading">
        <div>
          <p className="eyebrow">NIEDOSTĘPNE</p>
          <h2>Metryki niedostępne w tej integracji</h2>
        </div>
      </div>
      <div className="emptyState">
        <h3>Wymaga YouTube Analytics API</h3>
        <p>
          RCC korzysta obecnie wyłącznie z <strong>YouTube Data API v3</strong>, który udostępnia tylko wyświetlenia, polubienia i
          komentarze. Poniższe metryki wymagają osobnej integracji z YouTube Analytics API (inny zakres OAuth) i nie są jeszcze
          zaimplementowane — nie są tu pokazywane żadne przybliżone ani zerowe wartości.
        </p>
        <ul className="unavailableMetricsList">
          {UNAVAILABLE_METRICS.map((metric) => (
            <li key={metric}>{metric}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
