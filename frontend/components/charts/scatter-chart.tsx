"use client";

import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart as RScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";

import { BRAND_ACCENT, CHART_TOKENS, compactNumber } from "./theme";
import { RccTooltip } from "./tooltip";

export function ScatterChartViz({
  data,
  xKey,
  yKey,
  nameKey,
  xLabel,
  yLabel,
  height = 300,
}: {
  data: Array<Record<string, unknown>>;
  xKey: string;
  yKey: string;
  nameKey: string;
  xLabel: string;
  yLabel: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RScatterChart margin={{ top: 6, right: 16, left: -8, bottom: 4 }}>
        <CartesianGrid stroke={CHART_TOKENS.grid} />
        <XAxis
          dataKey={xKey}
          type="number"
          name={xLabel}
          stroke={CHART_TOKENS.axis}
          tick={{ fill: CHART_TOKENS.textSecondary, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: CHART_TOKENS.axis }}
          tickFormatter={(value: number) => compactNumber(value)}
          label={{ value: xLabel, position: "insideBottom", offset: -4, fill: CHART_TOKENS.textSecondary, fontSize: 11 }}
        />
        <YAxis
          dataKey={yKey}
          type="number"
          name={yLabel}
          stroke={CHART_TOKENS.axis}
          tick={{ fill: CHART_TOKENS.textSecondary, fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(value: number) => compactNumber(value)}
          width={48}
        />
        <ZAxis dataKey={nameKey} name="Tytuł" />
        <Tooltip
          cursor={{ strokeDasharray: "0" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const point = payload[0]?.payload as Record<string, unknown> | undefined;
            if (!point) return null;
            return (
              <RccTooltip
                active
                label={String(point[nameKey] ?? "")}
                payload={[
                  { name: xLabel, value: Number(point[xKey]), color: BRAND_ACCENT },
                  { name: yLabel, value: Number(point[yKey]), color: BRAND_ACCENT },
                ]}
              />
            );
          }}
        />
        <Scatter data={data} fill={BRAND_ACCENT} fillOpacity={0.85} />
      </RScatterChart>
    </ResponsiveContainer>
  );
}
