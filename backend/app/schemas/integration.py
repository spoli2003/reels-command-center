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


class SyncResult(BaseModel):
    imported_videos: int
    channel_title: str
    synced_at: datetime
