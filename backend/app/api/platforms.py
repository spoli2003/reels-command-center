"""Generic multi-platform API — Release 0.8.0 (Parts 5-9, ADR-020/ADR-021).

One namespace (`/api/platforms/{platform}/...`) serves YouTube, Facebook, and
Instagram identically. For Facebook/Instagram this is the ONLY API surface —
for YouTube it is an additional, shallower surface on top of the existing
`/api/integrations/youtube/...` deep pages (which remain the full-depth,
unaffected YouTube experience). Data for all three platforms lives in the same
unified tables (`Publication`/`MetricSnapshot`/`ContentCommentThread`/
`ContentComment`); YouTube's rows are kept in sync there by
`youtube_unified_bridge.py`, never written here directly.

Mutating actions (sync, reply, edit, delete) are rejected for `platform=youtube`
with a pointer to the dedicated endpoint, since YouTube's own sync/comment
engine is deeper (quota-aware, incremental) than the generic one built for
Facebook/Instagram.
"""

import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.meta.client import GraphAPIError
from app.integrations.meta.oauth import (
    FACEBOOK_COMMENT_SYNC_SCOPES,
    FACEBOOK_COMMENT_WRITE_SCOPES,
    FACEBOOK_CONNECT_SCOPES,
    FACEBOOK_CONTENT_SYNC_SCOPES,
    INSTAGRAM_COMMENT_SYNC_SCOPES,
    INSTAGRAM_CONNECT_SCOPES,
    INSTAGRAM_CONTENT_SYNC_SCOPES,
    INSTAGRAM_INSIGHTS_SCOPES,
    MetaOAuthError,
    build_authorization_url,
    debug_token,
    exchange_code_for_token,
    exchange_for_long_lived_token,
    get_granted_permissions,
    get_linked_instagram_account,
    get_me,
    list_pages,
)
from app.models.comments import QuickReplyTemplate
from app.models.content import MetricSnapshot, Publication
from app.models.content_comments import ContentComment
from app.models.integration import PlatformAccount, SyncRun, YoutubeChannel
from app.schemas.comments import QuickReplyTemplateCreate, QuickReplyTemplateRead, QuickReplyTemplateUpdate
from app.schemas.platforms import (
    MetaPageSelectionRequest,
    MetaPageSelectionResult,
    MetaPendingInstagram,
    MetaPendingPage,
    MetaPendingPagesRead,
    PlatformCommentInboxRead,
    PlatformCommentInboxSummary,
    PlatformCommentThreadRead,
    PlatformReplyCreate,
    PlatformReplyRead,
    PlatformReplyUpdate,
    PlatformStatus,
    PlatformSummary,
    PlatformVideoRead,
)
from app.services import content_comment_actions as comment_actions
from app.services import meta_pending_selection, meta_scheduler
from app.services.meta_pending_selection import PendingSelectionStoreError
from app.services.content_comment_sync import ContentCommentSyncAlreadyRunningError, sync_platform_comments
from app.services.content_comments_query import build_inbox_rows, build_inbox_summary, filter_and_sort_rows
from app.services.content_intelligence_adapter import get_platform_intelligence_report, get_platform_video_history
from app.services.content_sync import ContentSyncAlreadyRunningError, get_publications_with_latest_snapshot
from app.services.meta_sync import build_meta_adapter, sync_meta_account
from app.services.platforms.base import PlatformAdapter
from app.services.token_crypto import decrypt_token, encrypt_token

router = APIRouter(prefix="/api/platforms", tags=["Platforms"])
oauth_logger = logging.getLogger("meta_oauth")

SUPPORTED_PLATFORMS = ("youtube", "facebook", "instagram")
SESSION_COOKIE_NAME = "session"  # Starlette SessionMiddleware's default cookie name (app/main.py doesn't override it).
META_PLATFORMS = ("facebook", "instagram")
ALL_PLATFORMS_KEY = "all"  # pseudo-platform: merged read across every connected platform (Part 7)
META_CONNECT_REQUIRED_SCOPES = {
    "facebook": set(FACEBOOK_CONNECT_SCOPES),
    "instagram": set(INSTAGRAM_CONNECT_SCOPES),
}
META_CONTENT_SYNC_REQUIRED_SCOPES = {
    "facebook": set(FACEBOOK_CONTENT_SYNC_SCOPES),
    "instagram": set(INSTAGRAM_CONTENT_SYNC_SCOPES),
}
META_COMMENT_SYNC_REQUIRED_SCOPES = {
    "facebook": set(FACEBOOK_COMMENT_SYNC_SCOPES),
    "instagram": set(INSTAGRAM_COMMENT_SYNC_SCOPES),
}
META_COMMENT_WRITE_REQUIRED_SCOPES = {
    "facebook": set(FACEBOOK_COMMENT_WRITE_SCOPES),
    "instagram": set(INSTAGRAM_COMMENT_SYNC_SCOPES),
}
META_OPTIONAL_COMMENT_SCOPES = {
    platform: META_COMMENT_SYNC_REQUIRED_SCOPES[platform] - META_CONTENT_SYNC_REQUIRED_SCOPES[platform]
    for platform in META_PLATFORMS
}


def _require_known_platform(platform: str) -> None:
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(404, f"Nieznana platforma: {platform}")


def _require_real_platform_for_videos(platform: str) -> None:
    if platform != ALL_PLATFORMS_KEY and platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(404, f"Nieznana platforma: {platform}")


