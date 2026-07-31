"""Release 0.8.1 — Meta Page Selection end-to-end flow (ADR-023). No live Meta
network calls: exchange_code_for_token/exchange_for_long_lived_token/list_pages/
get_linked_instagram_account are monkeypatched where app.api.platforms imports
them, simulating a full OAuth callback -> Page Selection -> connect round trip
through the real FastAPI TestClient (so the session cookie / CSRF state check
between /meta/connect and /meta/callback is exercised for real, not mocked)."""

import os
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

os.environ["DATABASE_URL"] = "sqlite:///./test-rcc.db"
os.environ["TOKEN_ENCRYPTION_KEY"] = "test-secret"
os.environ["META_APP_ID"] = "test-app-id"
os.environ["META_APP_SECRET"] = "test-app-secret"

import app.api.platforms as platforms_module
from app.core.config import get_settings

get_settings.cache_clear()

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.integrations.meta.oauth import MetaOAuthError
from app.main import app
from app.models.integration import PlatformAccount

client = TestClient(app)


def _start_oauth(target: str) -> str:
    """Drives GET /meta/connect and returns the `state` value Meta would echo
    back — the same TestClient instance carries the session cookie forward."""
    response = client.get(f"/api/platforms/meta/connect?target={target}", follow_redirects=False)
    assert response.status_code in (302, 307)
    query = parse_qs(urlparse(response.headers["location"]).query)
    return query["state"][0]


def _fake_page(page_id: str, name: str, fan_count: int = 100, category: str = "Prawnik", instagram: dict | None = None):
    return {
        "id": page_id,
        "name": name,
        "access_token": f"page-token-{page_id}",
        "category": category,
        "picture": {"data": {"url": f"https://example.test/{page_id}.jpg"}},
        "fan_count": fan_count,
    }, instagram


def _install_fakes(monkeypatch, pages_and_instagram: list[tuple[dict, dict | None]]):
    pages = [p for p, _ in pages_and_instagram]
    instagram_by_page_id = {p["id"]: ig for p, ig in pages_and_instagram}

    monkeypatch.setattr(platforms_module, "exchange_code_for_token", lambda settings, code: {"access_token": "short-lived"})
    monkeypatch.setattr(platforms_module, "exchange_for_long_lived_token", lambda settings, token: {"access_token": "long-lived"})
    monkeypatch.setattr(platforms_module, "get_me", lambda settings, token: {"id": "fb-user-1", "name": "Testowy Użytkownik"})
    monkeypatch.setattr(
        platforms_module,
        "debug_token",
        lambda settings, token: {
            "type": "USER",
            "scopes": [
                "pages_show_list",
                "business_management",
                "pages_read_engagement",
                "pages_read_user_content",
                "pages_manage_engagement",
                "instagram_basic",
                "instagram_manage_comments",
                "read_insights",
            ],
            "is_valid": True,
        },
    )
    monkeypatch.setattr(platforms_module, "list_pages", lambda settings, token: pages)
    monkeypatch.setattr(
        platforms_module, "get_linked_instagram_account", lambda settings, page_id, page_token: instagram_by_page_id.get(page_id)
    )
    monkeypatch.setattr(
        platforms_module,
        "sync_meta_account",
        lambda db, account, settings: SimpleNamespace(
            status="success",
            comment_error=None,
            content_run=SimpleNamespace(imported_items=2),
            comment_run=SimpleNamespace(comments_imported=3),
        ),
    )


def test_facebook_page_without_linked_instagram_still_builds_candidate(monkeypatch):
    """Regression test (ADR-024): a Facebook Page with no linked Instagram
    account is a normal, expected condition — must not prevent the Page from
    appearing as a connectable candidate."""
    page, _ig = _fake_page("page-noig-1", "Kancelaria Bez Instagrama", instagram=None)
    _install_fakes(monkeypatch, [(page, None)])

    state = _start_oauth("facebook")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    assert callback.status_code in (302, 307)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]

    pending = client.get(f"/api/platforms/meta/pending-pages?selection={selection_id}")
    assert pending.status_code == 200
    entry = pending.json()["pages"][0]
    assert entry["id"] == "page-noig-1"
    assert entry["instagram"] is None


