from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReplyRead(BaseModel):
    platform_comment_id: str
    author_channel_id: Optional[str] = None
    author_display_name: str
    author_avatar_url: Optional[str] = None
    text_original: str
    like_count: int
    published_at: datetime
    updated_at: datetime
    is_own_reply: bool


class CommentThreadRead(BaseModel):
    platform_thread_id: str
    youtube_video_id: str
    video_title: str
    video_thumbnail_url: Optional[str] = None
    top_level_comment_id: str
    author_channel_id: Optional[str] = None
    author_display_name: str
    author_avatar_url: Optional[str] = None
    text_original: str
    like_count: int
    published_at: datetime
    updated_at: datetime
    total_reply_count: int
    can_reply: bool
    is_answered: bool
    is_likely_question: bool
    priority_score: float
    replies: list[ReplyRead]


class CommentInboxSummary(BaseModel):
    total_visible: int
    unanswered_count: int
    questions_count: int
    recent_count: int
    with_replies_count: int


class CommentInboxRead(BaseModel):
    summary: CommentInboxSummary
    threads: list[CommentThreadRead]


class ReplyCreate(BaseModel):
    text: str


class ReplyUpdate(BaseModel):
    text: str


class CommentSyncTrigger(BaseModel):
    mode: str = "incremental"  # "incremental" | "full"
    youtube_video_id: Optional[str] = None


class CommentSyncStatus(BaseModel):
    last_synced_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_duration_seconds: Optional[float] = None
    last_sync_threads_discovered: Optional[int] = None
    last_sync_comments_imported: Optional[int] = None
    last_sync_replies_imported: Optional[int] = None
    last_sync_videos_failed: Optional[int] = None
    last_sync_error: Optional[str] = None
    automatic_sync_enabled: bool = False
    automatic_sync_next_at: Optional[datetime] = None
    comments_scope_granted: bool = False


class QuickReplyTemplateRead(BaseModel):
    id: int
    text: str
    position: int


class QuickReplyTemplateCreate(BaseModel):
    text: str


class QuickReplyTemplateUpdate(BaseModel):
    text: str
