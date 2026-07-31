from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContentVideo(Base):
    __tablename__ = "content_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid4()), nullable=False)
    title: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="pl", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    publications: Mapped[list["Publication"]] = relationship(back_populates="content_video", cascade="all, delete-orphan")


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_video_id: Mapped[int] = mapped_column(ForeignKey("content_videos.id", ondelete="CASCADE"), index=True, nullable=False)
    platform_account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("platform_accounts.id", ondelete="SET NULL"), index=True, nullable=True)
    platform: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    content_video: Mapped[ContentVideo] = relationship(back_populates="publications")
    snapshots: Mapped[list["MetricSnapshot"]] = relationship(back_populates="publication", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("platform", "external_id", name="uq_publication_platform_external_id"),)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), index=True, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)
    views: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reach: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    impressions: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    likes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    saves: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    watch_time_seconds: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    followers_gained: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    publication: Mapped[Publication] = relationship(back_populates="snapshots")
