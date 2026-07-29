"use client";

import { Bar, BarChart as RBarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { BRAND_ACCENT, CHART_TOKENS, compactNumber, seriesColor } from "./theme";
import { RccTooltip } from "./tooltip";

export type BarSeries = { key: string; label: string; color?: string };

export function BarChartViz({
  data,
  xKey,
  series,
  layout = "vertical",
  height = 260,
}: {
  data: Array<Record<string, unknown>>;
  xKey: string;
  series: BarSeries[];
  layout?: "vertical" | "horizontal";
  height?: number;
}) {
  const singleSeries = series.length === 1;
  const isHorizontalBars = layout === "horizontal";
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RBarChart
        data={data}
        layout={isHorizontalBars ? "vertical" : "horizontal"}
        margin={{ top: 6, right: 16, left: isHorizontalBars ? 8 : -8, bottom: 0 }}
      >
        <CartesianGrid horizontal={!isHorizontalBars} vertical={isHorizontalBars} stroke={CHART_TOKENS.grid} />
        {isHorizontalBars ? (
          <>
            <XAxis
              type="number"
              stroke={CHART_TOKENS.axis}
              tick={{ fill: CHART_TOKENS.textSecondary, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => compactNumber(value)}
            />
            <YAxis
              dataKey={xKey}
              type="category"
              stroke={CHART_TOKENS.axis}
              tick={{ fill: CHART_TOKENS.textSecondary, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={140}
              tickFormatter={(value: string) => (value.length > 22 ? `${value.slice(0, 22)}…` : value)}
            />
          </>
        ) : (
          <>
            <XAxis
              dataKey={xKey}
              stroke={CHART_TOKENS.axis}
              tick={{ fill: CHART_TOKENS.textSecondary, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: CHART_TOKENS.axis }}
            />
            <YAxis
              stroke={CHART_TOKENS.axis}
              tick={{ fill: CHART_TOKENS.textSecondary, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => compactNumber(value)}
              width={48}
            />
          </>
        )}
        <Tooltip content={<RccTooltip />} cursor={{ fill: "rgba(255,255,255,.04)" }} />
        {!singleSeries ? <Legend wrapperStyle={{ fontSize: 12, color: CHART_TOKENS.textSecondary }} /> : null}
        {series.map((item, index) => (
          <Bar
            key={item.key}
            dataKey={item.key}
            name={item.label}
            fill={item.color ?? (singleSeries ? BRAND_ACCENT : seriesColor(index))}
            radius={isHorizontalBars ? [0, 4, 4, 0] : [4, 4, 0, 0]}
            maxBarSize={24}
          />
        ))}
      </RBarChart>
    </ResponsiveContainer>
  );
}
