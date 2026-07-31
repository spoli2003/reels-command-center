"""Release 0.8.0 — GraphClient HTTP wrapper. Verifies Graph API HTTP errors are
translated into GraphAPIError (with the status code preserved) rather than
leaking raw httpx exceptions up into the adapters, and that insights failures
degrade to an empty dict instead of failing the whole content-item mapping."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.integrations.meta.client import GraphAPIError, GraphClient


class _FakeErrorResponse:
    def __init__(self, status_code):
        self.status_code = status_code

    def raise_for_status(self):
        request = httpx.Request("GET", "https://graph.facebook.com/test")
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("error", request=request, response=response)


def test_get_wraps_http_error_as_graph_api_error(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, params=None, timeout=None: _FakeErrorResponse(400))
    client = GraphClient("token-1")
    with pytest.raises(GraphAPIError) as excinfo:
        client.get_page("page-1")
    assert excinfo.value.status_code == 400


class _FakeErrorResponseWithToken:
    """Simulates what a real failed Graph API call looks like: the request URL
    genuinely contains access_token as a query param, exactly like Meta's API
    requires. GraphAPIError must never let that URL leak into its message."""

    def __init__(self, status_code):
        self.status_code = status_code

    def raise_for_status(self):
        request = httpx.Request("GET", "https://graph.facebook.com/v19.0/me?access_token=super-secret-page-token&fields=id")
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("error", request=request, response=response)


def test_get_failure_does_not_leak_access_token(monkeypatch):
    """Regression test (ADR-024): a real Page access token leaked into this
    app's own logs this way during OAuth debugging — GraphAPIError's message
    must be a fixed, credential-free string, and the original httpx exception
    (which does embed the URL) must not be chained where a default traceback
    formatter would still print it."""
    monkeypatch.setattr(httpx, "get", lambda url, params=None, timeout=None: _FakeErrorResponseWithToken(403))
    client = GraphClient("token-1")
    with pytest.raises(GraphAPIError) as excinfo:
        client.get_page("page-1")
    assert excinfo.value.status_code == 403
    assert "super-secret-page-token" not in str(excinfo.value)
    assert "access_token" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None


def test_post_insights_degrades_to_empty_dict_on_error(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, params=None, timeout=None: _FakeErrorResponse(403))
    client = GraphClient("token-1")
    assert client.get_post_insights("post-1") == {}


def test_post_engagement_keeps_likes_and_comments_when_shares_field_is_unsupported(monkeypatch):
    calls = []

    class _OkResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "likes": {"summary": {"total_count": 12}},
                "comments": {"summary": {"total_count": 3}},
            }

    def fake_get(url, params=None, timeout=None):
        calls.append(params["fields"])
        if params["fields"] == "shares":
            return _FakeErrorResponse(400)
        return _OkResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    result = GraphClient("token-1").get_post_engagement("video-1")

    assert result == {"likes": 12, "comments": 3, "shares": 0}
    assert calls == ["likes.summary(true),comments.summary(true)", "shares"]


def test_post_engagement_still_raises_for_non_400_shares_failure(monkeypatch):
    class _OkResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"likes": {"summary": {"total_count": 1}}, "comments": {"summary": {"total_count": 2}}}

    def fake_get(url, params=None, timeout=None):
        if params["fields"] == "shares":
            return _FakeErrorResponse(500)
        return _OkResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(GraphAPIError) as excinfo:
        GraphClient("token-1").get_post_engagement("post-1")
    assert excinfo.value.status_code == 500


@pytest.mark.parametrize("status_code", [400, 403])
def test_post_engagement_degrades_when_node_metrics_are_not_accessible(monkeypatch, status_code):
    monkeypatch.setattr(httpx, "get", lambda url, params=None, timeout=None: _FakeErrorResponse(status_code))
    assert GraphClient("token-1").get_post_engagement("restricted-video") == {
        "likes": 0,
        "comments": 0,
        "shares": 0,
    }


def test_delete_wraps_http_error(monkeypatch):
    monkeypatch.setattr(httpx, "delete", lambda url, params=None, timeout=None: _FakeErrorResponse(404))
    client = GraphClient("token-1")
    with pytest.raises(GraphAPIError):
        client.delete_comment("comment-1")


def test_graph_api_version_is_configurable_not_hardcoded(monkeypatch):
    """Guards against the client.py/oauth.py version-inconsistency bug found
    during the Meta integration preflight: GraphClient must build its base URL
    from the version passed in (settings.meta_graph_api_version in production
    — see app/api/platforms.py::_build_adapter), not a hardcoded constant."""
    captured_urls = []

    class _OkResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    def fake_get(url, params=None, timeout=None):
        captured_urls.append(url)
        return _OkResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    GraphClient("token-1", "v21.0").get_page("page-1")
    assert captured_urls[-1].startswith("https://graph.facebook.com/v21.0/")


def test_graph_api_version_defaults_when_not_specified(monkeypatch):
    captured_urls = []

    class _OkResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    def fake_get(url, params=None, timeout=None):
        captured_urls.append(url)
        return _OkResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    GraphClient("token-1").get_page("page-1")
    assert captured_urls[-1].startswith("https://graph.facebook.com/v19.0/")


def test_facebook_history_is_paginated_and_stops_at_local_120_day_cutoff(monkeypatch):
    client = GraphClient("token-1")
    cutoff = datetime.now(timezone.utc) - timedelta(days=120)
    calls = []

    def fake_get(path, params):
        calls.append(dict(params))
        if "after" not in params:
            return {
                "data": [{"id": "recent", "created_time": (cutoff + timedelta(days=1)).isoformat()}],
                "paging": {"cursors": {"after": "page-2"}},
            }
        return {
            "data": [
                {"id": "still-in-range", "created_time": (cutoff + timedelta(hours=1)).isoformat()},
                {"id": "too-old", "created_time": (cutoff - timedelta(days=1)).isoformat()},
            ],
            "paging": {"cursors": {"after": "page-3"}},
        }

    monkeypatch.setattr(client, "_get", fake_get)
    result = client.list_page_videos("page-1")

    assert [item["id"] for item in result] == ["recent", "still-in-range"]
    assert len(calls) == 2
    assert calls[0]["limit"] == 100
    assert calls[0]["since"] <= int(cutoff.timestamp()) + 2
    assert calls[1]["after"] == "page-2"


def test_facebook_share_count_is_read_from_narrow_post_wrapper_request(monkeypatch):
    client = GraphClient("token-1")
    calls = []

    def fake_get(path, params):
        calls.append((path, dict(params)))
        return {"shares": {"count": 147}}

    monkeypatch.setattr(client, "_get", fake_get)
    assert client.get_post_share_count("page-post-1") == 147
    assert calls == [("/page-post-1", {"fields": "shares"})]


@pytest.mark.parametrize("status_code", [400, 403, 500])
def test_facebook_optional_share_count_failure_never_aborts_content_sync(monkeypatch, status_code):
    monkeypatch.setattr(httpx, "get", lambda url, params=None, timeout=None: _FakeErrorResponse(status_code))

    assert GraphClient("token-1").get_post_share_count("restricted-page-post") == 0


def test_instagram_insights_use_one_batched_request_on_happy_path(monkeypatch):
    client = GraphClient("token-1")
    calls = []

    def fake_get(path, params):
        calls.append((path, dict(params)))
        return {
            "data": [
                {"name": "views", "total_value": {"value": 12_345}},
                {"name": "reach", "values": [{"value": 9_000}]},
                {"name": "saved", "total_value": {"value": 81}},
                {"name": "shares", "total_value": {"value": 47}},
            ]
        }

    monkeypatch.setattr(client, "_get", fake_get)
    result = client.get_instagram_media_insights("ig-media-1", "REELS")

    assert result == {"views": 12_345, "reach": 9_000, "saved": 81, "shares": 47}
    assert calls == [
        ("/ig-media-1/insights", {"metric": "views,reach,saved,shares"}),
    ]


def test_instagram_insights_fall_back_per_metric_when_batch_is_rejected(monkeypatch):
    client = GraphClient("token-1")
    calls = []

    def fake_get(path, params):
        metric = params["metric"]
        calls.append(metric)
        if "," in metric:
            raise GraphAPIError("unsupported metric set", status_code=400)
        if metric == "views":
            return {"data": [{"name": "views", "total_value": {"value": 321}}]}
        raise GraphAPIError("unsupported metric", status_code=400)

    monkeypatch.setattr(client, "_get", fake_get)
    result = client.get_instagram_media_insights("ig-media-2", "REELS")

    assert result == {"views": 321}
    assert calls == ["views,reach,saved,shares", "views", "reach", "saved", "shares", "plays", "impressions"]
