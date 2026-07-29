import type { Insight } from "../lib/youtube-metrics";

export function InsightsList({ insights }: { insights: Insight[] }) {
  return (
    <div className="suggestionsList">
      {insights.map((insight) => (
        <div key={insight.id} className="suggestionCard">
          <p>{insight.text}</p>
        </div>
      ))}
    </div>
  );
}
