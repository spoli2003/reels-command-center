"""Release 0.8.0 — /api/platforms/* generic surface (ADR-020/ADR-021).
Endpoint-level smoke tests: platform overview/status, the YouTube-rejects-
mutations guard rails, and quick-reply template CRUD (already platform-neutral,
reused unchanged for Facebook/Instagram accounts)."""

import os
from contextlib import contextmanager
from types import SimpleNamespace

os.environ["DATABASE_URL"] = "sqlite:///./test-rcc.db"
os.environ["TOKEN_ENCRYPTION_KEY"] = "test-secret"

import pytest
import app.api.platforms as platforms_module
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.content import ContentVideo, MetricSnapshot, Publication
from app.models.content_comments import ContentComment, ContentCommentThread
from app.models.integration import PlatformAccount
from app.integrations.meta.oauth import FACEBOOK_CONTENT_SYNC_SCOPES

client = TestClient(app)


@contextmanager
def _without_meta_credentials():
    """Settings.meta_app_id/meta_app_secret are read from the real .env file
    via pydantic-settings' env_file=.env — once real Meta credentials exist
    there (as they do once you actually connect a Meta account), the ambient
    environment is no longer "unconfigured" by default. Deleting the OS env
    var isn't enough to blank it out (pydantic-settings falls back to reading
    .env directly); explicitly overriding with an empty string is what
    actually simulates "unconfigured" regardless of what's in .env."""
    previous = {key: os.environ.get(key) for key in ("META_APP_ID", "META_APP_SECRET")}
    os.environ["META_APP_ID"] = ""
    os.environ["META_APP_SECRET"] = ""
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


@pytest.fixture(autouse=True, scope="module")
def _clean_meta_platform_state():
    """Other test modules (test_platform_content_sync.py, test_platform_comments.py,
    test_platform_intelligence_adapter.py, ...) create their own facebook/instagram
    PlatformAccount + Publication rows against the shared test DB (conftest.py resets
    it once per test run, not per module). This module's assertions rely on a clean
    "nothing connected yet" state for facebook/instagram, so start from a clean slate
    regardless of which order test modules happen to run in."""
    db = SessionLocal()
    try:
        thread_ids = db.scalars(select(ContentCommentThread.id).where(ContentCommentThread.platform.in_(["facebook", "instagram"]))).all()
        if thread_ids:
            db.execute(delete(ContentComment).where(ContentComment.thread_id.in_(thread_ids)))
            db.execute(delete(ContentCommentThread).where(ContentCommentThread.id.in_(thread_ids)))
        publication_ids = db.scalars(select(Publication.id).where(Publication.platform.in_(["facebook", "instagram"]))).all()
        if publication_ids:
            db.execute(delete(MetricSnapshot).where(MetricSnapshot.publication_id.in_(publication_ids)))
            db.execute(delete(Publication).where(Publication.id.in_(publication_ids)))
        db.execute(delete(PlatformAccount).where(PlatformAccount.platform.in_(["facebook", "instagram"])))
        db.commit()
    finally:
        db.close()
    yield


def _make_facebook_account(external_id: str) -> PlatformAccount:
    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "facebook", PlatformAccount.external_account_id == external_id))
        if account is None:
            account = PlatformAccount(platform="facebook", external_account_id=external_id, display_name="Strona API-test", access_token_encrypted="x")
            db.add(account)
            db.commit()
            db.refresh(account)
        return account
    finally:
        db.close()


def test_list_platforms_returns_all_three():
    response = client.get("/api/platforms")
    assert response.status_code == 200
    platforms = {item["platform"] for item in response.json()}
    assert platforms == {"youtube", "facebook", "instagram"}


def test_unknown_platform_returns_404():
    assert client.get("/api/platforms/tiktok/status").status_code == 404
    assert client.get("/api/platforms/tiktok/videos").status_code == 404


def test_status_for_unconfigured_unconnected_platform():
    with _without_meta_credentials():
        response = client.get("/api/platforms/instagram/status")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["configured"] is False
    assert "poświadczenia" in body["message"].lower() or "skonfiguruj" in body["message"].lower()


def test_youtube_rejects_generic_mutating_endpoints_with_pointer():
    assert client.post("/api/platforms/youtube/sync").status_code == 400
    assert client.post("/api/platforms/youtube/comments/sync").status_code == 400
    assert client.post("/api/platforms/youtube/comments/threads/x/reply", json={"text": "x"}).status_code == 400
    assert client.put("/api/platforms/youtube/comments/x", json={"text": "x"}).status_code == 400
    assert client.delete("/api/platforms/youtube/comments/x").status_code == 400
    assert client.delete("/api/platforms/youtube/disconnect").status_code == 400


def test_sync_without_connected_account_returns_409():
    response = client.post("/api/platforms/facebook/sync")
    assert response.status_code == 409


def test_facebook_status_keeps_content_sync_available_without_comment_permission():
    account = _make_facebook_account("fb-optional-comments-status")
    db = SessionLocal()
    try:
        stored = db.get(PlatformAccount, account.id)
        stored.scopes = ",".join(sorted(FACEBOOK_CONTENT_SYNC_SCOPES))
        db.commit()
    finally:
        db.close()

    response = client.get("/api/platforms/facebook/status")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["message"] == "Połączono"
    assert body["missing_permissions"] == []
    assert body["missing_optional_permissions"] == ["pages_read_user_content"]
    assert "pages_read_user_content" not in body["required_permissions"]
    client.delete("/api/platforms/facebook/disconnect")


