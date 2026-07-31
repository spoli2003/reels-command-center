from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SummaryRead(BaseModel):
    # last_synced_at intentionally NOT here — GET /status is the single source of
    # truth for synchronization time/state across the whole app (bugfix: Home,
    # Dashboard, and Video Detail previously each read a separately-computed
    # last_synced_at from this schema, which could show stale data relative to
    # /status; see docs/DECISIONS.md ADR-016).
    channel_title: Optional[str] = None
    subscriber_count: int = 0
    total_videos: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    avg_views_per_video: float = 0.0
    avg_engagement_rate: float = 0.0
    days_since_oldest_video: Optional[int] = None
    channel_views_per_day: Optional[float] = None


class TimeseriesPoint(BaseModel):
    date: str
    value: int


class UploadBucket(BaseModel):
    bucket: str
    count: int


class VideoRowRead(BaseModel):
    youtube_video_id: str
    title: str
    published_at: datetime
    thumbnail_url: Optional[str] = None
    views: int
    likes: int
    comments: int
    followers_gained: Optional[int] = None
    engagement_rate: float


class TopVideoRead(VideoRowRead):
    score: float


class ScatterPoint(BaseModel):
    youtube_video_id: str
    title: str
    views: int
    likes: int


class VideoDetailRead(BaseModel):
    youtube_video_id: str
    title: str
    description: str
    published_at: datetime
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    is_short_candidate: bool
    views: int
    likes: int
    comments: int
    engagement_rate: float
    views_per_day: float
    like_ratio: float
    comment_ratio: float
    # Deterministic structured metadata (Sprint 5 / Part 8) — same fields and same
    # computation as the /videos list endpoint, so they never disagree.
    trend: str = "insufficient_data"
    performance_score: float = 0.0
    performance_label: str = "average"
    engagement_category: str = "low"
    growth_category: str = "unknown"
    topic_keywords: list[str] = []
    velocity: Optional[float] = None
    acceleration: Optional[float] = None
    views_gained_24h: Optional[int] = None
    views_gained_7d: Optional[int] = None
    views_gained_30d: Optional[int] = None
    peak_growth_date: Optional[str] = None
    peak_growth_views: Optional[int] = None
    largest_slowdown_date: Optional[str] = None
    largest_slowdown_views: Optional[int] = None
    snapshot_count: int = 0


class VideoHistoryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    captured_at: datetime
    views: int
    likes: int
    comments: int


class VideoHistoryBucket(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    period_start: datetime
    period_end: datetime
    views: int
    likes: int
    comments: int


class VideoHistoryRead(BaseModel):
    """Sprint 6 / Part 9 — raw synchronization points plus a creator-oriented,
    age-anchored bucketing of the same data for charting. `insufficient` is True
    when fewer than 2 buckets exist, meaning the caller should render an
    explanatory empty state instead of a chart."""

    points: list[VideoHistoryPoint]
    granularity: str
    buckets: list[VideoHistoryBucket]
    insufficient: bool


class ChannelHistoryBucket(BaseModel):
    label: str
    period_start: datetime
    period_end: datetime
    subscriber_count: int
    view_count: int
    video_count: int


class ChannelHistoryRead(BaseModel):
    """Sprint 6 / Part 10 — channel-wide history, bucketed the same way as video
    history but anchored to how long RCC has been tracking this channel (its first
    stored snapshot), since a channel has no single "publish date"."""

    granularity: str
    buckets: list[ChannelHistoryBucket]
    insufficient: bool


class DataQualityReport(BaseModel):
    videos_checked: int
    snapshots_checked: int
    exact_duplicate_snapshots_found: int
    exact_duplicate_snapshots_repaired: int
    impossible_timestamps: list[dict]
    non_monotonic_view_drops: list[dict]
    naive_timestamps_found: int
    is_clean: bool
