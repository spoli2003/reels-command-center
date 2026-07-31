"""Generic Creator Intelligence adapter — Release 0.8.0 (ADR-020 / ADR-007).

Converts unified ContentVideo/Publication/MetricSnapshot rows into the
platform-agnostic ContentItem shape and runs them through the SAME
`services/intelligence/engine.py` YouTube already uses (ADR-007: the engine
never imports a platform-specific model). This is the second real adapter that
engine was designed for — Facebook and Instagram get the daily brief,
winning/attention videos, topic clustering, publishing patterns, and
recommendations for free, with zero changes inside intelligence/.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import MetricSnapshot, Publication
from app.services.intelligence import engine
from app.services.intelligence.content_metrics import bucket_history
from app.services.intelligence.types import ContentItem, SnapshotPoint


def _build_content_items(db: Session, platform: str) -> list[ContentItem]:
    publications = db.scalars(select(Publication).where(Publication.platform == platform)).all()
    items: list[ContentItem] = []
    for publication in publications:
        snapshots = db.scalars(
            select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id).order_by(MetricSnapshot.captured_at.asc())
        ).all()
        history = [SnapshotPoint(captured_at=s.captured_at, views=s.views, likes=s.likes, comments=s.comments) for s in snapshots]
        latest = snapshots[-1] if snapshots else None
        video = publication.content_video
        items.append(
            ContentItem(
                id=publication.external_id,
                platform=platform,
                title=video.title,
                url=publication.url,
                thumbnail_url=video.thumbnail_url,
                published_at=publication.published_at or datetime.now(timezone.utc),
                views=latest.views if latest else 0,
                likes=latest.likes if latest else 0,
                comments=latest.comments if latest else 0,
                history=history,
            )
        )
    return items


def get_platform_video_history(db: Session, platform: str, external_id: str, now: Optional[datetime] = None) -> Optional[dict]:
    """Generic per-video snapshot history (Part 8) — mirrors
    youtube_intelligence_adapter.get_video_history_buckets, bucketed with the same
    platform-agnostic `bucket_history` helper, anchored to the publish date."""
    now = now or datetime.now(timezone.utc)
    publication = db.scalar(select(Publication).where(Publication.platform == platform, Publication.external_id == external_id))
    if publication is None:
        return None
    snapshots = db.scalars(
        select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id).order_by(MetricSnapshot.captured_at.asc())
    ).all()
    points = [{"captured_at": s.captured_at, "views": s.views, "likes": s.likes, "comments": s.comments} for s in snapshots]
    history = [SnapshotPoint(captured_at=s.captured_at, views=s.views, likes=s.likes, comments=s.comments) for s in snapshots]
    anchor = publication.published_at or (snapshots[0].captured_at if snapshots else now)
    buckets = bucket_history(history, anchor, now)
    return {"points": points, **buckets}


def get_platform_intelligence_report(db: Session, platform: str, now: Optional[datetime] = None) -> Optional[dict]:
    now = now or datetime.now(timezone.utc)
    content_items = _build_content_items(db, platform)
    if not content_items:
        return None
    from app.services.intelligence.content_metrics import derive

    derived_items = [derive(item, now) for item in content_items]
    lookup = {item.id: item for item in content_items}
    report = engine.build_intelligence_report(derived_items, now, subscriber_history=[])

    def supporting(video_id: Optional[str]) -> Optional[dict]:
        if not video_id:
            return None
        item = lookup.get(video_id)
        return None if item is None else {"external_id": item.id, "title": item.title, "thumbnail_url": item.thumbnail_url}

    def recommendation(rec) -> dict:
        return {
            "id": rec.id,
            "category": rec.category,
            "headline": rec.headline,
            "explanation": rec.explanation,
            "confidence": rec.confidence.value,
            "supporting_metrics": rec.supporting_metrics,
            "supporting_videos": [v for v in (supporting(vid) for vid in rec.supporting_video_ids) if v is not None],
        }

    brief = report.daily_brief
    return {
        "daily_brief": {
            "views_gained_24h": brief.views_gained_24h,
            "subscribers_gained_24h": None,  # no generic follower-history snapshot yet — see TODO.md
            "best_growing_video": supporting(brief.best_growing_video_id),
            "best_growing_video_gain": brief.best_growing_video_gain,
            "biggest_slowdown_video": supporting(brief.biggest_slowdown_video_id),
            "biggest_slowdown_delta": brief.biggest_slowdown_delta,
            "attention_video_count": len(brief.attention_video_ids),
            "days_since_last_upload": brief.days_since_last_upload,
            "no_upload_warning": brief.no_upload_warning,
        },
        "winning_videos": [recommendation(r) for r in report.winning_videos],
        "attention_videos": [recommendation(r) for r in report.attention_videos],
        "too_new_count": report.too_new_count,
        "topics": [
            {
                "keyword": topic.keyword,
                "video_count": topic.video_count,
                "median_views": topic.median_views,
                "median_views_per_day": topic.median_views_per_day,
                "median_engagement": topic.median_engagement,
                "best_video": supporting(topic.best_video_id),
                "worst_video": supporting(topic.worst_video_id),
                "trend": topic.trend,
            }
            for topic in report.topics
        ],
        "publishing": {
            "best_weekday": report.publishing.best_weekday,
            "best_weekday_median_vpd": report.publishing.best_weekday_median_vpd,
            "best_hour": report.publishing.best_hour,
            "best_hour_median_vpd": report.publishing.best_hour_median_vpd,
            "best_cadence_label": report.publishing.best_cadence_label,
            "best_cadence_median_vpd": report.publishing.best_cadence_median_vpd,
            "best_streak_start": report.publishing.best_streak_start,
            "best_streak_end": report.publishing.best_streak_end,
            "best_streak_video_count": report.publishing.best_streak_video_count,
            "best_streak_avg_vpd": report.publishing.best_streak_avg_vpd,
            "worst_streak_start": report.publishing.worst_streak_start,
            "worst_streak_end": report.publishing.worst_streak_end,
            "worst_streak_video_count": report.publishing.worst_streak_video_count,
            "worst_streak_avg_vpd": report.publishing.worst_streak_avg_vpd,
            "insufficient_data_notes": report.publishing.insufficient_data_notes,
        },
        "follow_up_opportunities": [recommendation(r) for r in report.follow_up_opportunities],
        "title_patterns": [recommendation(r) for r in report.title_patterns],
        "content_recommendations": [recommendation(r) for r in report.content_recommendations],
    }
