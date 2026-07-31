"""Generic platform adapter contract — Release 0.8.0 / Parts 2 & 9 (ADR-020).

Every platform beyond YouTube (Facebook, Instagram, and any future platform
like TikTok) implements this ONE interface. The generic sync/comment services
(content_sync.py, content_comment_sync.py, content_comment_actions.py) drive
any adapter identically — adding a platform means writing a new adapter module,
never a new sync/service/table.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol


@dataclass
class RawContentItem:
    """One post/video/reel from any platform, normalized. The generic sync
    service maps this into ContentVideo/Publication/MetricSnapshot rows."""

    external_id: str
    title: str
    description: str
    url: Optional[str]
    published_at: Optional[datetime]
    thumbnail_url: Optional[str]
    duration_seconds: Optional[int]
    views: int
    likes: int
    comments: int
    shares: int = 0
    saves: int = 0
    reach: Optional[int] = None
    impressions: Optional[int] = None
    watch_time_seconds: Optional[int] = None
    # Populate only when the connected platform attributes audience growth to
    # this exact item. Never infer it from channel/account-level totals.
    followers_gained: Optional[int] = None
    # Some APIs expose one piece of content through more than one edge and
    # assign a different id to the wrapper object. Facebook, for example,
    # returns a Reel through both /videos (the canonical video id) and /posts
    # (a Page post id). Adapters can report those wrapper ids here so the
    # generic sync can merge legacy duplicates into the canonical publication.
    alternate_external_ids: tuple[str, ...] = ()


@dataclass
class RawComment:
    external_id: str
    parent_external_id: Optional[str]  # None for a top-level comment
    author_external_id: Optional[str]
    author_display_name: str
    author_avatar_url: Optional[str]
    text: str
    like_count: int
    published_at: datetime
    is_own: bool


@dataclass
class RawCommentThread:
    external_id: str  # equal to the top-level comment's external_id
    top_level: RawComment
    total_reply_count: int
    can_reply: bool = True
    replies: list[RawComment] = field(default_factory=list)


class PlatformAdapter(Protocol):
    """Implemented by FacebookAdapter, InstagramAdapter, ... A future TikTok
    adapter is the only new code a new platform requires."""

    platform: str

    def list_content_items(self) -> list[RawContentItem]: ...

    def list_comment_threads(self, external_content_id: str) -> list[RawCommentThread]:
        """All comment threads for one content item — full thread (top-level +
        every reply) in one call; the generic comment sync handles pagination
        internally per-adapter if the platform requires it."""
        ...

    def post_reply(self, thread_external_id: str, text: str) -> RawComment: ...

    def update_reply(self, comment_external_id: str, text: str) -> RawComment: ...

    def delete_reply(self, comment_external_id: str) -> None: ...
