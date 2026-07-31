"""Facebook Page adapter — Release 0.8.0 / Part 3.

Imports Page posts and videos (Reels are returned by the /videos edge with
`is_reels_video` when present — Graph API doesn't have a fully separate "Reels"
list endpoint, unlike Instagram) with available Insights metrics, and Page-level
comments, into the generic PlatformAdapter contract.
"""

import re
from typing import Optional

from app.integrations.meta.client import GraphClient, parse_graph_timestamp
from app.services.platforms.base import RawComment, RawCommentThread, RawContentItem


class FacebookAdapter:
    platform = "facebook"

    def __init__(self, client: GraphClient, page_id: str):
        self.client = client
        self.page_id = page_id

    def get_audience_count(self) -> int | None:
        value = self.client.get_page(self.page_id).get("fan_count")
        return int(value) if isinstance(value, (int, float)) else None

    def list_content_items(self) -> list[RawContentItem]:
        items: list[RawContentItem] = []
        videos = self.client.list_page_videos(self.page_id)
        video_ids = {str(raw["id"]) for raw in videos}
        alternate_ids_by_video: dict[str, list[str]] = {}
        linked_posts_by_video: dict[str, dict] = {}
        genuine_posts: list[dict] = []

        # Meta exposes a Reel twice: /videos returns the actual video node,
        # while /posts returns a Page-post wrapper with a different id. The
        # wrapper permalink still contains the canonical Reel id, e.g.
        #   post id:  PAGE_ID_POST_ID
        #   URL:      facebook.com/reel/VIDEO_ID/
        # Prefer the video node (it carries the real view count) and retain the
        # wrapper id as an alias so the sync service can clean old duplicates.
        for raw in self.client.list_page_posts(self.page_id):
            linked_video_id = _video_id_from_permalink(raw.get("permalink_url"))
            if linked_video_id and linked_video_id in video_ids:
                alternate_ids_by_video.setdefault(linked_video_id, []).append(str(raw["id"]))
                linked_posts_by_video[linked_video_id] = raw
            else:
                genuine_posts.append(raw)

        for raw in videos:
            item = self._video_to_item(raw, linked_posts_by_video.get(str(raw["id"])))
            item.alternate_external_ids = tuple(alternate_ids_by_video.get(str(raw["id"]), ()))
            items.append(item)

        for raw in genuine_posts:
            # A few Graph responses use the same id on both edges instead of
            # a wrapper id. Keep the old exact-id guard as a second line of
            # defence.
            if str(raw["id"]) not in video_ids:
                items.append(self._post_to_item(raw))

        return items

    def _video_to_item(self, raw: dict, linked_post: Optional[dict] = None) -> RawContentItem:
        engagement = self.client.get_post_engagement(raw["id"])
        # Meta exposes Reel views on the video node but shares on its Page-post
        # wrapper. Reading shares from the video node silently produced zeros
        # for almost every Reel (14 total at 2.3M views in the live account).
        wrapper_shares = self.client.get_post_share_count(linked_post["id"]) if linked_post is not None else None
        title = raw.get("title") or (raw.get("description") or "Film bez tytułu")[:80]
        return RawContentItem(
            external_id=raw["id"],
            title=title,
            description=raw.get("description", ""),
            url=raw.get("permalink_url"),
            published_at=parse_graph_timestamp(raw["created_time"]) if raw.get("created_time") else None,
            thumbnail_url=raw.get("picture"),
            duration_seconds=int(raw["length"]) if raw.get("length") else None,
            views=int(raw.get("views") or 0),
            likes=engagement.get("likes", 0),
            comments=engagement.get("comments", 0),
            shares=wrapper_shares if wrapper_shares is not None else engagement.get("shares", 0),
            impressions=None,
        )

    def _post_to_item(self, raw: dict) -> RawContentItem:
        insights = self.client.get_post_insights(raw["id"])
        engagement = self.client.get_post_engagement(raw["id"])
        message = raw.get("message", "")
        title = message[:80] if message else "Post bez treści"
        thumbnail = raw.get("full_picture")
        if not thumbnail:
            attachments = (raw.get("attachments") or {}).get("data", [])
            if attachments:
                thumbnail = ((attachments[0].get("media") or {}).get("image") or {}).get("src")
        return RawContentItem(
            external_id=raw["id"],
            title=title,
            description=message,
            url=raw.get("permalink_url"),
            published_at=parse_graph_timestamp(raw["created_time"]) if raw.get("created_time") else None,
            thumbnail_url=thumbnail,
            duration_seconds=None,
            views=insights.get("post_impressions", 0),
            likes=engagement.get("likes", 0),
            comments=engagement.get("comments", 0),
            shares=_share_count(raw) if "shares" in raw else engagement.get("shares", 0),
            impressions=insights.get("post_impressions"),
        )

    def list_comment_threads(self, external_content_id: str) -> list[RawCommentThread]:
        response = self.client.list_comments(external_content_id)
        top_level_comments = [c for c in response.get("data", []) if not c.get("parent")]

        threads: list[RawCommentThread] = []
        for raw in top_level_comments:
            replies_response = self.client.list_comments(raw["id"])
            replies = [self._to_raw_comment(reply, parent_external_id=raw["id"]) for reply in replies_response.get("data", [])]
            threads.append(
                RawCommentThread(
                    external_id=raw["id"],
                    top_level=self._to_raw_comment(raw, parent_external_id=None),
                    total_reply_count=raw.get("comment_count", len(replies)),
                    can_reply=True,
                    replies=replies,
                )
            )
        return threads

    def _to_raw_comment(self, raw: dict, parent_external_id: Optional[str]) -> RawComment:
        author = raw.get("from") or {}
        author_id = author.get("id")
        return RawComment(
            external_id=raw["id"],
            parent_external_id=parent_external_id,
            author_external_id=author_id,
            author_display_name=author.get("name", "Nieznany użytkownik"),
            author_avatar_url=f"https://graph.facebook.com/{author_id}/picture" if author_id else None,
            text=raw.get("message", ""),
            like_count=raw.get("like_count", 0),
            published_at=parse_graph_timestamp(raw["created_time"]),
            is_own=author_id == self.page_id,
        )

    def post_reply(self, thread_external_id: str, text: str) -> RawComment:
        created = self.client.post_comment_reply(thread_external_id, text)
        full = self.client.get_comment(created["id"])
        return self._to_raw_comment(full, parent_external_id=thread_external_id)

    def update_reply(self, comment_external_id: str, text: str) -> RawComment:
        self.client.update_comment(comment_external_id, text)
        full = self.client.get_comment(comment_external_id)
        parent_id = (full.get("parent") or {}).get("id")
        return self._to_raw_comment(full, parent_external_id=parent_id)

    def delete_reply(self, comment_external_id: str) -> None:
        self.client.delete_comment(comment_external_id)


def _video_id_from_permalink(url: Optional[str]) -> Optional[str]:
    """Return the canonical video id embedded in a Facebook Reel/video URL.

    This is deliberately structural rather than fuzzy title/date matching, so
    two genuinely separate posts with similar copy are never collapsed.
    """
    if not url:
        return None
    match = re.search(r"/(?:reel|videos?)/(\d+)(?:[/?#]|$)", url)
    return match.group(1) if match else None


def _share_count(raw: Optional[dict]) -> int:
    shares = (raw or {}).get("shares") or {}
    value = shares.get("count", 0) if isinstance(shares, dict) else 0
    return int(value) if isinstance(value, (int, float)) else 0
