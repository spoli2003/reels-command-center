"""Thin Meta Graph API wrapper — no SDK, plain HTTP via httpx (same dependency
already used elsewhere in the backend). Used by both the Facebook and Instagram
platform adapters (app/services/platforms/facebook_adapter.py,
instagram_adapter.py); this module itself has no platform-specific business
logic, only raw Graph API calls."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

# Fallback only — GraphClient is always constructed with settings.meta_graph_api_version
# in production (see app/api/platforms.py::_build_adapter). This default exists so
# tests/ad-hoc scripts that instantiate GraphClient without a version don't break.
DEFAULT_GRAPH_API_VERSION = "v19.0"
META_CONTENT_LOOKBACK_DAYS = 120


class GraphAPIError(Exception):
    """Message is always a fixed, credential-free string — never str(exc) or
    the original httpx exception. access_token travels as a query param on
    every request this client makes (Meta's API requires it), and httpx's
    HTTPStatusError embeds the full request URL verbatim; chaining it via
    `from exc` would keep it reachable through the traceback too. A real Page
    access token leak of exactly this shape was found live in this app's logs
    during OAuth debugging — see docs/KNOWN_ISSUES.md."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class GraphClient:
    def __init__(self, access_token: str, graph_api_version: str = DEFAULT_GRAPH_API_VERSION):
        self.access_token = access_token
        self.base_url = f"https://graph.facebook.com/{graph_api_version}"

    def _get(self, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        query = {"access_token": self.access_token, **(params or {})}
        try:
            response = httpx.get(f"{self.base_url}{path}", params=query, timeout=20)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GraphAPIError(f"Graph API request failed with HTTP {exc.response.status_code}", status_code=exc.response.status_code) from None
        return response.json()

    def _post(self, path: str, data: Optional[dict] = None) -> dict[str, Any]:
        query = {"access_token": self.access_token}
        try:
            response = httpx.post(f"{self.base_url}{path}", params=query, data=data or {}, timeout=20)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GraphAPIError(f"Graph API request failed with HTTP {exc.response.status_code}", status_code=exc.response.status_code) from None
        return response.json()

    def _delete(self, path: str) -> None:
        query = {"access_token": self.access_token}
        try:
            response = httpx.delete(f"{self.base_url}{path}", params=query, timeout=20)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GraphAPIError(f"Graph API request failed with HTTP {exc.response.status_code}", status_code=exc.response.status_code) from None

    def _get_all(
        self,
        path: str,
        params: Optional[dict] = None,
        max_pages: int = 100,
        *,
        stop_before: Optional[datetime] = None,
        timestamp_field: str = "created_time",
    ) -> list[dict[str, Any]]:
        """Follow cursor pagination without ever following Meta's full `next`
        URL (which contains the access token and is therefore unsafe to log or
        propagate). A hard page cap protects the local scheduler from a broken
        cursor loop while still allowing 10,000 items at the usual page size."""
        request_params = dict(params or {})
        items: list[dict[str, Any]] = []
        seen_cursors: set[str] = set()
        for _ in range(max_pages):
            response = self._get(path, request_params)
            page_items = response.get("data", [])
            reached_cutoff = False
            if stop_before is not None:
                kept_items = []
                for item in page_items:
                    raw_timestamp = item.get(timestamp_field)
                    if not raw_timestamp:
                        kept_items.append(item)
                        continue
                    try:
                        published_at = parse_graph_timestamp(raw_timestamp)
                    except (TypeError, ValueError):
                        kept_items.append(item)
                        continue
                    if published_at >= stop_before:
                        kept_items.append(item)
                    else:
                        reached_cutoff = True
                page_items = kept_items
            items.extend(page_items)
            if reached_cutoff:
                break
            after = ((response.get("paging") or {}).get("cursors") or {}).get("after")
            if not after or after in seen_cursors:
                break
            seen_cursors.add(after)
            request_params["after"] = after
        return items

    # --- Facebook Page ------------------------------------------------------

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._get(f"/{page_id}", {"fields": "id,name,fan_count,picture,category"})

    def list_page_posts(self, page_id: str, limit: int = 50) -> list[dict[str, Any]]:
        fields = "id,message,permalink_url,created_time,full_picture,attachments{media_type,media}"
        cutoff = datetime.now(timezone.utc) - timedelta(days=META_CONTENT_LOOKBACK_DAYS)
        return self._get_all(
            f"/{page_id}/posts",
            {"fields": fields, "limit": max(limit, 100), "since": int(cutoff.timestamp())},
            max_pages=20,
            stop_before=cutoff,
        )

    def list_page_videos(self, page_id: str, limit: int = 50) -> list[dict[str, Any]]:
        # `views` is a first-class field on Page video nodes. Post insights
        # metrics (post_impressions, etc.) are not valid on these nodes and
        # silently degraded to zero in the old adapter.
        fields = "id,title,description,permalink_url,created_time,picture,length,views"
        cutoff = datetime.now(timezone.utc) - timedelta(days=META_CONTENT_LOOKBACK_DAYS)
        return self._get_all(
            f"/{page_id}/videos",
            {"fields": fields, "limit": max(limit, 100), "since": int(cutoff.timestamp())},
            max_pages=20,
            stop_before=cutoff,
        )

    def get_post_insights(self, post_id: str) -> dict[str, int]:
        """Returns a flattened {metric_name: value} dict — Facebook's insights
        endpoint returns a nested per-metric structure we simplify here."""
        metrics = "post_impressions,post_engaged_users,post_reactions_by_type_total"
        try:
            response = self._get(f"/{post_id}/insights", {"metric": metrics})
        except GraphAPIError:
            return {}
        flattened: dict[str, int] = {}
        for item in response.get("data", []):
            values = item.get("values", [])
            if values:
                value = values[-1].get("value")
                flattened[item["name"]] = value if isinstance(value, int) else 0
        return flattened

    def get_post_engagement(self, post_id: str) -> dict[str, int]:
        # `shares` exists on Page post nodes, but not on every Page video node.
        # Requesting it together with likes/comments makes Meta reject the
        # entire request with OAuthException #100 for videos. Fetch the fields
        # common to both node types first, then treat shares as an optional
        # enrichment so one unsupported field never aborts a full sync.
        try:
            response = self._get(f"/{post_id}", {"fields": "likes.summary(true),comments.summary(true)"})
        except GraphAPIError as exc:
            # Meta can list a Page video/post while denying its engagement
            # edge (notably older or restricted videos) with #200/HTTP 403,
            # or reject an unsupported node/field combination with HTTP 400.
            # The content itself is still valid and should be imported.
            if exc.status_code in {400, 403}:
                return {"likes": 0, "comments": 0, "shares": 0}
            raise
        likes = (response.get("likes", {}).get("summary", {}) or {}).get("total_count", 0)
        comments = (response.get("comments", {}).get("summary", {}) or {}).get("total_count", 0)
        shares = 0
        try:
            shares_response = self._get(f"/{post_id}", {"fields": "shares"})
        except GraphAPIError as exc:
            if exc.status_code not in {400, 403}:
                raise
        else:
            shares = (shares_response.get("shares") or {}).get("count", 0)
        return {"likes": likes, "comments": comments, "shares": shares}

    def get_post_share_count(self, post_id: str) -> int:
        """Read shares from a Page-post wrapper, never from its video node.

        Requesting ``shares`` in the paginated /posts fields caused a live
        HTTP 500 for this Page, while the narrow post-node request is stable.
        Unsupported/restricted historical posts degrade to zero without
        aborting the complete 120-day import.
        """
        try:
            response = self._get(f"/{post_id}", {"fields": "shares"})
        except GraphAPIError as exc:
            if exc.status_code in {400, 403, 500}:
                return 0
            raise
        value = (response.get("shares") or {}).get("count", 0)
        return int(value) if isinstance(value, (int, float)) else 0

    def get_comment(self, comment_id: str) -> dict[str, Any]:
        """POST /{comment}/comments only returns {"id": ...} — fetch full
        details (author, text, timestamps) right after creating/updating one."""
        fields = "id,message,from,created_time,like_count,comment_count,parent"
        return self._get(f"/{comment_id}", {"fields": fields})

    def list_comments(self, object_id: str, limit: int = 100, after: Optional[str] = None) -> dict[str, Any]:
        fields = "id,message,from,created_time,like_count,comment_count,parent"
        params = {"fields": fields, "limit": limit}
        if after:
            params["after"] = after
        return self._get(f"/{object_id}/comments", params)

    def post_comment_reply(self, comment_id: str, message: str) -> dict[str, Any]:
        return self._post(f"/{comment_id}/comments", {"message": message})

    def update_comment(self, comment_id: str, message: str) -> dict[str, Any]:
        return self._post(f"/{comment_id}", {"message": message})

    def delete_comment(self, comment_id: str) -> None:
        self._delete(f"/{comment_id}")

    # --- Instagram (via the linked Facebook Page) ---------------------------

    def list_instagram_media(self, ig_user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        fields = "id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count"
        return self._get_all(f"/{ig_user_id}/media", {"fields": fields, "limit": max(limit, 100)})

    def get_instagram_media_insights(self, media_id: str, media_product_type: str) -> dict[str, int]:
        # Meta accepts a comma-separated metric list. The old implementation
        # made six serial HTTP requests for every Reel (more than 1,100 calls
        # for the live 184-item library), so the UI could spend many minutes in
        # an indeterminate "pobieranie" phase. Try the current Reel metrics in
        # one request and retain the defensive per-metric fallback for older or
        # unusual media where Meta rejects a mixed metric set.
        current_metrics = ["views", "reach", "saved", "shares"]
        try:
            response = self._get(f"/{media_id}/insights", {"metric": ",".join(current_metrics)})
        except GraphAPIError as exc:
            if exc.status_code not in {400, 403}:
                raise
        else:
            flattened = self._flatten_instagram_insights(response)
            if flattened:
                return flattened

        # Availability differs by media type and Graph API version. One
        # unsupported legacy metric must not erase every valid result.
        metrics = [*current_metrics, "plays", "impressions"]
        flattened: dict[str, int] = {}
        for metric in metrics:
            try:
                response = self._get(f"/{media_id}/insights", {"metric": metric})
            except GraphAPIError as exc:
                if exc.status_code in {400, 403}:
                    continue
                raise
            flattened.update(self._flatten_instagram_insights(response))
        return flattened

    @staticmethod
    def _flatten_instagram_insights(response: dict[str, Any]) -> dict[str, int]:
        flattened: dict[str, int] = {}
        for item in response.get("data", []):
            values = item.get("values", [])
            # Meta currently returns some lifetime Instagram media insights
            # under total_value.value, while older versions used
            # values[-1].value. Supporting both formats prevents a valid views
            # response from silently turning into zero.
            total_value = item.get("total_value") or {}
            value = values[-1].get("value") if values else total_value.get("value", item.get("value"))
            if isinstance(value, (int, float)):
                flattened[item["name"]] = int(value)
        return flattened

    def get_instagram_account(self, ig_user_id: str) -> dict[str, Any]:
        return self._get(
            f"/{ig_user_id}",
            {"fields": "id,username,followers_count,media_count,profile_picture_url"},
        )

    def list_instagram_comments(self, media_id: str, limit: int = 100, after: Optional[str] = None) -> dict[str, Any]:
        fields = "id,text,username,timestamp,like_count"
        params = {"fields": fields, "limit": limit}
        if after:
            params["after"] = after
        return {"data": self._get_all(f"/{media_id}/comments", params)}

    def list_instagram_comment_replies(self, comment_id: str, limit: int = 100) -> list[dict[str, Any]]:
        fields = "id,text,username,timestamp,like_count"
        return self._get_all(f"/{comment_id}/replies", {"fields": fields, "limit": limit})

    def post_instagram_comment_reply(self, comment_id: str, message: str) -> dict[str, Any]:
        return self._post(f"/{comment_id}/replies", {"message": message})

    def get_instagram_comment(self, comment_id: str) -> dict[str, Any]:
        fields = "id,text,username,timestamp,like_count"
        return self._get(f"/{comment_id}", {"fields": fields})

    def update_instagram_comment(self, comment_id: str, message: str) -> dict[str, Any]:
        # Instagram comments can't be edited via the Graph API (unlike Facebook) —
        # documented in docs/KNOWN_ISSUES.md. Delete + repost is NOT attempted
        # automatically since it would change the comment's identity/timestamp.
        raise GraphAPIError("Instagram Graph API nie obsługuje edycji komentarzy.")

    def delete_instagram_comment(self, comment_id: str) -> None:
        self._delete(f"/{comment_id}")


def parse_graph_timestamp(value: str) -> datetime:
    """Graph API timestamps are ISO-8601 with a numeric UTC offset (e.g.
    2026-07-29T10:00:00+0000) — Python's fromisoformat needs the colon."""
    if len(value) >= 5 and value[-5] in "+-" and value[-3] != ":":
        value = f"{value[:-2]}:{value[-2:]}"
    return datetime.fromisoformat(value).astimezone(timezone.utc)
