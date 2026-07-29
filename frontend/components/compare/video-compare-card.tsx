import Link from "next/link";

import { PerformanceLabelBadge } from "../performance-label-badge";
import { ExternalLink, youtubeWatchUrl } from "../external-link";
import { truncateTitle, type ScoredVideo } from "../../lib/youtube-metrics";

export function VideoCompareCard({ video, showScore }: { video: ScoredVideo; showScore: boolean }) {
  return (
    <article className="compareCard">
      <Link href={`/youtube/videos/${video.youtube_video_id}`} title={video.title} className="compareCardThumbLink">
        {video.thumbnail_url ? (
          <img className="compareCardThumb" src={video.thumbnail_url} alt="" />
        ) : (
          <div className="compareCardThumb placeholder" />
        )}
      </Link>
      <div className="compareCardBody">
        <div className="compareCardTitleRow">
          <Link href={`/youtube/videos/${video.youtube_video_id}`} title={video.title}>
            <strong>{truncateTitle(video.title, 56)}</strong>
          </Link>
          <ExternalLink href={youtubeWatchUrl(video.youtube_video_id)} label="Obejrzyj na YouTube" />
        </div>
        <PerformanceLabelBadge label={video.performance_label} />
        <p className="muted">{new Date(video.published_at).toLocaleDateString("pl-PL")}</p>
        <dl className="compareCardStats">
          <div>
            <dt>Wyświetlenia</dt>
            <dd>{video.views.toLocaleString("pl-PL")}</dd>
          </div>
          <div>
            <dt>Wyśw./dzień</dt>
            <dd>{video.views_per_day.toLocaleString("pl-PL")}</dd>
          </div>
          <div>
            <dt>Polubienia</dt>
            <dd>{video.likes.toLocaleString("pl-PL")}</dd>
          </div>
          <div>
            <dt>Komentarze</dt>
            <dd>{video.comments.toLocaleString("pl-PL")}</dd>
          </div>
          <div>
            <dt>Engagement</dt>
            <dd>{video.engagement_rate.toFixed(2)}%</dd>
          </div>
        </dl>
        {showScore ? (
          <div className="compareCardScore">
            Wynik: <strong>{Math.round(video.performance_score)}</strong>/100
          </div>
        ) : null}
      </div>
    </article>
  );
}
