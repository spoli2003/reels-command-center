from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.youtube.client import YoutubeClient, parse_iso8601_duration, parse_published_at
from app.models.integration import PlatformAccount, SyncRun, YoutubeChannel, YoutubeChannelSnapshot, YoutubeMetricSnapshot, YoutubeVideo

# A "running" SyncRun older than this is assumed orphaned (process killed/restarted
# mid-sync, not still working) so a new sync isn't blocked forever. See DECISIONS.md.
STALE_RUN_MINUTES = 30

# Deterministic dedup strategy (Sprint 6 / Part 3): a snapshot younger than this for
# the same video/channel is considered a duplicate of an accidental repeat
# invocation (double-click, overlapping manual + scheduled trigger) and is skipped
# rather than inserted. A legitimate periodic re-sync (default: every 6h) is always
# far apart enough to never hit this guard.
MIN_SNAPSHOT_INTERVAL_MINUTES = 5


class SyncAlreadyRunningError(Exception):
    """Raised when a sync is requested while another one is genuinely still in flight."""


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _reclaim_stale_running_run(db: Session, platform: str) -> None:
    """Idempotency/overlap guard (Sprint 6 / Parts 3 & 5). Raises if another sync for
    this platform is genuinely running; silently marks a stuck 'running' row as
    failed (and lets this call proceed) if it's older than STALE_RUN_MINUTES."""
    running = db.scalar(select(SyncRun).where(SyncRun.platform == platform, SyncRun.status == "running"))
    if running is None:
        return
    if datetime.now(timezone.utc) - _aware(running.started_at) <= timedelta(minutes=STALE_RUN_MINUTES):
        raise SyncAlreadyRunningError("Synchronizacja już trwa — poczekaj na jej zakończenie.")
    running.status = "failed"
    running.error_message = "Przerwana — proces został prawdopodobnie zrestartowany w trakcie synchronizacji."
    running.finished_at = datetime.now(timezone.utc)
    db.commit()


def sync_youtube(db: Session, account: PlatformAccount, client: YoutubeClient, max_items: int = 100) -> tuple[YoutubeChannel, int]:
    _reclaim_stale_running_run(db, "youtube")

    run = SyncRun(platform="youtube", status="running")
    db.add(run)
    db.commit()
    # One timestamp shared by every snapshot (channel + all videos) created in this
    # run, instead of a fresh datetime.now() per row — the run happened at one moment.
    run_captured_at = datetime.now(timezone.utc)
    try:
        raw_channel = client.get_my_channel()
        snippet = raw_channel.get("snippet", {})
        statistics = raw_channel.get("statistics", {})
        uploads_id = raw_channel["contentDetails"]["relatedPlaylists"]["uploads"]
        channel = db.scalar(select(YoutubeChannel).where(YoutubeChannel.youtube_channel_id == raw_channel["id"]))
        if channel is None:
            channel = YoutubeChannel(account_id=account.id, youtube_channel_id=raw_channel["id"], title=snippet.get("title", "Kanał YouTube"), uploads_playlist_id=uploads_id)
            db.add(channel)
            db.flush()
        channel.title = snippet.get("title", channel.title)
        channel.uploads_playlist_id = uploads_id
        channel.subscriber_count = _integer(statistics.get("subscriberCount"))
        channel.view_count = _integer(statistics.get("viewCount"))
        channel.video_count = _integer(statistics.get("videoCount"))
        channel.thumbnail_url = ((snippet.get("thumbnails") or {}).get("high") or {}).get("url")
        channel.synced_at = datetime.now(timezone.utc)

        last_channel_snapshot = db.scalar(
            select(YoutubeChannelSnapshot)
            .where(YoutubeChannelSnapshot.channel_id == channel.id)
            .order_by(YoutubeChannelSnapshot.captured_at.desc())
            .limit(1)
        )
        channel_snapshot_deduplicated = last_channel_snapshot is not None and (
            run_captured_at - _aware(last_channel_snapshot.captured_at) < timedelta(minutes=MIN_SNAPSHOT_INTERVAL_MINUTES)
        )
        if not channel_snapshot_deduplicated:
            db.add(
                YoutubeChannelSnapshot(
                    channel_id=channel.id,
                    captured_at=run_captured_at,
                    subscriber_count=channel.subscriber_count,
                    view_count=channel.view_count,
                    video_count=channel.video_count,
                )
            )

        video_ids = client.list_upload_video_ids(uploads_id, max_items=max_items)
        imported = 0
        videos_discovered = 0
        snapshots_created = 0
        snapshots_deduplicated = 1 if channel_snapshot_deduplicated else 0
        videos_failed = 0
        for raw in client.get_videos(video_ids):
            videos_discovered += 1
            try:
                # Per-video savepoint: one bad/malformed API response must not roll
                # back the entire run's already-processed videos (Sprint 6 / Part 4).
                with db.begin_nested():
                    snippet = raw.get("snippet", {})
                    details = raw.get("contentDetails", {})
                    statistics = raw.get("statistics", {})
                    video = db.scalar(select(YoutubeVideo).where(YoutubeVideo.youtube_video_id == raw["id"]))
                    duration = parse_iso8601_duration(details.get("duration"))
                    is_new = video is None
                    if video is None:
                        video = YoutubeVideo(
                            channel_id=channel.id,
                            youtube_video_id=raw["id"],
                            title=snippet.get("title", "Bez tytułu"),
                            description=snippet.get("description", ""),
                            published_at=parse_published_at(snippet["publishedAt"]),
                        )
                        db.add(video)
                        db.flush()
                    video.title = snippet.get("title", video.title)
                    video.description = snippet.get("description", video.description)
                    video.thumbnail_url = ((snippet.get("thumbnails") or {}).get("high") or {}).get("url")
                    video.duration_seconds = duration
                    video.is_short_candidate = duration is not None and duration <= 180

                    last_snapshot = db.scalar(
                        select(YoutubeMetricSnapshot)
                        .where(YoutubeMetricSnapshot.video_id == video.id)
                        .order_by(YoutubeMetricSnapshot.captured_at.desc())
                        .limit(1)
                    )
                    is_duplicate = last_snapshot is not None and (
                        run_captured_at - _aware(last_snapshot.captured_at) < timedelta(minutes=MIN_SNAPSHOT_INTERVAL_MINUTES)
                    )
                    if is_duplicate:
                        snapshots_deduplicated += 1
                    else:
                        db.add(
                            YoutubeMetricSnapshot(
                                video_id=video.id,
                                captured_at=run_captured_at,
                                views=_integer(statistics.get("viewCount")),
                                likes=_integer(statistics.get("likeCount")),
                                comments=_integer(statistics.get("commentCount")),
                            )
                        )
                        snapshots_created += 1
                if is_new:
                    imported += 1
            except Exception:
                videos_failed += 1
                continue

        run.status = "success" if videos_failed == 0 else "partial"
        run.imported_items = imported
        run.videos_discovered = videos_discovered
        run.videos_updated = videos_discovered - imported
        run.snapshots_created = snapshots_created
        run.snapshots_deduplicated = snapshots_deduplicated
        run.videos_failed = videos_failed
        if videos_failed:
            run.error_message = f"{videos_failed} z {videos_discovered} filmów nie udało się zaktualizować (patrz logi)."
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(channel)
        return channel, imported
    except Exception as exc:
        db.rollback()
        failed = db.get(SyncRun, run.id)
        if failed:
            failed.status = "failed"
            failed.error_message = str(exc)[:2000]
            failed.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise
