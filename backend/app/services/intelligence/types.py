"""Platform-agnostic domain types for the Creator Intelligence engine.

Nothing in this module (or anywhere under app/services/intelligence/) may import
a YouTube-specific model. A future Facebook/Instagram/TikTok adapter builds the
same ContentItem shape from its own tables and every function here works unchanged.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


@dataclass
class SnapshotPoint:
    captured_at: datetime
    views: int
    likes: int
    comments: int


@dataclass
class ContentItem:
    id: str
    platform: str
    title: str
    url: Optional[str]
    thumbnail_url: Optional[str]
    published_at: datetime
    views: int
    likes: int
    comments: int
    history: list[SnapshotPoint] = field(default_factory=list)


class Trend(str, Enum):
    ACCELERATING = "accelerating"
    STEADY = "steady"
    SLOWING = "slowing"
    DECLINING = "declining"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class DerivedItem(ContentItem):
    age_days: int = 0
    views_per_day: float = 0.0
    engagement_rate: float = 0.0
    velocity: Optional[float] = None
    acceleration: Optional[float] = None
    trend: Trend = Trend.INSUFFICIENT_DATA


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Recommendation:
    id: str
    category: str
    headline: str
    explanation: str
    confidence: Confidence
    supporting_metrics: dict
    supporting_video_ids: list[str] = field(default_factory=list)
