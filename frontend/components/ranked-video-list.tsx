import Link from "next/link";
import type { ReactNode } from "react";

import { truncateTitle } from "../lib/youtube-metrics";

export type RankedVideoItem = {
  youtube_video_id: string;
  ranking_key?: string;
  title: string;
  thumbnail_url: string | null;
  published_at: string | null;
};

export function RankedVideoList<T extends RankedVideoItem>({
  items,
  renderMetrics,
  renderBadge,
  renderMeta,
  renderExtra,
  renderActions,
  highlightTopN = 0,
  emptyMessage,
  hrefBuilder,
}: {
  items: T[];
  renderMetrics: (item: T) => ReactNode;
  renderBadge?: (item: T) => ReactNode;
  renderMeta?: (item: T) => ReactNode;
  renderExtra?: (item: T) => ReactNode;
  /** Rendered as a SIBLING of the internal Link (never nested inside it) — for external links etc. */
  renderActions?: (item: T) => ReactNode;
  highlightTopN?: number;
  emptyMessage: string;
  /** Defaults to /youtube/videos/{id} — overridden by generic platform pages
   * (Facebook/Instagram use /platforms/{platform}/videos/{id}). */
  hrefBuilder?: (item: T) => string;
}) {
  const buildHref = hrefBuilder ?? ((item: T) => `/youtube/videos/${item.youtube_video_id}`);
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
          <div key={item.ranking_key ?? item.youtube_video_id} className={isTop ? "rankedRow topRanked" : "rankedRow"}>
            <div className="rankedRowMain">
              <Link href={buildHref(item)} className="rankedRowLink">
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
                  <div className="rankedInfoMeta">
                    <span>{item.published_at ? new Date(item.published_at).toLocaleDateString("pl-PL") : "Data: brak danych"}</span>
                    {renderMeta ? renderMeta(item) : null}
                  </div>
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