def test_instagram_connection_with_linked_instagram_includes_it_in_candidate(monkeypatch):
    """Regression test (ADR-024): the successful-resolution path must keep
    working exactly as before — only the failure path changed."""
    page, ig = _fake_page(
        "page-ig-1", "Kancelaria Z Instagramem", instagram={"id": "ig-1", "username": "kancelaria_z_ig", "profile_picture_url": "https://example.test/ig-1.jpg"}
    )
    _install_fakes(monkeypatch, [(page, ig)])

    state = _start_oauth("instagram")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]

    pending = client.get(f"/api/platforms/meta/pending-pages?selection={selection_id}")
    entry = pending.json()["pages"][0]
    assert entry["instagram"]["username"] == "kancelaria_z_ig"


def test_instagram_connection_with_multiple_linked_pages_keeps_every_candidate(monkeypatch):
    page_a, ig_a = _fake_page(
        "page-ig-many-a",
        "Kancelaria Instagram A",
        instagram={"id": "ig-many-a", "username": "kancelaria_a"},
    )
    page_b, ig_b = _fake_page(
        "page-ig-many-b",
        "Kancelaria Instagram B",
        instagram={"id": "ig-many-b", "username": "kancelaria_b"},
    )
    _install_fakes(monkeypatch, [(page_a, ig_a), (page_b, ig_b)])

    state = _start_oauth("instagram")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    assert callback.status_code in (302, 307)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]

    pending = client.get(f"/api/platforms/meta/pending-pages?selection={selection_id}")
    assert pending.status_code == 200
    assert pending.json()["target"] == "instagram"
    assert {
        (page["id"], page["instagram"]["id"])
        for page in pending.json()["pages"]
    } == {
        ("page-ig-many-a", "ig-many-a"),
        ("page-ig-many-b", "ig-many-b"),
    }


def test_facebook_connection_does_not_query_optional_instagram_field(monkeypatch):
    """Facebook connection must not depend on Instagram permissions or fields."""
    page, _ig = _fake_page("page-400-1", "Kancelaria 400", instagram=None)
    pages = [page]
    monkeypatch.setattr(platforms_module, "exchange_code_for_token", lambda settings, code: {"access_token": "short-lived"})
    monkeypatch.setattr(platforms_module, "exchange_for_long_lived_token", lambda settings, token: {"access_token": "long-lived"})
    monkeypatch.setattr(platforms_module, "get_me", lambda settings, token: {"id": "fb-user-1", "name": "Testowy Użytkownik"})
    monkeypatch.setattr(
        platforms_module,
        "debug_token",
        lambda settings, token: {"type": "USER", "scopes": ["pages_show_list", "business_management", "pages_read_engagement"], "is_valid": True},
    )
    monkeypatch.setattr(platforms_module, "list_pages", lambda settings, token: pages)

    def _raise_400(settings, page_id, page_token):
        raise MetaOAuthError(400)

    monkeypatch.setattr(platforms_module, "get_linked_instagram_account", _raise_400)

    state = _start_oauth("facebook")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    assert callback.status_code in (302, 307)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]

    pending = client.get(f"/api/platforms/meta/pending-pages?selection={selection_id}")
    assert pending.status_code == 200
    entry = pending.json()["pages"][0]
    assert entry["id"] == "page-400-1"
    assert entry["instagram"] is None

    # Full flow to a created PlatformAccount (point 6 — verify end to end).
    selected = client.post("/api/platforms/meta/select-page", json={"selection_id": selection_id, "page_id": "page-400-1"})
    assert selected.status_code == 200
    assert selected.json()["platform"] == "facebook"
    assert selected.json()["display_name"] == "Kancelaria 400"
    status = client.get("/api/platforms/facebook/status")
    assert status.json()["connected"] is True

    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "facebook", PlatformAccount.external_account_id == "page-400-1"))
        assert account is not None
    finally:
        db.close()
    client.delete("/api/platforms/facebook/disconnect")


def test_instagram_lookup_non_400_error_is_reported_as_upstream_failure(monkeypatch):
    page, _ig = _fake_page("page-500-1", "Kancelaria 500", instagram=None)
    pages = [page]
    monkeypatch.setattr(platforms_module, "exchange_code_for_token", lambda settings, code: {"access_token": "short-lived"})
    monkeypatch.setattr(platforms_module, "exchange_for_long_lived_token", lambda settings, token: {"access_token": "long-lived"})
    monkeypatch.setattr(platforms_module, "get_me", lambda settings, token: {"id": "fb-user-1", "name": "Testowy Użytkownik"})
    monkeypatch.setattr(
        platforms_module,
        "debug_token",
        lambda settings, token: {
            "type": "USER",
            "scopes": [
                "pages_show_list",
                "business_management",
                "pages_read_engagement",
                "instagram_basic",
                "instagram_manage_comments",
                "read_insights",
            ],
            "is_valid": True,
        },
    )
    monkeypatch.setattr(platforms_module, "list_pages", lambda settings, token: pages)

    def _raise_500(settings, page_id, page_token):
        raise MetaOAuthError(500)

    monkeypatch.setattr(platforms_module, "get_linked_instagram_account", _raise_500)

    state = _start_oauth("instagram")
    response = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    assert response.status_code == 502
    assert "Instagram" in response.json()["detail"]


