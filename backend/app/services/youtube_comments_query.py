"""Community Inbox query/filter logic (Release 0.7.0 / Part 5).

Fetches once, classifies once (deterministic — see comment_intelligence.py), then
filters/sorts in Python. RCC's data scale (one channel, thousands of comments at
most) doesn't need SQL-level filtering; keeping this in Python keeps the filter
combinations trivially composable and testable without a query-builder.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.comments import YoutubeComment, YoutubeCommentThread
from app.models.integration import YoutubeVideo
from app.services.comment_intelligence import comment_priority_score, is_likely_question

RECENT_DAYS = 7


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def build_inbox_rows(db: Session, channel_id: int, now: Optional[datetime] = None) -> list[dict]:
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

    rows: list[dict] = []
    for thread in threads:
        thread_replies = replies_by_thread.get(thread.id, [])
        is_answered = any(reply.is_own_reply for reply in thread_replies)
        likely_question = is_likely_question(thread.text_original)
        priority = comment_priority_score(
            is_unanswered=not is_answered,
            is_question=likely_question,
            published_at=thread.published_at,
            like_count=thread.like_count,
            reply_count=thread.total_reply_count,
            now=now,
        )
        rows.append(
            {
                "thread": thread,
                "replies": thread_replies,
                "video": videos_by_id.get(thread.video_id),
                "is_answered": is_answered,
                "is_likely_question": likely_question,
                "priority_score": priority,
            }
        )
    return rows


def filter_and_sort_rows(
    rows: list[dict],
    *,
    quick: Optional[str] = None,
    video_id: Optional[int] = None,
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort: str = "newest",
    now: Optional[datetime] = None,
) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    filtered = rows

    if video_id is not None:
        filtered = [r for r in filtered if r["video"] is not None and r["video"].id == video_id]

    if quick == "unanswered":
        filtered = [r for r in filtered if not r["is_answered"]]
    elif quick == "answered":
        filtered = [r for r in filtered if r["is_answered"]]
    elif quick == "questions":
        filtered = [r for r in filtered if r["is_likely_question"]]
    elif quick == "recent":
        cutoff = now - timedelta(days=RECENT_DAYS)
        filtered = [r for r in filtered if _aware(r["thread"].published_at) >= cutoff]
    elif quick == "with_replies":
        filtered = [r for r in filtered if r["thread"].total_reply_count > 0]

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
    elif sort == "priority":
        filtered = sorted(filtered, key=lambda r: r["priority_score"], reverse=True)
    else:
        filtered = sorted(filtered, key=lambda r: r["thread"].published_at, reverse=True)
    return filtered


def build_inbox_summary(rows: list[dict], now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RECENT_DAYS)
    return {
        "total_visible": len(rows),
        "unanswered_count": sum(1 for r in rows if not r["is_answered"]),
        "questions_count": sum(1 for r in rows if r["is_likely_question"]),
        "recent_count": sum(1 for r in rows if _aware(r["thread"].published_at) >= cutoff),
        "with_replies_count": sum(1 for r in rows if r["thread"].total_reply_count > 0),
    }