def _get_account(db: Session, platform: str) -> Optional[PlatformAccount]:
    return db.scalar(select(PlatformAccount).where(PlatformAccount.platform == platform))


def _require_account(db: Session, platform: str) -> PlatformAccount:
    account = _get_account(db, platform)
    if account is None:
        raise HTTPException(409, f"Najpierw połącz konto ({platform}).")
    return account


def _platform_configured(platform: str, settings) -> bool:
    if platform == "youtube":
        return settings.client_secrets_path.exists() and bool(settings.token_encryption_key)
    if platform in META_PLATFORMS:
        return bool(settings.meta_app_id and settings.meta_app_secret and settings.token_encryption_key)
    return False


def _require_scope_names(granted: set[str], required: set[str], action: str) -> None:
    missing = sorted(required - granted)
    if not missing:
        return
    raise HTTPException(
        409,
        "Meta nie przyznała RCC uprawnień wymaganych do "
        f"{action}: {', '.join(missing)}. Dodaj je w Facebook Login for Business → "
        "Configurations → Permissions, usuń stare połączenie RCC w Integracjach "
        "biznesowych Facebooka i połącz konto ponownie.",
    )


def _require_comment_scope_names(granted: set[str], required: set[str], action: str) -> None:
    """Gate only the comment feature, never the Page connection/content sync.

    ``pages_read_user_content`` is a real Facebook permission for reading
    user-generated Page content, including comment text. It is not required to
    connect a Page or import Page-owned posts/videos. Some Facebook Login for
    Business Configurations do not expose it, so RCC must degrade gracefully
    instead of presenting the whole Facebook account as disconnected.
    """
    missing = sorted(required - granted)
    if not missing:
        return
    raise HTTPException(
        409,
        f"{action.capitalize()} jest niedostępna dla tego połączenia Meta. "
        f"Brakujące uprawnienia tej funkcji: {', '.join(missing)}. "
        "Połączenie konta i synchronizacja postów, filmów oraz statystyk nadal działają. "
        "Uprawnienie do komentarzy można dodać później, jeśli aktywna konfiguracja Meta je udostępnia.",
    )


def _comment_skip_reason(platform: str, missing: set[str]) -> str:
    names = ", ".join(sorted(missing))
    return (
        f"Pominięto komentarze {platform}: token nie ma opcjonalnych uprawnień {names}. "
        "Posty, filmy i statystyki zostały zsynchronizowane."
    )


def _live_meta_scopes(settings, access_token: str, action: str) -> set[str]:
    """Read the scopes Meta actually granted to this token.

    PlatformAccount.scopes is only a cached diagnostic value. Authorization
    decisions must use /debug_token so a stale or previously over-optimistic DB
    value can never make a broken connection look usable.
    """
    try:
        info = debug_token(settings, access_token)
    except MetaOAuthError as exc:
        raise HTTPException(502, f"Nie udało się sprawdzić uprawnień Meta przed {action} (HTTP {exc.status_code}).") from None
    if not info.get("is_valid", True):
        raise HTTPException(401, "Token Meta wygasł lub został unieważniony. Połącz konto ponownie.")
    return set(info.get("scopes") or [])


def _build_adapter(db: Session, platform: str, settings) -> tuple[PlatformAccount, PlatformAdapter]:
    if platform not in META_PLATFORMS:
        raise HTTPException(400, f"Platforma '{platform}' nie obsługuje generycznej synchronizacji.")
    account = _require_account(db, platform)
    return account, build_meta_adapter(account, settings)


def _video_to_read(publication: Publication, snapshot: Optional[MetricSnapshot]) -> PlatformVideoRead:
    video = publication.content_video
    views = snapshot.views if snapshot else 0
    likes = snapshot.likes if snapshot else 0
    comments = snapshot.comments if snapshot else 0
    engagement_rate = round((likes + comments) / views * 100, 2) if views else 0.0
    return PlatformVideoRead(
        external_id=publication.external_id,
        platform=publication.platform,
        title=video.title,
        description=video.description,
        url=publication.url,
        published_at=publication.published_at,
        thumbnail_url=video.thumbnail_url,
        duration_seconds=video.duration_seconds,
        views=views,
        likes=likes,
        comments=comments,
        shares=snapshot.shares if snapshot else 0,
        saves=snapshot.saves if snapshot else 0,
        reach=snapshot.reach if snapshot else None,
        impressions=snapshot.impressions if snapshot else None,
        followers_gained=snapshot.followers_gained if snapshot else None,
        engagement_rate=engagement_rate,
    )


def _reply_to_read(reply: ContentComment) -> PlatformReplyRead:
    return PlatformReplyRead(
        platform_comment_id=reply.platform_comment_id,
        author_external_id=reply.author_external_id,
        author_display_name=reply.author_display_name,
        author_avatar_url=reply.author_avatar_url,
        text_original=reply.text_original,
        like_count=reply.like_count,
        published_at=reply.published_at,
        updated_at=reply.updated_at,
        is_own_reply=reply.is_own_reply,
    )


