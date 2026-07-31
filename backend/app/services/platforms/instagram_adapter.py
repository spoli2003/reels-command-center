"""Instagram professional account adapter — Release 0.8.0 / Part 4.

Imports media (Reels, feed posts/carousels, images) via the Instagram Graph
API (reached through the linked Facebook Page's access token — there is no
separate Instagram-only OAuth). Editing a posted reply is NOT supported by the
Instagram Graph API (only Facebook's is) — see GraphClient.update_instagram_comment
and docs/KNOWN_ISSUES.md; this adapter surfaces that honestly rather than faking it.
"""

from app.integrations.meta.client import GraphClient, parse_graph_timestamp
from app.services.platforms.base import RawComment, RawCommentThread, RawContentItem


class InstagramAdapter:
    platform = "instagram"

    def __init__(self, client: GraphClient, ig_user_id: str, own_username: str = "", include_insights: bool = True):
        self.client = client
        self.ig_user_id = ig_user_id
        self.own_username = own_username
        self.include_insights = include_insights
        self.excluded_content_ids: set[str] = set()

    def get_audience_count(self) -> int | None:
        value = self.client.get_instagram_account(self.ig_user_id).get("followers_count")
        return int(value) if isinstance(value, (int, float)) else None

    def list_content_items(self) -> list[RawContentItem]:
        items: list[RawContentItem] = []
        for raw in self.client.list_instagram_media(self.ig_user_id):
            # RCC tracks short-form video performance. Feed photos and carousel
            # albums polluted the Reels dashboard and made every aggregate
            # incomparable, so remember their ids for local cleanup and never
            # import them as content videos.
            media_type = (raw.get("media_type") or "").upper()
            media_product_type = (raw.get("media_product_type") or "").upper()
            if media_type not in {"VIDEO"} and media_product_type not in {"REELS"}:
                self.excluded_content_ids.add(str(raw["id"]))
                continue
            insights = (
                self.client.get_instagram_media_insights(raw["id"], raw.get("media_product_type", ""))
                if self.include_insights
                else {}
            )
            caption = raw.get("caption", "") or ""
            title = caption[:80] if caption else f"{raw.get('media_product_type', 'Media').title()} bez opisu"
            items.append(
                RawContentItem(
                    external_id=raw["id"],
                    title=title,
                    description=caption,
                    url=raw.get("permalink"),
                    published_at=parse_graph_timestamp(raw["timestamp"]) if raw.get("timestamp") else None,
                    thumbnail_url=raw.get("thumbnail_url") or raw.get("media_url"),
                    duration_seconds=None,
                    # `reach` is unique accounts reached, not views. Older RCC
                    # mirrored reach into views, which made the dashboard look
                    # complete but was semantically false. Prefer the current
                    # `views` metric and fall back only to the legacy `plays`
                    # metric (both are actual viewing counters), never reach.
                    views=insights.get("views", insights.get("plays", 0)),
                    likes=raw.get("like_count", 0),
                    comments=raw.get("comments_count", 0),
                    shares=insights.get("shares", 0),
                    saves=insights.get("saved", 0),
                    reach=insights.get("reach"),
                    impressions=insights.get("impressions"),
                )
            )
        return items

    def list_comment_threads(self, external_content_id: str) -> list[RawCommentThread]:
        response = self.client.list_instagram_comments(external_content_id)
        threads: list[RawCommentThread] = []
        for raw in response.get("data", []):
            reply_items = self.client.list_instagram_comment_replies(raw["id"])
            replies = [self._to_raw_comment(reply, parent_external_id=raw["id"]) for reply in reply_items]
            threads.append(
                RawCommentThread(
                    external_id=raw["id"],
                    top_level=self._to_raw_comment(raw, parent_external_id=None),
                    total_reply_count=len(replies),
                    can_reply=True,
                    replies=replies,
                )
            )
        return threads

    def _to_raw_comment(self, raw: dict, parent_external_id: str | None) -> RawComment:
        username = raw.get("username", "")
        return RawComment(
            external_id=raw["id"],
            parent_external_id=parent_external_id,
            author_external_id=username or None,
            author_display_name=f"@{username}" if username else "Nieznany użytkownik",
            author_avatar_url=None,  # Instagram Graph API doesn't expose commenter profile pictures.
            text=raw.get("text", ""),
            like_count=raw.get("like_count", 0),
            published_at=parse_graph_timestamp(raw["timestamp"]),
            is_own=bool(self.own_username) and username == self.own_username,
        )

    def post_reply(self, thread_external_id: str, text: str) -> RawComment:
        created = self.client.post_instagram_comment_reply(thread_external_id, text)
        full = self.client.get_instagram_comment(created["id"])
        return self._to_raw_comment(full, parent_external_id=thread_external_id)

    def update_reply(self, comment_external_id: str, text: str) -> RawComment:
        # Always raises GraphAPIError — Instagram Graph API has no comment-edit
        # endpoint (see GraphClient.update_instagram_comment).
        self.client.update_instagram_comment(comment_external_id, text)

    def delete_reply(self, comment_external_id: str) -> None:
        self.client.delete_instagram_comment(comment_external_id)
