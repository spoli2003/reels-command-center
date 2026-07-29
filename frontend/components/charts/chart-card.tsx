import type { ReactNode } from "react";

export function ChartCard({
  title,
  subtitle,
  isEmpty,
  emptyMessage,
  children,
}: {
  title: string;
  subtitle?: string;
  isEmpty?: boolean;
  emptyMessage?: string;
  children: ReactNode;
}) {
  return (
    <div className="chartCard">
      <div className="chartCardHeader">
        <h3>{title}</h3>
        {subtitle ? <p className="muted">{subtitle}</p> : null}
      </div>
      {isEmpty ? (
        <div className="chartEmpty">{emptyMessage ?? "Brak danych do wyświetlenia."}</div>
      ) : (
        <div className="chartCardBody">{children}</div>
      )}
    </div>
  );
}