def test_facebook_sync_imports_content_and_skips_comments_when_optional_permission_is_missing(monkeypatch):
    _make_facebook_account("fb-optional-comments-sync")
    calls = []

    monkeypatch.setattr(platforms_module, "decrypt_token", lambda *_args: "page-token")
    monkeypatch.setattr(platforms_module, "_live_meta_scopes", lambda *_args: set(FACEBOOK_CONTENT_SYNC_SCOPES))

    def fake_sync(_db, _account, _settings, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status="partial",
            comment_error=kwargs["comment_skip_reason"],
            content_run=SimpleNamespace(
                imported_items=2,
                videos_discovered=4,
                videos_updated=2,
                snapshots_created=4,
                snapshots_deduplicated=0,
                videos_failed=0,
            ),
            comment_run=None,
        )

    monkeypatch.setattr(platforms_module, "sync_meta_account", fake_sync)
    response = client.post("/api/platforms/facebook/sync")

    assert response.status_code == 200
    assert response.json()["imported_items"] == 2
    assert response.json()["threads_discovered"] == 0
    assert "pages_read_user_content" in response.json()["comment_sync_error"]
    assert calls == [
        {
            "sync_comments": False,
            "comment_skip_reason": response.json()["comment_sync_error"],
        }
    ]
    client.delete("/api/platforms/facebook/disconnect")


def test_facebook_comment_sync_missing_permission_does_not_claim_account_is_broken(monkeypatch):
    _make_facebook_account("fb-comments-feature-gate")
    monkeypatch.setattr(platforms_module, "decrypt_token", lambda *_args: "page-token")
    monkeypatch.setattr(platforms_module, "_live_meta_scopes", lambda *_args: set(FACEBOOK_CONTENT_SYNC_SCOPES))

    response = client.post("/api/platforms/facebook/comments/sync")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "pages_read_user_content" in detail
    assert "synchronizacja postów, filmów oraz statystyk nadal działają" in detail
    assert "usuń stare połączenie" not in detail
    client.delete("/api/platforms/facebook/disconnect")


def test_videos_endpoint_empty_for_platform_with_no_publications():
    response = client.get("/api/platforms/instagram/videos")
    assert response.status_code == 200
    assert response.json() == []


def test_video_detail_404_when_not_found():
    response = client.get("/api/platforms/facebook/videos/does-not-exist")
    assert response.status_code == 404


def test_videos_endpoint_exposes_audience_gain_without_inventing_missing_values():
    account = _make_facebook_account("audience-gain-account")
    db = SessionLocal()
    try:
        with_gain = ContentVideo(title="Z atrybucją", description="")
        without_gain = ContentVideo(title="Bez atrybucji", description="")
        db.add_all([with_gain, without_gain])
        db.flush()
        publication_with = Publication(content_video_id=with_gain.id, platform_account_id=account.id, platform="facebook", external_id="audience-gain-present")
        publication_without = Publication(content_video_id=without_gain.id, platform_account_id=account.id, platform="facebook", external_id="audience-gain-missing")
        db.add_all([publication_with, publication_without])
        db.flush()
        db.add_all([
            MetricSnapshot(publication_id=publication_with.id, views=100, followers_gained=9),
            MetricSnapshot(publication_id=publication_without.id, views=100, followers_gained=None),
        ])
        db.commit()
    finally:
        db.close()

    response = client.get("/api/platforms/facebook/videos")
    assert response.status_code == 200
    by_id = {item["external_id"]: item for item in response.json()}
    assert by_id["audience-gain-present"]["followers_gained"] == 9
    assert by_id["audience-gain-missing"]["followers_gained"] is None


def test_quick_reply_template_crud_for_connected_account():
    _make_facebook_account("qr-account-1")

    created = client.post("/api/platforms/facebook/quick-replies", json={"text": "Dziękujemy za komentarz!"})
    assert created.status_code == 200
    template = created.json()
    assert template["text"] == "Dziękujemy za komentarz!"

    listed = client.get("/api/platforms/facebook/quick-replies")
    assert listed.status_code == 200
    assert any(t["id"] == template["id"] for t in listed.json())

    updated = client.put(f"/api/platforms/facebook/quick-replies/{template['id']}", json={"text": "Zaktualizowany szablon"})
    assert updated.status_code == 200
    assert updated.json()["text"] == "Zaktualizowany szablon"

    empty = client.post("/api/platforms/facebook/quick-replies", json={"text": "   "})
    assert empty.status_code == 400

    deleted = client.delete(f"/api/platforms/facebook/quick-replies/{template['id']}")
    assert deleted.status_code == 204
    listed_after = client.get("/api/platforms/facebook/quick-replies")
    assert all(t["id"] != template["id"] for t in listed_after.json())


def test_quick_replies_require_a_connected_account():
    response = client.get("/api/platforms/instagram/quick-replies")
    assert response.status_code == 409


def test_disconnect_removes_the_account():
    _make_facebook_account("qr-account-disconnect")
    assert client.get("/api/platforms/facebook/status").json()["connected"] is True
    assert client.delete("/api/platforms/facebook/disconnect").status_code == 204
    assert client.get("/api/platforms/facebook/status").json()["connected"] is False


def test_meta_connect_requires_configuration():
    with _without_meta_credentials():
        response = client.get("/api/platforms/meta/connect", follow_redirects=False)
    assert response.status_code == 500


def test_meta_connect_rejects_unknown_target():
    previous = {key: os.environ.get(key) for key in ("META_APP_ID", "META_APP_SECRET")}
    os.environ["META_APP_ID"] = "test-app-id"
    os.environ["META_APP_SECRET"] = "test-app-secret"
    get_settings.cache_clear()
    try:
        response = client.get("/api/platforms/meta/connect?target=tiktok", follow_redirects=False)
        assert response.status_code == 400
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
