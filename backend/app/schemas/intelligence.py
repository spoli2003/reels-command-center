from typing import Optional

from pydantic import BaseModel


class SupportingVideoRead(BaseModel):
    youtube_video_id: str
    title: str
    thumbnail_url: Optional[str] = None


class RecommendationRead(BaseModel):
    id: str
    category: str
    headline: str
    explanation: str
    confidence: str
    supporting_metrics: dict
    supporting_videos: list[SupportingVideoRead] = []


class DailyBriefRead(BaseModel):
    views_gained_24h: Optional[int] = None
    subscribers_gained_24h: Optional[int] = None
    best_growing_video: Optional[SupportingVideoRead] = None
    best_growing_video_gain: Optional[int] = None
    biggest_slowdown_video: Optional[SupportingVideoRead] = None
    biggest_slowdown_delta: Optional[float] = None
    attention_video_count: int = 0
    days_since_last_upload: Optional[int] = None
    no_upload_warning: Optional[str] = None


class TopicRead(BaseModel):
    keyword: str
    video_count: int
    median_views: float
    median_views_per_day: float
    median_engagement: float
    best_video: Optional[SupportingVideoRead] = None
    worst_video: Optional[SupportingVideoRead] = None
    trend: str


class PublishingInsightRead(BaseModel):
    best_weekday: Optional[str] = None
    best_weekday_median_vpd: Optional[float] = None
    best_hour: Optional[int] = None
    best_hour_median_vpd: Optional[float] = None
    best_cadence_label: Optional[str] = None
    best_cadence_median_vpd: Optional[float] = None
    best_streak_start: Optional[str] = None
    best_streak_end: Optional[str] = None
    best_streak_video_count: Optional[int] = None
    best_streak_avg_vpd: Optional[float] = None
    worst_streak_start: Optional[str] = None
    worst_streak_end: Optional[str] = None
    worst_streak_video_count: Optional[int] = None
    worst_streak_avg_vpd: Optional[float] = None
    insufficient_data_notes: list[str] = []


class IntelligenceReportRead(BaseModel):
    daily_brief: DailyBriefRead
    winning_videos: list[RecommendationRead]
    attention_videos: list[RecommendationRead]
    too_new_count: int
    topics: list[TopicRead]
    publishing: PublishingInsightRead
    follow_up_opportunities: list[RecommendationRead]
    title_patterns: list[RecommendationRead]
    content_recommendations: list[RecommendationRead]
