"""Release 0.8.0 — Meta OAuth helpers (ADR-021). No live network calls: httpx.get
is monkeypatched so the token-exchange/list-pages helpers are exercised against
a fake Graph API response, matching the pattern used for other integrations in
this suite (fake clients instead of real network access, per docs/TODO.md
Part 14's "no live API calls in automated tests")."""

import httpx
import pytest

from app.core.config import Settings
from app.integrations.meta.oauth import (
    MetaOAuthError,
    build_authorization_url,
    exchange_code_for_token,
    exchange_for_long_lived_token,
    get_linked_instagram_account,
    list_pages,
)


def _settings() -> Settings:
    # meta_login_config_id explicitly blanked: real .env now has a real
    # Configuration ID once Meta credentials are actually set up, and any
    # field not passed here would otherwise fall through to that real value
    # (pydantic-settings reads env_file directly for unset fields) — this
    # helper represents the "classic flow, no Configuration" scenario.
    return Settings(meta_app_id="app-123", meta_app_secret="secret-xyz", meta_redirect_uri="https://rcc.test/callback", meta_login_config_id="")


def test_build_authorization_url_includes_client_id_state_and_scopes():
    url = build_authorization_url(_settings(), state="state-abc")
    assert "client_id=app-123" in url
    assert "state=state-abc" in url
    assert "pages_show_list" in url


def test_build_authorization_url_classic_flow_omits_config_id():
    """META_LOGIN_CONFIG_ID unset (the default) -> classic scope-based dialog,
    unchanged from before Facebook Login for Business support was added."""
    url = build_authorization_url(_settings(), state="state-abc")
    assert "config_id" not in url
    assert "scope=" in url


def test_build_authorization_url_uses_config_id_when_configured():
    """Facebook Login for Business Configuration flow: config_id present,
    scope entirely absent — the Configuration owns the permission set, so
    sending scope alongside it would be redundant per Meta's documented
    Configuration-based Login flow."""
    settings = Settings(
        meta_app_id="app-123",
        meta_app_secret="secret-xyz",
        meta_redirect_uri="https://rcc.test/callback",
        meta_login_config_id="1234567890",
    )
    url = build_authorization_url(settings, state="state-abc")
    assert "config_id=1234567890" in url
    assert "scope=" not in url
    assert "client_id=app-123" in url
    assert "state=state-abc" in url
    assert "redirect_uri=" in url


def test_build_authorization_url_config_id_takes_precedence_and_is_url_encoded():
    settings = Settings(
        meta_app_id="app-123",
        meta_app_secret="secret-xyz",
        meta_redirect_uri="https://rcc.test/callback",
        meta_login_config_id="cfg id/with-special+chars",
    )
    url = build_authorization_url(settings, state="state-abc")
    assert "scope" not in url
    from urllib.parse import parse_qs, urlparse

    query = parse_qs(urlparse(url).query)
    assert query["config_id"] == ["cfg id/with-special+chars"]


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeErrorResponse:
    def __init__(self, status_code, url_with_secret):
        self.status_code = status_code
        self._url_with_secret = url_with_secret

    def raise_for_status(self):
        request = httpx.Request("GET", self._url_with_secret)
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("error", request=request, response=response)


def test_exchange_code_for_token_failure_does_not_leak_client_secret(monkeypatch):
    """Regression test (ADR-024): a failed token exchange used to raise
    httpx.HTTPStatusError directly, whose message/repr embeds the full request
    URL — including client_secret, since Meta's token endpoint requires it as
    a query param. A real secret leaked into this app's own logs this way
    during OAuth debugging. MetaOAuthError must never carry the URL or any
    param value, only the HTTP status code."""
    leaked_url = "https://graph.facebook.com/v19.0/oauth/access_token?client_id=app-123&client_secret=super-secret-value&redirect_uri=https://rcc.test/callback&code=bad-code"
    monkeypatch.setattr("app.integrations.meta.oauth.httpx.get", lambda url, params=None, timeout=None: _FakeErrorResponse(400, leaked_url))

    with pytest.raises(MetaOAuthError) as excinfo:
        exchange_code_for_token(_settings(), "bad-code")

    assert excinfo.value.status_code == 400
    assert "super-secret-value" not in str(excinfo.value)
    assert "client_secret" not in str(excinfo.value)
    assert "graph.facebook.com" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None  # from None — the original (secret-laden) exception isn't chained


def test_exchange_code_for_token(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"access_token": "short-lived-token", "token_type": "bearer"})

    monkeypatch.setattr("app.integrations.meta.oauth.httpx.get", fake_get)
    result = exchange_code_for_token(_settings(), "auth-code-1")
    assert result["access_token"] == "short-lived-token"
    assert captured["params"]["code"] == "auth-code-1"
    assert captured["params"]["client_secret"] == "secret-xyz"


def test_exchange_for_long_lived_token(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        assert params["fb_exchange_token"] == "short-lived-token"
        assert params["grant_type"] == "fb_exchange_token"
        return _FakeResponse({"access_token": "long-lived-token", "expires_in": 5184000})

    monkeypatch.setattr("app.integrations.meta.oauth.httpx.get", fake_get)
    result = exchange_for_long_lived_token(_settings(), "short-lived-token")
    assert result["access_token"] == "long-lived-token"


def test_list_pages_returns_data_array(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        assert params["access_token"] == "user-token-1"
        return _FakeResponse({"data": [{"id": "page-1", "name": "Moja Strona", "access_token": "page-token-1"}]})

    monkeypatch.setattr("app.integrations.meta.oauth.httpx.get", fake_get)
    pages = list_pages(_settings(), "user-token-1")
    assert pages == [{"id": "page-1", "name": "Moja Strona", "access_token": "page-token-1"}]


def test_get_linked_instagram_account_returns_none_when_absent(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return _FakeResponse({})  # Page has no linked Instagram professional account

    monkeypatch.setattr("app.integrations.meta.oauth.httpx.get", fake_get)
    result = get_linked_instagram_account(_settings(), "page-1", "page-token-1")
    assert result is None


def test_get_linked_instagram_account_returns_account_when_present(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params["fields"]))
        if url.endswith("/page-1"):
            return _FakeResponse({"instagram_business_account": {"id": "ig-1"}})
        return _FakeResponse({"id": "ig-1", "username": "moja_marka", "account_type": "BUSINESS"})

    monkeypatch.setattr("app.integrations.meta.oauth.httpx.get", fake_get)
    result = get_linked_instagram_account(_settings(), "page-1", "page-token-1")
    assert result == {"id": "ig-1", "username": "moja_marka", "account_type": "BUSINESS"}
    assert calls[0][1] == "instagram_business_account"
    assert calls[1][0].endswith("/ig-1")


def test_get_linked_instagram_account_keeps_id_when_optional_enrichment_is_rejected(monkeypatch):
    calls = 0

    def fake_get(url, params=None, timeout=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _FakeResponse({"instagram_business_account": {"id": "ig-1"}})
        return _FakeErrorResponse(400, "https://graph.facebook.com/v19.0/ig-1?access_token=secret")

    monkeypatch.setattr("app.integrations.meta.oauth.httpx.get", fake_get)

    result = get_linked_instagram_account(_settings(), "page-1", "page-token-1")

    assert result == {"id": "ig-1"}
