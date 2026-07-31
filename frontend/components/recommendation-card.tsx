import Link from "next/link";

import { ConfidenceBadge } from "./confidence-badge";
import { PlatformBadge } from "./platform-badge";
import type { PlatformKey } from "../lib/platform-api";
import { truncateTitle } from "../lib/youtube-metrics";
import type { RecommendationData } from "../lib/youtube-api";

export function RecommendationCard({ recommendation, platform = "youtube" }: { recommendation: RecommendationData; platform?: PlatformKey }) {
  return (
    <article className="recommendationCard">
      <div className="recommendationHeader">
        <h4>{recommendation.headline}</h4>
        <ConfidenceBadge confidence={recommendation.confidence} />
      </div>
      <p>{recommendation.explanation}</p>
      {recommendation.supporting_videos.length > 0 ? (
        <div className="recommendationVideos">
          {recommendation.supporting_videos.map((video) => (
            <Link
              key={video.youtube_video_id}
              href={`/youtube/videos/${video.youtube_video_id}`}
              className="recommendationVideoChip"
              title={video.title}
            >
              <span className="recommendationVideoThumb">
                {video.thumbnail_url ? <img src={video.thumbnail_url} alt="" /> : <span className="recommendationVideoChipPlaceholder" />}
                <span className={`recommendationPlatformMark ${platform}`} aria-hidden="true">
                  {platform === "youtube" ? "▶" : platform === "facebook" ? "f" : "◎"}
                </span>
              </span>
              <span className="recommendationVideoCopy">
                <PlatformBadge platform={platform} />
                <strong>{truncateTitle(video.title, 64)}</strong>
                <small>Otwórz materiał →</small>
              </span>
            </Link>
          ))}
        </div>
      ) : null}
    </article>
  );
}

export function RecommendationList({
  recommendations,
  emptyMessage,
}: {
  recommendations: RecommendationData[];
  emptyMessage: string;
}) {
  if (recommendations.length === 0) {
    return (
      <div className="emptyState">
        <h3>Brak danych</h3>
        <p>{emptyMessage}</p>
      </div>
    );
  }
  return (
    <div className="recommendationList">
      {recommendations.map((recommendation) => (
        <RecommendationCard key={recommendation.id} recommendation={recommendation} platform="youtube" />
      ))}
    </div>
  );
}
