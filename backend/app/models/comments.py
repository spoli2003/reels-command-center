"""YouTube Community Inbox data model (Release 0.7.0).

A thread's top-level comment lives on YoutubeCommentThread itself (mirroring the
YouTube Data API's commentThreads resource, which embeds the top-level comment in
its own snippet). YoutubeComment stores only replies — YouTube comments are a flat,
two-level structure (no nested replies-of-replies), so `parent_comment_id` always
points back to the thread's `top_level_comment_id`.

Both tables are upsert-only from the sync service: a row is never deleted just
because a later sync no longer returns it (the API can temporarily omit items during
pagination hiccups or moderation review) — see docs/DECISIONS.md ADR-018.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class YoutubeCommentThread(Base):
    __tablename__ = "youtube_comment_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_thread_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("youtube_videos.id", ondelete="CASCADE"), nullable=False, index=True)
    top_level_comment_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    author_channel_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    author_display_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    author_avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_original: Mapped[str] = mapped_column(Text, default="", nullable=False)
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(32), default="published", nullable=False)
    can_reply: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Read-only reflection of the connected channel's OWN like on this comment
    # (YouTube's `viewerRating`, values "like"/"none") — the API has no "like
    # count contributed by me" concept beyond this. Never a like button (Part 3).
    viewer_rating: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    video = relationship("YoutubeVideo")
    replies: Mapped[list["YoutubeComment"]] = relationship(back_populates="thread", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_comment_threads_video_published", "video_id", "published_at"),)


class YoutubeComment(Base):
    __tablename__ = "youtube_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_comment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("youtube_comment_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_comment_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    author_channel_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    author_display_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    author_avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_original: Mapped[str] = mapped_column(Text, default="", nullable=False)
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_own_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(32), default="published", nullable=False)
    viewer_rating: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    thread: Mapped[YoutubeCommentThread] = relationship(back_populates="replies")

    __table_args__ = (Index("ix_comments_thread_published", "thread_id", "published_at"),)


class QuickReplyTemplate(Base):
    """Locally managed reply templates (Part 9). Scoped by `account_id` — RCC is
    single-tenant today; once Workspace exists (ADR-010), add a workspace_id and
    this becomes workspace-scoped without changing shape."""

    __tablename__ = "quick_reply_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
