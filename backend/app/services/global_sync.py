from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.meta.oauth import (
    FACEBOOK_COMMENT_SYNC_SCOPES,
    FACEBOOK_CONTENT_SYNC_SCOPES,
    INSTAGRAM_COMMENT_SYNC_SCOPES,
    INSTAGRAM_CONTENT_SYNC_SCOPES,
    debug_token,
)
from app.models.integration import PlatformAccount
from app.schemas.synchronization import GlobalSyncPlatformResult, GlobalSyncResult
from app.services.meta_sync import sync_meta_account
from app.services.token_crypto import decrypt_token
from app.services.youtube_client_factory import build_youtube_client
from app.services.youtube_sync import sync_youtube
from app.services.youtube_unified_bridge import bridge_all_youtube_videos


CONTENT_SCOPES = {
    "facebook": set(FACEBOOK_CONTENT_SYNC_SCOPES),
    "instagram": set(INSTAGRAM_CONTENT_SYNC_SCOPES),
}
COMMENT_SCOPES = {
    "facebook": set(FACEBOOK_COMMENT_SYNC_SCOPES),
    "instagram": set(INSTAGRAM_COMMENT_SYNC_SCOPES),
}


class GlobalSyncConfigurationError(RuntimeError):
    pass


def _sync_youtube(db: Session, account: PlatformAccount, settings: Settings) -> GlobalSyncPlatformResult:
    client = build_youtube_client(account, settings)
    channel, imported = sync_youtube(db, account, client)
    bridge_all_youtube_videos(db, account, channel)
    return GlobalSyncPlatformResult(
        platform="youtube",
        status="success",
        message=f"YouTube: synchronizacja zakończona ({imported} nowych filmów).",
        imported_items=imported,
    )


def _sync_meta(db: Session, account: PlatformAccount, settings: Settings) -> GlobalSyncPlatformResult:
    access_token = decrypt_token(account.access_token_encrypted, settings.token_encryption_key)
    token_info = debug_token(settings, access_token)
    granted = set(token_info.get("scopes") or [])
    missing_content = CONTENT_SCOPES[account.platform] - granted
    if missing_content:
        names = ", ".join(sorted(missing_content))
        raise GlobalSyncConfigurationError(f"Brak uprawnień wymaganych do synchronizacji treści: {names}.")

    missing_comments = COMMENT_SCOPES[account.platform] - granted
    account.scopes = ",".join(sorted(granted))
    db.commit()
    result = sync_meta_account(
        db,
        account,
        settings,
        sync_comments=not missing_comments,
        comment_skip_reason=(
            f"Pominięto komentarze: brak opcjonalnych uprawnień {', '.join(sorted(missing_comments))}."
            if missing_comments
            else None
        ),
    )
    return GlobalSyncPlatformResult(
        platform=account.platform,
        status=result.status,
        message=(
            f"{account.display_name}: treści zsynchronizowane. {result.comment_error}"
            if result.comment_error
            else f"{account.display_name}: treści i komentarze zsynchronizowane."
        ),
        imported_items=result.content_run.imported_items,
        snapshots_created=result.content_run.snapshots_created,
        comments_imported=result.comment_run.comments_imported if result.comment_run else 0,
    )


def sync_all_connected(db: Session, settings: Settings) -> GlobalSyncResult:
    """Synchronize every connected account without letting one failure stop the rest."""
    started_at = datetime.now(timezone.utc)
    accounts = {
        account.platform: account
        for account in db.scalars(
            select(PlatformAccount).where(PlatformAccount.platform.in_(["youtube", "facebook", "instagram"]))
        ).all()
    }
    results: list[GlobalSyncPlatformResult] = []

    for platform in ("youtube", "facebook", "instagram"):
        account = accounts.get(platform)
        if account is None:
            results.append(
                GlobalSyncPlatformResult(
                    platform=platform,
                    status="skipped",
                    message="Platforma nie jest połączona — pominięto.",
                )
            )
            continue
        try:
            result = _sync_youtube(db, account, settings) if platform == "youtube" else _sync_meta(db, account, settings)
        except Exception as exc:
            db.rollback()
            safe_message = (
                str(exc)
                if isinstance(exc, GlobalSyncConfigurationError)
                else f"Synchronizacja nie powiodła się ({type(exc).__name__}). Szczegóły są dostępne w historii i logu backendu."
            )
            result = GlobalSyncPlatformResult(
                platform=platform,
                status="failed",
                message=safe_message,
            )
        else:
            db.commit()
        results.append(result)

    attempted = [result for result in results if result.status != "skipped"]
    if not attempted:
        aggregate_status = "skipped"
    elif all(result.status == "success" for result in attempted):
        aggregate_status = "success"
    elif all(result.status == "failed" for result in attempted):
        aggregate_status = "failed"
    else:
        aggregate_status = "partial"

    return GlobalSyncResult(
        status=aggregate_status,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        results=results,
    )
