from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class YoutubeStatus(BaseModel):
    configured: bool
    connected: bool
    channel_title: Optional[str] = None
    channel_id: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    video_count: int = 0
    message: str
    last_sync_status: Optional[str] = None
    last_sync_duration_seconds: Optional[float] = None
    last_sync_videos_discovered: Optional[int] = None
    last_sync_videos_new: Optional[int] = None
    last_sync_videos_updated: Optional[int] = None
    last_sync_snapshots_created: Optional[int] = None
    last_sync_snapshots_deduplicated: Optional[int] = None
    last_sync_videos_failed: Optional[int] = None
    last_sync_error: Optional[str] = None
    automatic_sync_enabled: bool = False
    automatic_sync_interval_hours: Optional[float] = None
    automatic_sync_next_at: Optional[datetime] = None
    automatic_sync_note: str = "Automatyczna synchronizacja nie jest jeszcze skonfigurowana — uruchamiaj ją ręcznie."
    # Release 0.7.0 — Community Inbox needs the youtube.force-ssl scope (read+write
    # comments), which existing connections made before this release don't have.
    comments_scope_granted: bool = False
    comments_reconnect_required: bool = False


class YoutubeVideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    youtube_video_id: str
    title: str
    published_at: datetime
    thumbnail_url: Optional[str]
    duration_seconds: Optional[int]
    is_short_candidate: bool
    views: int = 0
    likes: int = 0
    comments: int = 0
    # Deterministic structured metadata (Sprint 5 / Part 8) — same fields on the
    # detail endpoint, computed by the same function, so they never disagree.
    views_per_day: float = 0.0
    engagement_rate: float = 0.0
    trend: str = "insufficient_data"
    performance_score: float = 0.0
    performance_label: str = "average"
    engagement_category: str = "low"
    growth_category: str = "unknown"
    topic_keywords: list[str] = []
    # Historical growth metadata (Sprint 6 / Parts 7 & 12) — deterministic, for a
    # future AI layer to consume; never computed by AI itself.
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


class SyncResult(BaseModel):
    imported_videos: int
    channel_title: str
    synced_at: datetime
