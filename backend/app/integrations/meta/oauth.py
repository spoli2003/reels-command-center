"""Meta (Facebook + Instagram) OAuth — Release 0.8.0 / ADR-021.

One Meta Developer App drives both Facebook Pages and Instagram professional
accounts (Instagram is only reachable via its linked Facebook Page — there is no
separate Instagram-only OAuth app). The user must create this app themselves and
provide META_APP_ID/META_APP_SECRET — RCC cannot create a Meta Developer App on
their behalf, the same bootstrap step YouTube required with
google_client_secret.json.

Unlike Google, Meta has no long-lived "refresh token" concept: a short-lived user
token is exchanged for a long-lived one (~60 days), and Page access tokens derived
from a long-lived user token do not expire on their own. RCC stores the Page
access token as the account's access_token; refresh_token_encrypted is left empty
for Meta accounts (see PlatformAccount.refresh_token_encrypted docstring context).

Some Meta app types (Business-type apps in particular) only expose "Facebook
Login for Business" in the dashboard, which replaces the classic scope-based
Login product with named "Configurations" — each Configuration pre-defines its
own permission set server-side and is referenced by a Configuration ID at
authorize time, instead of RCC sending `scope` itself. `build_authorization_url`
supports both: set `META_LOGIN_CONFIG_ID` to use a Configuration (sends
`config_id`, omits `scope`); leave it empty to use the classic `SCOPES`-based
flow unchanged. Token exchange, long-lived-token exchange, and every Graph API
call after authorization are identical either way — the Configuration only
affects the initial authorize dialog.
"""

from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings

# Least-privilege scopes for reading Page/Instagram content, insights, and
# managing comments — see docs/DECISIONS.md ADR-021 and KNOWN_ISSUES.md for
# Meta App Review implications on accounts outside the developer's own.
#
# business_management (ADR-024): required for GET /me/accounts to return a
# Page that lives inside a Business Portfolio, even when the authenticated
# user has full admin/"Full control" access to it. Without this permission,
# pages_show_list alone is granted but /me/accounts legitimately returns an
# empty array for Business-Portfolio-owned Pages — confirmed against a real
# account that verifiably manages a Page. See KNOWN_ISSUES.md.
PAGE_DISCOVERY_SCOPES = frozenset({"pages_show_list", "business_management"})
FACEBOOK_CONNECT_SCOPES = PAGE_DISCOVERY_SCOPES | {"pages_read_engagement"}
FACEBOOK_CONTENT_SYNC_SCOPES = FACEBOOK_CONNECT_SCOPES | {"read_insights"}
FACEBOOK_COMMENT_SYNC_SCOPES = FACEBOOK_CONNECT_SCOPES | {"pages_read_user_content"}
FACEBOOK_COMMENT_WRITE_SCOPES = FACEBOOK_COMMENT_SYNC_SCOPES | {"pages_manage_engagement"}

# Instagram API with Facebook Login supports both Business and Creator
# professional accounts linked to a Facebook Page. Core media and comments can
# be imported without Insights. Instagram Insights specifically requires
# ``instagram_manage_insights``; Facebook's ``read_insights`` grant does not
# authorize /{ig-media-id}/insights (confirmed by Meta OAuthException #10 on a
# live token). Treat Insights as an optional enrichment so an otherwise valid
# Instagram connection never spins through thousands of guaranteed 400s.
INSTAGRAM_CONNECT_SCOPES = PAGE_DISCOVERY_SCOPES | {
    "pages_read_engagement",
    "instagram_basic",
    "instagram_manage_comments",
}
INSTAGRAM_CONTENT_SYNC_SCOPES = PAGE_DISCOVERY_SCOPES | {
    "pages_read_engagement",
    "instagram_basic",
}
INSTAGRAM_COMMENT_SYNC_SCOPES = PAGE_DISCOVERY_SCOPES | {
    "pages_read_engagement",
    "instagram_basic",
    "instagram_manage_comments",
}
INSTAGRAM_INSIGHTS_SCOPES = frozenset({"instagram_manage_insights"})

SCOPES = sorted(
    FACEBOOK_COMMENT_WRITE_SCOPES
    | FACEBOOK_CONTENT_SYNC_SCOPES
    | INSTAGRAM_CONNECT_SCOPES
    | INSTAGRAM_INSIGHTS_SCOPES
)


def _graph_url(settings: Settings, path: str) -> str:
    return f"https://graph.facebook.com/{settings.meta_graph_api_version}{path}"


class MetaOAuthError(Exception):
    """Deliberately carries no request URL/params. Every function below sends
    a secret (client_secret) or a bearer credential (user/Page access token)
    as a query parameter — Meta's API requires this for these endpoints — and
    httpx's own HTTPStatusError embeds the full request URL verbatim in its
    message. Left uncaught, that exception's string form (and therefore any
    traceback log) would leak the credential in cleartext. Found live in this
    app's own logs during OAuth debugging — see docs/KNOWN_ISSUES.md."""

    def __init__(self, status_code: int):
        super().__init__(f"Meta Graph API call failed with HTTP {status_code}")
        self.status_code = status_code


def _get_or_sanitize(url: str, params: dict) -> httpx.Response:
    response = httpx.get(url, params=params, timeout=15)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise MetaOAuthError(exc.response.status_code) from None
    return response


def build_authorization_url(settings: Settings, state: str) -> str:
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "state": state,
        "response_type": "code",
    }
    if settings.meta_login_config_id:
        # Facebook Login for Business Configuration flow: the Configuration
        # itself owns the permission set (assigned in the Meta dashboard) —
        # sending `scope` alongside `config_id` is redundant and not part of
        # Meta's documented Configuration-based Login flow, so it's omitted.
        params["config_id"] = settings.meta_login_config_id
    else:
        params["scope"] = ",".join(SCOPES)
    return f"https://www.facebook.com/{settings.meta_graph_api_version}/dialog/oauth?{urlencode(params)}"


def exchange_code_for_token(settings: Settings, code: str) -> dict[str, Any]:
    response = _get_or_sanitize(
        _graph_url(settings, "/oauth/access_token"),
        {
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "redirect_uri": settings.meta_redirect_uri,
            "code": code,
        },
    )
    return response.json()


def exchange_for_long_lived_token(settings: Settings, short_lived_token: str) -> dict[str, Any]:
    response = _get_or_sanitize(
        _graph_url(settings, "/oauth/access_token"),
        {
            "grant_type": "fb_exchange_token",
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "fb_exchange_token": short_lived_token,
        },
    )
    return response.json()


def list_pages(settings: Settings, user_access_token: str) -> list[dict[str, Any]]:
    """Each item includes its own Page access token — the one RCC actually
    stores and uses for subsequent Page/Instagram calls. `fan_count` (Page
    followers) and `category` are included for the Page Selection screen
    (Release 0.8.1 / ADR-023) — display-only, not used for auth. `tasks` (the
    user's permitted actions on that Page — MODERATE, ADVERTISE, ...) is used
    for OAuth diagnostics (ADR-024) and is otherwise informational.

    Keep Page discovery independent from Instagram enrichment. Meta rejects the
    entire ``/me/accounts`` request when even one nested Instagram subfield is
    unavailable for the current account/API version. Instagram is resolved per
    Page afterwards by ``get_linked_instagram_account`` so an optional profile
    field can never hide an otherwise valid Facebook Page."""
    response = _get_or_sanitize(
        _graph_url(settings, "/me/accounts"),
        {
            "access_token": user_access_token,
            "fields": "id,name,access_token,category,picture,fan_count,tasks",
        },
    )
    return response.json().get("data", [])


def get_me(settings: Settings, user_access_token: str) -> dict[str, Any]:
    """The authenticated Facebook user's own id/name — used for OAuth
    diagnostics (ADR-024) to confirm which Meta identity actually completed
    the consent flow, independent of whatever Pages that identity does or
    doesn't manage."""
    response = _get_or_sanitize(_graph_url(settings, "/me"), {"access_token": user_access_token, "fields": "id,name"})
    return response.json()


def get_granted_permissions(settings: Settings, user_access_token: str) -> dict[str, str]:
    """{permission_name: "granted"|"declined"} for this specific token, via
    GET /me/permissions. The only way to distinguish, from the server side,
    "pages_show_list was never granted on this consent" from "it was granted
    but zero Pages were shared as assets" — both produce an identical empty
    GET /me/accounts response otherwise. See ADR-024."""
    response = _get_or_sanitize(_graph_url(settings, "/me/permissions"), {"access_token": user_access_token})
    return {item["permission"]: item["status"] for item in response.json().get("data", [])}


def debug_token(settings: Settings, token_to_inspect: str) -> dict[str, Any]:
    """Authoritative token-type/scope inspection via GET /debug_token
    (ADR-024) — more reliable than inferring token type indirectly from which
    fields a /me call happens to return. `access_token` here is the
    documented app-access-token format (`app_id|app_secret`), not the token
    being inspected; still routed through _get_or_sanitize since it's
    secret-bearing like every other call here."""
    app_access_token = f"{settings.meta_app_id}|{settings.meta_app_secret}"
    response = _get_or_sanitize(_graph_url(settings, "/debug_token"), {"input_token": token_to_inspect, "access_token": app_access_token})
    return response.json().get("data", {})


def get_linked_instagram_account(settings: Settings, page_id: str, page_access_token: str) -> dict[str, Any] | None:
    # Resolve the relationship with the smallest documented Page field first.
    # Asking Meta to expand every optional Instagram profile field inline made
    # the real callback fail with HTTP 400 before RCC could show Page Selection.
    response = _get_or_sanitize(
        _graph_url(settings, f"/{page_id}"),
        {
            "fields": "instagram_business_account",
            "access_token": page_access_token,
        },
    )
    linked = response.json().get("instagram_business_account")
    if not linked or not linked.get("id"):
        return None

    # Enrichment is display-only. A missing/unsupported optional field must not
    # prevent the account id from reaching Page Selection and PlatformAccount
    # creation; the sync engine only needs the id. Preserve strict handling for
    # authentication/server failures.
    try:
        details = _get_or_sanitize(
            _graph_url(settings, f"/{linked['id']}"),
            {
                # ``account_type`` is rejected with OAuthException #100 for
                # the live Facebook-Login-backed professional account while
                # every field below is available. It is display-only, so one
                # unsupported field must not discard the username needed for
                # own-comment detection and account labelling.
                "fields": "id,username,profile_picture_url,followers_count,media_count",
                "access_token": page_access_token,
            },
        ).json()
    except MetaOAuthError as exc:
        if exc.status_code in {400, 403}:
            return linked
        raise
    return {**linked, **details}
