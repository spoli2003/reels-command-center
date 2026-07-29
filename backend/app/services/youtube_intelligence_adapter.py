"""The ONLY YouTube-specific file in the Creator Intelligence path.

Converts stored YoutubeVideo/YoutubeMetricSnapshot/YoutubeChannelSnapshot rows
into the platform-agnostic ContentItem shape, runs them through
app.services.intelligence.engine, then re-attaches display fields (title,
thumbnail) for the API response. A future Facebook/Instagram/TikTok adapter
would be a similarly small file — nothing in engine.py or topics.py changes.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import YoutubeChannel, YoutubeChannelSnapshot, YoutubeMetricSnapshot, YoutubeVideo
from app.services.intelligence import engine
from app.services.intelligence.content_metrics import (
    bucket_history,
    compute_composite_scores,
    derive,
    engagement_category,
    gained_since,
    growth_category,
    median_or_none,
    peak_growth_day,
    performance_label,
    largest_slowdown_interval,
)
from app.services.intelligence.topics import tokenize_title
from app.services.intelligence.types import ContentItem, Recommendation, SnapshotPoint


def _build_content_items(db: Session) -> list[ContentItem]:
    videos = db.scalars(select(YoutubeVideo)).all()
    snapshots = db.scalars(select(YoutubeMetricSnapshot).order_by(YoutubeMetricSnapshot.captured_at.asc())).all()
    snapshots_by_video: dict[int, list[YoutubeMetricSnapshot]] = {}
    for snapshot in snapshots:
        snapshots_by_video.setdefault(snapshot.video_id, []).append(snapshot)

    items: list[ContentItem] = []
    for video in videos:
        video_snapshots = snapshots_by_video.get(video.id, [])
        history = [
            SnapshotPoint(captured_at=s.captured_at, views=s.views, likes=s.likes, comments=s.comments) for s in video_snapshots
        ]
        latest = video_snapshots[-1] if video_snapshots else None
        items.append(
            ContentItem(
                id=video.youtube_video_id,
                platform="youtube",
                title=video.title,
                url=f"https://www.youtube.com/watch?v={video.youtube_video_id}",
                thumbnail_url=video.thumbnail_url,
                published_at=video.published_at,
                views=latest.views if latest else 0,
                likes=latest.likes if latest else 0,
                comments=latest.comments if latest else 0,
                history=history,
            )
        )
    return items


def _subscriber_history(db: Session) -> list[tuple[datetime, int]]:
    channel = db.scalar(select(YoutubeChannel).order_by(YoutubeChannel.synced_at.desc()))
    if channel is None:
        return []
    rows = db.scalars(
        select(YoutubeChannelSnapshot)
        .where(YoutubeChannelSnapshot.channel_id == channel.id)
        .order_by(YoutubeChannelSnapshot.captured_at.asc())
    ).all()
    return [(row.captured_at, row.subscriber_count) for row in rows]


def _supporting_video(video_id: str, lookup: dict[str, ContentItem]) -> Optional[dict]:
    item = lookup.get(video_id)
    if item is None:
        return None
    return {"youtube_video_id": item.id, "title": item.title, "thumbnail_url": item.thumbnail_url}


def _recommendation_to_dict(rec: Recommendation, lookup: dict[str, ContentItem]) -> dict:
    supporting = [video for video in (_supporting_video(vid, lookup) for vid in rec.supporting_video_ids) if video is not None]
    return {
        "id": rec.id,
        "category": rec.category,
        "headline": rec.headline,
        "explanation": rec.explanation,
        "confidence": rec.confidence.value,
        "supporting_metrics": rec.supporting_metrics,
        "supporting_videos": supporting,
    }


def compute_all_video_metadata(db: Session, now: Optional[datetime] = None) -> dict[str, dict]:
    """Deterministic, AI-ready structured metadata for every video (Sprint 5 / Part 8) —
    computed once, keyed by youtube_video_id, reused by both the /videos list endpoint
    and the /videos/{id} detail endpoint so they never disagree with each other."""
    now = now or datetime.now(timezone.utc)
    content_items = _build_content_items(db)
    derived_items = [derive(item, now) for item in content_items]
    scores = compute_composite_scores(derived_items)
    channel_median_vpd = median_or_none([item.views_per_day for item in derived_items]) or 0

    metadata: dict[str, dict] = {}
    for item in derived_items:
        score = scores.get(item.id, 0.0)
        peak = peak_growth_day(item)
        slowdown = largest_slowdown_interval(item)
        metadata[item.id] = {
            "views_per_day": item.views_per_day,
            "engagement_rate": item.engagement_rate,
            "trend": item.trend.value,
            "performance_score": score,
            "performance_label": performance_label(item, score, channel_median_vpd),
            "engagement_category": engagement_category(item.engagement_rate),
            "growth_category": growth_category(item.trend),
            "topic_keywords": list(dict.fromkeys(tokenize_title(item.title)))[:5],
            # Sprint 6 / Parts 7 & 12 — historical growth metadata, all deterministic.
            "velocity": item.velocity,
            "acceleration": item.acceleration,
            "views_gained_24h": gained_since(item, now, 1),
            "views_gained_7d": gained_since(item, now, 7),
            "views_gained_30d": gained_since(item, now, 30),
            "peak_growth_date": peak[0].isoformat() if peak else None,
            "peak_growth_views": peak[1] if peak else None,
            "largest_slowdown_date": slowdown[0].isoformat() if slowdown else None,
            "largest_slowdown_views": slowdown[1] if slowdown else None,
            "snapshot_count": len(item.history),
        }
    return metadata


def get_video_history_buckets(db: Session, youtube_video_id: str, now: Optional[datetime] = None) -> Optional[dict]:
    """Sprint 6 / Part 9 — creator-oriented chart buckets for one video's history,
    anchored to its publish date rather than raw synchronization timestamps."""
    now = now or datetime.now(timezone.utc)
    video = db.scalar(select(YoutubeVideo).where(YoutubeVideo.youtube_video_id == youtube_video_id))
    if video is None:
        return None
    snapshots = db.scalars(
        select(YoutubeMetricSnapshot)
        .where(YoutubeMetricSnapshot.video_id == video.id)
        .order_by(YoutubeMetricSnapshot.captured_at.asc())
    ).all()
    history = [SnapshotPoint(captured_at=s.captured_at, views=s.views, likes=s.likes, comments=s.comments) for s in snapshots]
    return bucket_history(history, video.published_at, now)


def get_intelligence_report(db: Session, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    content_items = _build_content_items(db)
    lookup = {item.id: item for item in content_items}
    derived_items = [derive(item, now) for item in content_items]
    subscriber_history = _subscriber_history(db)
    report = engine.build_intelligence_report(derived_items, now, subscriber_history)

    brief = report.daily_brief
    return {
        "daily_brief": {
            "views_gained_24h": brief.views_gained_24h,
            "subscribers_gained_24h": brief.subscribers_gained_24h,
            "best_growing_video": _supporting_video(brief.best_growing_video_id, lookup) if brief.best_growing_video_id else None,
            "best_growing_video_gain": brief.best_growing_video_gain,
            "biggest_slowdown_video": _supporting_video(brief.biggest_slowdown_video_id, lookup) if brief.biggest_slowdown_video_id else None,
            "biggest_slowdown_delta": brief.biggest_slowdown_delta,
            "attention_video_count": len(brief.attention_video_ids),
            "days_since_last_upload": brief.days_since_last_upload,
            "no_upload_warning": brief.no_upload_warning,
        },
        "winning_videos": [_recommendation_to_dict(rec, lookup) for rec in report.winning_videos],
        "attention_videos": [_recommendation_to_dict(rec, lookup) for rec in report.attention_videos],
        "too_new_count": report.too_new_count,
        "topics": [
            {
                "keyword": topic.keyword,
                "video_count": topic.video_count,
                "median_views": topic.median_views,
                "median_views_per_day": topic.median_views_per_day,
                "median_engagement": topic.median_engagement,
                "best_video": _supporting_video(topic.best_video_id, lookup),
                "worst_video": _supporting_video(topic.worst_video_id, lookup),
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
        "follow_up_opportunities": [_recommendation_to_dict(rec, lookup) for rec in report.follow_up_opportunities],
        "title_patterns": [_recommendation_to_dict(rec, lookup) for rec in report.title_patterns],
        "content_recommendations": [_recommendation_to_dict(rec, lookup) for rec in report.content_recommendations],
    }
