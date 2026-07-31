import type { ReactNode } from "react";

export function StatsGrid({ children }: { children: ReactNode }) {
  return <section className="statsGrid">{children}</section>;
}

export function StatCard({
  label,
  value,
  hint,
  tooltip,
  featured,
  breakdown,
}: {
  label: string;
  value: string;
  hint?: string;
  /** Native hover tooltip with the exact calculation — supplements (never replaces) the visible hint. */
  tooltip?: string;
  featured?: boolean;
  breakdown?: { label: string; value: string; href?: string; tone?: string }[];
}) {
  return (
    <article className={featured ? "metricCard featured" : "metricCard"} title={tooltip}>
      <span>
        {label}
        {tooltip ? <span className="statInfoMark" aria-hidden="true">ⓘ</span> : null}
      </span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
      {breakdown?.length ? (
        <div className="metricBreakdown">
          {breakdown.map((item) =>
            item.href ? (
              <a key={item.label} href={item.href} className={item.tone}>
                <span>{item.label}</span><b>{item.value}</b>
              </a>
            ) : (
              <div key={item.label} className={item.tone}>
                <span>{item.label}</span><b>{item.value}</b>
              </div>
            ),
          )}
        </div>
      ) : null}
    </article>
  );
}
