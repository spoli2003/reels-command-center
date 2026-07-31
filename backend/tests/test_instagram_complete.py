"""Sprint 0.8.3 regression coverage for the Instagram-complete path."""

from types import SimpleNamespace

from app.core.config import Settings
from app.integrations.meta.client import GraphAPIError, GraphClient
from app.integrations.meta.oauth import (
    FACEBOOK_CONNECT_SCOPES,
    FACEBOOK_CONTENT_SYNC_SCOPES,
    INSTAGRAM_COMMENT_SYNC_SCOPES,
    INSTAGRAM_CONNECT_SCOPES,
    INSTAGRAM_CONTENT_SYNC_SCOPES,
    INSTAGRAM_INSIGHTS_SCOPES,
    list_pages,
)
from app.services.meta_scheduler import optional_comment_sync_scopes, required_sync_scopes
from app.services import meta_scheduler


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _settings() -> Settings:
    return Settings(
        meta_app_id="test",
        meta_app_secret="secret",
        meta_redirect_uri="https://rcc.test/callback",
        meta_login_config_id="",
    )


def test_instagram_connect_scope_set_covers_core_content_and_comments():
    assert INSTAGRAM_CONTENT_SYNC_SCOPES <= INSTAGRAM_CONNECT_SCOPES
    assert INSTAGRAM_COMMENT_SYNC_SCOPES <= INSTAGRAM_CONNECT_SCOPES
    assert {"instagram_basic", "instagram_manage_comments"} <= INSTAGRAM_CONNECT_SCOPES
    assert "read_insights" not in INSTAGRAM_CONNECT_SCOPES
    assert "instagram_manage_insights" not in INSTAGRAM_CONNECT_SCOPES
    assert INSTAGRAM_INSIGHTS_SCOPES == {"instagram_manage_insights"}
    assert required_sync_scopes("instagram") == set(INSTAGRAM_CONTENT_SYNC_SCOPES)
    assert optional_comment_sync_scopes("instagram") == set(INSTAGRAM_COMMENT_SYNC_SCOPES - INSTAGRAM_CONTENT_SYNC_SCOPES)


def test_instagram_permission_fix_does_not_change_facebook_requirements():
    assert FACEBOOK_CONNECT_SCOPES == {
        "pages_show_list",
        "business_management",
        "pages_read_engagement",
    }
    assert FACEBOOK_CONTENT_SYNC_SCOPES == FACEBOOK_CONNECT_SCOPES | {"read_insights"}