def _thread_to_read(row: dict) -> PlatformCommentThreadRead:
    thread = row["thread"]
    publication = row["publication"]
    video = publication.content_video if publication else None
    return PlatformCommentThreadRead(
        platform_thread_id=thread.platform_thread_id,
        external_id=publication.external_id if publication else "",
        video_title=video.title if video else "Materiał usunięty lub niezsynchronizowany",
        video_thumbnail_url=video.thumbnail_url if video else None,
        top_level_comment_id=thread.top_level_comment_id,
        author_external_id=thread.author_external_id,
        author_display_name=thread.author_display_name,
        author_avatar_url=thread.author_avatar_url,
        text_original=thread.text_original,
        like_count=thread.like_count,
        published_at=thread.published_at,
        updated_at=thread.updated_at,
        total_reply_count=thread.total_reply_count,
        can_reply=thread.can_reply,
        is_own_thread=row["is_own_thread"],
        conversation_state=row["conversation_state"].value,
        last_message_at=row["last_message_at"],
        is_likely_question=row["is_likely_question"],
        is_highly_liked=row["is_highly_liked"],
        priority_score=row["priority_score"],
        replies=[_reply_to_read(r) for r in row["replies"]],
    )


def _own_external_id(db: Session, platform: str, account: PlatformAccount) -> Optional[str]:
    if platform == "facebook":
        return account.external_account_id
    if platform == "instagram":
        return account.display_name or None  # the IG username is stored as display_name
    if platform == "youtube":
        channel = db.scalar(select(YoutubeChannel).where(YoutubeChannel.account_id == account.id))
        return channel.youtube_channel_id if channel else None
    return None


# --- Overview ----------------------------------------------------------------


@router.get("", response_model=list[PlatformSummary])
def list_platforms(db: Session = Depends(get_db)):
    result = []
    for platform in SUPPORTED_PLATFORMS:
        account = _get_account(db, platform)
        audience_count = account.audience_count if account else None
        if platform == "youtube" and account is not None:
            channel = db.scalar(select(YoutubeChannel).where(YoutubeChannel.account_id == account.id))
            audience_count = channel.subscriber_count if channel else None
        granted = {scope for scope in (account.scopes.split(",") if account else []) if scope}
        result.append(
            PlatformSummary(
                platform=platform,
                connected=account is not None,
                display_name=account.display_name if account else None,
                audience_count=audience_count,
                views_available=platform != "instagram" or INSTAGRAM_INSIGHTS_SCOPES <= granted,
            )
        )
    return result


# --- Meta OAuth (Facebook Pages + Instagram Professional accounts) -----------


def _log_oauth_diagnostics(request: Request, stage: str, **extra_yes_no: bool) -> None:
    """Runtime OAuth-state audit trail (ADR-024) — every field here is
    non-secret by construction: request metadata and yes/no facts only, never
    a cookie value, session id, state string, code, or token. Exists because
    "Nieprawidłowy stan OAuth" has exactly one cause class (the session cookie
    set during /meta/connect not reaching /meta/callback) and that class has
    several distinct root causes (hostname mismatch, SameSite policy, an
    expired/pruned cookie, a genuine CSRF replay) that are otherwise
    indistinguishable from the outside."""
    fields = {
        "stage": stage,
        "host": request.headers.get("host"),
        "origin": request.headers.get("origin"),
        "referer": request.headers.get("referer"),
        "url": f"{request.url.scheme}://{request.url.netloc}{request.url.path}",
        "session_cookie_present": SESSION_COOKIE_NAME in request.cookies,
        **extra_yes_no,
    }
    # .warning, not .info — the app has no logging.basicConfig anywhere, so the
    # root logger's default level (WARNING) would otherwise silently swallow
    # this without a single handler/level being reconfigured app-wide.
    oauth_logger.warning("meta_oauth_diagnostics %s", fields)


def _log_token_diagnostics(user_token: str, settings) -> dict:
    """Credential-free token health diagnostic.

    GET /debug_token is the authoritative source for token type and granted
    scopes. Keeping this compact audit is useful when a Meta Configuration is
    edited, while never logging the token itself.
    """
    try:
        info = debug_token(settings, user_token)
    except Exception:
        oauth_logger.warning("meta_oauth_token_diagnostics {'error': 'debug_token call failed'}")
        return {}
    oauth_logger.warning(
        "meta_oauth_token_diagnostics %s",
        {"token_type": info.get("type"), "scopes": info.get("scopes"), "is_valid": info.get("is_valid"), "expires_at": info.get("expires_at")},
    )
    return info


def _log_me_accounts_diagnostics(me: dict, pages: list[dict]) -> None:
    """Compact Page-discovery diagnostic with no tokens or profile URLs.

    The earlier raw-response diagnostic helped identify the missing
    ``business_management`` grant but also made logs unnecessarily noisy.
    Counts, Page ids/names and Page tasks are sufficient for future support.
    """
    fields = {
        "identity_resolved": bool(me.get("id")),
        "pages_count": len(pages),
        "pages": [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "tasks": p.get("tasks"),
                "instagram_linked": bool(p.get("instagram_business_account")),
            }
            for p in pages
        ],
    }
    oauth_logger.warning("meta_oauth_me_accounts_diagnostics %s", fields)


def _empty_pages_error_message(settings, user_token: str) -> str:
    """GET /me/accounts returning zero Pages is not proof the account manages
    none — Facebook Login for Business explicitly delegates access per
    consent (ADR-024): a Page the user administers is only visible here if it
    was both (a) covered by a granted permission and (b) actually shared as an
    asset during that specific login. Distinguish the two via GET
    /me/permissions rather than asserting either as fact — the previous
    message ("to konto nie zarządza żadną Stroną") was actively misleading
    when the real cause is (a) or (b), which is exactly what was reported."""
    try:
        permissions = get_granted_permissions(settings, user_token)
    except Exception:
        permissions = {}
    oauth_logger.warning("meta_oauth_permissions_diagnostics %s", {"permissions": permissions})

    if permissions.get("pages_show_list") != "granted":
        return (
            "Meta nie przyznała RCC uprawnienia pages_show_list podczas tego logowania — to NIE oznacza, że "
            "konto nie zarządza żadną Stroną. Sprawdź w Meta App Dashboard, czy pages_show_list jest dodane "
            "do użytego Login Configuration (Facebook Login for Business → Configurations → Permissions) "
            "i do odpowiedniego Use Case, a następnie połącz się ponownie."
        )
    return (
        "Meta przyznała dostęp do listy Stron, ale żadna konkretna Strona nie została udostępniona podczas "
        "tego logowania. To konto może zarządzać Stronami — sprawdź, czy w oknie zgody Meta faktycznie wybrano "
        "Strony do udostępnienia (krok wyboru zasobów), oraz czy ta Strona należy do tego samego Portfolio "
        "Biznesowego co aplikacja, a następnie połącz się ponownie."
    )


@router.get("/meta/connect")
def meta_connect(request: Request, target: str = Query("facebook", description="facebook|instagram")):
    settings = get_settings()
    if target not in META_PLATFORMS:
        raise HTTPException(400, "target musi być 'facebook' lub 'instagram'.")
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise HTTPException(500, "Brak META_APP_ID / META_APP_SECRET w konfiguracji.")
    if not settings.token_encryption_key:
        raise HTTPException(500, "Brak TOKEN_ENCRYPTION_KEY w konfiguracji")
    state = secrets.token_urlsafe(32)
    request.session["meta_oauth_state"] = state
    request.session["meta_oauth_target"] = target
    _log_oauth_diagnostics(request, "connect", session_id_present=bool(request.session), stored_state_written=True)
    return RedirectResponse(build_authorization_url(settings, state))


def _build_page_candidates(settings, pages: list[dict], target: str, granted_scopes: set[str]) -> list[dict]:
    """One candidate dict per Facebook Page the Meta account manages, with
    everything the Page Selection screen needs to display (Release 0.8.1 /
    ADR-023) plus the Page's own access token — encrypted at rest even in this
    short-lived in-memory store, consistent with how RCC treats every other
    stored token. The linked Instagram account (if any) is resolved eagerly so
    the picker can show it, and so selecting "Instagram" for a Page never needs
    a second round-trip.

    Instagram is resolved only for an Instagram connection. A Facebook
    connection does not need that optional Graph field and therefore must not
    fail (or falsely display "no Instagram") because Instagram permissions were
    not requested. For an Instagram connection, a successful response without
    the field means "not linked"; an HTTP error means "could not verify" and is
    never converted into a false "not linked" result."""
    candidates = []
    for page in pages:
        page_token = page["access_token"]
        # Page discovery intentionally does not request nested Instagram fields:
        # Meta can reject the whole /me/accounts call when one optional nested
        # field is unavailable. Retain support for an embedded value in mocked
        # or older responses, otherwise resolve the relationship per Page.
        instagram = page.get("instagram_business_account") if target == "instagram" else None
        if target == "instagram":
            if instagram is None:
                try:
                    instagram = get_linked_instagram_account(settings, page["id"], page_token)
                except MetaOAuthError as exc:
                    oauth_logger.warning("meta_oauth_instagram_lookup_failed %s", {"page_id": page.get("id"), "status_code": exc.status_code})
                    if exc.status_code == 400:
                        raise HTTPException(
                            409,
                            "Meta przyznała wymagane uprawnienia, ale odrzuciła odczyt połączonego konta Instagram. "
                            "Sprawdź, czy profil jest kontem profesjonalnym (Business lub Creator) i jest połączony "
                            "z tą Stroną na Facebooku, a następnie połącz Instagram ponownie.",
                        ) from None
                    raise HTTPException(502, f"Meta nie pozwoliła sprawdzić połączonego konta Instagram (HTTP {exc.status_code}).") from None
        picture_url = ((page.get("picture") or {}).get("data") or {}).get("url")
        candidates.append(
            {
                "id": page["id"],
                "name": page.get("name", "Facebook"),
                "category": page.get("category"),
                "picture_url": picture_url,
                "followers": page.get("fan_count"),
                "access_token_encrypted": encrypt_token(page_token, settings.token_encryption_key),
                "granted_scopes": sorted(granted_scopes),
                "instagram": (
                    {
                        "id": instagram["id"],
                        "username": instagram.get("username"),
                        "picture_url": instagram.get("profile_picture_url"),
                        "account_type": instagram.get("account_type"),
                        "followers": instagram.get("followers_count"),
                        "media_count": instagram.get("media_count"),
                    }
                    if instagram
                    else None
                ),
            }
        )
    return candidates


