from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    channels: Mapped[list["YoutubeChannel"]] = relationship(back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("platform", "external_account_id", name="uq_platform_external_account"),)


class YoutubeChannel(Base):
    __tablename__ = "youtube_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    youtube_channel_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    uploads_playlist_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subscriber_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    video_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[PlatformAccount] = relationship(back_populates="channels")
    videos: Mapped[list["YoutubeVideo"]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    snapshots: Mapped[list["YoutubeChannelSnapshot"]] = relationship(back_populates="channel", cascade="all, delete-orphan")


class YoutubeChannelSnapshot(Base):
    """Channel-level point-in-time snapshot, written once per sync run alongside video snapshots.

    Only accumulates from the moment this model was introduced onward — there is
    no way to backfill historical subscriber counts for periods before this table existed.
    """

    __tablename__ = "youtube_channel_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("youtube_channels.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    subscriber_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    video_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    channel: Mapped[YoutubeChannel] = relationship(back_populates="snapshots")


class YoutubeVideo(Base):
    __tablename__ = "youtube_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("youtube_channels.id", ondelete="CASCADE"), nullable=False, index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_short_candidate: Mapped[bool] = mapped_column(default=False, nullable=False)

    channel: Mapped[YoutubeChannel] = relationship(back_populates="videos")
    snapshots: Mapped[list["YoutubeMetricSnapshot"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class YoutubeMetricSnapshot(Base):
    __tablename__ = "youtube_metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("youtube_videos.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    views: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    video: Mapped[YoutubeVideo] = relationship(back_populates="snapshots")


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    videos_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    videos_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    snapshots_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    snapshots_deduplicated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    videos_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Comment-sync-specific counts (Release 0.7.0, platform="youtube_comments" rows
    # only) — reusing this same table/model as the ONE source of truth for every
    # sync type, discriminated by `platform`, rather than a parallel table.
    threads_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    replies_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
