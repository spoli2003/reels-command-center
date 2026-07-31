"""Release 0.8.0 — Facebook/Instagram adapters (ADR-020) and the shared Graph
API client helper. No live network calls: a FakeGraphClient stands in for
app.integrations.meta.client.GraphClient (duck-typed to the same method
signatures the adapters call), exercising the raw-dict-to-RawContentItem/
RawComment mapping logic directly."""

from datetime import timezone

from app.integrations.meta.client import GraphAPIError, parse_graph_timestamp
from app.services.platforms.facebook_adapter import FacebookAdapter
from app.services.platforms.instagram_adapter import InstagramAdapter


def test_parse_graph_timestamp_without_colon_offset():
    parsed = parse_graph_timestamp("2026-07-29T10:00:00+0000")
    assert parsed.tzinfo is not None
    assert parsed.astimezone(timezone.utc).isoformat().startswith("2026-07-29T10:00:00")


def test_parse_graph_timestamp_with_colon_offset():
    parsed = parse_graph_timestamp("2026-07-29T10:00:00+02:00")
    assert parsed.astimezone(timezone.utc).hour == 8


# --- Facebook -----------------------------------------------------------------


class FakeFacebookGraphClient:
    def __init__(self):
        self.videos = []
        self.posts = []
        self.insights_by_id = {}
        self.engagement_by_id = {}
        self.comments_by_object = {}
        self.replies_created = []
        self.comments_updated = []
        self.comments_deleted = []
        self.share_counts_by_id = {}
        self._reply_counter = 0

    def list_page_videos(self, page_id):
        return self.videos

    def list_page_posts(self, page_id):
        return self.posts

    def get_post_insights(self, post_id):
        return self.insights_by_id.get(post_id, {})

    def get_post_engagement(self, post_id):
        return self.engagement_by_id.get(post_id, {"likes": 0, "comments": 0, "shares": 0})

    def get_post_share_count(self, post_id):
        return self.share_counts_by_id.get(post_id, 0)

    def list_comments(self, object_id):
        return {"data": self.comments_by_object.get(object_id, [])}

    def get_comment(self, comment_id):
        self._reply_counter += 1
        return {
            "id": comment_id,
            "message": "Treść po utworzeniu",
            "from": {"id": "page-1", "name": "Strona Testowa"},
            "created_time": "2026-07-29T10:00:00+0000",
            "like_count": 0,
            "parent": {"id": "comment-top-1"},
        }

    def post_comment_reply(self, comment_id, message):
        self.replies_created.append((comment_id, message))
        return {"id": f"new-reply-{len(self.replies_created)}"}

    def update_comment(self, comment_id, message):
        self.comments_updated.append((comment_id, message))
        return {"id": comment_id}

    def delete_comment(self, comment_id):
        self.comments_deleted.append(comment_id)


def test_facebook_adapter_dedups_video_and_post_edges_by_id():
    client = FakeFacebookGraphClient()
    client.videos = [
        {
            "id": "content-1",
            "title": "Film testowy",
            "created_time": "2026-07-29T10:00:00+0000",
            "length": "45",
            "views": 500,
        }
    ]
    # Same id also returned by the /posts edge (Graph API sometimes surfaces a video there too) — must not be duplicated.
    client.posts = [{"id": "content-1", "message": "Powinno zostać zignorowane jako duplikat"}]
    client.engagement_by_id["content-1"] = {"likes": 10, "comments": 2, "shares": 1}

    adapter = FacebookAdapter(client, "page-1")
    items = adapter.list_content_items()

    assert len(items) == 1
    assert items[0].external_id == "content-1"
    assert items[0].title == "Film testowy"
    assert items[0].views == 500
    assert items[0].likes == 10
    assert items[0].duration_seconds == 45


def test_facebook_adapter_merges_reel_post_wrapper_with_different_id():
    client = FakeFacebookGraphClient()
    client.videos = [
        {
            "id": "28277141851870146",
            "description": "Ta sama rolka",
            "permalink_url": "/reel/28277141851870146/",
            "created_time": "2026-07-30T13:41:27+0000",
            "views": 2632,
        }
    ]
    client.posts = [
        {
            "id": "100580101507405_1738695091074410",
            "message": "Ta sama rolka",
            "permalink_url": "https://www.facebook.com/reel/28277141851870146/",
            "created_time": "2026-07-30T13:41:42+0000",
        }
    ]
    client.share_counts_by_id["100580101507405_1738695091074410"] = 147

    items = FacebookAdapter(client, "page-1").list_content_items()

    assert len(items) == 1
    assert items[0].external_id == "28277141851870146"
    assert items[0].views == 2632
    assert items[0].shares == 147
    assert items[0].alternate_external_ids == ("100580101507405_1738695091074410",)