@router.get("/meta/callback")
def meta_callback(request: Request, state: str, code: str):
    """Never auto-connects a Page (ADR-023) — fetches every Page the Meta
    account manages (with its linked Instagram account resolved), stores them
    server-side keyed by an opaque `selection_id`, and redirects the browser to
    the frontend's Page Selection screen. The actual PlatformAccount is only
    written once the user picks one, in POST /meta/select-page below."""
    settings = get_settings()
    stored_state = request.session.get("meta_oauth_state")
    _log_oauth_diagnostics(
        request,
        "callback",
        session_id_present=bool(request.session),
        stored_state_exists=stored_state is not None,
        callback_state_exists=bool(state),
        state_matches=(state == stored_state),
    )
    if state != request.session.pop("meta_oauth_state", None):
        raise HTTPException(400, "Nieprawidłowy stan OAuth")
    target = request.session.pop("meta_oauth_target", "facebook")

    short_lived = exchange_code_for_token(settings, code)
    long_lived = exchange_for_long_lived_token(settings, short_lived["access_token"])
    user_token = long_lived["access_token"]

    me = get_me(settings, user_token)
    token_info = _log_token_diagnostics(user_token, settings)
    granted_scopes = set(token_info.get("scopes") or [])
    _require_scope_names(
        granted_scopes,
        META_CONNECT_REQUIRED_SCOPES[target],
        f"połączenia konta {target}",
    )
    try:
        pages = list_pages(settings, user_token)
    except MetaOAuthError as exc:
        raise HTTPException(
            502,
            f"Meta odrzuciła pobranie listy Stron (HTTP {exc.status_code}). Połącz konto ponownie; "
            "jeśli problem się powtórzy, sprawdź uprawnienia pages_show_list, business_management "
            "i pages_read_engagement w aktywnej konfiguracji logowania.",
        ) from None
    _log_me_accounts_diagnostics(me, pages)
    if not pages:
        raise HTTPException(400, _empty_pages_error_message(settings, user_token))

    candidates = _build_page_candidates(settings, pages, target, granted_scopes)
    try:
        selection_id = meta_pending_selection.create_selection(target, candidates)
    except PendingSelectionStoreError as exc:
        oauth_logger.exception("meta_pending_selection_write_failed target=%s", target)
        raise HTTPException(
            503,
            "Nie udało się zachować listy Stron do wyboru. Sprawdź usługę Redis i połącz konto ponownie.",
        ) from exc
    return RedirectResponse(f"{settings.frontend_url}/platforms/meta/select-page?selection={selection_id}")


@router.get("/meta/pending-pages", response_model=MetaPendingPagesRead)
def meta_pending_pages(selection: str = Query(...)):
    try:
        entry = meta_pending_selection.get_selection(selection)
    except PendingSelectionStoreError as exc:
        raise HTTPException(503, "Nie udało się odczytać listy Stron. Sprawdź usługę Redis i spróbuj ponownie.") from exc
    if entry is None:
        raise HTTPException(404, "Brak oczekujących Stron do wyboru — sesja wygasła, połącz się ponownie.")
    return MetaPendingPagesRead(
        target=entry["target"],
        pages=[
            MetaPendingPage(
                id=page["id"],
                name=page["name"],
                category=page["category"],
                picture_url=page["picture_url"],
                followers=page["followers"],
                instagram=MetaPendingInstagram(**page["instagram"]) if page["instagram"] else None,
            )
            for page in entry["pages"]
        ],
    )


@router.post("/meta/select-page", response_model=MetaPageSelectionResult)
def meta_select_page(payload: MetaPageSelectionRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        entry = meta_pending_selection.get_selection(payload.selection_id)
    except PendingSelectionStoreError as exc:
        raise HTTPException(503, "Nie udało się odczytać listy Stron. Sprawdź usługę Redis i spróbuj ponownie.") from exc
    if entry is None:
        raise HTTPException(404, "Brak oczekujących Stron do wyboru — sesja wygasła, połącz się ponownie.")
    chosen = next((page for page in entry["pages"] if page["id"] == payload.page_id), None)
    if chosen is None:
        raise HTTPException(404, "Wybrana Strona nie znajduje się na liście oczekujących.")

    target = entry["target"]
    page_token = decrypt_token(chosen["access_token_encrypted"], settings.token_encryption_key)

    if target == "facebook":
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "facebook", PlatformAccount.external_account_id == chosen["id"]))
        if account is None:
            account = PlatformAccount(platform="facebook", external_account_id=chosen["id"], display_name=chosen["name"], access_token_encrypted="")
            db.add(account)
        account.display_name = chosen["name"]
        account.access_token_encrypted = encrypt_token(page_token, settings.token_encryption_key)
        account.scopes = ",".join(chosen.get("granted_scopes") or [])
        account.audience_count = chosen.get("followers")
        db.commit()
        meta_pending_selection.consume_selection(payload.selection_id)
        return MetaPageSelectionResult(platform="facebook", display_name=chosen["name"])

    instagram = chosen.get("instagram")
    if instagram is None:
        # Deliberately NOT consuming the selection — the user can pick a
        # different Page from the same list without restarting OAuth.
        raise HTTPException(400, f"Strona '{chosen['name']}' nie ma podłączonego konta Instagram Professional. Wybierz inną Stronę.")
    account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "instagram", PlatformAccount.external_account_id == instagram["id"]))
    if account is None:
        account = PlatformAccount(platform="instagram", external_account_id=instagram["id"], display_name=instagram.get("username") or "Instagram", access_token_encrypted="")
        db.add(account)
    account.display_name = instagram.get("username") or account.display_name
    account.access_token_encrypted = encrypt_token(page_token, settings.token_encryption_key)
    account.scopes = ",".join(chosen.get("granted_scopes") or [])
    account.audience_count = instagram.get("followers")
    db.commit()
    db.refresh(account)

    # First real sync is part of connecting Instagram, not a hidden second
    # step. Keep the account connected if Meta returns a data-side error so the
    # creator can retry from the dashboard without repeating OAuth.
    initial_sync_status = "success"
    initial_sync_message = None
    imported_items = 0
    comments_imported = 0
    try:
        sync_result = sync_meta_account(db, account, settings)
        initial_sync_status = sync_result.status
        imported_items = sync_result.content_run.imported_items
        comments_imported = sync_result.comment_run.comments_imported if sync_result.comment_run else 0
        initial_sync_message = sync_result.comment_error
    except Exception:
        oauth_logger.exception("instagram_initial_sync_failed account_id=%s", account.id)
        initial_sync_status = "failed"
        initial_sync_message = "Konto połączono, ale pierwsza synchronizacja nie powiodła się. Użyj „Synchronizuj teraz”, aby ponowić."
    meta_pending_selection.consume_selection(payload.selection_id)
    return MetaPageSelectionResult(
        platform="instagram",
        display_name=account.display_name,
        initial_sync_status=initial_sync_status,
        initial_sync_message=initial_sync_message,
        imported_items=imported_items,
        comments_imported=comments_imported,
    )


