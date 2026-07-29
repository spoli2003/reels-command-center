import Link from "next/link";

import { truncateTitle, type Suggestion } from "../lib/youtube-metrics";

function formatNumber(value: number) {
  return value.toLocaleString("pl-PL");
}

export function SuggestionsList({ suggestions }: { suggestions: Suggestion[] }) {
  return (
    <div className="suggestionsList">
      {suggestions.map((suggestion) => {
        if ("unavailable" in suggestion) {
          return (
            <div key={suggestion.id} className="suggestionCard unavailable">
              <p className="muted">{suggestion.reason}</p>
            </div>
          );
        }

        if (suggestion.kind === "best-performer") {
          return (
            <div key={suggestion.id} className="suggestionCard">
              <p>{suggestion.text}</p>
              <p className="suggestionStat">
                <Link href={`/youtube/videos/${suggestion.videoId}`} title={suggestion.videoTitle}>
                  {truncateTitle(suggestion.videoTitle)}
                </Link>{" "}
                · {formatNumber(suggestion.viewsPerDay)} wyświetleń/dzień
              </p>
            </div>
          );
        }

        if (suggestion.kind === "weekday") {
          return (
            <div key={suggestion.id} className="suggestionCard">
              <p>{suggestion.text}</p>
              <p className="suggestionStat">
                Mediana: {formatNumber(suggestion.weekdayMedianVpd)} vs mediana kanału {formatNumber(suggestion.channelMedianVpd)} wyświetleń/dzień
                (na podstawie {suggestion.sampleCount} filmów)
              </p>
            </div>
          );
        }

        return (
          <div key={suggestion.id} className="suggestionCard">
            <p>{suggestion.text}</p>
            <p className="suggestionStat">
              {suggestion.matchCount} filmów · mediana {formatNumber(suggestion.keywordMedianVpd)} vs mediana kanału{" "}
              {formatNumber(suggestion.channelMedianVpd)} wyświetleń/dzień ({suggestion.percentDiff > 0 ? "+" : ""}
              {suggestion.percentDiff}%)
            </p>
            <div className="suggestionSources">
              {suggestion.sampleVideos.map((video) => (
                <Link key={video.id} href={`/youtube/videos/${video.id}`} title={video.title}>
                  {truncateTitle(video.title, 30)}
                </Link>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
