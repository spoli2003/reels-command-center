"""Generic, platform-neutral schemas — Release 0.8.0 (ADR-020). Structurally
mirrors backend/app/schemas/comments.py and integration.py, but field names are
platform-neutral (external_id/platform, not youtube_video_id) since the same
shape now serves YouTube, Facebook, and Instagram identically."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PlatformSummary(BaseModel):
    platform: str
    connected: bool
    display_name: Optional[str] = None
    audience_count: Optional[int] = None
    views_available: bool = True


class PlatformStatus(BaseModel):
    platform: str
    connected: bool
    configured: bool
    display_name: Optional[str] = None
    video_count: int = 0
    last_synced_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_error: Optional[str] = None
    last_comments_synced_at: Optional[datetime] = None
    last_comments_sync_status: Optional[str] = None
    last_comments_sync_error: Optional[str] = None
    required_permissions: list[str] = Field(default_factory=list)
    granted_permissions: list[str] = Field(default_factory=list)
    missing_permissions: list[str] = Field(default_factory=list)
    optional_permissions: list[str] = Field(default_factory=list)
    missing_optional_permissions: list[str] = Field(default_factory=list)
    scheduler_enabled: bool = False
    next_scheduled_sync_at: Optional[datetime] = None
    message: str


class PlatformVideoRead(BaseModel):
    external_id: str
    platform: str
    title: str
    description: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    views: int
    likes: int
    comments: int
    shares: int
    saves: int
    reach: Optional[int] = None
    impressions: Optional[int] = None
    followers_gained: Optional[int] = None
    engagement_rate: float


class PlatformReplyRead(BaseModel):
    platform_comment_id: str
    author_external_id: Optional[str] = None
    author_display_name: str
    author_avatar_url: Optional[str] = None
    text_original: str
    like_count: int
    published_at: datetime
    updated_at: datetime
    is_own_reply: bool


class PlatformCommentThreadRead(BaseModel):
    platform_thread_id: str
    external_id: str  # the video/post/reel's external_id
    video_title: str
    video_thumbnail_url: Optional[str] = None
    top_level_comment_id: str
    author_external_id: Optional[str] = None
    author_display_name: str
    author_avatar_url: Optional[str] = None
    text_original: str
    like_count: int
    published_at: datetime
    updated_at: datetime
    total_reply_count: int
    can_reply: bool
    is_own_thread: bool
    conversation_state: str
    last_message_at: datetime
    is_likely_question: bool
    is_highly_liked: bool
    priority_score: float
    replies: list[PlatformReplyRead]


class PlatformCommentInboxSummary(BaseModel):
    total_visible: int
    own_threads_count: int
    new_count: int
    waiting_count: int
    resolved_count: int
    closed_count: int
    awaiting_reply_count: int
    questions_count: int
    recent_count: int
    with_replies_count: int


class PlatformCommentInboxRead(BaseModel):
    summary: PlatformCommentInboxSummary
    threads: list[PlatformCommentThreadRead]


class PlatformReplyCreate(BaseModel):
    text: str


class PlatformReplyUpdate(BaseModel):
    text: str


# --- Meta Page Selection (Release 0.8.1 / ADR-023) ---------------------------
# RCC never auto-connects the first Facebook Page returned by Meta — the user
# always picks explicitly from every Page their account manages, with enough
# context (picture, category, followers, linked Instagram) to choose correctly.


class MetaPendingInstagram(BaseModel):
    id: str
    username: Optional[str] = None
    picture_url: Optional[str] = None
    account_type: Optional[str] = None
    followers: Optional[int] = None
    media_count: Optional[int] = None


class MetaPendingPage(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    picture_url: Optional[str] = None
    followers: Optional[int] = None
    instagram: Optional[MetaPendingInstagram] = None


class MetaPendingPagesRead(BaseModel):
    target: str
    pages: list[MetaPendingPage]


class MetaPageSelectionRequest(BaseModel):
    selection_id: str
    page_id: str


class MetaPageSelectionResult(BaseModel):
    platform: str
    display_name: str
    initial_sync_status: str = "not_started"
    initial_sync_message: Optional[str] = None
    imported_items: int = 0
    comments_imported: int = 0