def test_facebook_adapter_keeps_genuine_post_separate_from_reel():
    client = FakeFacebookGraphClient()
    client.videos = [{"id": "video-1", "description": "Film", "views": 100}]
    client.posts = [
        {
            "id": "page-1_post-1",
            "message": "Samodzielny post",
            "permalink_url": "https://www.facebook.com/page/posts/1739520890991830",
        }
    ]

    items = FacebookAdapter(client, "page-1").list_content_items()

    assert [item.external_id for item in items] == ["video-1", "page-1_post-1"]


def test_facebook_adapter_post_falls_back_to_message_and_attachment_thumbnail():
    client = FakeFacebookGraphClient()
    client.posts = [
        {
            "id": "content-2",
            "message": "Zwykły post bez wideo",
            "created_time": "2026-07-29T10:00:00+0000",
            "attachments": {"data": [{"media": {"image": {"src": "https://example.test/attachment.jpg"}}}]},
        }
    ]
    client.insights_by_id["content-2"] = {}
    client.engagement_by_id["content-2"] = {"likes": 0, "comments": 0, "shares": 0}

    adapter = FacebookAdapter(client, "page-1")
    items = adapter.list_content_items()

    assert items[0].title == "Zwykły post bez wideo"
    assert items[0].thumbnail_url == "https://example.test/attachment.jpg"
    assert items[0].duration_seconds is None


def test_facebook_adapter_comment_threads_with_nested_replies_and_own_detection():
    client = FakeFacebookGraphClient()
    client.comments_by_object["content-3"] = [
        {
            "id": "comment-top-1",
            "message": "Pytanie od widza",
            "from": {"id": "viewer-1", "name": "Widz"},
            "created_time": "2026-07-29T10:00:00+0000",
            "like_count": 3,
            "comment_count": 1,
        }
    ]
    client.comments_by_object["comment-top-1"] = [
        {
            "id": "reply-1",
            "message": "Odpowiedź strony",
            "from": {"id": "page-1", "name": "Strona Testowa"},
            "created_time": "2026-07-29T11:00:00+0000",
            "like_count": 0,
        }
    ]

    adapter = FacebookAdapter(client, "page-1")
    threads = adapter.list_comment_threads("content-3")

    assert len(threads) == 1
    thread = threads[0]
    assert thread.top_level.is_own is False
    assert thread.top_level.author_display_name == "Widz"
    assert len(thread.replies) == 1
    assert thread.replies[0].is_own is True  # author id matches page_id
    assert thread.replies[0].parent_external_id == "comment-top-1"


def test_facebook_adapter_post_reply_calls_client_and_refetches_full_comment():
    client = FakeFacebookGraphClient()
    adapter = FacebookAdapter(client, "page-1")
    reply = adapter.post_reply("comment-top-1", "Dziękujemy!")
    assert client.replies_created == [("comment-top-1", "Dziękujemy!")]
    assert reply.text == "Treść po utworzeniu"
    assert reply.parent_external_id == "comment-top-1"


def test_facebook_adapter_delete_reply_calls_client():
    client = FakeFacebookGraphClient()
    adapter = FacebookAdapter(client, "page-1")
    adapter.delete_reply("reply-1")
    assert client.comments_deleted == ["reply-1"]


# --- Instagram ------------------------------------------------------------------


class FakeInstagramGraphClient:
    def __init__(self):
        self.media = []
        self.insights_by_id = {}
        self.insights_requested = []
        self.comments_by_media = {}
        self.replies_created = []
        self.comments_deleted = []

    def list_instagram_media(self, ig_user_id):
        return self.media

    def get_instagram_media_insights(self, media_id, media_product_type):
        self.insights_requested.append((media_id, media_product_type))
        return self.insights_by_id.get(media_id, {})

    def list_instagram_comments(self, media_id):
        return {"data": self.comments_by_media.get(media_id, [])}

    def list_instagram_comment_replies(self, comment_id):
        for comments in self.comments_by_media.values():
            for comment in comments:
                if comment["id"] == comment_id:
                    return (comment.get("replies") or {}).get("data", [])
        return []

    def post_instagram_comment_reply(self, comment_id, message):
        self.replies_created.append((comment_id, message))
        return {"id": f"new-ig-reply-{len(self.replies_created)}"}

    def get_instagram_comment(self, comment_id):
        return {"id": comment_id, "text": "Treść po utworzeniu", "username": "moja_marka", "timestamp": "2026-07-29T10:00:00+0000", "like_count": 0}

    def update_instagram_comment(self, comment_id, message):
        raise GraphAPIError("Instagram Graph API nie obsługuje edycji komentarzy.")

    def delete_instagram_comment(self, comment_id):
        self.comments_deleted.append(comment_id)


