from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import YoutubeChannel, YoutubeChannelSnapshot, YoutubeMetricSnapshot, YoutubeVideo
from app.services.intelligence.content_metrics import DAILY_BUCKET_MAX_AGE_DAYS, WEEKLY_BUCKET_MAX_AGE_DAYS, ensure_aware


def _engagement_rate(likes: int, comments: int, views: int) -> float:
    if not views:
        return 0.0
    return round((likes + comments) / views * 100, 2)


def _latest_snapshots_by_video(db: Session) -> dict[int, YoutubeMetricSnapshot]:
    snapshots = db.scalars(
        select(YoutubeMetricSnapshot).order_by(YoutubeMetricSnapshot.captured_at.asc())
    ).all()
    latest: dict[int, YoutubeMetricSnapshot] = {}
    for snapshot in snapshots:
        latest[snapshot.video_id] = snapshot
    return latest


def _video_rows(db: Session) -> list[dict]:
    videos = db.scalars(select(YoutubeVideo)).all()
    latest = _latest_snapshots_by_video(db)
    rows = []
    for video in videos:
        snapshot = latest.get(video.id)
        views = snapshot.views if snapshot else 0
        likes = snapshot.likes if snapshot else 0
        comments = snapshot.comments if snapshot else 0
        rows.append(
            {
                "youtube_video_id": video.youtube_video_id,
                "title": video.title,
                "published_at": video.published_at,
                "thumbnail_url": video.thumbnail_url,
                "views": views,
                "likes": likes,
                "comments": comments,
                "engagement_rate": _engagement_rate(likes, comments, views),
            }
        )
    return rows


def get_channel(db: Session) -> Optional[YoutubeChannel]:
    """The single lookup for "the connected YouTube channel" — every page and
    endpoint that needs channel identity or sync state (last_synced_at, title,
    subscriber_count, ...) must go through this function, never re-implement its
    own query, so there is exactly one source of truth for that data (bugfix:
    Home/Dashboard/Video-detail and the YouTube panel previously used two
    independently-written queries for this same lookup). RCC is single-tenant
    today (one real connected channel — see ADR-010 for the future multi-workspace
    plan), so "most recently synced" is the correct and only sensible tiebreaker."""
    return db.scalar(select(YoutubeChannel).order_by(YoutubeChannel.synced_at.desc()))


def get_summary(db: Session) -> dict:
    channel = get_channel(db)
    rows = _video_rows(db)
    total_videos = len(rows)
    total_views = sum(row["views"] for row in rows)
    total_likes = sum(row["likes"] for row in rows)
    total_comments = sum(row["comments"] for row in rows)
    engaged = [row["engagement_rate"] for row in rows if row["views"]]

    # "Channel views/day" is total views divided by days since the OLDEST
    # video RCC currently tracks — never by channel account age, which would
    # silently include years of inactivity for dormant/relaunched channels.
    oldest_published_at = min((row["published_at"] for row in rows), default=None)
    days_since_oldest_video: Optional[int] = None
    channel_views_per_day: Optional[float] = None
    if oldest_published_at is not None:
        if oldest_published_at.tzinfo is None:
            oldest_published_at = oldest_published_at.replace(tzinfo=timezone.utc)
        days_since_oldest_video = max(1, (datetime.now(timezone.utc) - oldest_published_at).days)
        channel_views_per_day = round(total_views / days_since_oldest_video, 2)

    return {
        "channel_title": channel.title if channel else None,
        "subscriber_count": channel.subscriber_count if channel else 0,
        "total_videos": total_videos,
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "avg_views_per_video": round(total_views / total_videos, 2) if total_videos else 0.0,
        "avg_engagement_rate": round(sum(engaged) / len(engaged), 2) if engaged else 0.0,
        "days_since_oldest_video": days_since_oldest_video,
        "channel_views_per_day": channel_views_per_day,
    }


def get_top_videos(db: Session, metric: str, limit: int) -> list[dict]:
    rows = _video_rows(db)
    for row in rows:
        row["score"] = row["views"] if metric == "views" else row["engagement_rate"]
    rows.sort(key=lambda row: row["score"], reverse=True)
    return rows[:limit]


def get_recent_video_rows(db: Session, limit: int) -> list[dict]:
    rows = _video_rows(db)
    rows.sort(key=lambda row: row["published_at"], reverse=True)
    return rows[:limit]


def get_scatter(db: Session) -> list[dict]:
    rows = _video_rows(db)
    return [
        {
            "youtube_video_id": row["youtube_video_id"],
            "title": row["title"],
            "views": row["views"],
            "likes": row["likes"],
        }
        for row in rows
    ]


def get_upload_frequency(db: Session, interval: str) -> list[dict]:
    published_dates = db.scalars(select(YoutubeVideo.published_at)).all()
    buckets: dict[str, int] = defaultdict(int)
    for published_at in published_dates:
        key = published_at.strftime("%G-W%V") if interval == "week" else published_at.strftime("%Y-%m")
        buckets[key] += 1
    return [{"bucket": key, "count": count} for key, count in sorted(buckets.items())]


