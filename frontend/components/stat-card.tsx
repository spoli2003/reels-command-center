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
}: {
  label: string;
  value: string;
  hint?: string;
  /** Native hover tooltip with the exact calculation — supplements (never replaces) the visible hint. */
  tooltip?: string;
  featured?: boolean;
}) {
  return (
    <article className={featured ? "metricCard featured" : "metricCard"} title={tooltip}>
      <span>
        {label}
        {tooltip ? <span className="statInfoMark" aria-hidden="true">ⓘ</span> : null}
      </span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </article>
  );
}
