import Link from "next/link";

import type { ScoreBreakdown } from "../lib/content-score";

function formatRaw(key: string, value: number) {
  if (key === "engagement") return `${value.toFixed(2)}%`;
  return Math.round(value).toLocaleString("pl-PL");
}

export function ScoreBreakdownDetails({ breakdown, score = breakdown.total, defaultOpen = false }: { breakdown: ScoreBreakdown; score?: number; defaultOpen?: boolean }) {
  return (
    <details className="scoreBreakdown" open={defaultOpen}>
      <summary><span>Dlaczego {Math.round(score)} pkt?</span><span className="scoreBreakdownHint">Pokaż składowe</span></summary>
      <p className="scoreBreakdownIntro">Wynik jest względny: ten materiał porównano z {breakdown.scope_size} materiałami w bieżącym zestawie.</p>
      <div className="scoreComponentList">
        {breakdown.components.map((component) => (
          <div className="scoreComponent" key={component.key}>
            <div className="scoreComponentHeading"><strong>{component.label}</strong><span>{Math.round(component.weight * 100)}% wyniku</span></div>
            <div className="scoreComponentFacts">
              <span>Wartość: <strong>{formatRaw(component.key, component.raw_value)}</strong></span>
              <span>Po normalizacji: <strong>{Math.round(component.normalized)}/100</strong></span>
            </div>
            <div className="scoreProgress" aria-label={`${component.label}: ${Math.round(component.normalized)} na 100`}>
              <span style={{ width: `${Math.max(0, Math.min(100, component.normalized))}%` }} />
            </div>
            <div className="scorePointImpact">
              <span className="scoreAdded">+{component.points_added.toFixed(1)} pkt dodane</span>
              <span className="scoreLost">−{component.points_lost.toFixed(1)} pkt do maksimum</span>
            </div>
          </div>
        ))}
      </div>
      <div className="scoreBreakdownFooter"><strong>Razem: {Math.round(breakdown.total)}/100</strong><Link href="/faq/punktacja">Jak działa punktacja? →</Link></div>
    </details>
  );
}
