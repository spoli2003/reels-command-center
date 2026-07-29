import { TOO_NEW_DAYS, type BaselineMetric, type ChannelBaseline } from "../lib/youtube-metrics";

function formatMetricValue(key: BaselineMetric["key"], value: number): string {
  if (key === "engagement_rate") return `${value.toFixed(2)}%`;
  return Math.round(value).toLocaleString("pl-PL");
}

function diffTone(percentDiff: number | null): "positive" | "negative" | "neutral" {
  if (percentDiff === null) return "neutral";
  if (percentDiff >= 10) return "positive";
  if (percentDiff <= -10) return "negative";
  return "neutral";
}

export function ChannelBaselineView({ baseline }: { baseline: ChannelBaseline }) {
  if (baseline.status !== "ok") {
    return (
      <div className="emptyState">
        <h3>Za mało danych</h3>
        <p>{baseline.message}</p>
      </div>
    );
  }
  return (
    <div className="baselineList">
      <p className="muted">
        Porównanie z medianą {baseline.comparableCount} porównywalnych filmów kanału (starszych niż {TOO_NEW_DAYS} dni).
      </p>
      {baseline.metrics.map((metric) => (
        <div key={metric.key} className="baselineRow">
          <span className="baselineLabel">{metric.label}</span>
          <span className="baselineValue">{formatMetricValue(metric.key, metric.videoValue)}</span>
          <span className="baselineMedian">
            mediana: {metric.channelMedian !== null ? formatMetricValue(metric.key, metric.channelMedian) : "Brak danych"}
          </span>
          <span className={`baselineDiff ${diffTone(metric.percentDiff)}`}>
            {metric.percentDiff !== null ? `${metric.percentDiff > 0 ? "+" : ""}${metric.percentDiff}%` : "—"}
          </span>
          <span className="baselineInterpretation">{metric.interpretation}</span>
        </div>
      ))}
    </div>
  );
}
