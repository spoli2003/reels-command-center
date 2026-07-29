"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart as RLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { BRAND_ACCENT, CHART_TOKENS, compactNumber, seriesColor } from "./theme";
import { RccTooltip } from "./tooltip";

export type LineSeries = { key: string; label: string; color?: string };

export function LineChartViz({
  data,
  xKey,
  series,
  height = 260,
}: {
  data: Array<Record<string, unknown>>;
  xKey: string;
  series: LineSeries[];
  height?: number;
}) {
  const singleSeries = series.length === 1;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RLineChart data={data} margin={{ top: 6, right: 12, left: -8, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={CHART_TOKENS.grid} />
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
        <Tooltip content={<RccTooltip />} cursor={{ stroke: CHART_TOKENS.axis, strokeWidth: 1 }} />
        {!singleSeries ? <Legend wrapperStyle={{ fontSize: 12, color: CHART_TOKENS.textSecondary }} /> : null}
        {series.map((item, index) => (
          <Line
            key={item.key}
            type="monotone"
            dataKey={item.key}
            name={item.label}
            stroke={item.color ?? (singleSeries ? BRAND_ACCENT : seriesColor(index))}
            strokeWidth={2}
            dot={{ r: 4, strokeWidth: 2, stroke: "#0c1320" }}
            activeDot={{ r: 6, strokeWidth: 2, stroke: "#0c1320" }}
          />
        ))}
      </RLineChart>
    </ResponsiveContainer>
  );
}