def get_timeseries(db: Session, metric: str) -> list[dict]:
    rows = db.execute(
        select(
            YoutubeMetricSnapshot.video_id,
            YoutubeMetricSnapshot.captured_at,
            YoutubeMetricSnapshot.views,
            YoutubeMetricSnapshot.likes,
            YoutubeMetricSnapshot.comments,
        )
    ).all()
    metric_index = {"views": 2, "likes": 3, "comments": 4}[metric]
    per_day_latest: dict[tuple[int, object], tuple[datetime, int]] = {}
    for row in rows:
        video_id, captured_at, *_ = row
        day = captured_at.date()
        key = (video_id, day)
        existing = per_day_latest.get(key)
        if existing is None or captured_at > existing[0]:
            per_day_latest[key] = (captured_at, row[metric_index])
    totals: dict[object, int] = defaultdict(int)
    for (video_id, day), (_, value) in per_day_latest.items():
        totals[day] += value
    return [{"date": day.isoformat(), "value": total} for day, total in sorted(totals.items())]


def get_video_detail(db: Session, youtube_video_id: str) -> Optional[dict]:
    video = db.scalar(select(YoutubeVideo).where(YoutubeVideo.youtube_video_id == youtube_video_id))
    if video is None:
        return None
    latest = db.scalar(
        select(YoutubeMetricSnapshot)
        .where(YoutubeMetricSnapshot.video_id == video.id)
        .order_by(YoutubeMetricSnapshot.captured_at.desc())
        .limit(1)
    )
    views = latest.views if latest else 0
    likes = latest.likes if latest else 0
    comments = latest.comments if latest else 0
    published_at = video.published_at
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    days_since_published = max(1, (datetime.now(timezone.utc) - published_at).days)
    return {
        "youtube_video_id": video.youtube_video_id,
        "title": video.title,
        "description": video.description,
        "published_at": video.published_at,
        "thumbnail_url": video.thumbnail_url,
        "duration_seconds": video.duration_seconds,
        "is_short_candidate": video.is_short_candidate,
        "views": views,
        "likes": likes,
        "comments": comments,
        "engagement_rate": _engagement_rate(likes, comments, views),
        "views_per_day": round(views / days_since_published, 2),
        "like_ratio": round(likes / views * 100, 3) if views else 0.0,
        "comment_ratio": round(comments / views * 100, 3) if views else 0.0,
    }


def get_video_history(db: Session, youtube_video_id: str) -> Optional[list[YoutubeMetricSnapshot]]:
    video = db.scalar(select(YoutubeVideo).where(YoutubeVideo.youtube_video_id == youtube_video_id))
    if video is None:
        return None
    return db.scalars(
        select(YoutubeMetricSnapshot)
        .where(YoutubeMetricSnapshot.video_id == video.id)
        .order_by(YoutubeMetricSnapshot.captured_at.asc())
    ).all()


def get_channel_history(db: Session, now: Optional[datetime] = None) -> Optional[dict]:
    """Sprint 6 / Part 10 — channel-wide history bucketed by how long RCC has been
    tracking the channel (its first stored snapshot), the same daily/weekly/monthly
    rule used for per-video history (see content_metrics.bucket_history)."""
    now = now or datetime.now(timezone.utc)
    channel = get_channel(db)
    if channel is None:
        return None
    snapshots = db.scalars(
        select(YoutubeChannelSnapshot)
        .where(YoutubeChannelSnapshot.channel_id == channel.id)
        .order_by(YoutubeChannelSnapshot.captured_at.asc())
    ).all()
    if not snapshots:
        return {"granularity": "daily", "buckets": [], "insufficient": True}

    anchor = ensure_aware(snapshots[0].captured_at)
    age_days = max(0, (now - anchor).days)
    if age_days < DAILY_BUCKET_MAX_AGE_DAYS:
        granularity, period_days, label_prefix = "daily", 1, "Dzień"
    elif age_days <= WEEKLY_BUCKET_MAX_AGE_DAYS:
        granularity, period_days, label_prefix = "weekly", 7, "Tydz."
    else:
        granularity, period_days, label_prefix = "monthly", 30, "Mies."

    grouped: dict[int, YoutubeChannelSnapshot] = {}
    for snapshot in snapshots:
        captured_at = ensure_aware(snapshot.captured_at)
        period_index = max(0, (captured_at - anchor).days) // period_days
        existing = grouped.get(period_index)
        if existing is None or captured_at >= ensure_aware(existing.captured_at):
            grouped[period_index] = snapshot

    buckets = [
        {
            "label": f"{label_prefix} {period_index + 1}",
            "period_start": anchor + timedelta(days=period_index * period_days),
            "period_end": anchor + timedelta(days=(period_index + 1) * period_days),
            "subscriber_count": snapshot.subscriber_count,
            "view_count": snapshot.view_count,
            "video_count": snapshot.video_count,
        }
        for period_index, snapshot in sorted(grouped.items())
    ]
    return {"granularity": granularity, "buckets": buckets, "insufficient": len(buckets) < 2}
