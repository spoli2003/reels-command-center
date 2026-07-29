"""Historical data quality audit (Sprint 6 / Part 13).

Read-only by default: reports what it finds. The only auto-repair performed is
removing EXACT duplicate snapshot rows (same video, same captured_at, same
values) — which can only exist from a bug, never from two legitimate syncs (a
legitimate re-sync's captured_at always differs). Near-duplicate snapshots from
before the Sprint 6 dedup fix are left alone and only reported: they're still a
real (if noisy) point in a video's history, and deleting them destructively
would violate "never delete history" (see docs/DECISIONS.md).
"""

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import YoutubeMetricSnapshot, YoutubeVideo


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def audit_youtube_data_quality(db: Session, repair: bool = True) -> dict:
    videos = db.scalars(select(YoutubeVideo)).all()
    snapshots = db.scalars(select(YoutubeMetricSnapshot)).all()
    videos_by_id = {video.id: video for video in videos}

    snapshots_by_video: dict[int, list[YoutubeMetricSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        snapshots_by_video[snapshot.video_id].append(snapshot)

    exact_duplicates: list[int] = []
    impossible_timestamps: list[dict] = []
    non_monotonic_videos: list[dict] = []
    naive_timestamps = 0

    for video_id, video_snapshots in snapshots_by_video.items():
        video = videos_by_id.get(video_id)
        seen_exact: dict[tuple, YoutubeMetricSnapshot] = {}
        ordered = sorted(video_snapshots, key=lambda s: s.captured_at)
        previous_views = None
        for snapshot in ordered:
            if snapshot.captured_at.tzinfo is None:
                naive_timestamps += 1
            key = (snapshot.captured_at, snapshot.views, snapshot.likes, snapshot.comments)
            if key in seen_exact:
                exact_duplicates.append(snapshot.id)
            else:
                seen_exact[key] = snapshot

            if video is not None and _aware(snapshot.captured_at) < _aware(video.published_at):
                impossible_timestamps.append({"video_id": video.youtube_video_id, "snapshot_id": snapshot.id})

            if previous_views is not None and snapshot.views < previous_views:
                non_monotonic_videos.append(
                    {
                        "video_id": video.youtube_video_id if video else str(video_id),
                        "snapshot_id": snapshot.id,
                        "previous_views": previous_views,
                        "views": snapshot.views,
                    }
                )
            previous_views = snapshot.views

    repaired = 0
    if repair and exact_duplicates:
        db.query(YoutubeMetricSnapshot).filter(YoutubeMetricSnapshot.id.in_(exact_duplicates)).delete(synchronize_session=False)
        db.commit()
        repaired = len(exact_duplicates)

    return {
        "videos_checked": len(videos),
        "snapshots_checked": len(snapshots),
        "exact_duplicate_snapshots_found": len(exact_duplicates),
        "exact_duplicate_snapshots_repaired": repaired,
        "impossible_timestamps": impossible_timestamps,
        "non_monotonic_view_drops": non_monotonic_videos,
        "naive_timestamps_found": naive_timestamps,
        "is_clean": not impossible_timestamps and not non_monotonic_videos and not exact_duplicates,
    }