def test_instagram_adapter_maps_reels_insights():
    client = FakeInstagramGraphClient()
    client.media = [
        {
            "id": "media-1",
            "caption": "Nowy reels!",
            "media_product_type": "REELS",
            "permalink": "https://instagram.test/media-1",
            "timestamp": "2026-07-29T10:00:00+0000",
            "like_count": 20,
            "comments_count": 4,
        }
    ]
    client.insights_by_id["media-1"] = {"views": 1200, "reach": 900, "saved": 12, "shares": 3}

    adapter = InstagramAdapter(client, "ig-user-1", own_username="moja_marka")
    items = adapter.list_content_items()

    assert items[0].title == "Nowy reels!"
    assert items[0].views == 1200
    assert items[0].reach == 900
    assert items[0].saves == 12
    assert items[0].shares == 3
    assert items[0].likes == 20


def test_instagram_adapter_title_falls_back_to_media_type_when_no_caption():
    client = FakeInstagramGraphClient()
    client.media = [{"id": "media-2", "media_product_type": "IMAGE", "timestamp": "2026-07-29T10:00:00+0000"}]
    client.insights_by_id["media-2"] = {}

    adapter = InstagramAdapter(client, "ig-user-1")
    items = adapter.list_content_items()
    assert items == []
    assert adapter.excluded_content_ids == {"media-2"}


def test_instagram_adapter_skips_insights_without_instagram_insights_scope():
    client = FakeInstagramGraphClient()
    client.media = [
        {
            "id": "media-no-insights",
            "caption": "Materiał bez dostępu do insights",
            "media_product_type": "REELS",
            "timestamp": "2026-07-29T10:00:00+0000",
            "like_count": 7,
            "comments_count": 2,
        }
    ]
    adapter = InstagramAdapter(client, "ig-user-1", include_insights=False)

    items = adapter.list_content_items()

    assert client.insights_requested == []
    assert items[0].views == 0
    assert items[0].likes == 7
    assert items[0].comments == 2


def test_instagram_adapter_comment_threads_own_detection_by_username():
    client = FakeInstagramGraphClient()
    client.comments_by_media["media-3"] = [
        {
            "id": "comment-ig-1",
            "text": "Świetny reels!",
            "username": "widz_123",
            "timestamp": "2026-07-29T10:00:00+0000",
            "like_count": 1,
            "replies": {"data": [{"id": "reply-ig-1", "text": "Dzięki!", "username": "moja_marka", "timestamp": "2026-07-29T11:00:00+0000", "like_count": 0}]},
        }
    ]

    adapter = InstagramAdapter(client, "ig-user-1", own_username="moja_marka")
    threads = adapter.list_comment_threads("media-3")

    assert len(threads) == 1
    assert threads[0].top_level.is_own is False
    assert threads[0].top_level.author_display_name == "@widz_123"
    assert threads[0].replies[0].is_own is True


def test_instagram_adapter_update_reply_always_raises_not_faked():
    """The Instagram Graph API has no comment-edit endpoint — the adapter must
    surface that honestly (GraphAPIError) rather than silently no-op or fake success."""
    client = FakeInstagramGraphClient()
    adapter = InstagramAdapter(client, "ig-user-1")
    try:
        adapter.update_reply("reply-ig-1", "Próba edycji")
        assert False, "expected GraphAPIError"
    except GraphAPIError:
        pass


def test_instagram_adapter_post_reply_and_delete():
    client = FakeInstagramGraphClient()
    adapter = InstagramAdapter(client, "ig-user-1", own_username="moja_marka")
    reply = adapter.post_reply("comment-ig-1", "Dzięki za komentarz!")
    assert client.replies_created == [("comment-ig-1", "Dzięki za komentarz!")]
    assert reply.is_own is True

    adapter.delete_reply("reply-ig-1")
    assert client.comments_deleted == ["reply-ig-1"]
