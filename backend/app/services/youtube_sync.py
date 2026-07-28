from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.youtube.client import YoutubeClient, parse_iso8601_duration, parse_published_at
from app.models.integration import PlatformAccount, SyncRun, YoutubeChannel, YoutubeMetricSnapshot, YoutubeVideo


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def sync_youtube(db: Session, account: PlatformAccount, client: YoutubeClient, max_items: int = 100) -> tuple[YoutubeChannel, int]:
    run = SyncRun(platform="youtube", status="running")
    db.add(run)
    db.commit()
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

        video_ids = client.list_upload_video_ids(uploads_id, max_items=max_items)
        imported = 0
        for raw in client.get_videos(video_ids):
            snippet = raw.get("snippet", {})
            details = raw.get("contentDetails", {})
            statistics = raw.get("statistics", {})
            video = db.scalar(select(YoutubeVideo).where(YoutubeVideo.youtube_video_id == raw["id"]))
            duration = parse_iso8601_duration(details.get("duration"))
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
                imported += 1
            video.title = snippet.get("title", video.title)
            video.description = snippet.get("description", video.description)
            video.thumbnail_url = ((snippet.get("thumbnails") or {}).get("high") or {}).get("url")
            video.duration_seconds = duration
            video.is_short_candidate = duration is not None and duration <= 180
            db.add(YoutubeMetricSnapshot(video_id=video.id, views=_integer(statistics.get("viewCount")), likes=_integer(statistics.get("likeCount")), comments=_integer(statistics.get("commentCount"))))

        run.status = "success"
        run.imported_items = imported
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
