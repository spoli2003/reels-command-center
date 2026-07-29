"""Posting/editing/deleting comment replies (Release 0.7.0 / Parts 6, 7 & 13).

All authorization checks happen here, server-side, never trusting client-supplied
IDs at face value:
  - the thread being replied to must belong to a video owned by the connected
    channel (never an arbitrary/foreign comment ID) — see get_authorized_thread,
  - editing/deleting a reply requires is_own_reply=True on that exact DB row — a
    viewer's own comment can never be edited or deleted through RCC, regardless of
    what the client claims.

Editing/deleting one's own reply IS supported by the official YouTube Data API v3
(`comments.update`/`comments.delete`) for comments the connected channel authored,
so this is implemented for real, not faked — see docs/DECISIONS.md ADR-018.

Explicitly deleting a reply through RCC removes its local row (the user's intent
is genuinely "this reply should no longer exist"). This is different from comment
*sync*, which never deletes a row just because a later API response omits it.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.youtube.client import YoutubeClient, parse_published_at
from app.models.comments import YoutubeComment, YoutubeCommentThread
from app.models.integration import YoutubeChannel, YoutubeVideo


class CommentActionError(Exception):
    """Raised for any authorization/validation failure — the API layer translates
    this into an HTTP 403/404/400, never leaking token or internal error details."""


def get_authorized_thread(db: Session, channel_id: int, thread_platform_id: str) -> YoutubeCommentThread:
    thread = db.scalar(
        select(YoutubeCommentThread)
        .join(YoutubeVideo, YoutubeCommentThread.video_id == YoutubeVideo.id)
        .where(YoutubeCommentThread.platform_thread_id == thread_platform_id, YoutubeVideo.channel_id == channel_id)
    )
    if thread is None:
        raise CommentActionError("Wątek komentarza nie istnieje lub nie należy do połączonego kanału.")
    if not thread.can_reply:
        raise CommentActionError("Ten wątek nie zezwala na odpowiedzi.")
    return thread


def get_own_reply(db: Session, channel_id: int, comment_platform_id: str) -> YoutubeComment:
    comment = db.scalar(
        select(YoutubeComment)
        .join(YoutubeCommentThread, YoutubeComment.thread_id == YoutubeCommentThread.id)
        .join(YoutubeVideo, YoutubeCommentThread.video_id == YoutubeVideo.id)
        .where(YoutubeComment.platform_comment_id == comment_platform_id, YoutubeVideo.channel_id == channel_id)
    )
    if comment is None:
        raise CommentActionError("Odpowiedź nie istnieje lub nie należy do połączonego kanału.")
    if not comment.is_own_reply:
        raise CommentActionError("Można edytować lub usuwać wyłącznie własne odpowiedzi.")
    return comment


def post_reply(db: Session, channel: YoutubeChannel, client: YoutubeClient, thread_platform_id: str, text: str) -> YoutubeComment:
    text = text.strip()
    if not text:
        raise CommentActionError("Treść odpowiedzi nie może być pusta.")
    thread = get_authorized_thread(db, channel.id, thread_platform_id)

    raw = client.insert_reply(thread.top_level_comment_id, text)
    snippet = raw["snippet"]
    now = datetime.now(timezone.utc)
    comment = YoutubeComment(
        platform_comment_id=raw["id"],
        thread_id=thread.id,
        parent_comment_id=snippet.get("parentId", thread.top_level_comment_id),
        author_channel_id=(snippet.get("authorChannelId") or {}).get("value") or channel.youtube_channel_id,
        author_display_name=snippet.get("authorDisplayName") or channel.title,
        author_avatar_url=snippet.get("authorProfileImageUrl"),
        text_original=snippet.get("textOriginal", text),
        like_count=snippet.get("likeCount", 0),
        published_at=parse_published_at(snippet["publishedAt"]),
        updated_at=parse_published_at(snippet.get("updatedAt") or snippet["publishedAt"]),
        is_own_reply=True,
        moderation_status=snippet.get("moderationStatus", "published"),
        imported_at=now,
        last_synced_at=now,
    )
    db.add(comment)
    thread.total_reply_count += 1
    thread.last_synced_at = now
    db.commit()
    db.refresh(comment)
    return comment


def edit_reply(db: Session, channel: YoutubeChannel, client: YoutubeClient, comment_platform_id: str, text: str) -> YoutubeComment:
    text = text.strip()
    if not text:
        raise CommentActionError("Treść odpowiedzi nie może być pusta.")
    comment = get_own_reply(db, channel.id, comment_platform_id)
    raw = client.update_comment(comment.platform_comment_id, text)
    snippet = raw["snippet"]
    comment.text_original = snippet.get("textOriginal", text)
    comment.updated_at = parse_published_at(snippet.get("updatedAt") or snippet["publishedAt"])
    comment.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)
    return comment


def delete_reply(db: Session, channel: YoutubeChannel, client: YoutubeClient, comment_platform_id: str) -> None:
    comment = get_own_reply(db, channel.id, comment_platform_id)
    client.delete_comment(comment.platform_comment_id)
    thread = db.get(YoutubeCommentThread, comment.thread_id)
    db.delete(comment)
    if thread is not None and thread.total_reply_count > 0:
        thread.total_reply_count -= 1
    db.commit()
