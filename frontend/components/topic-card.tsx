import Link from "next/link";

import { truncateTitle } from "../lib/youtube-metrics";
import type { TopicSummary } from "../lib/youtube-api";

const TREND_META: Record<string, { label: string; icon: string; tone: string }> = {
  accelerating: { label: "Przyspiesza", icon: "▲", tone: "positive" },
  steady: { label: "Stabilny", icon: "▶", tone: "neutral" },
  slowing: { label: "Zwalnia", icon: "▼", tone: "warning" },
  declining: { label: "Spada", icon: "▼", tone: "negative" },
  insufficient_data: { label: "Za mało danych", icon: "•", tone: "neutral" },
};

export function TopicCard({ topic }: { topic: TopicSummary }) {
  const sameVideo = topic.worst_video && topic.best_video && topic.worst_video.youtube_video_id === topic.best_video.youtube_video_id;
  const trend = TREND_META[topic.trend] ?? { label: topic.trend, icon: "•", tone: "neutral" };
  return (
    <article className="topicCard">
      <div className="topicCardHeader">
        <h4>„{topic.keyword}”</h4>
        <span className="topicCardCount">{topic.video_count} filmów</span>
      </div>
      <dl className="topicCardStats">
        <div>
          <dt>Mediana wyśw.</dt>
          <dd>{topic.median_views.toLocaleString("pl-PL")}</dd>
        </div>
        <div>
          <dt>Mediana wyśw./dzień</dt>
          <dd>{topic.median_views_per_day.toLocaleString("pl-PL")}</dd>
        </div>
        <div>
          <dt>Mediana engagement</dt>
          <dd>{topic.median_engagement.toFixed(2)}%</dd>
        </div>
        <div>
          <dt>Trend</dt>
          <dd className={`trendValue ${trend.tone}`}>
            <span aria-hidden="true">{trend.icon}</span> {trend.label}
          </dd>
        </div>
      </dl>
      <div className="topicCardVideos">
        {topic.best_video ? (
          <Link href={`/youtube/videos/${topic.best_video.youtube_video_id}`} title={topic.best_video.title}>
            🏆 Najlepszy: {truncateTitle(topic.best_video.title, 32)}
          </Link>
        ) : null}
        {topic.worst_video && !sameVideo ? (
          <Link href={`/youtube/videos/${topic.worst_video.youtube_video_id}`} title={topic.worst_video.title}>
            Najsłabszy: {truncateTitle(topic.worst_video.title, 32)}
          </Link>
        ) : null}
      </div>
    </article>
  );
}
