from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MetricSnapshotCreate(BaseModel):
    views: int = Field(default=0, ge=0)
    reach: Optional[int] = Field(default=None, ge=0)
    impressions: Optional[int] = Field(default=None, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    watch_time_seconds: Optional[int] = Field(default=None, ge=0)
    followers_gained: Optional[int] = Field(default=None, ge=0)


class MetricSnapshotRead(MetricSnapshotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    captured_at: datetime


class PublicationCreate(BaseModel):
    platform: str = Field(min_length=2, max_length=32)
    external_id: str = Field(min_length=1, max_length=255)
    url: Optional[str] = None
    published_at: Optional[datetime] = None


class PublicationRead(PublicationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    latest_metrics: Optional[MetricSnapshotRead] = None


class ContentVideoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    category: Optional[str] = Field(default=None, max_length=100)
    duration_seconds: Optional[int] = Field(default=None, ge=0)
    language: str = Field(default="pl", min_length=2, max_length=16)


class ContentVideoUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    duration_seconds: Optional[int] = Field(default=None, ge=0)
    language: Optional[str] = Field(default=None, min_length=2, max_length=16)


class ContentVideoRead(ContentVideoCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    public_id: str
    created_at: datetime
    updated_at: datetime
    publications: list[PublicationRead] = []
    total_views: int = 0
    total_interactions: int = 0
    engagement_rate: float = 0.0
