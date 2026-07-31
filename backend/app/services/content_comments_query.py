"""Generic Community Inbox query/filter logic — Release 0.8.0 (ADR-020). Mirrors
youtube_comments_query.py exactly (same conversation-state engine reuse, same
percentile "highly liked" highlighting), operating over the generic
ContentCommentThread/ContentComment tables so Facebook and Instagram share one
implementation with each other (and structurally with YouTube's own inbox)."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import Publication
from app.models.content_comments import ContentComment, ContentCommentThread
from app.services.comment_intelligence import comment_priority_score, determine_conversation_state, is_likely_question

RECENT_DAYS = 7
HIGHLY_LIKED_PERCENTILE = 0.9


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _is_moderated(_moderation_status: str) -> bool:
    return False  # Facebook/Instagram Graph API doesn't expose a moderation status field for comments today.


def _last_message(
    thread: ContentCommentThread, replies: list[ContentComment], own_external_id: Optional[str]
) -> tuple[datetime, bool]:
    top_level_is_own = bool(own_external_id) and thread.author_external_id == own_external_id
    messages: list[tuple[datetime, bool]] = [(thread.published_at, top_level_is_own)]
    messages.extend((reply.published_at, reply.is_own_reply) for reply in replies)
    messages.sort(key=lambda m: _aware(m[0]))
    return messages[-1]


def build_inbox_rows(db: Session, account_id: int, own_external_id: Optional[str] = None, now: Optional[datetime] = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    threads = list(
        db.scalars(
            select(ContentCommentThread)
            .join(Publication, ContentCommentThread.publication_id == Publication.id)
            .where(Publication.platform_account_id == account_id)
            .order_by(ContentCommentThread.published_at.desc())
        ).all()
    )
    if not threads:
        return []

    thread_ids = [t.id for t in threads]
    replies = db.scalars(
        select(ContentComment).where(ContentComment.thread_id.in_(thread_ids)).order_by(ContentComment.published_at.asc())
    ).all()
    replies_by_thread: dict[int, list[ContentComment]] = {}
    for reply in replies:
        replies_by_thread.setdefault(reply.thread_id, []).append(reply)

    publication_ids = {t.publication_id for t in threads}
    publications_by_id = {p.id: p for p in db.scalars(select(Publication).where(Publication.id.in_(publication_ids))).all()}

    all_like_counts = sorted(t.like_count for t in threads)
    highly_liked_threshold = (
        all_like_counts[min(len(all_like_counts) - 1, int(len(all_like_counts) * HIGHLY_LIKED_PERCENTILE))] if all_like_counts else 0
    )

    rows: list[dict] = []
    for thread in threads:
        thread_replies = replies_by_thread.get(thread.id, [])
        top_level_is_own = bool(own_external_id) and thread.author_external_id == own_external_id
        has_channel_spoken = top_level_is_own or any(reply.is_own_reply for reply in thread_replies)
        last_message_at, last_message_is_own = _last_message(thread, thread_replies, own_external_id)
        state = determine_conversation_state(
            has_own_reply=has_channel_spoken, last_message_is_own=last_message_is_own, is_moderated=False
        )
        likely_question = is_likely_question(thread.text_original)
        priority = comment_priority_score(
            state=state,
            is_question=likely_question,
            last_message_at=last_message_at,
            like_count=thread.like_count,
            reply_count=thread.total_reply_count,
            now=now,
        )
        rows.append(
            {
                "thread": thread,
                "replies": thread_replies,
                "publication": publications_by_id.get(thread.publication_id),
                "conversation_state": state,
                "is_own_thread": top_level_is_own,
                "is_likely_question": likely_question,
                "priority_score": priority,
                "last_message_at": last_message_at,
                "is_highly_liked": thread.like_count > 0 and thread.like_count >= highly_liked_threshold and highly_liked_threshold > 0,
            }
        )
    return rows


def filter_and_sort_rows(
    rows: list[dict],
    *,
    quick: Optional[str] = None,
    publication_id: Optional[int] = None,
    author: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "newest",
    now: Optional[datetime] = None,
) -> list[dict]:
    from app.services.comment_intelligence import ConversationState

    now = now or datetime.now(timezone.utc)
    if quick == "mine":
        filtered = [r for r in rows if r["is_own_thread"]]
    else:
        filtered = [r for r in rows if not r["is_own_thread"]]

    if publication_id is not None:
        filtered = [r for r in filtered if r["publication"] is not None and r["publication"].id == publication_id]

    state_filters = {
        "new": ConversationState.NEW,
        "waiting": ConversationState.WAITING,
        "resolved": ConversationState.RESOLVED,
        "closed": ConversationState.CLOSED,
    }
    if quick in state_filters:
        filtered = [r for r in filtered if r["conversation_state"] == state_filters[quick]]
    elif quick == "unanswered":
        filtered = [r for r in filtered if r["conversation_state"] in (ConversationState.NEW, ConversationState.WAITING)]
    elif quick == "answered":
        filtered = [r for r in filtered if r["conversation_state"] == ConversationState.RESOLVED]
    elif quick == "questions":
        filtered = [r for r in filtered if r["is_likely_question"]]
    elif quick == "recent":
        cutoff = now - timedelta(days=RECENT_DAYS)
        filtered = [r for r in filtered if _aware(r["thread"].published_at) >= cutoff]
    elif quick == "with_replies":
        filtered = [r for r in filtered if r["thread"].total_reply_count > 0]
    elif quick == "highly_liked":
        filtered = [r for r in filtered if r["is_highly_liked"]]

    if author:
        needle_author = author.strip().lower()
        filtered = [r for r in filtered if needle_author in r["thread"].author_display_name.lower()]
    if search:
        needle = search.strip().lower()
        filtered = [
            r for r in filtered if needle in r["thread"].text_original.lower() or needle in r["thread"].author_display_name.lower()
        ]

    if sort == "oldest":
        filtered = sorted(filtered, key=lambda r: r["thread"].published_at)
    elif sort == "most_liked":
        filtered = sorted(filtered, key=lambda r: r["thread"].like_count, reverse=True)
    elif sort == "most_replies":
        filtered = sorted(filtered, key=lambda r: r["thread"].total_reply_count, reverse=True)
    elif sort == "priority":
        filtered = sorted(filtered, key=lambda r: r["priority_score"], reverse=True)
    elif sort == "recently_active":
        filtered = sorted(filtered, key=lambda r: r["last_message_at"], reverse=True)
    else:
        filtered = sorted(filtered, key=lambda r: r["thread"].published_at, reverse=True)
    return filtered


def build_inbox_summary(rows: list[dict], now: Optional[datetime] = None) -> dict:
    from app.services.comment_intelligence import ConversationState

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RECENT_DAYS)
    audience_rows = [r for r in rows if not r["is_own_thread"]]
    return {
        "total_visible": len(audience_rows),
        "own_threads_count": sum(1 for r in rows if r["is_own_thread"]),
        "new_count": sum(1 for r in audience_rows if r["conversation_state"] == ConversationState.NEW),
        "waiting_count": sum(1 for r in audience_rows if r["conversation_state"] == ConversationState.WAITING),
        "resolved_count": sum(1 for r in audience_rows if r["conversation_state"] == ConversationState.RESOLVED),
        "closed_count": sum(1 for r in audience_rows if r["conversation_state"] == ConversationState.CLOSED),
        "awaiting_reply_count": sum(1 for r in audience_rows if r["conversation_state"] in (ConversationState.NEW, ConversationState.WAITING)),
        "questions_count": sum(1 for r in audience_rows if r["is_likely_question"]),
        "recent_count": sum(1 for r in audience_rows if _aware(r["thread"].published_at) >= cutoff),
        "with_replies_count": sum(1 for r in audience_rows if r["thread"].total_reply_count > 0),
    }
