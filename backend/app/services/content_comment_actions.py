"""Generic reply post/edit/delete — Release 0.8.0 (ADR-020). Mirrors
youtube_comment_actions.py's authorization pattern exactly: every action is
checked server-side against the connected account's own imported data, and
editing/deleting is only possible for the account's own reply rows."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import Publication
from app.models.content_comments import ContentComment, ContentCommentThread
from app.models.integration import PlatformAccount
from app.services.platforms.base import PlatformAdapter


class ContentCommentActionError(Exception):
    pass


def get_authorized_thread(db: Session, account: PlatformAccount, thread_platform_id: str) -> ContentCommentThread:
    thread = db.scalar(
        select(ContentCommentThread)
        .join(Publication, ContentCommentThread.publication_id == Publication.id)
        .where(ContentCommentThread.platform_thread_id == thread_platform_id, Publication.platform_account_id == account.id)
    )
    if thread is None:
        raise ContentCommentActionError("Wątek komentarza nie istnieje lub nie należy do połączonego konta.")
    if not thread.can_reply:
        raise ContentCommentActionError("Ten wątek nie zezwala na odpowiedzi.")
    return thread


def get_own_reply(db: Session, account: PlatformAccount, comment_platform_id: str) -> ContentComment:
    comment = db.scalar(
        select(ContentComment)
        .join(ContentCommentThread, ContentComment.thread_id == ContentCommentThread.id)
        .join(Publication, ContentCommentThread.publication_id == Publication.id)
        .where(ContentComment.platform_comment_id == comment_platform_id, Publication.platform_account_id == account.id)
    )
    if comment is None:
        raise ContentCommentActionError("Odpowiedź nie istnieje lub nie należy do połączonego konta.")
    if not comment.is_own_reply:
        raise ContentCommentActionError("Można edytować lub usuwać wyłącznie własne odpowiedzi.")
    return comment


def post_reply(db: Session, account: PlatformAccount, adapter: PlatformAdapter, thread_platform_id: str, text: str) -> ContentComment:
    text = text.strip()
    if not text:
        raise ContentCommentActionError("Treść odpowiedzi nie może być pusta.")
    thread = get_authorized_thread(db, account, thread_platform_id)

    raw_reply = adapter.post_reply(thread.top_level_comment_id, text)
    now = datetime.now(timezone.utc)
    comment = ContentComment(
        platform=account.platform,
        platform_comment_id=raw_reply.external_id,
        thread_id=thread.id,
        parent_comment_id=thread.top_level_comment_id,
        author_external_id=raw_reply.author_external_id,
        author_display_name=raw_reply.author_display_name,
        author_avatar_url=raw_reply.author_avatar_url,
        text_original=raw_reply.text,
        like_count=raw_reply.like_count,
        published_at=raw_reply.published_at,
        updated_at=raw_reply.published_at,
        is_own_reply=True,
        imported_at=now,
        last_synced_at=now,
    )
    db.add(comment)
    thread.total_reply_count += 1
    thread.last_synced_at = now
    db.commit()
    db.refresh(comment)
    return comment


def edit_reply(db: Session, account: PlatformAccount, adapter: PlatformAdapter, comment_platform_id: str, text: str) -> ContentComment:
    text = text.strip()
    if not text:
        raise ContentCommentActionError("Treść odpowiedzi nie może być pusta.")
    comment = get_own_reply(db, account, comment_platform_id)
    raw_reply = adapter.update_reply(comment.platform_comment_id, text)
    comment.text_original = raw_reply.text
    comment.updated_at = raw_reply.published_at
    comment.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)
    return comment


def delete_reply(db: Session, account: PlatformAccount, adapter: PlatformAdapter, comment_platform_id: str) -> None:
    comment = get_own_reply(db, account, comment_platform_id)
    adapter.delete_reply(comment.platform_comment_id)
    thread = db.get(ContentCommentThread, comment.thread_id)
    db.delete(comment)
    if thread is not None and thread.total_reply_count > 0:
        thread.total_reply_count -= 1
    db.commit()
