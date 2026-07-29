"""YouTube comment synchronization (Release 0.7.0 / Part 4).

Quota-conscious strategy: `commentThreads.list`/`comments.list` cost 1 quota unit
per page (cheap), so listing is not the concern — re-fetching a video's ENTIRE
comment history on every scheduled tick is. Videos published within
RECENT_VIDEO_DAYS are synced on every run (comments concentrate on new uploads);
older videos are only re-synced every OLDER_VIDEO_SYNC_EVERY_N_RUNS scheduled runs,
or immediately via an explicit manual "full refresh" (`mode="full"`) or a
single-video sync (`video_id=...`). See docs/DECISIONS.md ADR-018.

Never deletes a locally stored thread/comment just because a later sync omits it
(moderation, temporary API hiccups) — sync is upsert-only, matching the
"never delete history" principle already established for metric snapshots.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from googleapiclient.errors import HttpError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations.youtube.client import YoutubeClient, parse_published_at
from app.models.comments import YoutubeComment, YoutubeCommentThread
from app.models.integration import SyncRun, YoutubeChannel, YoutubeVideo

STALE_RUN_MINUTES = 30
RECENT_VIDEO_DAYS = 30
OLDER_VIDEO_SYNC_EVERY_N_RUNS = 4


class CommentSyncAlreadyRunningError(Exception):
    """Raised when a comment sync is requested while another is genuinely in flight."""


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _is_comments_disabled_error(exc: HttpError) -> bool:
    try:
        reasons = [detail.get("reason") for detail in (exc.error_details or [])]
    except Exception:
        reasons = []
    return "commentsDisabled" in reasons or "commentsDisabled" in str(exc)


def _reclaim_stale_running_run(db: Session) -> None:
    running = db.scalar(select(SyncRun).where(SyncRun.platform == "youtube_comments", SyncRun.status == "running"))
    if running is None:
        return
    if datetime.now(timezone.utc) - _aware(running.started_at) <= timedelta(minutes=STALE_RUN_MINUTES):
        raise CommentSyncAlreadyRunningError("Synchronizacja komentarzy już trwa — poczekaj na jej zakończenie.")
    running.status = "failed"
    running.error_message = "Przerwana — proces został prawdopodobnie zrestartowany w trakcie synchronizacji."
    running.finished_at = datetime.now(timezone.utc)
    db.commit()


def _select_target_videos(db: Session, channel_id: int, mode: str, video_id: Optional[int]) -> list[YoutubeVideo]:
    if video_id is not None:
        video = db.scalar(select(YoutubeVideo).where(YoutubeVideo.id == video_id, YoutubeVideo.channel_id == channel_id))
        return [video] if video else []

    all_videos = list(db.scalars(select(YoutubeVideo).where(YoutubeVideo.channel_id == channel_id)).all())
    if mode == "full":
        return all_videos

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RECENT_VIDEO_DAYS)
    recent = [v for v in all_videos if _aware(v.published_at) >= cutoff]
    older = [v for v in all_videos if _aware(v.published_at) < cutoff]

    completed_runs = (
        db.scalar(select(func.count(SyncRun.id)).where(SyncRun.platform == "youtube_comments", SyncRun.status != "running")) or 0
    )
    if completed_runs % OLDER_VIDEO_SYNC_EVERY_N_RUNS == 0:
        return recent + older
    return recent


def _upsert_thread(db: Session, video: YoutubeVideo, raw_thread: dict) -> tuple[YoutubeCommentThread, bool]:
    snippet = raw_thread["snippet"]
    top_comment = snippet["topLevelComment"]
    top_snippet = top_comment["snippet"]
    platform_thread_id = raw_thread["id"]

    existing = db.scalar(select(YoutubeCommentThread).where(YoutubeCommentThread.platform_thread_id == platform_thread_id))
    is_new = existing is None
    thread = existing or YoutubeCommentThread(platform_thread_id=platform_thread_id, top_level_comment_id=top_comment["id"])

    now = datetime.now(timezone.utc)
    thread.video_id = video.id
    thread.top_level_comment_id = top_comment["id"]
    thread.author_channel_id = (top_snippet.get("authorChannelId") or {}).get("value")
    thread.author_display_name = top_snippet.get("authorDisplayName", "")
    thread.author_avatar_url = top_snippet.get("authorProfileImageUrl")
    thread.text_original = top_snippet.get("textOriginal", "")
    thread.like_count = top_snippet.get("likeCount", 0)
    thread.published_at = parse_published_at(top_snippet["publishedAt"])
    thread.updated_at = parse_published_at(top_snippet.get("updatedAt") or top_snippet["publishedAt"])
    thread.total_reply_count = snippet.get("totalReplyCount", 0)
    thread.moderation_status = top_snippet.get("moderationStatus", "published")
    thread.can_reply = snippet.get("canReply", True)
    thread.viewer_rating = top_snippet.get("viewerRating")
    thread.last_synced_at = now
    if is_new:
        thread.imported_at = now
        db.add(thread)
        db.flush()
    return thread, is_new


def _upsert_reply(db: Session, thread: YoutubeCommentThread, raw_comment: dict, own_channel_youtube_id: Optional[str]) -> bool:
    snippet = raw_comment["snippet"]
    platform_comment_id = raw_comment["id"]

    existing = db.scalar(select(YoutubeComment).where(YoutubeComment.platform_comment_id == platform_comment_id))
    is_new = existing is None
    comment = existing or YoutubeComment(
        platform_comment_id=platform_comment_id,
        thread_id=thread.id,
        parent_comment_id=snippet.get("parentId", thread.top_level_comment_id),
    )

    now = datetime.now(timezone.utc)
    author_channel_id = (snippet.get("authorChannelId") or {}).get("value")
    comment.thread_id = thread.id
    comment.parent_comment_id = snippet.get("parentId", thread.top_level_comment_id)
    comment.author_channel_id = author_channel_id
    comment.author_display_name = snippet.get("authorDisplayName", "")
    comment.author_avatar_url = snippet.get("authorProfileImageUrl")
    comment.text_original = snippet.get("textOriginal", "")
    comment.like_count = snippet.get("likeCount", 0)
    comment.published_at = parse_published_at(snippet["publishedAt"])
    comment.updated_at = parse_published_at(snippet.get("updatedAt") or snippet["publishedAt"])
    comment.is_own_reply = bool(own_channel_youtube_id) and author_channel_id == own_channel_youtube_id
    comment.moderation_status = snippet.get("moderationStatus", "published")
    comment.viewer_rating = snippet.get("viewerRating")
    comment.last_synced_at = now
    if is_new:
        comment.imported_at = now
        db.add(comment)
    return is_new


def _sync_one_video(db: Session, video: YoutubeVideo, client: YoutubeClient, own_channel_youtube_id: Optional[str]) -> dict:
    """Returns counts for this video; raises only on genuine (non-"comments
    disabled") API errors so the caller can isolate the failure per video."""
    threads_discovered = 0
    comments_imported = 0
    replies_imported = 0

    page_token = None
    while True:
        try:
            response = client.list_comment_threads_page(video.youtube_video_id, page_token)
        except HttpError as exc:
            if _is_comments_disabled_error(exc):
                break
            raise

        for raw_thread in response.get("items", []):
            threads_discovered += 1
            thread, is_new_thread = _upsert_thread(db, video, raw_thread)
            if is_new_thread:
                comments_imported += 1

            inline_replies = (raw_thread.get("replies") or {}).get("comments", [])
            seen_reply_ids = set()
            for raw_reply in inline_replies:
                seen_reply_ids.add(raw_reply["id"])
                if _upsert_reply(db, thread, raw_reply, own_channel_youtube_id):
                    replies_imported += 1

            # Full thread retrieval when commentThreads.list doesn't include every reply.
            if thread.total_reply_count > len(inline_replies):
                reply_page_token = None
                while True:
                    reply_response = client.list_replies_page(thread.top_level_comment_id, reply_page_token)
                    for raw_reply in reply_response.get("items", []):
                        if raw_reply["id"] in seen_reply_ids:
                            continue
                        seen_reply_ids.add(raw_reply["id"])
                        if _upsert_reply(db, thread, raw_reply, own_channel_youtube_id):
                            replies_imported += 1
                    reply_page_token = reply_response.get("nextPageToken")
                    if not reply_page_token:
                        break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return {"threads_discovered": threads_discovered, "comments_imported": comments_imported, "replies_imported": replies_imported}


def sync_youtube_comments(
    db: Session, channel: YoutubeChannel, client: YoutubeClient, mode: str = "incremental", video_id: Optional[int] = None
) -> SyncRun:
    _reclaim_stale_running_run(db)

    run = SyncRun(platform="youtube_comments", status="running")
    db.add(run)
    db.commit()

    try:
        targets = _select_target_videos(db, channel.id, mode, video_id)
        threads_discovered = 0
        comments_imported = 0
        replies_imported = 0
        videos_failed = 0

        for video in targets:
            try:
                with db.begin_nested():
                    counts = _sync_one_video(db, video, client, channel.youtube_channel_id)
                threads_discovered += counts["threads_discovered"]
                comments_imported += counts["comments_imported"]
                replies_imported += counts["replies_imported"]
            except Exception:
                videos_failed += 1
                continue

        run.status = "success" if videos_failed == 0 else "partial"
        run.videos_discovered = len(targets)
        run.videos_failed = videos_failed
        run.threads_discovered = threads_discovered
        run.comments_imported = comments_imported
        run.replies_imported = replies_imported
        if videos_failed:
            run.error_message = f"{videos_failed} z {len(targets)} filmów nie udało się zsynchronizować (komentarze)."
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return run
    except Exception as exc:
        db.rollback()
        failed = db.get(SyncRun, run.id)
        if failed:
            failed.status = "failed"
            failed.error_message = str(exc)[:2000]
            failed.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise
