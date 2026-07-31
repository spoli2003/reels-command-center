"""Community Inbox query/filter logic.

Fetches once, classifies once (deterministic — see comment_intelligence.py), then
filters/sorts in Python. RCC's data scale (one channel, thousands of comments at
most) doesn't need SQL-level filtering; keeping this in Python keeps the filter
combinations trivially composable and testable without a query-builder.

Release 0.7.1 fixed the conversation-state computation (see ADR-019) and added
percentile-based "highly liked" highlighting.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.comments import YoutubeComment, YoutubeCommentThread
from app.models.integration import YoutubeVideo
from app.services.comment_intelligence import ConversationState, comment_priority_score, determine_conversation_state, is_likely_question

RECENT_DAYS = 7
HIGHLY_LIKED_PERCENTILE = 0.9  # top 10% of like counts within the currently visible set


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _is_moderated(moderation_status: str) -> bool:
    return moderation_status not in ("published", "")


def _last_message(thread: YoutubeCommentThread, replies: list[YoutubeComment], own_channel_youtube_id: Optional[str]) -> tuple[datetime, bool]:
    """The most recent message in the FULL thread (top-level comment + every
    reply), never just the top-level comment — Part 1's core requirement."""
    messages: list[tuple[datetime, bool]] = [
        (thread.published_at, bool(own_channel_youtube_id) and thread.author_channel_id == own_channel_youtube_id)
    ]
    messages.extend((reply.published_at, reply.is_own_reply) for reply in replies)
    messages.sort(key=lambda m: _aware(m[0]))
    return messages[-1]


def build_inbox_rows(db: Session, channel_id: int, channel_youtube_id: Optional[str] = None, now: Optional[datetime] = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    threads = list(
        db.scalars(
            select(YoutubeCommentThread)
            .join(YoutubeVideo, YoutubeCommentThread.video_id == YoutubeVideo.id)
            .where(YoutubeVideo.channel_id == channel_id)
            .order_by(YoutubeCommentThread.published_at.desc())
        ).all()
    )
    if not threads:
        return []

    thread_ids = [t.id for t in threads]
    replies = db.scalars(
        select(YoutubeComment).where(YoutubeComment.thread_id.in_(thread_ids)).order_by(YoutubeComment.published_at.asc())
    ).all()
    replies_by_thread: dict[int, list[YoutubeComment]] = {}
    for reply in replies:
        replies_by_thread.setdefault(reply.thread_id, []).append(reply)

    video_ids = {t.video_id for t in threads}
    videos_by_id = {v.id: v for v in db.scalars(select(YoutubeVideo).where(YoutubeVideo.id.in_(video_ids))).all()}

    # Percentile threshold for "highly liked" — computed once over the whole
    # channel's visible comments, not per-filter, so the badge means the same
    # thing regardless of which filter is currently active.
    all_like_counts = sorted(t.like_count for t in threads)
    highly_liked_threshold = (
        all_like_counts[min(len(all_like_counts) - 1, int(len(all_like_counts) * HIGHLY_LIKED_PERCENTILE))] if all_like_counts else 0
    )

    rows: list[dict] = []
    for thread in threads:
        thread_replies = replies_by_thread.get(thread.id, [])
        last_message_at, last_message_is_own = _last_message(thread, thread_replies, channel_youtube_id)
        # "Has the channel ever spoken in this thread" includes the top-level
        # comment itself, not just replies — a creator's own pinned top-level
        # comment (a common practice, e.g. linking the full video) must not be
        # flagged "New / needs reply" just because it has no reply rows.
        top_level_is_own = bool(channel_youtube_id) and thread.author_channel_id == channel_youtube_id
        has_channel_spoken = top_level_is_own or any(reply.is_own_reply for reply in thread_replies)
        state = determine_conversation_state(
            has_own_reply=has_channel_spoken,
            last_message_is_own=last_message_is_own,
            is_moderated=_is_moderated(thread.moderation_status),
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
                "video": videos_by_id.get(thread.video_id),
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
    video_id: Optional[int] = None,
    author: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort: str = "newest",
    now: Optional[datetime] = None,
) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    # The default inbox is an audience inbox: creator-authored top-level
    # comments (including pinned promotional comments) are kept in the
    # database, but live in the dedicated `mine` view. Replies written by the
    # creator inside a viewer-started thread remain part of that viewer thread.
    if quick == "mine":
        filtered = [r for r in rows if r["is_own_thread"]]
    else:
        filtered = [r for r in rows if not r["is_own_thread"]]

    if video_id is not None:
        filtered = [r for r in filtered if r["video"] is not None and r["video"].id == video_id]

    state_filters = {"new": ConversationState.NEW, "waiting": ConversationState.WAITING, "resolved": ConversationState.RESOLVED, "closed": ConversationState.CLOSED}
    if quick in state_filters:
        filtered = [r for r in filtered if r["conversation_state"] == state_filters[quick]]
    elif quick == "unanswered":
        # Convenience alias: anything that isn't fully resolved (nor closed).
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
            r
            for r in filtered
            if needle in r["thread"].text_original.lower() or needle in r["thread"].author_display_name.lower()
        ]
    if date_from is not None:
        date_from = _aware(date_from)
        filtered = [r for r in filtered if _aware(r["thread"].published_at) >= date_from]
    if date_to is not None:
        date_to = _aware(date_to)
        filtered = [r for r in filtered if _aware(r["thread"].published_at) <= date_to]

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
        # "awaiting reply" = anything not resolved/closed — the actionable count.
        "awaiting_reply_count": sum(1 for r in audience_rows if r["conversation_state"] in (ConversationState.NEW, ConversationState.WAITING)),
        "questions_count": sum(1 for r in audience_rows if r["is_likely_question"]),
        "recent_count": sum(1 for r in audience_rows if _aware(r["thread"].published_at) >= cutoff),
        "with_replies_count": sum(1 for r in audience_rows if r["thread"].total_reply_count > 0),
    }
