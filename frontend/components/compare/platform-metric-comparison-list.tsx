import Link from "next/link";

import { truncateTitle } from "../../lib/youtube-metrics";
import type { PlatformKey } from "../../lib/platform-api";

export type PlatformComparisonItem = {
  external_id: string;
  title: string;
  thumbnail_url: string | null;
  value: number;
};

/** Mirrors components/compare/metric-comparison-list.tsx exactly, linking into
 * /platforms/{platform}/videos/{id} instead of /youtube/videos/{id}. */
export function PlatformMetricComparisonList({
  platform,
  title,
  explanation,
  items,
  formatValue,
}: {
  platform: PlatformKey;
  title: string;
  explanation?: string;
  items: PlatformComparisonItem[];
  formatValue: (value: number) => string;
}) {
  const sorted = [...items].sort((a, b) => b.value - a.value);
  const winner = sorted[0];
  const second = sorted[1];
  const max = winner?.value ?? 0;
  const average = items.length ? items.reduce((sum, item) => sum + item.value, 0) / items.length : 0;
  const sortedValues = [...items.map((i) => i.value)].sort((a, b) => a - b);
  const setMedian = sortedValues.length
    ? sortedValues.length % 2
      ? sortedValues[(sortedValues.length - 1) / 2]
      : (sortedValues[sortedValues.length / 2 - 1] + sortedValues[sortedValues.length / 2]) / 2
    : 0;

  return (
    <div className="metricComparison">
      <h4 title={explanation}>{title}</h4>
      {winner ? (
        <p className="metricComparisonSummary">
          Zwycięzca: <strong title={winner.title}>{truncateTitle(winner.title, 34)}</strong> — {formatValue(winner.value)}
          {second ? <> (przewaga {formatValue(winner.value - second.value)} nad kolejnym)</> : null}
        </p>
      ) : null}
      <p className="metricComparisonBaselines">
        <span>Śr. porównywanych: {formatValue(average)}</span>
        <span>Mediana porównywanych: {formatValue(setMedian)}</span>
      </p>
      <div className="metricComparisonList">
        {sorted.map((item, index) => (
          <Link key={item.external_id} href={`/platforms/${platform}/videos/${item.external_id}`} className={index === 0 ? "metricRow winner" : "metricRow"}>
            {item.thumbnail_url ? <img className="metricRowThumb" src={item.thumbnail_url} alt="" /> : <div className="metricRowThumb placeholder" />}
            <span className="metricRowTitle" title={item.title}>
              {index === 0 ? <span className="metricRowWinnerTag">Zwycięzca</span> : null}
              {truncateTitle(item.title, 30)}
            </span>
            <div className="metricRowBar">
              <div className="metricRowBarFill" style={{ width: max ? `${(item.value / max) * 100}%` : "0%" }} />
            </div>
            <span className="metricRowValue">{formatValue(item.value)}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