def test_instagram_lookup_400_is_not_misreported_as_missing_account(monkeypatch):
    page, _ig = _fake_page("page-ig-400", "Kancelaria Instagram 400", instagram=None)
    _install_fakes(monkeypatch, [(page, None)])

    def _raise_400(settings, page_id, page_token):
        raise MetaOAuthError(400)

    monkeypatch.setattr(platforms_module, "get_linked_instagram_account", _raise_400)

    state = _start_oauth("instagram")
    response = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)

    assert response.status_code == 409
    assert "Business lub Creator" in response.json()["detail"]
    assert "nie ma podłączonego konta" not in response.json()["detail"]


def test_callback_never_auto_connects_redirects_to_selection_with_every_page(monkeypatch):
    page_a, ig_a = _fake_page("page-a1", "Kancelaria A", instagram=None)
    page_b, ig_b = _fake_page("page-b1", "Kancelaria B", instagram={"id": "ig-b1", "username": "kancelaria_b", "profile_picture_url": "https://example.test/ig-b.jpg"})
    _install_fakes(monkeypatch, [(page_a, ig_a), (page_b, ig_b)])

    state = _start_oauth("facebook")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    assert callback.status_code in (302, 307)
    location = urlparse(callback.headers["location"])
    assert location.path == "/platforms/meta/select-page"
    selection_id = parse_qs(location.query)["selection"][0]

    # No PlatformAccount was written yet — the whole point of ADR-023.
    assert client.get("/api/platforms/facebook/status").json()["connected"] is False

    pending = client.get(f"/api/platforms/meta/pending-pages?selection={selection_id}")
    assert pending.status_code == 200
    body = pending.json()
    assert body["target"] == "facebook"
    assert {p["id"] for p in body["pages"]} == {"page-a1", "page-b1"}
    page_b_entry = next(p for p in body["pages"] if p["id"] == "page-b1")
    assert page_b_entry["instagram"] is None  # Facebook connect deliberately skips optional Instagram discovery.
    assert page_b_entry["followers"] == 100
    assert page_b_entry["category"] == "Prawnik"
    page_a_entry = next(p for p in body["pages"] if p["id"] == "page-a1")
    assert page_a_entry["instagram"] is None


def test_selecting_a_facebook_page_creates_the_account_and_consumes_selection(monkeypatch):
    page_a, ig_a = _fake_page("page-c1", "Kancelaria C", instagram=None)
    _install_fakes(monkeypatch, [(page_a, ig_a)])

    state = _start_oauth("facebook")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]

    selected = client.post("/api/platforms/meta/select-page", json={"selection_id": selection_id, "page_id": "page-c1"})
    assert selected.status_code == 200
    assert selected.json()["platform"] == "facebook"
    assert selected.json()["display_name"] == "Kancelaria C"

    status = client.get("/api/platforms/facebook/status")
    assert status.json()["connected"] is True
    assert status.json()["display_name"] == "Kancelaria C"

    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "facebook", PlatformAccount.external_account_id == "page-c1"))
        assert account is not None
        assert account.access_token_encrypted  # a real (encrypted) token was stored, not the placeholder
        assert "pages_read_engagement" in account.scopes
    finally:
        db.close()

    # Selection is single-use — replaying it must fail, not silently reconnect.
    replay = client.post("/api/platforms/meta/select-page", json={"selection_id": selection_id, "page_id": "page-c1"})
    assert replay.status_code == 404

    client.delete("/api/platforms/facebook/disconnect")


