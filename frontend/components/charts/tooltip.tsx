"use client";

import { CHART_TOKENS } from "./theme";

type Entry = {
  name?: string;
  value?: number | string;
  color?: string;
  payload?: Record<string, unknown>;
};

export function RccTooltip({
  active,
  label,
  payload,
  valueFormatter = (value: number) => value.toLocaleString("pl-PL"),
}: {
  active?: boolean;
  label?: string | number;
  payload?: Entry[];
  valueFormatter?: (value: number) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      style={{
        background: CHART_TOKENS.tooltipBg,
        border: `1px solid ${CHART_TOKENS.tooltipBorder}`,
        borderRadius: 10,
        padding: "10px 12px",
        fontSize: 12,
        color: CHART_TOKENS.textPrimary,
        boxShadow: "0 12px 30px rgba(0,0,0,.35)",
      }}
    >
      {label !== undefined ? (
        <div style={{ color: CHART_TOKENS.textSecondary, marginBottom: 6, fontSize: 11 }}>{label}</div>
      ) : null}
      {payload.map((entry, index) => (
        <div key={index} style={{ display: "flex", alignItems: "center", gap: 8, padding: "2px 0" }}>
          <span style={{ width: 10, height: 2, background: entry.color, display: "inline-block", borderRadius: 2 }} />
          <strong style={{ color: CHART_TOKENS.textPrimary }}>
            {typeof entry.value === "number" ? valueFormatter(entry.value) : entry.value}
          </strong>
          <span style={{ color: CHART_TOKENS.textSecondary }}>{entry.name}</span>
        </div>
      ))}
    </div>
  );
}
