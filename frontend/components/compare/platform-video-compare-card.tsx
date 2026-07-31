import Link from "next/link";

import { truncateTitle } from "../../lib/youtube-metrics";
import type { PlatformScoredVideo } from "../../lib/platform-metrics";

export function PlatformVideoCompareCard({ video, showScore }: { video: PlatformScoredVideo; showScore: boolean }) {
  return (
    <article className="compareCard">
      <Link href={`/platforms/${video.platform}/videos/${video.external_id}`} title={video.title} className="compareCardThumbLink">
        {video.thumbnail_url ? <img className="compareCardThumb" src={video.thumbnail_url} alt="" /> : <div className="compareCardThumb placeholder" />}
      </Link>
      <div className="compareCardBody">
        <div className="compareCardTitleRow">
          <Link href={`/platforms/${video.platform}/videos/${video.external_id}`} title={video.title}>
            <strong>{truncateTitle(video.title, 56)}</strong>
          </Link>
          {video.url ? (
            <a className="externalIconLink" href={video.url} target="_blank" rel="noopener noreferrer" title="Otwórz oryginał" aria-label="Otwórz oryginał">
              <span aria-hidden="true">↗</span>
            </a>
          ) : null}
        </div>
        <p className="muted">{video.published_at ? new Date(video.published_at).toLocaleDateString("pl-PL") : "—"}</p>
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
