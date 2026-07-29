import Link from "next/link";

import { truncateTitle } from "../../lib/youtube-metrics";

export type ComparisonItem = {
  youtube_video_id: string;
  title: string;
  thumbnail_url: string | null;
  value: number;
};

export function MetricComparisonList({
  title,
  subtitle,
  explanation,
  items,
  formatValue,
  channelMedian,
  channelAverage,
  channelBest,
}: {
  title: string;
  subtitle?: string;
  /** Shown as a tooltip on the metric title — what the metric means / how it's calculated. */
  explanation?: string;
  items: ComparisonItem[];
  formatValue: (value: number) => string;
  /** Median/average/best-ever across the WHOLE channel (not just the compared set) — Sprint 5 / Part 5. */
  channelMedian?: number;
  channelAverage?: number;
  channelBest?: number;
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
      {subtitle ? <p className="muted">{subtitle}</p> : null}
      {winner ? (
        <p className="metricComparisonSummary">
          Zwycięzca: <strong title={winner.title}>{truncateTitle(winner.title, 34)}</strong> — {formatValue(winner.value)}
          {second ? (
            <>
              {" "}
              (przewaga {formatValue(winner.value - second.value)} nad kolejnym filmem)
            </>
          ) : null}
        </p>
      ) : null}
      <p className="metricComparisonBaselines">
        <span>Śr. porównywanych: {formatValue(average)}</span>
        <span>Mediana porównywanych: {formatValue(setMedian)}</span>
        {channelMedian !== undefined ? <span>Mediana kanału: {formatValue(channelMedian)}</span> : null}
        {channelAverage !== undefined ? <span>Średnia kanału: {formatValue(channelAverage)}</span> : null}
        {channelBest !== undefined ? <span>Najlepszy wynik w historii kanału: {formatValue(channelBest)}</span> : null}
      </p>
      <div className="metricComparisonList">
        {sorted.map((item, index) => (
          <Link
            key={item.youtube_video_id}
            href={`/youtube/videos/${item.youtube_video_id}`}
            className={index === 0 ? "metricRow winner" : "metricRow"}
          >
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
