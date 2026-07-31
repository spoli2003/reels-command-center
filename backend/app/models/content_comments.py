"""Generic, cross-platform comment model — Release 0.8.0 (ADR-020).

Mirrors app/models/comments.py's YouTube-specific shape exactly, but FK'd to the
unified `Publication` (not `YoutubeVideo`), so Facebook and Instagram comments
share ONE storage + ONE query/sync/action service, reusing
comment_intelligence.py unchanged. YouTube's own comment tables/services are
untouched by this — see ADR-020.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContentCommentThread(Base):
    __tablename__ = "content_comment_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    platform_thread_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, index=True)
    top_level_comment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    author_external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    author_display_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    author_avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_original: Mapped[str] = mapped_column(Text, default="", nullable=False)
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    can_reply: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    publication = relationship("Publication")
    replies: Mapped[list["ContentComment"]] = relationship(back_populates="thread", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_content_comment_threads_publication_published", "publication_id", "published_at"),)


class ContentComment(Base):
    __tablename__ = "content_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    platform_comment_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("content_comment_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_comment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    author_external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    author_display_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    author_avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_original: Mapped[str] = mapped_column(Text, default="", nullable=False)
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_own_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    thread: Mapped[ContentCommentThread] = relationship(back_populates="replies")

    __table_args__ = (Index("ix_content_comments_thread_published", "thread_id", "published_at"),)