# --- Status / connection lifecycle -------------------------------------------


@router.get("/{platform}/status", response_model=PlatformStatus)
def platform_status(platform: str, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    settings = get_settings()
    configured = _platform_configured(platform, settings)
    account = _get_account(db, platform)
    video_count = db.scalar(select(func.count(Publication.id)).where(Publication.platform == platform)) or 0
    sync_platform_name = platform if platform != "youtube" else "youtube"
    last_run = db.scalar(
        select(SyncRun).where(SyncRun.platform == sync_platform_name, SyncRun.status != "running").order_by(SyncRun.started_at.desc())
    )
    last_comments_run = db.scalar(
        select(SyncRun)
        .where(SyncRun.platform == f"{platform}_comments", SyncRun.status != "running")
        .order_by(SyncRun.started_at.desc())
    ) if platform in META_PLATFORMS else None
    required_permissions = sorted(META_CONTENT_SYNC_REQUIRED_SCOPES.get(platform, set()))
    optional_scope_set = set(META_OPTIONAL_COMMENT_SCOPES.get(platform, set()))
    if platform == "instagram":
        optional_scope_set |= set(INSTAGRAM_INSIGHTS_SCOPES)
    optional_permissions = sorted(optional_scope_set)
    granted_permissions = sorted({scope for scope in (account.scopes.split(",") if account else []) if scope})
    missing_permissions = sorted(set(required_permissions) - set(granted_permissions))
    missing_optional_permissions = sorted(set(optional_permissions) - set(granted_permissions))
    if account is None:
        message = "Gotowe do połączenia" if configured else "Skonfiguruj poświadczenia, aby połączyć."
    elif missing_permissions:
        message = "Połącz ponownie konto, aby przyznać brakujące uprawnienia Meta."
    else:
        message = "Połączono"
    return PlatformStatus(
        platform=platform,
        connected=account is not None,
        configured=configured,
        display_name=account.display_name if account else None,
        video_count=video_count,
        last_synced_at=last_run.finished_at if last_run else None,
        last_sync_status=last_run.status if last_run else None,
        last_sync_error=last_run.error_message if last_run else None,
        last_comments_synced_at=last_comments_run.finished_at if last_comments_run else None,
        last_comments_sync_status=last_comments_run.status if last_comments_run else None,
        last_comments_sync_error=last_comments_run.error_message if last_comments_run else None,
        required_permissions=required_permissions,
        granted_permissions=granted_permissions,
        missing_permissions=missing_permissions,
        optional_permissions=optional_permissions,
        missing_optional_permissions=missing_optional_permissions,
        scheduler_enabled=settings.meta_sync_enabled if platform in META_PLATFORMS else False,
        next_scheduled_sync_at=meta_scheduler.next_run_at() if platform in META_PLATFORMS else None,
        message=message,
    )


@router.delete("/{platform}/disconnect", status_code=204)
def disconnect_platform(platform: str, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    if platform == "youtube":
        raise HTTPException(400, "Rozłącz YouTube przez DELETE /api/integrations/youtube/disconnect.")
    accounts = db.scalars(select(PlatformAccount).where(PlatformAccount.platform == platform)).all()
    for account in accounts:
        db.delete(account)
    db.commit()


@router.post("/{platform}/sync")
def sync_platform(platform: str, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    if platform == "youtube":
        raise HTTPException(400, "YouTube ma dedykowany silnik synchronizacji — użyj POST /api/integrations/youtube/sync.")
    settings = get_settings()
    account = _require_account(db, platform)
    access_token = decrypt_token(account.access_token_encrypted, settings.token_encryption_key)
    granted_scopes = _live_meta_scopes(settings, access_token, "synchronizacją")
    _require_scope_names(granted_scopes, META_CONTENT_SYNC_REQUIRED_SCOPES[platform], f"synchronizacji treści {platform}")
    missing_comment_scopes = META_COMMENT_SYNC_REQUIRED_SCOPES[platform] - granted_scopes
    account.scopes = ",".join(sorted(granted_scopes))
    db.commit()
    try:
        result = sync_meta_account(
            db,
            account,
            settings,
            sync_comments=not missing_comment_scopes,
            comment_skip_reason=_comment_skip_reason(platform, missing_comment_scopes) if missing_comment_scopes else None,
        )
    except ContentSyncAlreadyRunningError as exc:
        raise HTTPException(409, str(exc)) from exc
    except GraphAPIError as exc:
        raise HTTPException(502, f"Meta odrzuciła synchronizację {platform} (HTTP {exc.status_code or 'nieznany'}).") from None
    run = result.content_run
    comment_run = result.comment_run
    return {
        "status": result.status,
        "imported_items": run.imported_items,
        "videos_discovered": run.videos_discovered,
        "videos_updated": run.videos_updated,
        "snapshots_created": run.snapshots_created,
        "snapshots_deduplicated": run.snapshots_deduplicated,
        "videos_failed": run.videos_failed,
        "threads_discovered": comment_run.threads_discovered if comment_run else 0,
        "comments_imported": comment_run.comments_imported if comment_run else 0,
        "replies_imported": comment_run.replies_imported if comment_run else 0,
        "comment_sync_error": result.comment_error,
    }


# --- Videos / Intelligence (read-only, work for all 3 platforms incl. bridged YouTube) --


@router.get("/{platform}/videos", response_model=list[PlatformVideoRead])
def platform_videos(platform: str, db: Session = Depends(get_db)):
    _require_real_platform_for_videos(platform)
    rows = get_publications_with_latest_snapshot(db, None if platform == ALL_PLATFORMS_KEY else platform)
    return [_video_to_read(pub, snap) for pub, snap in rows]


@router.get("/{platform}/videos/{external_id}", response_model=PlatformVideoRead)
def platform_video_detail(platform: str, external_id: str, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    publication = db.scalar(select(Publication).where(Publication.platform == platform, Publication.external_id == external_id))
    if publication is None:
        raise HTTPException(404, "Nie znaleziono materiału")
    latest = db.scalar(
        select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id).order_by(MetricSnapshot.captured_at.desc()).limit(1)
    )
    return _video_to_read(publication, latest)


@router.get("/{platform}/videos/{external_id}/history")
def platform_video_history(platform: str, external_id: str, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    history = get_platform_video_history(db, platform, external_id)
    if history is None:
        raise HTTPException(404, "Nie znaleziono materiału")
    return history


@router.get("/{platform}/intelligence")
def platform_intelligence(platform: str, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    report = get_platform_intelligence_report(db, platform)
    if report is None:
        raise HTTPException(404, "Za mało danych, aby zbudować raport Creator Intelligence dla tej platformy.")
    return report


# --- Comments (Community Engine, reused for all 3 platforms) ----------------


@router.get("/{platform}/comments", response_model=PlatformCommentInboxRead)
def platform_comments(
    platform: str,
    quick: Optional[str] = Query(None, description="mine|new|waiting|resolved|closed|unanswered|answered|questions|recent|with_replies|highly_liked"),
    video: Optional[str] = Query(None, description="Filter by external_id"),
    author: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    sort: str = Query("newest", description="newest|oldest|most_liked|most_replies|priority|recently_active"),
    db: Session = Depends(get_db),
):
    _require_known_platform(platform)
    account = _require_account(db, platform)
    own_external_id = _own_external_id(db, platform, account)
    rows = build_inbox_rows(db, account.id, own_external_id)
    summary = build_inbox_summary(rows)

    publication_id = None
    if video:
        pub = db.scalar(select(Publication).where(Publication.platform == platform, Publication.external_id == video))
        publication_id = pub.id if pub else -1

    filtered = filter_and_sort_rows(rows, quick=quick, publication_id=publication_id, author=author, search=q, sort=sort)
    return PlatformCommentInboxRead(summary=PlatformCommentInboxSummary(**summary), threads=[_thread_to_read(r) for r in filtered])


@router.post("/{platform}/comments/sync")
def sync_platform_comments_endpoint(platform: str, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    if platform == "youtube":
        raise HTTPException(400, "YouTube ma dedykowany endpoint komentarzy — użyj POST /api/integrations/youtube/comments/sync.")
    settings = get_settings()
    account = _require_account(db, platform)
    access_token = decrypt_token(account.access_token_encrypted, settings.token_encryption_key)
    granted_scopes = _live_meta_scopes(settings, access_token, "synchronizacją komentarzy")
    _require_comment_scope_names(granted_scopes, META_COMMENT_SYNC_REQUIRED_SCOPES[platform], f"synchronizacja komentarzy {platform}")
    account.scopes = ",".join(sorted(granted_scopes))
    db.commit()
    account, adapter = _build_adapter(db, platform, settings)
    try:
        run = sync_platform_comments(db, account, adapter)
    except ContentCommentSyncAlreadyRunningError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "status": run.status,
        "threads_discovered": run.threads_discovered,
        "comments_imported": run.comments_imported,
        "replies_imported": run.replies_imported,
        "videos_failed": run.videos_failed,
    }


@router.post("/{platform}/comments/threads/{thread_platform_id}/reply", response_model=PlatformReplyRead)
def platform_reply(platform: str, thread_platform_id: str, payload: PlatformReplyCreate, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    if platform == "youtube":
        raise HTTPException(400, "YouTube ma dedykowany endpoint komentarzy — użyj /api/integrations/youtube/comments/threads/{id}/reply.")
    settings = get_settings()
    account = _require_account(db, platform)
    access_token = decrypt_token(account.access_token_encrypted, settings.token_encryption_key)
    granted_scopes = _live_meta_scopes(settings, access_token, "publikacją odpowiedzi")
    _require_comment_scope_names(granted_scopes, META_COMMENT_WRITE_REQUIRED_SCOPES[platform], f"odpowiadanie na komentarze {platform}")
    account, adapter = _build_adapter(db, platform, settings)
    try:
        comment = comment_actions.post_reply(db, account, adapter, thread_platform_id, payload.text)
    except comment_actions.ContentCommentActionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except GraphAPIError as exc:
        raise HTTPException(502, f"Platforma odrzuciła publikację odpowiedzi: {exc}") from exc
    return _reply_to_read(comment)


@router.put("/{platform}/comments/{comment_platform_id}", response_model=PlatformReplyRead)
def platform_edit_reply(platform: str, comment_platform_id: str, payload: PlatformReplyUpdate, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    if platform == "youtube":
        raise HTTPException(400, "YouTube ma dedykowany endpoint komentarzy — użyj PUT /api/integrations/youtube/comments/{id}.")
    settings = get_settings()
    account = _require_account(db, platform)
    access_token = decrypt_token(account.access_token_encrypted, settings.token_encryption_key)
    granted_scopes = _live_meta_scopes(settings, access_token, "edycją odpowiedzi")
    _require_comment_scope_names(granted_scopes, META_COMMENT_WRITE_REQUIRED_SCOPES[platform], f"edycja odpowiedzi {platform}")
    account, adapter = _build_adapter(db, platform, settings)
    try:
        comment = comment_actions.edit_reply(db, account, adapter, comment_platform_id, payload.text)
    except comment_actions.ContentCommentActionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except GraphAPIError as exc:
        raise HTTPException(502, f"Platforma odrzuciła edycję odpowiedzi: {exc}") from exc
    return _reply_to_read(comment)


@router.delete("/{platform}/comments/{comment_platform_id}", status_code=204)
def platform_delete_reply(platform: str, comment_platform_id: str, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    if platform == "youtube":
        raise HTTPException(400, "YouTube ma dedykowany endpoint komentarzy — użyj DELETE /api/integrations/youtube/comments/{id}.")
    settings = get_settings()
    account = _require_account(db, platform)
    access_token = decrypt_token(account.access_token_encrypted, settings.token_encryption_key)
    granted_scopes = _live_meta_scopes(settings, access_token, "usunięciem odpowiedzi")
    _require_comment_scope_names(granted_scopes, META_COMMENT_WRITE_REQUIRED_SCOPES[platform], f"usuwanie odpowiedzi {platform}")
    account, adapter = _build_adapter(db, platform, settings)
    try:
        comment_actions.delete_reply(db, account, adapter, comment_platform_id)
    except comment_actions.ContentCommentActionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except GraphAPIError as exc:
        raise HTTPException(502, f"Platforma odrzuciła usunięcie odpowiedzi: {exc}") from exc


# --- Quick reply templates (already platform-neutral — QuickReplyTemplate.account_id
# works unchanged for any PlatformAccount) -------------------------------------


@router.get("/{platform}/quick-replies", response_model=list[QuickReplyTemplateRead])
def list_platform_quick_replies(platform: str, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    account = _require_account(db, platform)
    templates = db.scalars(
        select(QuickReplyTemplate).where(QuickReplyTemplate.account_id == account.id).order_by(QuickReplyTemplate.position)
    ).all()
    return [QuickReplyTemplateRead(id=t.id, text=t.text, position=t.position) for t in templates]


@router.post("/{platform}/quick-replies", response_model=QuickReplyTemplateRead)
def create_platform_quick_reply(platform: str, payload: QuickReplyTemplateCreate, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    account = _require_account(db, platform)
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "Treść szablonu nie może być pusta.")
    max_position = db.scalar(
        select(QuickReplyTemplate).where(QuickReplyTemplate.account_id == account.id).order_by(QuickReplyTemplate.position.desc())
    )
    template = QuickReplyTemplate(account_id=account.id, text=text, position=(max_position.position + 1) if max_position else 0)
    db.add(template)
    db.commit()
    db.refresh(template)
    return QuickReplyTemplateRead(id=template.id, text=template.text, position=template.position)


@router.put("/{platform}/quick-replies/{template_id}", response_model=QuickReplyTemplateRead)
def update_platform_quick_reply(platform: str, template_id: int, payload: QuickReplyTemplateUpdate, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    account = _require_account(db, platform)
    template = db.scalar(select(QuickReplyTemplate).where(QuickReplyTemplate.id == template_id, QuickReplyTemplate.account_id == account.id))
    if template is None:
        raise HTTPException(404, "Nie znaleziono szablonu")
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "Treść szablonu nie może być pusta.")
    template.text = text
    db.commit()
    db.refresh(template)
    return QuickReplyTemplateRead(id=template.id, text=template.text, position=template.position)


@router.delete("/{platform}/quick-replies/{template_id}", status_code=204)
def delete_platform_quick_reply(platform: str, template_id: int, db: Session = Depends(get_db)):
    _require_known_platform(platform)
    account = _require_account(db, platform)
    template = db.scalar(select(QuickReplyTemplate).where(QuickReplyTemplate.id == template_id, QuickReplyTemplate.account_id == account.id))
    if template is None:
        raise HTTPException(404, "Nie znaleziono szablonu")
    db.delete(template)
    db.commit()