def test_selecting_instagram_target_auto_resolves_linked_account(monkeypatch):
    page_a, ig_a = _fake_page("page-d1", "Kancelaria D", instagram={"id": "ig-d1", "username": "kancelaria_d", "profile_picture_url": None})
    _install_fakes(monkeypatch, [(page_a, ig_a)])

    state = _start_oauth("instagram")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]

    selected = client.post("/api/platforms/meta/select-page", json={"selection_id": selection_id, "page_id": "page-d1"})
    assert selected.status_code == 200
    assert selected.json()["platform"] == "instagram"
    assert selected.json()["display_name"] == "kancelaria_d"
    assert selected.json()["initial_sync_status"] == "success"
    assert selected.json()["imported_items"] == 2
    assert selected.json()["comments_imported"] == 3

    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "instagram", PlatformAccount.external_account_id == "ig-d1"))
        assert account is not None
    finally:
        db.close()

    client.delete("/api/platforms/instagram/disconnect")


def test_instagram_account_stays_connected_when_initial_sync_fails(monkeypatch):
    page, instagram = _fake_page(
        "page-initial-failure",
        "Kancelaria Sync Failure",
        instagram={"id": "ig-initial-failure", "username": "ig_sync_failure", "profile_picture_url": None},
    )
    _install_fakes(monkeypatch, [(page, instagram)])

    def fail_sync(db, account, settings):
        raise RuntimeError("synthetic sync failure")

    monkeypatch.setattr(platforms_module, "sync_meta_account", fail_sync)
    state = _start_oauth("instagram")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]
    selected = client.post("/api/platforms/meta/select-page", json={"selection_id": selection_id, "page_id": "page-initial-failure"})

    assert selected.status_code == 200
    assert selected.json()["initial_sync_status"] == "failed"
    assert client.get("/api/platforms/instagram/status").json()["connected"] is True
    client.delete("/api/platforms/instagram/disconnect")


def test_selecting_page_without_instagram_for_instagram_target_keeps_selection_alive(monkeypatch):
    page_a, ig_a = _fake_page("page-e1", "Kancelaria E", instagram=None)
    _install_fakes(monkeypatch, [(page_a, ig_a)])

    state = _start_oauth("instagram")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]

    rejected = client.post("/api/platforms/meta/select-page", json={"selection_id": selection_id, "page_id": "page-e1"})
    assert rejected.status_code == 400
    assert "Instagram" in rejected.json()["detail"]

    # The selection must still be usable — the user can pick a different Page
    # from the SAME screen without restarting OAuth from scratch.
    still_pending = client.get(f"/api/platforms/meta/pending-pages?selection={selection_id}")
    assert still_pending.status_code == 200


def test_unknown_selection_id_returns_404():
    assert client.get("/api/platforms/meta/pending-pages?selection=does-not-exist").status_code == 404
    response = client.post("/api/platforms/meta/select-page", json={"selection_id": "does-not-exist", "page_id": "page-x"})
    assert response.status_code == 404


def test_unknown_page_id_within_a_real_selection_returns_404(monkeypatch):
    page_a, ig_a = _fake_page("page-f1", "Kancelaria F", instagram=None)
    _install_fakes(monkeypatch, [(page_a, ig_a)])

    state = _start_oauth("facebook")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]

    response = client.post("/api/platforms/meta/select-page", json={"selection_id": selection_id, "page_id": "not-in-the-list"})
    assert response.status_code == 404


def test_callback_rejects_account_with_no_pages_and_reports_missing_permission(monkeypatch):
    """Regression test (ADR-024): a real account that DOES manage Pages hit
    this exact path — GET /me/accounts legitimately returned zero Pages
    because pages_show_list wasn't actually granted on that consent. The
    error message must say so, not claim the account manages no Pages."""
    _install_fakes(monkeypatch, [])
    monkeypatch.setattr(platforms_module, "get_granted_permissions", lambda settings, token: {"public_profile": "granted"})
    state = _start_oauth("facebook")
    response = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "pages_show_list" in detail
    assert "To konto Meta nie zarządza żadną Stroną na Facebooku." not in detail  # the old, misleading message


def test_callback_rejects_account_with_no_pages_but_permission_granted(monkeypatch):
    """The other branch: pages_show_list WAS granted, but GET /me/accounts
    still returned zero Pages — Meta's asset-sharing step didn't include any
    Page. Different message, still not "account manages no Pages"."""
    _install_fakes(monkeypatch, [])
    monkeypatch.setattr(platforms_module, "get_granted_permissions", lambda settings, token: {"pages_show_list": "granted"})
    state = _start_oauth("facebook")
    response = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "udostępniona" in detail or "udostępnione" in detail
    assert "To konto Meta nie zarządza żadną Stroną na Facebooku." not in detail  # the old, misleading message


