import Link from "next/link";
import type { ReactNode } from "react";

import { truncateTitle } from "../lib/youtube-metrics";

export type RankedVideoItem = {
  youtube_video_id: string;
  title: string;
  thumbnail_url: string | null;
  published_at: string;
};

export function RankedVideoList<T extends RankedVideoItem>({
  items,
  renderMetrics,
  renderBadge,
  renderExtra,
  renderActions,
  highlightTopN = 0,
  emptyMessage,
}: {
  items: T[];
  renderMetrics: (item: T) => ReactNode;
  renderBadge?: (item: T) => ReactNode;
  renderExtra?: (item: T) => ReactNode;
  /** Rendered as a SIBLING of the internal Link (never nested inside it) — for external links etc. */
  renderActions?: (item: T) => ReactNode;
  highlightTopN?: number;
  emptyMessage: string;
}) {
  if (items.length === 0) {
    return (
      <div className="emptyState">
        <h3>Brak danych</h3>
        <p>{emptyMessage}</p>
      </div>
    );
  }
  return (
    <div className="rankedList">
      {items.map((item, index) => {
        const isTop = index < highlightTopN;
        return (
          <div key={item.youtube_video_id} className={isTop ? "rankedRow topRanked" : "rankedRow"}>
            <div className="rankedRowMain">
              <Link href={`/youtube/videos/${item.youtube_video_id}`} className="rankedRowLink">
                <span className="rank">
                  {String(index + 1).padStart(2, "0")}
                  {isTop ? <span className="rankTag">Czołowy wynik</span> : null}
                </span>
                {item.thumbnail_url ? (
                  <img className="rankedThumb" src={item.thumbnail_url} alt="" />
                ) : (
                  <div className="rankedThumb placeholder" />
                )}
                <div className="rankedInfo">
                  <strong title={item.title}>{truncateTitle(item.title)}</strong>
                  <p>{new Date(item.published_at).toLocaleDateString("pl-PL")}</p>
                </div>
                <div className="rankedMetrics">{renderMetrics(item)}</div>
                {renderBadge ? <div className="rankedBadge">{renderBadge(item)}</div> : null}
              </Link>
              {renderActions ? <div className="rankedActions">{renderActions(item)}</div> : null}
            </div>
            {renderExtra ? <div className="rankedExtra">{renderExtra(item)}</div> : null}
          </div>
        );
      })}
    </div>
  );
}
