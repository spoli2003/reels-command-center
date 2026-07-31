import Link from "next/link";

import { ConfidenceBadge } from "./confidence-badge";
import { truncateTitle } from "../lib/youtube-metrics";
import type { PlatformKey, PlatformRecommendation } from "../lib/platform-api";

/** Same layout/classes as RecommendationCard (components/recommendation-card.tsx)
 * — links into /platforms/{platform}/videos/{id} instead of /youtube/videos/{id}. */
export function PlatformRecommendationCard({ platform, recommendation }: { platform: PlatformKey; recommendation: PlatformRecommendation }) {
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
              key={video.external_id}
              href={`/platforms/${platform}/videos/${video.external_id}`}
              className="recommendationVideoChip"
              title={video.title}
            >
              {video.thumbnail_url ? <img src={video.thumbnail_url} alt="" /> : <div className="recommendationVideoChipPlaceholder" />}
              <span>{truncateTitle(video.title, 40)}</span>
            </Link>
          ))}
        </div>
      ) : null}
    </article>
  );
}

export function PlatformRecommendationList({
  platform,
  recommendations,
  emptyMessage,
}: {
  platform: PlatformKey;
  recommendations: PlatformRecommendation[];
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
        <PlatformRecommendationCard key={recommendation.id} platform={platform} recommendation={recommendation} />
      ))}
    </div>
  );
}