def test_callback_rejects_facebook_connection_without_read_permission(monkeypatch):
    page, _ig = _fake_page("page-missing-scope", "Kancelaria bez odczytu")
    _install_fakes(monkeypatch, [(page, None)])
    monkeypatch.setattr(
        platforms_module,
        "debug_token",
        lambda settings, token: {"type": "USER", "scopes": ["pages_show_list", "business_management"], "is_valid": True},
    )

    state = _start_oauth("facebook")
    response = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)

    assert response.status_code == 409
    assert "pages_read_engagement" in response.json()["detail"]


def test_callback_converts_page_discovery_failure_to_actionable_gateway_error(monkeypatch):
    page, _ig = _fake_page("page-list-error", "Kancelaria")
    _install_fakes(monkeypatch, [(page, None)])

    def fail_page_discovery(settings, token):
        raise MetaOAuthError(400)

    monkeypatch.setattr(platforms_module, "list_pages", fail_page_discovery)

    state = _start_oauth("instagram")
    response = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)

    assert response.status_code == 502
    assert "pobranie listy Stron" in response.json()["detail"]
    assert "Internal Server Error" not in response.text


def test_callback_lists_all_missing_instagram_permissions_at_once(monkeypatch):
    page, _ig = _fake_page("page-ig-permissions", "Kancelaria Instagram")
    _install_fakes(monkeypatch, [(page, None)])
    monkeypatch.setattr(
        platforms_module,
        "debug_token",
        lambda settings, token: {
            "type": "USER",
            "scopes": ["pages_show_list", "business_management", "pages_read_engagement"],
            "is_valid": True,
        },
    )

    state = _start_oauth("instagram")
    response = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "instagram_basic" in detail
    assert "instagram_manage_comments" in detail
    assert "read_insights" not in detail
    assert "instagram_manage_insights" not in detail


def test_instagram_connect_accepts_read_insights_and_creates_platform_account(monkeypatch):
    """Regression: the active Facebook Login for Business Configuration grants
    read_insights, not instagram_manage_insights. That real grant must reach the
    Page picker and create the Instagram PlatformAccount end to end."""
    page, instagram = _fake_page(
        "page-read-insights",
        "Kancelaria Read Insights",
        instagram={"id": "ig-read-insights", "username": "kancelaria_read_insights"},
    )
    _install_fakes(monkeypatch, [(page, instagram)])

    state = _start_oauth("instagram")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    assert callback.status_code in (302, 307)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]

    selected = client.post(
        "/api/platforms/meta/select-page",
        json={"selection_id": selection_id, "page_id": "page-read-insights"},
    )
    assert selected.status_code == 200
    assert selected.json()["platform"] == "instagram"
    assert selected.json()["initial_sync_status"] == "success"

    db = SessionLocal()
    try:
        account = db.scalar(
            select(PlatformAccount).where(
                PlatformAccount.platform == "instagram",
                PlatformAccount.external_account_id == "ig-read-insights",
            )
        )
        assert account is not None
        scopes = set(account.scopes.split(","))
        assert "read_insights" in scopes
        assert "instagram_manage_insights" not in scopes
    finally:
        db.close()
    client.delete("/api/platforms/instagram/disconnect")


def test_embedded_instagram_business_account_is_used_for_business_or_creator(monkeypatch):
    page, instagram = _fake_page("page-embedded-ig", "Kancelaria Creator")
    page["instagram_business_account"] = {
        "id": "ig-creator-1",
        "username": "kancelaria_creator",
        "account_type": "CREATOR",
        "followers_count": 1234,
        "media_count": 88,
    }
    _install_fakes(monkeypatch, [(page, instagram)])

    def should_not_be_called(*args, **kwargs):
        raise AssertionError("nested /me/accounts result should avoid the fallback Page request")

    monkeypatch.setattr(platforms_module, "get_linked_instagram_account", should_not_be_called)
    state = _start_oauth("instagram")
    callback = client.get(f"/api/platforms/meta/callback?state={state}&code=fake-code", follow_redirects=False)
    selection_id = parse_qs(urlparse(callback.headers["location"]).query)["selection"][0]
    pending = client.get(f"/api/platforms/meta/pending-pages?selection={selection_id}").json()

    assert pending["pages"][0]["instagram"]["account_type"] == "CREATOR"
    assert pending["pages"][0]["instagram"]["followers"] == 1234