def test_page_discovery_does_not_expand_optional_instagram_fields(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["fields"] = params["fields"]
        return _Response({"data": []})

    monkeypatch.setattr("app.integrations.meta.oauth.httpx.get", fake_get)
    assert list_pages(_settings(), "user-token") == []
    assert "instagram_business_account" not in captured["fields"]
    assert "id,name,access_token" in captured["fields"]


def test_graph_client_paginates_instagram_media_without_following_next_url(monkeypatch):
    client = GraphClient("secret-token")
    calls = []

    def fake_get(path, params=None):
        calls.append((path, dict(params or {})))
        if not params.get("after"):
            return {"data": [{"id": "m1"}], "paging": {"cursors": {"after": "cursor-1"}, "next": "https://example/?access_token=secret-token"}}
        return {"data": [{"id": "m2"}], "paging": {}}

    monkeypatch.setattr(client, "_get", fake_get)
    assert [item["id"] for item in client.list_instagram_media("ig-1")] == ["m1", "m2"]
    assert calls[1][1]["after"] == "cursor-1"
    assert all("access_token" not in params for _path, params in calls)


def test_instagram_insights_keep_supported_metrics_when_one_is_rejected(monkeypatch):
    client = GraphClient("secret-token")

    def fake_get(path, params=None):
        metric = params["metric"]
        if metric in {"plays", "impressions"}:
            raise GraphAPIError("unsupported", status_code=400)
        values = {"views": 1200, "reach": 900, "saved": 11, "shares": 4}
        if metric not in values:
            return {"data": []}
        if metric == "views":
            return {"data": [{"name": metric, "total_value": {"value": values[metric]}}]}
        return {"data": [{"name": metric, "values": [{"value": values[metric]}]}]}

    monkeypatch.setattr(client, "_get", fake_get)
    insights = client.get_instagram_media_insights("media-1", "REELS")
    assert insights == {"views": 1200, "reach": 900, "saved": 11, "shares": 4}


def test_instagram_comments_and_replies_are_cursor_paginated(monkeypatch):
    client = GraphClient("secret-token")

    def fake_get(path, params=None):
        after = (params or {}).get("after")
        if path == "/media-1/comments":
            return {"data": [{"id": "c2"}] if after else [{"id": "c1"}], "paging": {} if after else {"cursors": {"after": "comments-2"}}}
        if path == "/c1/replies":
            return {"data": [{"id": "r2"}] if after else [{"id": "r1"}], "paging": {} if after else {"cursors": {"after": "replies-2"}}}
        return {"data": [], "paging": {}}

    monkeypatch.setattr(client, "_get", fake_get)
    assert [row["id"] for row in client.list_instagram_comments("media-1")["data"]] == ["c1", "c2"]
    assert [row["id"] for row in client.list_instagram_comment_replies("c1")] == ["r1", "r2"]


class _ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _SchedulerSession:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False
        self.commits = 0

    def scalars(self, _statement):
        return _ScalarRows(self.rows)

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def test_meta_scheduler_uses_shared_sync_and_isolates_account_failures(monkeypatch):
    facebook = SimpleNamespace(platform="facebook", access_token_encrypted="fb", scopes="")
    instagram = SimpleNamespace(platform="instagram", access_token_encrypted="ig", scopes="")
    session = _SchedulerSession([facebook, instagram])
    synced = []

    monkeypatch.setattr(meta_scheduler, "SessionLocal", lambda: session)
    monkeypatch.setattr(meta_scheduler, "get_settings", lambda: SimpleNamespace(token_encryption_key="key"))
    monkeypatch.setattr(meta_scheduler, "decrypt_token", lambda encrypted, _key: encrypted)
    monkeypatch.setattr(
        meta_scheduler,
        "debug_token",
        lambda _settings, _token: {
            "is_valid": True,
            "scopes": sorted(required_sync_scopes("facebook") | required_sync_scopes("instagram")),
        },
    )

    def fake_sync(_db, account, _settings, **_kwargs):
        synced.append(account.platform)
        if account.platform == "facebook":
            raise RuntimeError("one platform must not block the other")
        return SimpleNamespace(status="success")

    monkeypatch.setattr(meta_scheduler, "sync_meta_account", fake_sync)
    meta_scheduler._run_once_sync()

    assert synced == ["facebook", "instagram"]
    assert session.closed is True
    assert session.commits == 2
    assert "instagram_basic" in instagram.scopes


def test_meta_scheduler_skips_account_when_live_token_misses_scope(monkeypatch):
    instagram = SimpleNamespace(platform="instagram", access_token_encrypted="ig", scopes="")
    session = _SchedulerSession([instagram])
    synced = []

    monkeypatch.setattr(meta_scheduler, "SessionLocal", lambda: session)
    monkeypatch.setattr(meta_scheduler, "get_settings", lambda: SimpleNamespace(token_encryption_key="key"))
    monkeypatch.setattr(meta_scheduler, "decrypt_token", lambda _encrypted, _key: "token")
    monkeypatch.setattr(
        meta_scheduler,
        "debug_token",
        lambda _settings, _token: {"is_valid": True, "scopes": ["pages_show_list"]},
    )
    monkeypatch.setattr(meta_scheduler, "sync_meta_account", lambda *_args, **_kwargs: synced.append("called"))

    meta_scheduler._run_once_sync()

    assert synced == []
    assert session.closed is True
    assert session.commits == 0


def test_meta_scheduler_syncs_facebook_content_without_optional_comment_permission(monkeypatch):
    facebook = SimpleNamespace(platform="facebook", access_token_encrypted="fb", scopes="")
    session = _SchedulerSession([facebook])
    calls = []

    monkeypatch.setattr(meta_scheduler, "SessionLocal", lambda: session)
    monkeypatch.setattr(meta_scheduler, "get_settings", lambda: SimpleNamespace(token_encryption_key="key"))
    monkeypatch.setattr(meta_scheduler, "decrypt_token", lambda _encrypted, _key: "token")
    monkeypatch.setattr(
        meta_scheduler,
        "debug_token",
        lambda _settings, _token: {
            "is_valid": True,
            "scopes": sorted(FACEBOOK_CONTENT_SYNC_SCOPES),
        },
    )

    def fake_sync(_db, account, _settings, **kwargs):
        calls.append((account.platform, kwargs))
        return SimpleNamespace(status="partial")

    monkeypatch.setattr(meta_scheduler, "sync_meta_account", fake_sync)
    meta_scheduler._run_once_sync()

    assert calls[0][0] == "facebook"
    assert calls[0][1]["sync_comments"] is False
    assert "pages_read_user_content" in calls[0][1]["comment_skip_reason"]
    assert session.closed is True
