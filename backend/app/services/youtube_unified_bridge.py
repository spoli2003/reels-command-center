"""Dual-writes YouTube sync results into the unified content engine
(ContentVideo/Publication/MetricSnapshot) — Release 0.8.0 / ADR-020.

Purely additive: makes YouTube data ALSO visible through the new generic
multi-platform surfaces (/platforms/youtube) without touching a single existing
YouTube-specific endpoint, schema, or test. `youtube_sync.py` itself is NOT
modified — this is called from the API/scheduler layer only, after a sync
already succeeded, and any failure here is swallowed (logged, never raised) so
it can never affect the primary YouTube sync's own success or response.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import ContentVideo, MetricSnapshot, Publication
from app.models.content_comments import ContentComment, ContentCommentThread
from app.models.comments import YoutubeComment, YoutubeCommentThread
from app.models.integration import PlatformAccount, YoutubeChannel, YoutubeMetricSnapshot, YoutubeVideo

logger = logging.getLogger("youtube_unified_bridge")


def _bridge_one_video(db: Session, account: PlatformAccount, video: YoutubeVideo, latest: Optional[YoutubeMetricSnapshot]) -> None:
    publication = db.scalar(select(Publication).where(Publication.platform == "youtube", Publication.external_id == video.youtube_video_id))
    if publication is None:
        content_video = ContentVideo(
            title=video.title,
            description=video.description,
            duration_seconds=video.duration_seconds,
            thumbnail_url=video.thumbnail_url,
        )
        db.add(content_video)
        db.flush()
        publication = Publication(
            content_video_id=content_video.id,
            platform_account_id=account.id,
            platform="youtube",
            external_id=video.youtube_video_id,
            url=f"https://www.youtube.com/watch?v={video.youtube_video_id}",
            published_at=video.published_at,
        )
        db.add(publication)
        db.flush()
    else:
        publication.content_video.title = video.title
        publication.content_video.description = video.description
        publication.content_video.duration_seconds = video.duration_seconds
        publication.content_video.thumbnail_url = video.thumbnail_url

    if latest is None:
        return
    last_bridged: Optional[datetime] = db.scalar(
        select(MetricSnapshot.captured_at).where(MetricSnapshot.publication_id == publication.id).order_by(MetricSnapshot.captured_at.desc()).limit(1)
    )
    if last_bridged is not None and last_bridged == latest.captured_at:
        return
    db.add(
        MetricSnapshot(
            publication_id=publication.id,
            captured_at=latest.captured_at,
            views=latest.views,
            likes=latest.likes,
            comments=latest.comments,
        )
    )


def bridge_all_youtube_videos(db: Session, account: PlatformAccount, channel: YoutubeChannel) -> None:
    """Best-effort. Never raises — a bridge problem must never surface as a
    YouTube sync failure to the user."""
    try:
        videos = db.scalars(select(YoutubeVideo).where(YoutubeVideo.channel_id == channel.id)).all()
        for video in videos:
            latest = db.scalar(
                select(YoutubeMetricSnapshot).where(YoutubeMetricSnapshot.video_id == video.id).order_by(YoutubeMetricSnapshot.captured_at.desc()).limit(1)
            )
            _bridge_one_video(db, account, video, latest)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Nie udało się zsynchronizować danych YouTube z jednolitym silnikiem treści (bridge) — synchronizacja YouTube nie została naruszona.")


def _bridge_one_thread(db: Session, publication: Publication, thread: YoutubeCommentThread, replies: list[YoutubeComment]) -> None:
    existing = db.scalar(select(ContentCommentThread).where(ContentCommentThread.platform_thread_id == thread.platform_thread_id))
    is_new = existing is None
    row = existing or ContentCommentThread(platform_thread_id=thread.platform_thread_id, top_level_comment_id=thread.top_level_comment_id)
    row.platform = "youtube"
    row.publication_id = publication.id
    row.top_level_comment_id = thread.top_level_comment_id
    row.author_external_id = thread.author_channel_id
    row.author_display_name = thread.author_display_name
    row.author_avatar_url = thread.author_avatar_url
    row.text_original = thread.text_original
    row.like_count = thread.like_count
    row.published_at = thread.published_at
    row.updated_at = thread.updated_at
    row.total_reply_count = thread.total_reply_count
    row.can_reply = thread.can_reply
    row.last_synced_at = thread.last_synced_at
    if is_new:
        row.imported_at = thread.imported_at
        db.add(row)
        db.flush()

    for reply in replies:
        existing_reply = db.scalar(select(ContentComment).where(ContentComment.platform_comment_id == reply.platform_comment_id))
        reply_row = existing_reply or ContentComment(
            platform_comment_id=reply.platform_comment_id, thread_id=row.id, parent_comment_id=reply.parent_comment_id
        )
        reply_row.platform = "youtube"
        reply_row.thread_id = row.id
        reply_row.parent_comment_id = reply.parent_comment_id
        reply_row.author_external_id = reply.author_channel_id
        reply_row.author_display_name = reply.author_display_name
        reply_row.author_avatar_url = reply.author_avatar_url
        reply_row.text_original = reply.text_original
        reply_row.like_count = reply.like_count
        reply_row.published_at = reply.published_at
        reply_row.updated_at = reply.updated_at
        reply_row.is_own_reply = reply.is_own_reply
        reply_row.last_synced_at = reply.last_synced_at
        if existing_reply is None:
            reply_row.imported_at = reply.imported_at
            db.add(reply_row)


def bridge_all_youtube_comments(db: Session, account: PlatformAccount) -> None:
    """Best-effort dual-write of YouTube's own comment engine into the generic
    ContentComment tables, so the generic Community Inbox (/platforms/youtube)
    shows the identical data as the dedicated YouTube Community Inbox. The
    dedicated YouTube comment tables/endpoints remain the source of truth and
    are completely unaffected by this."""
    try:
        threads = db.scalars(
            select(YoutubeCommentThread)
            .join(YoutubeVideo, YoutubeCommentThread.video_id == YoutubeVideo.id)
            .where(YoutubeVideo.channel_id.in_(select(YoutubeChannel.id).where(YoutubeChannel.account_id == account.id)))
        ).all()
        for thread in threads:
            publication = db.scalar(select(Publication).where(Publication.platform == "youtube", Publication.external_id == thread.video.youtube_video_id))
            if publication is None:
                continue  # video not bridged yet — will be picked up on the next sync
            replies = db.scalars(select(YoutubeComment).where(YoutubeComment.thread_id == thread.id)).all()
            _bridge_one_thread(db, publication, thread, replies)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Nie udało się zsynchronizować komentarzy YouTube z jednolitym silnikiem treści (bridge) — synchronizacja komentarzy nie została naruszona.")
